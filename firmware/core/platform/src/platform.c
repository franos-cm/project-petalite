#include "platform.h"
#include "transport.h"

void platform_cold_boot(void)
{
    _plat__Signal_PowerOn();
    _plat__Signal_Reset();
}