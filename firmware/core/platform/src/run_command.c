// Note: this is mostly a copy of a file that already exists in the original project

//**Introduction
// This module provides the platform specific entry and fail processing. The
// _plat__RunCommand() function is used to call to ExecuteCommand() in the TPM code.
// This function does whatever processing is necessary to set up the platform
// in anticipation of the call to the TPM including settup for error processing.
//
// The _plat__Fail() function is called when there is a failure in the TPM. The TPM
// code will have set the flag to indicate that the TPM is in failure mode.
// This call will then recursively call ExecuteCommand in order to build the
// failure mode response. When ExecuteCommand() returns to _plat__Fail(), the
// platform will do some platform specific operation to return to the environment in
// which the TPM is executing. For a simulator, setjmp/longjmp is used. For an OS,
// a system exit to the OS would be appropriate.

//** Includes and locals
#include "run_command.h"
#include "transport.h"
#include "log.h"

jmp_buf s_jumpBuffer;

//** Functions
//***_plat__RunCommand()
// This version of RunCommand will set up a jum_buf and call ExecuteCommand(). If
// the command executes without failing, it will return and RunCommand will return.
// If there is a failure in the command, then _plat__Fail() is called and it will
// longjump back to RunCommand which will call ExecuteCommand again. However, this
// time, the TPM will be in failure mode so ExecuteCommand will simply build
// a failure response and return.
LIB_EXPORT void _plat__RunCommand(
    uint32_t requestSize,    // IN: command buffer size
    unsigned char *request,  // IN: command buffer
    uint32_t *responseSize,  // IN/OUT: response buffer size
    unsigned char **response // IN/OUT: response buffer
)
{
    setjmp(s_jumpBuffer);
    ExecuteCommand(requestSize, request, responseSize, response);
}

//***_plat__Fail()
// This is the platform depended failure exit for the TPM.
LIB_EXPORT NORETURN void _plat__Fail(void)
{

    // Emit marker before assertion so host can parse
    debug_breakpoint(0xFF);
    LOGE("Platform failed!");
#if FAIL_TRACE
    extern const char *s_failFunctionName;
    extern UINT32 s_failLine;
    extern UINT32 s_failCode;
    LOGE("at %s:%u", s_failFunctionName ? s_failFunctionName : "(unknown)", s_failLine);
    LOGE("fail code %u (0x%08X)", s_failCode, s_failCode);
#else
    extern UINT32 s_failLine;
    extern UINT32 s_failCode;
    LOGE("line %u, fail code %u (0x%08X)", s_failLine, s_failCode, s_failCode);
#endif

#if ALLOW_FORCE_FAILURE_MODE
    // The simulator asserts during unexpected (i.e., un-forced) failure modes.
    if (!g_forceFailureMode)
    {
        // This calls, ultimately, pid and kill... but we can keep it for now
        assert(FALSE);
    }

    // Clear the forced-failure mode flag for next time.
    g_forceFailureMode = FALSE;
#endif // ALLOW_FORCE_FAILURE_MODE

    longjmp(&s_jumpBuffer[0], 1);
}
