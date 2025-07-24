#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <irq.h>
#include <libbase/uart.h>
#include <libbase/console.h>
#include <generated/csr.h>
#include <generated/mem.h>

#include "uart_utils.h"
#include "dilithium_utils.h"
#include "dilithium_sizes.h"

// NOTE: this should be 64 bit aligned
extern uint8_t _dilithium_buffer_start[];

int cstate0 = 0;
int cstate1 = 0;
int cstate2 = 0;
int ctr = 0;

static inline uint32_t align8(uint32_t x)
{
	return (x + 7) & ~7;
}

// static inline uint32_t dilithium_cstate0_read(void) {
// 	return csr_read_simple((CSR_BASE + 0x1010L));
// }
// static inline uint32_t dilithium_cstate1_read(void) {
// 	return csr_read_simple((CSR_BASE + 0x1014L));
// }
// static inline uint32_t dilithium_cstate2_read(void) {
// 	return csr_read_simple((CSR_BASE + 0x1018L));
// }

static inline void print_debug_state_change(void)
{
	int new_cstate0 = dilithium_cstate0_read();
	int new_cstate1 = dilithium_cstate1_read();
	int new_cstate2 = dilithium_cstate2_read();
	int new_ctr = dilithium_ctr_read();

	if ((new_cstate0 != cstate0) || (new_cstate1 != cstate1) || (new_cstate2 != cstate2) || ((new_ctr != ctr)))
	{
		cstate0 = new_cstate0;
		cstate1 = new_cstate1;
		cstate2 = new_cstate2;
		ctr = new_ctr;
		putchar(0xFF);
		putchar(ctr & 0xFF);
		putchar(cstate0 & 0xFF);
		putchar(cstate1 & 0xFF);
		putchar(cstate2 & 0xFF);
	}
}

// Buffers
// static uint8_t rx_buf[DILITHIUM_MAX_MSG_LEN];
// static uint8_t tx_buf[4096];

// static void send_response(const uint8_t *data, uint16_t len)
// {
// 	// Send length header
// 	putchar(len & 0xFF);
// 	putchar(len >> 8);

// 	// Send data in chunks, with ACKs
// 	for (int i = 0; i < len; i += DILITHIUM_CHUNK_SIZE)
// 	{
// 		uint16_t chunk_len = (len - i > DILITHIUM_CHUNK_SIZE) ? DILITHIUM_CHUNK_SIZE : (len - i);
// 		uart_send_chunk(&data[i], chunk_len);
// 		while (!readchar_nonblock())
// 			;
// 		if (getchar() != DILITHIUM_ACK_BYTE)
// 			break;
// 	}
// }

static int handle_verify(uint8_t sec_level, uint16_t msg_len)
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
	const uintptr_t h_addr = mlen_addr + sizeof(uint64_t);
	const uintptr_t msg_chunk_addr = h_addr + align8(h_len);
	const uintptr_t result_addr = msg_chunk_addr + align8(DILITHIUM_CHUNK_SIZE);
	const int first_payload_size = h_addr - base_buffer_addr;

	// Debug
	const size_t complete_payload_size = (size_t)(msg_chunk_addr - base_buffer_addr) + msg_len;
	putchar(0x11);
	putchar(0x11);
	putchar((complete_payload_size >> 0) & 0xFF);
	putchar((complete_payload_size >> 8) & 0xFF);
	putchar((complete_payload_size >> 16) & 0xFF);
	putchar((complete_payload_size >> 24) & 0xFF);

	// Load happens in the specific order defined by the Dilthium core used
	// TODO: maybe sending the non message ACKs is unnecessary
	int base_ack_group_length = 64;
	// Read Rho
	uart_readn((volatile uint8_t *)rho_addr, DILITHIUM_RHO_SIZE, DILITHIUM_RHO_SIZE);
	// Read C
	uart_readn((volatile uint8_t *)c_addr, DILITHIUM_C_SIZE, DILITHIUM_C_SIZE);
	// Read Z
	uart_readn((volatile uint8_t *)z_addr, z_len, base_ack_group_length);
	// Read T1
	uart_readn((volatile uint8_t *)t1_addr, t1_len, base_ack_group_length);
	// Write mlen
	((volatile uint8_t *)mlen_addr)[0] = (msg_len >> 8) & 0xFF; // high byte
	((volatile uint8_t *)mlen_addr)[1] = msg_len & 0xFF;		// low byte
	for (int i = 2; i < 8; ++i)
	{
		((volatile uint8_t *)mlen_addr)[i] = 0x00;
	}
	//*(uint64_t *)mlen_addr = msg_len;

	// Start DMA
	dilithium_dma_read_setup((uint64_t)base_buffer_addr, first_payload_size);
	dilithium_dma_read_start();
	// Writer too!
	dilithium_writer_base_write((uint64_t)result_addr);
	dilithium_writer_length_write(8); // TODO: check this
	dilithium_writer_enable_write(1);
	// And Dilithium!
	dilithium_start();

	// Read H
	uart_readn((volatile uint8_t *)h_addr, h_len, base_ack_group_length);
	// Receive first message chunk
	int chunk_len = (msg_len > DILITHIUM_CHUNK_SIZE) ? DILITHIUM_CHUNK_SIZE : (msg_len);
	uart_readn((volatile uint8_t *)msg_chunk_addr, chunk_len, 0); // Dont send ack yet!
	int message_bytes_read = chunk_len;

	putchar(0x22);
	putchar(0x22);
	putchar(0x22);

	// Check if first payload has been accepted
	dilithium_dma_read_wait();

	putchar(0x11);
	putchar(0x11);
	putchar(0x11);

	// Common base addr for chunks
	dilithium_dma_read_setup((uint64_t)msg_chunk_addr, chunk_len);
	dilithium_dma_read_start();

	putchar(0x33);
	putchar(0x33);
	putchar(0x33);

	// If so, we can start ingesting message in chunks
	while (message_bytes_read < msg_len)
	{
		putchar(0x66);
		putchar(0x66);
		putchar(0x66);

		chunk_len = (msg_len - message_bytes_read > DILITHIUM_CHUNK_SIZE)
						? DILITHIUM_CHUNK_SIZE
						: (msg_len - message_bytes_read);

		// When DMA is done, signal to uart that we are ready
		dilithium_dma_read_wait();

		putchar(0x44);
		putchar(0x44);
		putchar(0x44);

		// Ingest next chunk
		uart_send_ack();
		uart_readn((volatile uint8_t *)msg_chunk_addr, chunk_len, 0);
		// Pass it over to DMA
		putchar(0x22);
		putchar(0x22);
		putchar(0x22);

		dilithium_dma_read_setup((uint64_t)msg_chunk_addr, chunk_len);
		dilithium_dma_read_start();

		message_bytes_read += chunk_len;
	}
	// TODO: check if we need last ACK here
	uart_send_ack();

	putchar(0xBB);
	putchar(0xBB);
	putchar(0xBB);

	// Finally, we just need to ingest h
	// Wait for last message chunk to be done
	dilithium_dma_read_wait();

	putchar(0xDD);
	putchar(0xDD);
	putchar(0xDD);

	dilithium_dma_read_setup((uint64_t)h_addr, h_len);
	dilithium_dma_read_start();

	putchar(0xEE);
	putchar(0xEE);
	putchar(0xEE);

	// NOTE: we can reuse the base_addr since it has already been ingested

	putchar(0x99);
	putchar(0x99);
	putchar(0x99);

	// After input has been ingested, wait for output
	dilithium_dma_read_wait();

	putchar(0x88);
	putchar(0x88);
	putchar(0x88);

	while (!dilithium_writer_done_read())
	{
		print_debug_state_change();
	}

	putchar(0xFF);
	putchar(0xFF);
	putchar(0xFF);

	// Construct and send response
	dilithium_response_t rsp;
	rsp.verify_res = *((uint64_t *)base_buffer_addr);
	rsp.cmd = DILITHIUM_CMD_VERIFY;
	rsp.sec_lvl = sec_level;
	rsp.rsp_code = 0;

	return *((uint64_t *)base_buffer_addr);
}

static void process_uart_command(void)
{
	dilithium_header_t header;

	// Ingest header
	header.cmd = getchar();
	header.sec_lvl = getchar();
	header.msg_len = getchar();
	header.msg_len |= ((uint16_t)getchar()) << 8;
	// Ack header
	uart_send_ack();

	// if (header.msg_len == 0x21)
	// {
	// 	putchar(0x11);
	// 	putchar(0x11);
	// 	putchar(0x11);
	// 	putchar(0x11);
	// }

	// Check if header is valid
	// TODO: Make it so it returns the error code in the uart
	int invalid_header_code = invalid_header(&header);
	if (invalid_header_code)
		return;

	dilithium_reset();
	dilithium_setup(header.cmd, header.sec_lvl);
	if (header.cmd == DILITHIUM_CMD_KEYGEN)
	{
		return;
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

	// Wait for START
	while (getchar() != DILITHIUM_START_BYTE)
		;

	process_uart_command();
}