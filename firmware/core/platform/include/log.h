#pragma once
#include <stdarg.h>
#include <stdint.h>
#include <stddef.h>

// -----------------------------
// Configuration (override via -D):
//   LOG_LEVEL:      0=DEBUG,1=INFO,2=WARN,3=ERROR,4=OFF (default: 0 in debug, 1 in release)
//   LOG_USE_COLOR:  0/1 enable ANSI colors (default: 1)
//   LOG_TS_IN_US:   0/1 timestamps in microseconds (needs clock freq) else cycles (default: 1)
//   LOG_MODULE:     string tag for this compilation unit (default: file basename)
// -----------------------------

#ifndef LOG_LEVEL
#ifdef NDEBUG
#define LOG_LEVEL 1
#else
#define LOG_LEVEL 0
#endif
#endif

#ifndef LOG_USE_COLOR
#define LOG_USE_COLOR 1
#endif

#ifndef LOG_TS_IN_US
#define LOG_TS_IN_US 1
#endif

#ifdef __cplusplus
extern "C"
{
#endif

    typedef enum
    {
        LOG_DEBUG = 0,
        LOG_INFO = 1,
        LOG_WARN = 2,
        LOG_ERROR = 3,
        LOG_OFF = 4
    } log_level_t;

    typedef int (*log_write_fn)(const char *buf, size_t len);

    // ---- API ----
    void log_init(uint32_t sys_clk_hz);
    log_write_fn log_set_writer(log_write_fn fn);
    void log_enable(int on);
    int log_is_active(void);

    uint64_t log_now_cycles(void);
    uint64_t log_now_us(void);
    void log_printf(log_level_t lvl, const char *module, const char *fmt, ...)
        __attribute__((format(printf, 3, 4)));
    void log_hexdump(log_level_t lvl, const char *module,
                     const void *data, size_t len, uint32_t start_offset);
    const char *log_basename(const char *path);

#ifdef __cplusplus
} // extern "C"
#endif

// ---------- Convenience macros ----------
#if LOG_USE_COLOR
#define LOG__COL_RESET "\x1b[0m"
#define LOG__COL_DIM "\x1b[2m"
#define LOG__COL_DBG "\x1b[36m"
#define LOG__COL_INF "\x1b[32m"
#define LOG__COL_WRN "\x1b[33m"
#define LOG__COL_ERR "\x1b[31m"
#else
#define LOG__COL_RESET ""
#define LOG__COL_DIM ""
#define LOG__COL_DBG ""
#define LOG__COL_INF ""
#define LOG__COL_WRN ""
#define LOG__COL_ERR ""
#endif

#ifndef LOG_MODULE
#define LOG_MODULE log_basename(__FILE__)
#endif

#if LOG_LEVEL <= 0
#define LOGD(...) log_printf(LOG_DEBUG, LOG_MODULE, __VA_ARGS__)
#else
#define LOGD(...) \
    do            \
    {             \
    } while (0)
#endif
#if LOG_LEVEL <= 1
#define LOGI(...) log_printf(LOG_INFO, LOG_MODULE, __VA_ARGS__)
#else
#define LOGI(...) \
    do            \
    {             \
    } while (0)
#endif
#if LOG_LEVEL <= 2
#define LOGW(...) log_printf(LOG_WARN, LOG_MODULE, __VA_ARGS__)
#else
#define LOGW(...) \
    do            \
    {             \
    } while (0)
#endif
#if LOG_LEVEL <= 3
#define LOGE(...) log_printf(LOG_ERROR, LOG_MODULE, __VA_ARGS__)
#else
#define LOGE(...) \
    do            \
    {             \
    } while (0)
#endif

#define LOG_HEXDUMP(level, ptr, len) log_hexdump((level), LOG_MODULE, (ptr), (len), 0)
