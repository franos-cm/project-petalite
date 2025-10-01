#include "transport.h"
#include "platform.h"
#include "run_command.h"

int main(void)
{
    transport_irq_init();
    platform_cold_boot();

    _debug_transport_write_ready();

    for (;;)
    {
        if (transport_ingestion_done())
        {
            uint32_t cmd_len = transport_get_cmd_len();
            uint32_t cmd_read_error = transport_read_command();

            if (!cmd_read_error)
            {
                uint32_t resp_len = (uint32_t)sizeof(tpm_cmd_buf);
                uint8_t *resp_ptr = tpm_cmd_buf;

                // Optionally pause RX/IRQs so the ingress path can't stomp the buffer
                // receiver_pause();
                _plat__RunCommand(cmd_len, tpm_cmd_buf, &resp_len, &resp_ptr);

                _debug_transport_write_ready();
                transport_write_rsp(resp_ptr, resp_len);

                // Now send exactly resp_len bytes
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