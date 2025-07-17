#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <irq.h>
#include <libbase/uart.h>
#include <libbase/console.h>
#include <generated/csr.h>
#include <generated/mem.h>

/*-----------------------------------------------------------------------*/
/* Uart                                                                  */
/*-----------------------------------------------------------------------*/

static char *readstr(void)
{
	char c[2];
	static char s[64];
	static int ptr = 0;

	if (readchar_nonblock())
	{
		c[0] = getchar();
		c[1] = 0;
		switch (c[0])
		{
		case 0x7f:
		case 0x08:
			if (ptr > 0)
			{
				ptr--;
				fputs("\x08 \x08", stdout);
			}
			break;
		case 0x07:
			break;
		case '\r':
		case '\n':
			s[ptr] = 0x00;
			fputs("\n", stdout);
			ptr = 0;
			return s;
		default:
			if (ptr >= (sizeof(s) - 1))
				break;
			fputs(c, stdout);
			s[ptr] = c[0];
			ptr++;
			break;
		}
	}

	return NULL;
}

static char *get_token(char **str)
{
	char *c, *d;

	c = (char *)strchr(*str, ' ');
	if (c == NULL)
	{
		d = *str;
		*str = *str + strlen(*str);
		return d;
	}
	*c = 0;
	d = *str;
	*str = c + 1;
	return d;
}

static void prompt(void)
{
	printf("\e[92;1mpetalite\e[0m> ");
}

/*-----------------------------------------------------------------------*/
/* Help                                                                  */
/*-----------------------------------------------------------------------*/

static void help(void)
{
	puts("\nProject Petalite, built " __DATE__
		 " " __TIME__
		 "\n");
}

/*-----------------------------------------------------------------------*/
/* Commands                                                              */
/*-----------------------------------------------------------------------*/

static void reboot_cmd(void)
{
	ctrl_reset_write(1);
}

/*---------------------------------------------------------------------*/
/* Simple hexadecimal dump                                             */
/*---------------------------------------------------------------------*/
static void hexdump(const void *addr, unsigned length)
{
	const uint8_t *p = addr;
	for (unsigned i = 0; i < length; i++)
	{
		if ((i & 15) == 0)
			printf("%08x : ", (unsigned)(uintptr_t)(p + i));
		printf("%02x ", p[i]);
		if ((i & 15) == 15 || i == length - 1)
			printf("\n");
	}
}

/*---------------------------------------------------------------------*/
/* Run a single Dilithium “round-trip”                                 */
/*---------------------------------------------------------------------*/
// 7C9935A0B07694AA
// 0C6D10E4DB6B1ADD
// 2FD81A25CCB14803
// 2DCD739936737F2D
static const uint8_t test_msg[32] = {
	0x7C, 0x99, 0x35, 0xA0, 0xB0, 0x76, 0x94, 0xAA,
	0x0C, 0x6D, 0x10, 0xE4, 0xDB, 0x6B, 0x1A, 0xDD,
	0x2F, 0xD8, 0x1A, 0x25, 0xCC, 0xB1, 0x48, 0x03,
	0x2D, 0xCD, 0x73, 0x99, 0x36, 0x73, 0x7F, 0x2D};
extern uint8_t _end[];
static void dilithium_demo_cmd(void)
{

	printf("Start func...\n");
	/* ---- 1.  Choose two buffers in main RAM ----------------------- */
	volatile uint8_t *tx = (uint8_t *)((uintptr_t)_end + 0x100); /* +256 B */
	volatile uint8_t *rx = (uint8_t *)((uintptr_t)_end + 0x200); /* +512 B */
	const unsigned IN_LEN = sizeof(test_msg);					 // 32
	const unsigned OUT_LEN = 32;								 // 1312+2528

	/* 1. copy input to SRAM*/
	printf("Copying into SRAM...\n");
	memcpy((void *)tx, test_msg, IN_LEN);

	/* ---- 2.  Configure control CSRs ------------------------------- */
	printf("Configuring CSRs...\n");
	main_mode_write(0);	   /* your preferred mode       */
	main_sec_lvl_write(2); /* security level you want   */
	main_start_write(0);   /* keep core idle for now    */

	/* ---- 3.  Program DMA Reader (CPU → core) ---------------------- */
	printf("Configuring DMA READER...\n");
	dilithium_reader_base_write((uint64_t)(uintptr_t)tx);
	dilithium_reader_length_write(IN_LEN);
	dilithium_reader_enable_write(1); /* arm it */

	/* ---- 4.  Program DMA Writer (core → CPU) ---------------------- */
	printf("Configuring DMA WRITER...\n");
	dilithium_writer_base_write((uint64_t)(uintptr_t)rx);
	dilithium_writer_length_write(OUT_LEN); /* same length for demo */
	dilithium_writer_enable_write(1);

	/* ---- 5.  Kick the core ---------------------------------------- */
	main_start_write(1);
	main_start_write(0);
	printf("Start!\n");

	/* ---- 6.  Wait for DMA completion ------------------------------ */
	while (!dilithium_reader_done_read())
		;
	printf("Dilitihum finishes reading\n");
	while (!dilithium_writer_done_read())
		;

	printf("Dilithium + DMA finished!\n");

	/* ---- 7.  Inspect/print the result ----------------------------- */
	printf("Dilithium finished. First 32 bytes of output:\n");
	hexdump((const void *)rx, 32); /* or hexdump(rx, OUT_LEN) if you want all 3.8 kB */
}

/*-----------------------------------------------------------------------*/
/* Console service / Main                                                */
/*-----------------------------------------------------------------------*/

static void console_service(void)
{
	char *str;
	char *token;

	str = readstr();
	if (str == NULL)
		return;
	token = get_token(&str);
	if (strcmp(token, "help") == 0)
		help();
	else if (strcmp(token, "reboot") == 0)
		reboot_cmd();
	else if (strcmp(token, "dilithium") == 0)
		dilithium_demo_cmd();
	prompt();
}

int main(void)
{
#ifdef CONFIG_CPU_HAS_INTERRUPT
	irq_setmask(0);
	irq_setie(1);
#endif
	uart_init();

	help();
	dilithium_demo_cmd();
	prompt();

	return 0;
}
