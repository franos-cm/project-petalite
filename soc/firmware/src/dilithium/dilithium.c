#include "dilithium.h"

// NOTE: this should be 64 bit aligned
extern uint8_t _dilithium_buffer_start[];

void get_seed(volatile uint8_t *seed_buffer)
{
#ifdef CONFIG_SIM
    // For simulation, we receive the seed from the host.
    uart_readn((volatile uint8_t *)seed_buffer, DILITHIUM_SEED_SIZE, BASE_ACK_GROUP_LENGTH);
    uart_send_ack();
    return;
#else
    return;
#endif
}

// NOTE: this must be 64 bit aligned
uintptr_t get_sk_addr(int sk_id, uint8_t sec_level)
{
#ifdef CONFIG_SIM
    // For simulation, we receive the key from the host.
    const int buffer_start_offset = get_sig_len(sec_level) + sizeof(uint64_t) + DILITHIUM_CHUNK_SIZE;
    const uintptr_t sk_addr = (uintptr_t)_dilithium_buffer_start + align8(buffer_start_offset);
    const int sk_len = get_sk_len(sec_level);

    // Read the entire secret key into the beginning of our buffer.
    uart_send_ack();
    uart_readn((volatile uint8_t *)sk_addr, sk_len, BASE_ACK_GROUP_LENGTH);

    // Return the address where we stored it.
    return sk_addr;
#else
    return NULL;
#endif
}

// NOTE: DMA truncates last transfer if we dont provide a 8 byte multiple for length
int handle_verify(uint8_t sec_level, uint32_t msg_len)
{
    int z_len = get_z_len(sec_level);
    int t1_len = get_t1_len(sec_level);
    int h_len = get_h_len(sec_level);

    // This could in theory all be precomputed,
    // but I guess it would make it more confusing
    const uintptr_t base_buffer_addr = (uintptr_t)_dilithium_buffer_start;
    const uintptr_t rho_addr = base_buffer_addr;
    const uintptr_t c_addr = rho_addr + align8(DILITHIUM_RHO_SIZE);
    const uintptr_t z_addr = c_addr + align8(DILITHIUM_C_SIZE);
    const uintptr_t t1_addr = z_addr + align8(z_len);
    const uintptr_t mlen_addr = t1_addr + align8(t1_len);
    const uintptr_t msg_chunk_addr = mlen_addr + sizeof(uint64_t);
    const uintptr_t h_addr = msg_chunk_addr + align8(DILITHIUM_CHUNK_SIZE);
    const int first_payload_size = msg_chunk_addr - base_buffer_addr;
    const uintptr_t result_addr = base_buffer_addr;

    // NOTE: load happens in the specific order defined by the Dilthium core used
    // Read Rho
    uart_send_ack();
    uart_readn((volatile uint8_t *)rho_addr, DILITHIUM_RHO_SIZE, DILITHIUM_RHO_SIZE);
    // Read C
    uart_send_ack();
    uart_readn((volatile uint8_t *)c_addr, DILITHIUM_C_SIZE, DILITHIUM_C_SIZE);
    // Read Z
    uart_send_ack();
    uart_readn((volatile uint8_t *)z_addr, z_len, BASE_ACK_GROUP_LENGTH);
    // Read T1
    uart_send_ack();
    uart_readn((volatile uint8_t *)t1_addr, t1_len, BASE_ACK_GROUP_LENGTH);
    // Write mlen
    for (int i = 0; i < 4; i++)
        ((volatile uint8_t *)mlen_addr)[i] = 0x00;
    for (int i = 4; i < 8; i++)
        ((volatile uint8_t *)mlen_addr)[i] = (msg_len >> (8 * (7 - i))) & 0xFF;

    // Get writer and reader ready, and start Dilithium core!
    dilithium_write_setup((uint64_t)result_addr, sizeof(uint64_t));
    dilithium_write_start();
    dilithium_read_setup((uint64_t)rho_addr, first_payload_size);
    dilithium_read_start();
    dilithium_start();

    // Read H
    uart_send_ack();
    uart_readn((volatile uint8_t *)h_addr, h_len, BASE_ACK_GROUP_LENGTH);

    // Read msg
    dilithium_read_msg_in_chunks(msg_len, msg_chunk_addr);
    // Wait for the LAST message chunk's DMA to finish, and send final ACK.
    uart_send_ack();

    dilithium_read_wait();
    dilithium_read_setup((uint64_t)h_addr, h_len);
    dilithium_read_start();

    // Wait for the final result from the core
    dilithium_read_wait();
    dilithium_write_wait();

    // Final result
    uint64_t result = *((volatile uint64_t *)result_addr);

    // Construct and send response
    dilithium_response_t rsp;
    rsp.cmd = DILITHIUM_CMD_VERIFY;
    rsp.sec_lvl = sec_level;
    rsp.rsp_code = 0;
    rsp.verify_res = (result == 0);

    // Send response and wait for ACK
    uart_transmission_handshake();
    uart_send_response(&rsp);
    uart_wait_for_ack();

    return 0;
}

int handle_keygen(uint8_t sec_level)
{
    // Header ack
    uart_send_ack();

    const uintptr_t seed_addr = (uintptr_t)_dilithium_buffer_start;
    const uintptr_t keypair_addr = seed_addr + align8(DILITHIUM_SEED_SIZE);
    // NOTE: both pk and sk have Rho, but it is only output once by the module, so we subtract it
    int payload_size = get_pk_len(sec_level) + get_sk_len(sec_level) - DILITHIUM_RHO_SIZE;

    get_seed((volatile uint8_t *)seed_addr);

    dilithium_write_setup((uint64_t)keypair_addr, payload_size);
    dilithium_write_start();
    dilithium_read_setup((uint64_t)seed_addr, DILITHIUM_SEED_SIZE);
    dilithium_read_start();

    // Start dilithium core and wait for it to finish responding
    dilithium_start();
    dilithium_read_wait();
    dilithium_write_wait();

    // Construct response
    dilithium_response_t rsp;
    rsp.cmd = DILITHIUM_CMD_KEYGEN;
    rsp.sec_lvl = sec_level;
    rsp.rsp_code = 0;
    rsp.verify_res = -1;

    // Send response and wait for ACK
    uart_transmission_handshake();
    uart_send_response(&rsp);
    uart_wait_for_ack();

    // Send data
    uart_sendn((volatile uint8_t *)keypair_addr, payload_size, BASE_ACK_GROUP_LENGTH);
    uart_wait_for_ack();

    return 0;
}

int handle_sign(uint8_t sec_level, uint32_t msg_len)
{
    int s1_len = get_s1_len(sec_level);
    int s2_len = get_s2_len(sec_level);
    int t0_len = get_t0_len(sec_level);
    int z_len = get_z_len(sec_level);
    int h_len = get_h_len(sec_level);
    int sig_len = DILITHIUM_C_SIZE + z_len + h_len;

    // First we have a function that gets the key location. Then we start the transfer to the
    // dilithium core, alternating between mem positions from the key and from the buffer.
    // This should require less mem transfer than copying the sk into the buffer first.

    // NOTE: currently arbitrary secret key id
    const uintptr_t sk_addr = get_sk_addr(0, sec_level);
    const uintptr_t rho_addr = sk_addr;
    const uintptr_t k_addr = rho_addr + align8(DILITHIUM_RHO_SIZE);
    const uintptr_t tr_addr = k_addr + align8(DILITHIUM_K_SIZE);
    const uintptr_t s1_addr = tr_addr + align8(DILITHIUM_TR_SIZE);

    const uintptr_t base_buffer_addr = (uintptr_t)_dilithium_buffer_start;
    const uintptr_t mlen_addr = base_buffer_addr;
    const uintptr_t msg_chunk_addr = mlen_addr + sizeof(uint64_t);
    // TODO: check if we could have it be base_buffer_addr
    const uintptr_t signature_addr = msg_chunk_addr + DILITHIUM_CHUNK_SIZE;
    const uintptr_t z_addr = signature_addr;
    const uintptr_t h_addr = z_addr + align8(z_len);
    const uintptr_t c_addr = h_addr + align8(h_len);

    // sk is    rho, k, tr, s1, s2, t0
    // order is rho, mlen, tr, msg, k, s1, s2, t0
    // output is z, h, c istead of c, z, h
    // h is not integer sized

    // Get writer and reader ready...
    dilithium_write_setup((uint64_t)signature_addr, sig_len);
    dilithium_write_start();
    // Read rho in sk addr
    dilithium_read_setup((uint64_t)rho_addr, DILITHIUM_RHO_SIZE);
    dilithium_read_start();
    // Start Dilithium core!
    dilithium_start();

    // Write mlen
    for (int i = 0; i < 4; i++)
        ((volatile uint8_t *)mlen_addr)[i] = 0x00;
    for (int i = 4; i < 8; i++)
        ((volatile uint8_t *)mlen_addr)[i] = (msg_len >> (8 * (7 - i))) & 0xFF;

    // Read mlen in buffer
    dilithium_read_wait();
    dilithium_read_setup((uint64_t)mlen_addr, sizeof(uint64_t));
    dilithium_read_start();

    // Read tr in sk addr
    dilithium_read_wait();
    dilithium_read_setup((uint64_t)tr_addr, DILITHIUM_TR_SIZE);
    dilithium_read_start();

    // Read msg in buffer in chunked way
    // Both initial reader wait and header ack are done inside of the function
    dilithium_read_msg_in_chunks(msg_len, msg_chunk_addr);
    // Wait for the LAST message chunk's DMA to finish, and send final ACK.
    uart_send_ack();

    dilithium_read_wait();
    dilithium_read_setup((uint64_t)k_addr, DILITHIUM_K_SIZE);
    dilithium_read_start();

    dilithium_read_wait();
    dilithium_read_setup((uint64_t)s1_addr, s1_len + s2_len + t0_len);
    dilithium_read_start();

    // Wait for the final result from the core
    dilithium_read_wait();
    dilithium_write_wait();

    // Construct response
    dilithium_response_t rsp;
    rsp.cmd = DILITHIUM_CMD_SIGN;
    rsp.sec_lvl = sec_level;
    rsp.rsp_code = 0;
    rsp.verify_res = -1;

    // Send response and wait for ACK
    uart_transmission_handshake();
    uart_send_response(&rsp);
    uart_wait_for_ack();

    // Send data in the correct order
    uart_sendn((volatile uint8_t *)c_addr, DILITHIUM_C_SIZE, BASE_ACK_GROUP_LENGTH);
    uart_wait_for_ack();

    uart_sendn((volatile uint8_t *)z_addr, z_len, BASE_ACK_GROUP_LENGTH);
    uart_wait_for_ack();

    uart_sendn((volatile uint8_t *)h_addr, h_len, BASE_ACK_GROUP_LENGTH);
    uart_wait_for_ack();

    return 0;
}