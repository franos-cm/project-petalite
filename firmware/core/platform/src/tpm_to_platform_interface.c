// Minimal platform shim for MS TPM 2.0 reference core on bare-metal.
// TODO: replace sections with hardware hooks, and revise behaviour as a whole.
#include <string.h>
#include <stdint.h>

#include "platform.h"
#include "trng.h"
#include "transport.h"
#include "dilithium.h"
#include "log.h"

#if PLAT_ENTROPY_CONDITION_SHA256
#include <wolfssl/wolfcrypt/sha256.h>
#endif

// Fallbacks if not defined by headers
#ifndef LIB_EXPORT
#define LIB_EXPORT
#endif
#ifndef NORETURN
#if defined(__GNUC__)
#define NORETURN __attribute__((noreturn))
#else
#define
#endif
#endif

// ---------- Local "platform" state (RAM emulation for now) ----------

// Cancel flag (simulate host cancel)
static volatile int s_cancel_flag = 0;

// Software "tick" counter: increment this from a timer ISR or your board tick.
// Units: 1 tick == 1 millisecond (choose and keep consistent across the port).
static volatile uint64_t s_tick_ms = 0;

// Timer status flags the core may poll
static volatile int s_timer_reset_flag = 0;
static volatile int s_timer_stopped_flag = 0;

// Power-lost latch: return 1 once after a power event, then clear
static volatile int s_power_lost_latch = 0;

// NV emulation in RAM to let you link/run:
// - s_nv_image: "committed" persistent image
// - s_nv_shadow: staging area modified by NvMemoryWrite/Clear/Move
// - s_nv_dirty: tracks if shadow differs and Commit is needed
static uint8_t s_nv_image[NV_MEMORY_SIZE];
static uint8_t s_nv_shadow[NV_MEMORY_SIZE];
static int s_nv_dirty = 0;

// FIPS continuous test TRNG state (32-bit samples, change according to core)
static uint32_t s_last_entropy_word = 0;
static bool s_have_last_entropy = false;

// Vendor/firmware identifiers (pick meaningful values for your product)
static inline uint32_t fourcc(const char a[4])
{
    return ((uint32_t)(uint8_t)a[0] << 24) |
           ((uint32_t)(uint8_t)a[1] << 16) |
           ((uint32_t)(uint8_t)a[2] << 8) |
           ((uint32_t)(uint8_t)a[3] << 0);
}

// ---------- Tiny helpers you can call from your BSP ----------

// Call this from your SysTick/timer ISR every millisecond (or adjust units).
void _plat__Tick1ms(void) { s_tick_ms++; }

// If your platform detects a power-loss/restore, call this once on boot.
int _plat__Signal_PowerOn(void)
{
    s_power_lost_latch = 1;
    // If your hardware timer might have gone backwards across power,
    // call _plat__TimerReset() semantics:
    s_timer_reset_flag = 1;

    // Initialize modules. TODO: should we do this on power-on or somewhere else?
    // Initialize TRNG with defaults
    trng_init(NULL);
    s_have_last_entropy = false;
    s_last_entropy_word = 0;
    // Initialize uart and its interrupt service
    transport_irq_init();
    // Reset Dilithium
    dilithium_init();

    return 0;
}

//*** _plat_Signal_Reset()
// This a TPM reset without a power loss.
int _plat__Signal_Reset(void)
{
    // Command cancel
    s_cancel_flag = 0;

    _TPM_Init();

    return 0;
}

// If your platform can suspend the tick, call this on stop/start:
void _plat__Signal_TimerStopped(void) { s_timer_stopped_flag = 1; }

// Optional: set/clear cancel flag from host/GPIO/UART command
void _plat__SetCancel(void) { s_cancel_flag = 1; }

// ---------- Cancel.c ----------

LIB_EXPORT int _plat__IsCanceled(void)
{
    return s_cancel_flag ? 1 : 0;
}

// ---------- TimePlat.c ----------

LIB_EXPORT uint64_t _plat__TimerRead(void)
{
    // Return a monotonic, non-decreasing tick counter.
    // The core treats this as a "tick" time basis; keep units consistent.
    return s_tick_ms;
}

LIB_EXPORT int _plat__TimerWasReset(void)
{
    int was = s_timer_reset_flag;
    s_timer_reset_flag = 0;
    return was ? 1 : 0;
}

LIB_EXPORT int _plat__TimerWasStopped(void)
{
    int was = s_timer_stopped_flag;
    s_timer_stopped_flag = 0;
    return was ? 1 : 0;
}

LIB_EXPORT void _plat__ClockRateAdjust(_plat__ClockAdjustStep adjustment)
{
    // Optional: adjust your hardware timer's rate in small steps.
    // For now, a no-op is acceptable (the core tolerates it).
    (void)adjustment;
}

// ---------- DebugHelpers.c (simulation-ish) ----------

#if CERTIFYX509_DEBUG
int DebugFileInit(void) { return 0; }
void DebugDumpBuffer(int size, unsigned char *buf, const char *id)
{
    (void)size;
    (void)buf;
    (void)id;
}
#endif

// ---------- Entropy.c ----------
LIB_EXPORT int32_t _plat__GetEntropy(unsigned char *entropy, uint32_t amount)
{
    if (!entropy)
        return -1;
    if (amount == 0)
        return 0;

    // Discard first 32-bit word exactly once after power/reset
    if (!s_have_last_entropy)
    {
        (void)trng_read_u32();
        s_last_entropy_word = trng_read_u32();
        s_have_last_entropy = true;
    }

#if PLAT_ENTROPY_CONDITION_SHA256
    // SHA-256 conditioner at 2:1 ratio (64 in -> 32 out)
    const uint32_t out_block = 32;
    const uint32_t in_block = PLAT_ENTROPY_CONDITION_IN_PER_OUT32;
    unsigned char digest[out_block];
    unsigned char noise[in_block];

    uint32_t produced = 0;
    while (produced < amount)
    {
        // Fill 'noise' by reading words with continuous test
        uint32_t *wptr = (uint32_t *)noise;
        const uint32_t words = in_block / 4;
        for (uint32_t i = 0; i < words; ++i)
        {
            // TODO: warmup should be unnecessary, but it doesnt seem to be the case, at least in sims
            trng_warmup(1);
            uint32_t w = trng_read_u32();
            if (w == s_last_entropy_word)
            {
                LOGE("GetEntropy fail (equal consecutive 32-bit words): %d", w);
                return -1; // continuous test failure (sticky failure handled by caller)
            }
            s_last_entropy_word = w;
            wptr[i] = w; // little-endian platform; byte order of noise doesn't matter to hash
        }

        // Hash to produce 32 bytes of conditioned output
        wc_Sha256 sha;
        wc_InitSha256(&sha);
        wc_Sha256Update(&sha, noise, in_block);
        wc_Sha256Final(&sha, digest);

        // Copy as many bytes as needed from digest
        uint32_t remain = amount - produced;
        uint32_t take = remain < out_block ? remain : out_block;
        memcpy(entropy + produced, digest, take);
        produced += take;
    }
    return (int32_t)amount;
#else
    // Raw path: copy words to buffer with continuous test
    uint32_t produced = 0;
    while (produced < amount)
    {
        // TODO: warmup should be unnecessary, but it doesnt seem to be the case, at least in sims
        trng_warmup(1);
        uint32_t w = trng_read_u32();
        if (w == s_last_entropy_word)
        {
            LOGE("GetEntropy fail (equal consecutive 32-bit words): %d", w);
            return -1; // continuous test failure
        }
        s_last_entropy_word = w;

        uint32_t remain = amount - produced;
        uint32_t take = (remain >= 4) ? 4u : remain;
        for (uint32_t i = 0; i < take; ++i)
            entropy[produced + i] = (unsigned char)(w >> (8 * i)); // little-endian
        produced += take;
    }
    return (int32_t)produced;
#endif
}

// ---------- LocalityPlat.c ----------

LIB_EXPORT unsigned char _plat__LocalityGet(void)
{
    // If your transport encodes locality, return it here. Default to 0.
    return (unsigned char)0;
}

// ---------- NV (non-volatile) backing (RAM emulation) ----------

LIB_EXPORT int _plat__NVEnable(void *platParameter, size_t paramSize)
{
    (void)platParameter;
    (void)paramSize;
    // On first enable, initialize shadow = image. In a real port, you would:
    // - verify integrity of NV,
    // - load from flash/RPMB/EEPROM,
    // - handle failure modes.
    memcpy(s_nv_shadow, s_nv_image, NV_MEMORY_SIZE);
    s_nv_dirty = 0;
    return 0; // success
}

LIB_EXPORT int _plat__GetNvReadyState(void)
{
    // Return reasons NV is unavailable. Our RAM emu is always "ready".
    return NV_READY;
}

static int nv_inbounds(unsigned int off, unsigned int size)
{
    return (off <= NV_MEMORY_SIZE) && (size <= NV_MEMORY_SIZE) &&
           (off + size <= NV_MEMORY_SIZE);
}

LIB_EXPORT int _plat__NvMemoryRead(unsigned int startOffset, unsigned int size, void *data)
{
    if (!nv_inbounds(startOffset, size) || !data)
    {
        // Failure mode trigger in real HW port if desired
        return 0;
    }
    memcpy(data, &s_nv_shadow[startOffset], size);
    return 1;
}

LIB_EXPORT int _plat__NvGetChangedStatus(unsigned int startOffset, unsigned int size, void *data)
{
    if (!nv_inbounds(startOffset, size) || !data)
    {
        return NV_INVALID_LOCATION;
    }
    int diff = memcmp(&s_nv_shadow[startOffset], data, size);
    return diff ? NV_HAS_CHANGED : NV_IS_SAME;
}

LIB_EXPORT int _plat__NvMemoryWrite(unsigned int startOffset, unsigned int size, void *data)
{
    if (!nv_inbounds(startOffset, size) || !data)
        return 0;
    memcpy(&s_nv_shadow[startOffset], data, size);
    s_nv_dirty = 1;
    return 1;
}

LIB_EXPORT int _plat__NvMemoryClear(unsigned int startOffset, unsigned int size)
{
    if (!nv_inbounds(startOffset, size))
        return 0;
    // Erase state is usually all 0xFF for flash-like storage
    memset(&s_nv_shadow[startOffset], 0xFF, size);
    s_nv_dirty = 1;
    return 1;
}

LIB_EXPORT int _plat__NvMemoryMove(unsigned int sourceOffset,
                                   unsigned int destOffset,
                                   unsigned int size)
{
    if (!nv_inbounds(sourceOffset, size) || !nv_inbounds(destOffset, size))
        return 0;
    memmove(&s_nv_shadow[destOffset], &s_nv_shadow[sourceOffset], size);
    s_nv_dirty = 1;
    return 1;
}

LIB_EXPORT int _plat__NvCommit(void)
{
    if (s_nv_dirty)
    {
        // In a real port, write only the changed erase blocks and handle fail.
        memcpy(s_nv_image, s_nv_shadow, NV_MEMORY_SIZE);
        s_nv_dirty = 0;
    }
    return 0; // 0 == success
}

LIB_EXPORT void _plat__TearDown(void)
{
    // Zeroize NV on teardown (per header comment)
    memset(s_nv_image, 0, sizeof s_nv_image);
    memset(s_nv_shadow, 0, sizeof s_nv_shadow);
    s_nv_dirty = 0;
}

// ---------- PlatformACT.c (optional countdown timers) ----------

#if ACT_SUPPORT
LIB_EXPORT int _plat__ACT_GetImplemented(uint32_t act)
{
    (void)act;
    return 0; // none implemented by default
}

LIB_EXPORT uint32_t _plat__ACT_GetRemaining(uint32_t act)
{
    (void)act;
    return 0; // no countdown
}

LIB_EXPORT int _plat__ACT_GetSignaled(uint32_t act)
{
    (void)act;
    return 0; // not signaled
}

LIB_EXPORT void _plat__ACT_SetSignaled(uint32_t act, int on)
{
    (void)act;
    (void)on; // no-op
}

LIB_EXPORT int _plat__ACT_UpdateCounter(uint32_t act, uint32_t newValue)
{
    (void)act;
    (void)newValue;
    return 0; // FALSE => no update pending
}

LIB_EXPORT void _plat__ACT_EnableTicks(int enable)
{
    (void)enable; // would gate once-per-second tick processing
}

LIB_EXPORT int _plat__ACT_Initialize(void) { return 0; }
#endif // ACT_SUPPORT

// ---------- PowerPlat.c ----------

LIB_EXPORT int _plat__WasPowerLost(void)
{
    int was = s_power_lost_latch;
    s_power_lost_latch = 0;
    return was ? 1 : 0;
}

// ---------- PPPlat.c ----------

LIB_EXPORT int _plat__PhysicalPresenceAsserted(void)
{
    // Wire to a GPIO or policy. Default: not asserted.
    return 0;
}

extern NORETURN void _plat__Fail(void);

// ---------- Unique / manufacturing data / vendor caps ----------

#if VENDOR_PERMANENT_AUTH_ENABLED == YES
LIB_EXPORT uint32_t _plat__GetUnique(uint32_t which,
                                     uint32_t bSize,
                                     unsigned char *b)
{
    if (!b || bSize == 0)
        return 0;
    // Only 'which == 1' is defined currently by the header comment.
    if (which != 1)
        return 0;
    // TODO: Fill with device-unique, confidential value provisioned at manufacture.
    // For bring-up, return 0 bytes (not present).
    (void)bSize;
    (void)b;
    return 0;
}
#endif

LIB_EXPORT void _plat__GetPlatformManufactureData(uint8_t *pData, uint32_t bufferSize)
{
    // Called on manufacture and CLEAR. Provide a few bytes to embed in PERSISTENT_DATA.
    if (!pData || bufferSize == 0)
        return;
    // Default: stable all-zero bytes. Replace with board ID, revision, etc.
    memset(pData, 0, bufferSize);
}

LIB_EXPORT uint32_t _plat__GetManufacturerCapabilityCode()
{
    // 4 ASCII chars (no NUL). Choose your own; example "LTXS".
    return fourcc("LTXS");
}

LIB_EXPORT uint32_t _plat__GetVendorCapabilityCode(int index)
{
    // Up to 4 vendor strings, 1-based. Return packed 4 chars each; zeros otherwise.
    switch (index)
    {
    case 1:
        return fourcc("PETL"); // e.g., "PETL" for Petalite
    case 2:
        return fourcc("LITX"); // "LITX" for LiteX
    case 3:
        return fourcc("RV64");
    case 4:
        return fourcc("WOLF");
    default:
        return 0;
    }
}

LIB_EXPORT uint32_t _plat__GetTpmFirmwareVersionHigh()
{
    // MSB 32-bits of firmware version. Choose a scheme; example 1.0
    return 0x00010000u;
}

LIB_EXPORT uint32_t _plat__GetTpmFirmwareVersionLow()
{
    // LSB 32-bits of firmware version. Example minor/build.
    return 0x00000001u;
}

LIB_EXPORT uint16_t _plat__GetTpmFirmwareSvn(void)
{
    // Security Version Number (monotonic anti-rollback counter)
    return 0; // start at 0 unless you enforce anti-rollback
}

LIB_EXPORT uint16_t _plat__GetTpmFirmwareMaxSvn(void)
{
    return 0; // maximum SVN value (set accordingly if you use SVN)
}

#if SVN_LIMITED_SUPPORT
LIB_EXPORT int _plat__GetTpmFirmwareSvnSecret(uint16_t svn,
                                              uint16_t secret_buf_size,
                                              uint8_t *secret_buf,
                                              uint16_t *secret_size)
{
    (void)svn;
    (void)secret_buf_size;
    (void)secret_buf;
    (void)secret_size;
    // TODO: implement if you support SVN-limited secrets
    return -1;
}
#endif

#if FW_LIMITED_SUPPORT
LIB_EXPORT int _plat__GetTpmFirmwareSecret(uint16_t secret_buf_size,
                                           uint8_t *secret_buf,
                                           uint16_t *secret_size)
{
    (void)secret_buf_size;
    (void)secret_buf;
    (void)secret_size;
    // TODO: implement if you bind secrets to the current firmware image
    return -1;
}
#endif

// ---------- TPM Type ----------

LIB_EXPORT uint32_t _plat__GetTpmType()
{
    // TPM_PT_VENDOR_TPM_TYPE value. 0 is "not reported"; set per your product.
    // Common values used by some vendors: discrete(0x00000000), firmware(0x00000001), integrated(0x00000002)
    return 0; // not reported
}

// ---------- PQC hardware support ----------
#if ALG_DILITHIUM

// Buffer that is 64 bit aligned
// TODO: we shouldnt need this if our DMA could do unaligned accesses.
// NOTE: its size is currently defined by the max length of a message chunk, considering an 8 kB buffer
unsigned char dilithium_aligned_buffer[8176] __attribute__((aligned(8)));

uint32_t _plat__Dilithium_KeyGen(uint8_t sec_level,
                                 uint8_t *pk, uint16_t *pk_size,
                                 uint8_t *sk, uint16_t *sk_size)
{
    // TODO: define error codes instead of sending -1, -2, etc.
    if (!(pk_size && pk && sk_size && sk))
        return -1;

    // NOTE: buffer needs to be 8 byte aligned, so it works with Litex DMA
    uint8_t *seed = dilithium_aligned_buffer;
    // Get seed for generating keys
    if (_plat__GetEntropy(seed, DILITHIUM_SEED_SIZE) != (int)DILITHIUM_SEED_SIZE)
        return -2;
    // Generate keypair
    uint32_t rc = dilithium_keygen(sec_level, seed, pk, pk_size, sk, sk_size);

    // wipe seed
    for (size_t i = 0; i < sizeof(seed); i++)
        ((volatile uint8_t *)seed)[i] = 0;

    return rc;
}


uint32_t _plat__Dilithium_HashSignStart(uint8_t sec_level, uint32_t message_size,
                                        const uint8_t* sk, uint16_t sk_size,
                                        uint32_t* ctx_id)
{
    if (!(sk_size && sk))
        return -1;

    *ctx_id = 1; // constant token, since our hardware only supports a single op at a time (single session)
    return dilithium_sign_start(sec_level, message_size, sk, sk_size);
}

// Stream message chunks to hardware
uint32_t _plat__Dilithium_HashSignUpdate(uint32_t ctx_id,
                                         const uint8_t* chunk,
                                         uint16_t chunk_size)
{
    (void)ctx_id; // single-session hardware
    if (!(chunk_size && chunk))
        return -1;

    // NOTE: message needs to be 8 byte aligned, so it works with Litex DMA
    uint8_t *msg_buffer = dilithium_aligned_buffer;
    memcpy(msg_buffer, chunk, chunk_size);
    return dilithium_sign_update(msg_buffer, chunk_size);
}

// Finish: platform ingests SK-partB and produces the signature
uint32_t _plat__Dilithium_HashSignFinish(uint32_t ctx_id, uint8_t sec_level,
                                         const uint8_t* sk, uint16_t sk_size,
                                         uint8_t* sig, uint16_t* sig_size)
{
    (void)ctx_id; // single-session hardware
    if (!(sk && sk_size && sig && sig_size))
        return -1;
    return dilithium_sign_finish(sec_level, sk, sk_size, sig, sig_size);
}

#endif
