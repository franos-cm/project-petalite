#include "log.h"
#include <stdio.h>
#include <string.h>
#include <inttypes.h>
#include <libbase/uart.h>
#include "generated/csr.h"
#include "generated/soc.h"

// ---------- Internal state ----------
static uint32_t log__sys_clk_hz = 0;
static int log__enabled = 1;

static int log__stdout_write(const char *buf, size_t len)
{
    return (int)fwrite(buf, 1, len, stdout);
}
static int log__null_write(const char *buf, size_t len)
{
    (void)buf;
    return (int)len;
}
static log_write_fn log__writer = log__null_write;

static inline int log__has_real_sink(void) { return log__writer != log__null_write; }

int log_is_active(void) { return log__enabled && log__has_real_sink(); }

log_write_fn log_set_writer(log_write_fn fn)
{
    log_write_fn prev = log__writer;
    log__writer = fn ? fn : log__null_write;
    return prev;
}

void log_enable(int on) { log__enabled = !!on; }

const char *log_basename(const char *path)
{
    const char *p = path;
    const char *base = p;
    while (*p)
    {
        if (*p == '/' || *p == '\\')
            base = p + 1;
        ++p;
    }
    return base;
}

// ---------- Timestamps ----------
#if defined(__riscv)
static inline uint64_t log__rdcycle64(void)
{
    uint64_t x;
#if __riscv_xlen == 32
    uint32_t hi, lo, hi2;
    asm volatile("rdcycleh %0" : "=r"(hi));
    asm volatile("rdcycle %0" : "=r"(lo));
    asm volatile("rdcycleh %0" : "=r"(hi2));
    if (hi != hi2)
    {
        asm volatile("rdcycle %0" : "=r"(lo));
        asm volatile("rdcycleh %0" : "=r"(hi));
    }
    x = ((uint64_t)hi << 32) | lo;
#else
    asm volatile("rdcycle %0" : "=r"(x));
#endif
    return x;
}
#endif

uint64_t log_now_cycles(void)
{
#if defined(__riscv)
    return log__rdcycle64();
#else
    return 0;
#endif
}

uint64_t log_now_us(void)
{
    uint64_t cyc = log_now_cycles();
    if (cyc && log__sys_clk_hz)
    {
        return (cyc * 1000000ull + (log__sys_clk_hz / 2)) / log__sys_clk_hz;
    }
    return 0;
}

// ---------- Level formatting ----------
static inline const char *log__lvl_tag(log_level_t lvl)
{
    switch (lvl)
    {
    case LOG_DEBUG:
        return "DBG";
    case LOG_INFO:
        return "INF";
    case LOG_WARN:
        return "WRN";
    case LOG_ERROR:
        return "ERR";
    default:
        return "???";
    }
}
static inline const char *log__lvl_col(log_level_t lvl)
{
    switch (lvl)
    {
    case LOG_DEBUG:
        return LOG__COL_DBG;
    case LOG_INFO:
        return LOG__COL_INF;
    case LOG_WARN:
        return LOG__COL_WRN;
    case LOG_ERROR:
        return LOG__COL_ERR;
    default:
        return "";
    }
}

// ---------- Autodetect sink ----------
static void log__autodetect_sink(void)
{
#ifndef LOG_FORCE_ENABLE
#ifdef CSR_UART_BASE
    log__writer = log__stdout_write;
    log__enabled = 1;
#else
    log__writer = log__null_write;
    log__enabled = 0;
#endif
#else
    log__writer = log__stdout_write;
#endif
}

// ---------- Init ----------
void log_init(uint32_t sys_clk_hz)
{
    uart_init();
#ifdef CONFIG_CLOCK_FREQUENCY
    log__sys_clk_hz = CONFIG_CLOCK_FREQUENCY;
#else
    log__sys_clk_hz = sys_clk_hz;
#endif
    log__autodetect_sink();
}

// ---------- Write helpers ----------
static inline void log__write_str(const char *s)
{
    if (!log_is_active())
        return;
    log__writer(s, strlen(s));
}
static inline void log__write_buf(const char *b, size_t n)
{
    if (!log_is_active())
        return;
    log__writer(b, n);
}

// ---------- Core printf ----------
void log_printf(log_level_t lvl, const char *module, const char *fmt, ...)
{
    if (lvl < LOG_LEVEL || lvl >= LOG_OFF)
        return;
    if (!log_is_active())
        return;

    char buf[192];
    int n;

    uint64_t ts = 0;
#if LOG_TS_IN_US
    ts = log_now_us();
#else
    ts = log_now_cycles();
#endif
    const char *mod = module ? module : "?";

    if (ts)
    {
#if LOG_TS_IN_US
        n = snprintf(buf, sizeof(buf),
                     "%s[%s]%s %s%s%s: %s(%llu us)%s ",
                     LOG__COL_DIM, log__lvl_tag(lvl), LOG__COL_RESET,
                     log__lvl_col(lvl), mod, LOG__COL_RESET,
                     LOG__COL_DIM, (unsigned long long)ts, LOG__COL_RESET);
#else
        n = snprintf(buf, sizeof(buf),
                     "%s[%s]%s %s%s%s: %s(%llu cyc)%s ",
                     LOG__COL_DIM, log__lvl_tag(lvl), LOG__COL_RESET,
                     log__lvl_col(lvl), mod, LOG__COL_RESET,
                     LOG__COL_DIM, (unsigned long long)ts, LOG__COL_RESET);
#endif
    }
    else
    {
        n = snprintf(buf, sizeof(buf),
                     "%s[%s]%s %s%s%s: ",
                     LOG__COL_DIM, log__lvl_tag(lvl), LOG__COL_RESET,
                     log__lvl_col(lvl), mod, LOG__COL_RESET);
    }
    if (n > 0)
        log__write_buf(buf, (size_t)n);

    va_list ap;
    va_start(ap, fmt);
    n = vsnprintf(buf, sizeof(buf), fmt, ap);
    va_end(ap);
    if (n > 0)
    {
        size_t w = (n < (int)sizeof(buf)) ? (size_t)n : sizeof(buf) - 1;
        log__write_buf(buf, w);
    }
    log__write_str("\n");
}

// ---------- Hexdump ----------
void log_hexdump(log_level_t lvl, const char *module,
                 const void *data, size_t len, uint32_t start_offset)
{
    (void)module;
    if (lvl < LOG_LEVEL || lvl >= LOG_OFF)
        return;
    if (!log_is_active())
        return;

    const uint8_t *p = (const uint8_t *)data;
    uint32_t off = start_offset;
    char line[128];

    for (size_t i = 0; i < len; i += 16)
    {
        int n = snprintf(line, sizeof(line),
                         "%s[%s]%s %s%08x%s  ",
                         LOG__COL_DIM, log__lvl_tag(lvl), LOG__COL_RESET,
                         LOG__COL_DIM, off, LOG__COL_RESET);
        if (n > 0)
            log__write_buf(line, (size_t)n);

        for (size_t j = 0; j < 16; j++)
        {
            if (i + j < len)
                n = snprintf(line, sizeof(line), "%02x ", p[i + j]);
            else
                n = snprintf(line, sizeof(line), "   ");
            log__write_buf(line, (size_t)n);
            if (j == 7)
                log__write_str(" ");
        }

        log__write_str(" |");
        for (size_t j = 0; j < 16 && (i + j) < len; j++)
        {
            uint8_t c = p[i + j];
            char ch = (c >= 32 && c <= 126) ? (char)c : '.';
            log__write_buf(&ch, 1);
        }
        log__write_str("|\n");
        off += 16;
    }
}
