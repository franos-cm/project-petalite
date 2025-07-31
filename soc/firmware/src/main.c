#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdint.h>

#include <irq.h>
#include <libbase/uart.h>
#include <libbase/console.h>
#include <generated/csr.h>
#include <generated/mem.h>

#include "uart_utils.h"
#include "dilithium.h"

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

static void process_command(void)
{
	uart_send_ack();
	dilithium_request_t header = uart_parse_request_header();
	int invalid_header_code = invalid_header(&header);
	if (invalid_header_code)
		// TODO: Make it so it returns the error code in the uart
		return;

	dilithium_reset();
	dilithium_setup(header.cmd, header.sec_lvl);
	if (header.cmd == DILITHIUM_CMD_KEYGEN)
	{
		handle_keygen(header.sec_lvl);
	}
	else if (header.cmd == DILITHIUM_CMD_SIGN)
	{
		return;
	}
	else if (header.cmd == DILITHIUM_CMD_VERIFY)
	{
		handle_verify(header.sec_lvl, header.msg_len);
	}
}

int main(void)
{
#ifdef CONFIG_CPU_HAS_INTERRUPT
	irq_setmask(0);
	irq_setie(1);
#endif
	uart_init();
	dilithium_init();

	// Initial handshake should be SYNC(host)-READY(uart)
	// Then data transfer handshake should be START-ACK-HEADER-ACK-DATA-ACK
	while (1)
	{
		if (readchar_nonblock())
		{
			uint8_t signal = getchar();
			if (signal == DILITHIUM_SYNC_BYTE)
				uart_send_ready();
			else if (signal == DILITHIUM_START_BYTE)
				process_command();
		}
	}
}