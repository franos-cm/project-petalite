#include "shared.h"
#include "receiver.h"
#include "parser.h"

extern volatile uint8_t tpm_cmd_private_buf[TPM_MAX_CMD_LEN];

int main(void)
{
	uart_irq_init();

	for (;;)
	{
		if (receiver_ingestion_done())
		{
			uint32_t cmd_read_error = read_command(tpm_cmd_private_buf);
			if (!cmd_read_error)
				parse_and_dispatch(uint8_t *tpm_cmd_private_buf);
		}

		// Optional: low-power wait
		// asm volatile("wfi");
	}
}