// This file is Copyright (c) 2020 Florent Kermarrec <florent@enjoy-digital.fr>
// License: BSD

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <irq.h>
#include <libbase/uart.h>
#include <libbase/console.h>
#include <generated/csr.h>
#include <generated/mem.h>

int main(void)
{
#ifdef CONFIG_CPU_HAS_INTERRUPT
	irq_setmask(0);
	irq_setie(1);
#endif

	while (1)
	{
		// Wait for a command
		if (petalite_cmd_valid_read() && !cmd_ack_read())
		{
			uint32_t cmd = cmd_value_read();
			uint32_t response = cmd * 2;
			rsp_value_write(response);
			rsp_valid_write(1);
			cmd_ack_write(1);
		}

		// Wait for host to clear valid, then clear ack
		if (!cmd_valid_read() && cmd_ack_read())
		{
			cmd_ack_write(0);
		}

		// Wait for host to ack response, then clear valid
		if (rsp_valid_read() && rsp_ack_read())
		{
			rsp_valid_write(0);
		}
	}

	return 0;
}
