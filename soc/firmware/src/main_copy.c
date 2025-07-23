// #include <stdio.h>
// #include <stdlib.h>
// #include <string.h>

// #include <irq.h>
// #include <libbase/uart.h>
// #include <libbase/console.h>
// #include <generated/csr.h>
// #include <generated/mem.h>

// #include "uart_utils.h"
// #include "dilithium_utils.h"
// #include "dilithium_sizes.h"

// extern uint8_t _dilithium_buffer_start[8192];
// extern char _end[];
// static uint8_t *dilithium_runtime_buffer = (uint8_t *)_end;

// // Buffers
// // static uint8_t rx_buf[DILITHIUM_MAX_MSG_LEN];
// // static uint8_t tx_buf[4096];

// // static void send_response(const uint8_t *data, uint16_t len)
// // {
// // 	// Send length header
// // 	putchar(len & 0xFF);
// // 	putchar(len >> 8);

// // 	// Send data in chunks, with ACKs
// // 	for (int i = 0; i < len; i += DILITHIUM_CHUNK_SIZE)
// // 	{
// // 		uint16_t chunk_len = (len - i > DILITHIUM_CHUNK_SIZE) ? DILITHIUM_CHUNK_SIZE : (len - i);
// // 		uart_send_chunk(&data[i], chunk_len);
// // 		while (!readchar_nonblock())
// // 			;
// // 		if (getchar() != DILITHIUM_ACK_BYTE)
// // 			break;
// // 	}
// // }

// // static void handle_sign(uint8_t *data, uint16_t len)
// // {
// // 	const uintptr_t tx_addr = (uintptr_t)_end + 0x100;
// // 	const uintptr_t rx_addr = (uintptr_t)_end + 0x200;

// // 	memcpy((void *)tx_addr, data, len);

// // 	main_mode_write(0); // example: sign
// // 	main_sec_lvl_write(2);
// // 	main_start_write(0);

// // 	dilithium_reader_base_write((uint64_t)tx_addr);
// // 	dilithium_reader_length_write(len);
// // 	dilithium_reader_enable_write(1);

// // 	dilithium_writer_base_write((uint64_t)rx_addr);
// // 	dilithium_writer_length_write(4096); // conservative
// // 	dilithium_writer_enable_write(1);

// // 	main_start_write(1);
// // 	main_start_write(0);

// // 	while (!dilithium_reader_done_read())
// // 		;
// // 	while (!dilithium_writer_done_read())
// // 		;

// // 	send_response((const uint8_t *)rx_addr, 2048); // Adjust based on expected output
// // }

// static int handle_verify(uint8_t sec_level, uint16_t msg_len)
// {
// 	int z_len = get_z_len(sec_level);
// 	int t1_len = get_t1_len(sec_level);
// 	int h_len = get_h_len(sec_level);
// 	// This could in theory all be precomputed,
// 	// but I guess it would make it more confusing
// 	const uintptr_t base_buffer_addr = (uintptr_t)(dilithium_runtime_buffer);
// 	const uintptr_t rho_addr = base_buffer_addr;
// 	const uintptr_t c_addr = rho_addr + DILITHIUM_RHO_SIZE;
// 	const uintptr_t z_addr = c_addr + DILITHIUM_C_SIZE;
// 	const uintptr_t t1_addr = z_addr + z_len;
// 	const uintptr_t mlen_addr = t1_addr + t1_len;
// 	const int first_payload_size = mlen_addr - base_buffer_addr;
// 	const uintptr_t h_addr = mlen_addr + sizeof(uint64_t);
// 	const uintptr_t msg_chunk_addr = h_addr + h_len;

// 	// Load happens in the specific order defined by the Dilthium core used
// 	// TODO: maybe sending the non message ACKs is unnecessary
// 	// Read Rho
// 	putchar(DILITHIUM_ACK_BYTE);
// 	// for (uint32_t i = 0; i < 4; i++)
// 	// {
// 	// 	putchar(getchar());
// 	// }
// 	uart_readn((volatile uint8_t *)rho_addr, DILITHIUM_RHO_SIZE);
// 	putchar(0x77);
// 	uart_send_ack();
// 	putchar(0x66);
// 	// Read C
// 	uart_readn((volatile uint8_t *)c_addr, DILITHIUM_C_SIZE);
// 	uart_send_ack();
// 	// Read Z
// 	uart_readn((volatile uint8_t *)z_addr, z_len);
// 	uart_send_ack();
// 	// Read T1
// 	uart_readn((volatile uint8_t *)t1_addr, t1_len);
// 	uart_send_ack();
// 	// Write mlen
// 	*(uint64_t *)mlen_addr = msg_len;
// 	// Start DMA
// 	dilithium_reader_base_write((uint64_t)base_buffer_addr);
// 	dilithium_reader_length_write(first_payload_size);
// 	dilithium_reader_enable_write(1);
// 	// Read H
// 	uart_readn((volatile uint8_t *)h_addr, h_len);
// 	uart_send_ack();
// 	// Receive first message chunk
// 	uint16_t chunk_len = (msg_len > DILITHIUM_CHUNK_SIZE) ? DILITHIUM_CHUNK_SIZE : (msg_len);
// 	uart_readn((volatile uint8_t *)msg_chunk_addr, chunk_len);
// 	int message_bytes_read = chunk_len;
// 	// // Dont send ack yet!

// 	// Check if first payload has been accepted
// 	while (!dilithium_reader_done_read())
// 		;

// 	// Common base addr for chunks
// 	dilithium_reader_base_write((uint64_t)msg_chunk_addr);
// 	dilithium_reader_length_write(chunk_len);
// 	dilithium_reader_enable_write(1);

// 	// If so, we can start ingesting message in chunks
// 	while (message_bytes_read < msg_len)
// 	{
// 		chunk_len = (msg_len - message_bytes_read > DILITHIUM_CHUNK_SIZE)
// 						? DILITHIUM_CHUNK_SIZE
// 						: (msg_len - message_bytes_read);

// 		// When DMA is done, signal to uart that we are ready
// 		while (!dilithium_reader_done_read())
// 			;

// 		// Ingest next chunk
// 		uart_send_ack();
// 		uart_readn((volatile uint8_t *)msg_chunk_addr, chunk_len);
// 		// Pass it over to DMA
// 		dilithium_reader_length_write(chunk_len);
// 		dilithium_reader_enable_write(1);
// 		message_bytes_read += chunk_len;
// 	}
// 	// TODO: check if we need last ACK here

// 	// Finally, we just need to ingest h
// 	// Wait for last message chunk to be done
// 	while (!dilithium_reader_done_read())
// 		;

// 	dilithium_reader_base_write((uint64_t)h_addr);
// 	dilithium_reader_length_write(h_len);
// 	dilithium_reader_enable_write(1);

// 	// NOTE: we can reuse the base_addr since it has already been ingested
// 	dilithium_writer_base_write((uint64_t)base_buffer_addr);
// 	dilithium_writer_length_write(8); // TODO: check this

// 	// After input has been ingested, wait for output
// 	while (!dilithium_reader_done_read())
// 		;
// 	dilithium_writer_enable_write(1);
// 	while (!dilithium_writer_done_read())
// 		;

// 	return *((uint64_t *)base_buffer_addr);
// }

// static void process_uart_command(void)
// {
// 	dilithium_header_t header;

// 	// Ingest header
// 	dilithium_debug_state_write(3);
// 	header.cmd = getchar();
// 	header.sec_lvl = getchar();
// 	header.msg_len = getchar();
// 	header.msg_len |= ((uint16_t)getchar()) << 8;
// 	// Ack header

// 	// putchar(header.cmd);
// 	// putchar(header.sec_lvl);
// 	// putchar(header.msg_len);

// 	// #define DILITHIUM_ACK_BYTE 0xCC

// 	// Check if header is valid
// 	// TODO: Make it so it returns the error code in the uart
// 	// int invalid_header_code = invalid_header(&header);
// 	// if (invalid_header_code)
// 	// 	return;

// 	dilithium_reset();
// 	dilithium_setup(header.cmd, header.sec_lvl);
// 	if (header.cmd == DILITHIUM_CMD_KEYGEN)
// 	{
// 		return;
// 	}
// 	else if (header.cmd == DILITHIUM_CMD_SIGN)
// 	{
// 		return;
// 	}
// 	else if (header.cmd == DILITHIUM_CMD_VERIFY)
// 	{
// 		handle_verify(header.sec_lvl, header.msg_len);
// 	}
// }

// int main(void)
// {
// #ifdef CONFIG_CPU_HAS_INTERRUPT
// 	irq_setmask(0);
// 	irq_setie(1);
// #endif
// 	dilithium_reset();
// 	uart_init();

// 	// Wait for START
// 	while (getchar() != DILITHIUM_START_BYTE)
// 		;

// 	// while (1)
// 	// {
// 	// 	putchar(getchar());
// 	// }

// 	process_uart_command();
// }