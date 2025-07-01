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
		if (main_cmd_valid_read() && !main_cmd_ack_read())
		{
			uint32_t cmd = main_cmd_value_read();
			uint32_t response = cmd * 2;
			main_rsp_value_write(response);
			main_rsp_valid_write(1);
			main_cmd_ack_write(1);
		}

		// Wait for host to clear valid, then clear ack
		if (!main_cmd_valid_read() && main_cmd_ack_read())
		{
			main_cmd_ack_write(0);
		}

		// Wait for host to ack response, then clear valid
		if (main_rsp_valid_read() && main_rsp_ack_read())
		{
			main_rsp_valid_write(0);
		}
	}

	return 0;
}
