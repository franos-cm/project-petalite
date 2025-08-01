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