
#include "transport.h"
#include "run_command.h"

int main(void)
{
    transport_irq_init();
    for (;;)
    {
        if (transport_ingestion_done())
        {
            uint32_t cmd_read_error = transport_read_command();
            if (!cmd_read_error)
            {
                uint32_t cmd_len = transport_get_cmd_len();
                uint32_t resp_len = (uint32_t)sizeof(tpm_cmd_buf);
                uint8_t *resp_ptr = tpm_cmd_buf;

                // Optionally pause RX/IRQs so the ingress path can't stomp the buffer
                // receiver_pause();

                _plat__RunCommand(cmd_len, tpm_cmd_buf, &resp_len, &resp_ptr);

                // Now send exactly resp_len bytes
                // uart_write_exact(resp_ptr, resp_len);
                // receiver_resume();
            }
            else
            {
                ;
            }
        }
        // Optional: low-power wait
        // asm volatile("wfi");
    }
}