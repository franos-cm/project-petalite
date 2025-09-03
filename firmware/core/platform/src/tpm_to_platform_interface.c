// platform_shims.c
// Minimal platform shim for MS TPM 2.0 reference core on bare-metal.
// Safe to compile/link; replace TODO sections with your hardware hooks.

#include <stdint.h>
#include <stddef.h>
#include <string.h>

#include <public/tpm_public.h>
#include <tpm_to_platform_interface.h>

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
#ifndef NV_MEMORY_SIZE
// If profile didn't define it, pick a small default to compile.
// Replace with real value from your chosen TPM profile.
#define NV_MEMORY_SIZE 4096u
#endif
static uint8_t s_nv_image[NV_MEMORY_SIZE];
static uint8_t s_nv_shadow[NV_MEMORY_SIZE];
static int s_nv_dirty = 0;

// Optional: simple PRNG for _plat__GetEntropy when no TRNG is wired yet.
// NOTE: NOT CRYPTO-QUALITY. For compile-time only.
static uint32_t s_xorshift = 2463534242u;

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
void _plat__Signal_PowerOn(void)
{
    s_power_lost_latch = 1;
    // If your hardware timer might have gone backwards across power,
    // call _plat__TimerReset() semantics:
    s_timer_reset_flag = 1;
}

// If your platform can suspend the tick, call this on stop/start:
void _plat__Signal_TimerStopped(void) { s_timer_stopped_flag = 1; }

// Optional: set/clear cancel flag from host/GPIO/UART command
void _plat__SetCancel(int on) { s_cancel_flag = (on != 0); }

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
    // TODO: wire to a real TRNG. This xorshift is ONLY to unblock bringup.
    if (!entropy)
        return -1;
    for (uint32_t i = 0; i < amount; ++i)
    {
        // Xorshift32
        uint32_t x = s_xorshift;
        x ^= x << 13;
        x ^= x >> 17;
        x ^= x << 5;
        s_xorshift = x;
        entropy[i] = (unsigned char)(x & 0xFF);
    }
    return (int32_t)amount;
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

LIB_EXPORT NORETURN void _plat__Fail(void)
{
    // Fatal platform-dependent abort. Trap forever.
    for (;;)
    { /* spin */
    }
}

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
