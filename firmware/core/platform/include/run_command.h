// Note: this is mostly a copy of a file that already exists in the original project
#include <assert.h>
#include <setjmp.h>
#include <stdio.h>

#include <public/tpm_public.h>
#include <platform_interface/tpm_to_platform_interface.h>
#include <platform_interface/platform_to_tpm_interface.h>
#include <platform_interface/pcrstruct.h>
#include <platform_interface/prototypes/platform_pcr_fp.h>

// The following extern globals are copied here from Global.h to avoid including all of Tpm.h here.
// TODO: Improve the interface by which these values are shared.
extern BOOL g_inFailureMode; // Indicates that the TPM is in failure mode
#if ALLOW_FORCE_FAILURE_MODE
extern BOOL g_forceFailureMode; // flag to force failure mode during test
#endif
#if FAIL_TRACE
// The name of the function that triggered failure mode.
extern const char *s_failFunctionName;
#endif // FAIL_TRACE
extern UINT32 s_failFunction;
extern UINT32 s_failLine;
extern UINT32 s_failCode;

LIB_EXPORT void _plat__RunCommand(
    uint32_t requestSize,    // IN: command buffer size
    unsigned char *request,  // IN: command buffer
    uint32_t *responseSize,  // IN/OUT: response buffer size
    unsigned char **response // IN/OUT: response buffer
);

LIB_EXPORT NORETURN void _plat__Fail(void);
