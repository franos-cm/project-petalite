#ifndef _PLATFORM_H_
#define _PLATFORM_H_

#include <stdint.h>
#include <stddef.h>
#include <string.h>

#include <public/tpm_public.h>
#include <tpm_to_platform_interface.h>
#include <platform_to_tpm_interface.h>
#include <pcrstruct.h>
#include <prototypes/platform_pcr_fp.h>
#include "platform_public_interface.h"
#include "tpm_settings.h"

#include <TpmConfiguration/TpmBuildSwitches.h>
#include <TpmConfiguration/TpmProfile.h>

// TODO: revise this
#define GLOBAL_C
#define NV_C

void platform_cold_boot(void);

#endif // _PLATFORM_H_