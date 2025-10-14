#include "log.h"
#include "platform.h"
#include "transport.h"
#include "run_command.h"

int main(void)
{
    // Init logger when debugging through UART
    log_init(0);

    // Boot platform
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
                // receiver_resume();
            }
            else
            {
                ;
            }
        }
        // Low-power wait.
        // TODO: check if this actually works
        asm volatile("wfi");
    }
}