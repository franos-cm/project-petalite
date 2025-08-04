#include "dilithium.h"

// NOTE: this should be 64 bit aligned
extern uint8_t _dilithium_buffer_start[];

inline uint32_t align8(uint32_t x)
{
    return (x + 7) & ~7;
}

void get_seed(volatile uint8_t *seed_buffer)
{
#ifdef CONFIG_SIM
    /* simulation-specific behavior */
    uart_readn((volatile uint8_t *)seed_buffer, DILITHIUM_SEED_SIZE, BASE_ACK_GROUP_LENGTH);
    uart_send_ack();
    return;
#else
    /* hardware-specific behavior */
    return;
#endif
}

// TODO: do I really need to align the read length for dma?
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
    dilithium_read_setup((uint64_t)rho_addr, align8(first_payload_size));
    dilithium_read_start();
    dilithium_start();

    // Read H
    uart_send_ack();
    uart_readn((volatile uint8_t *)h_addr, h_len, BASE_ACK_GROUP_LENGTH);

    // Ingest the entire message in chunks.
    int message_bytes_read = 0;
    while (message_bytes_read < msg_len)
    {
        // Calculate the size of the next chunk to read.
        int remaining_msg_bytes = msg_len - message_bytes_read;
        int current_chunk_size = (remaining_msg_bytes > DILITHIUM_CHUNK_SIZE) ? DILITHIUM_CHUNK_SIZE : remaining_msg_bytes;

        // Before starting the next DMA, wait for the previous one to complete.
        dilithium_read_wait();

        // For chunks 2 and onwards, we must first ACK the previously received chunk.
        uart_send_ack();
        uart_readn((volatile uint8_t *)msg_chunk_addr, current_chunk_size, BASE_ACK_GROUP_LENGTH);

        // Pass the newly read chunk to the DMA.
        dilithium_read_setup((uint64_t)msg_chunk_addr, align8(current_chunk_size));
        dilithium_read_start();

        message_bytes_read += current_chunk_size;
    }
    // Wait for the LAST message chunk's DMA to finish.
    dilithium_read_wait();
    // Send the final ACK for the LAST message chunk.
    uart_send_ack();

    dilithium_read_setup((uint64_t)h_addr, align8(h_len));
    dilithium_read_start();
    dilithium_read_wait();

    // Wait for the final result from the core
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
    return 0;
}