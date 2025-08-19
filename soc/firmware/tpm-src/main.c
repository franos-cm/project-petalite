#include "receiver.h"

int main(void)
{
	uart_irq_init();

	for (;;)
	{
		if (receiver_ingestion_done())
		{
			uint32_t cmd_read_error = read_command();
			if (!cmd_read_error)
			{
				// -> parse & execute TPM command in cmd_buf[0..cmd_len-1]
			}
		}

		// Optional: low-power wait
		// asm volatile("wfi");
	}
}