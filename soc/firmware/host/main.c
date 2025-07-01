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
	printf("\e[92;1mlitex-demo-app\e[0m> ");
}

static void help(void)
{
	puts("\nLiteX minimal demo app built " __DATE__
		 " " __TIME__
		 "\n");
}

static void reboot_cmd(void)
{
	ctrl_reset_write(1);
}

static void send_command(uint32_t value)
{
	petalite_main_cmd_value_write(value);
	petalite_main_cmd_valid_write(1);

	// Wait for petalite_main to acknowledge
	while (!petalite_main_cmd_ack_read())
		;

	// Clear valid
	petalite_main_cmd_valid_write(0);

	// Wait for petalite_main to clear ack
	while (petalite_main_cmd_ack_read())
		;
}

static uint32_t receive_response(void)
{
	// Wait for valid response
	while (!petalite_main_rsp_valid_read())
		;

	uint32_t response = petalite_main_rsp_value_read();
	printf("Host received response: %u\n", response);

	// Acknowledge and wait for petalite_main to clear
	petalite_main_rsp_ack_write(1);
	while (petalite_main_rsp_valid_read())
		;
	petalite_main_rsp_ack_write(0);

	return response;
}

static void test_cmd(void)
{
	send_command(42);
	uint32_t res = receive_response(); // should be 84

	send_command(7);
	res = receive_response(); // should be 14
}

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
	else if (strcmp(token, "test") == 0)
		test_cmd();
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
	prompt();

	while (1)
	{
		console_service();
	}

	return 0;
}
