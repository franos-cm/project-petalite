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
    transport_write_ready();

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

                #ifdef INCLUDE_LATENCY_MEASURES
                // Measure cycles before/after TPM command
                uint64_t start_cycles = 0;
                uint64_t end_cycles = 0;
                asm volatile("rdcycle %0" : "=r"(start_cycles));
                #endif

                _plat__RunCommand(cmd_len, tpm_cmd_buf, &resp_len, &resp_ptr);

                #ifdef INCLUDE_LATENCY_MEASURES
                // Send latency info
                asm volatile("rdcycle %0" : "=r"(end_cycles));
                uint64_t delta_cycles = (end_cycles >= start_cycles) ? (end_cycles - start_cycles) : 0;
                transport_write_ready();
                transport_write_latency_record(delta_cycles);
                #endif
                
                // Send response
                transport_write_ready();
                transport_write_rsp(resp_ptr, resp_len);
            }
            else
            {
                ;
            }
        }
        // Low-power wait.
        asm volatile("wfi");
    }
}