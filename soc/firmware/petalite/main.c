// #include <stdio.h>
// #include <stdlib.h>
// #include <string.h>

// #include <irq.h>
// #include <libbase/uart.h>
// #include <libbase/console.h>
// #include <generated/csr.h>
// #include <generated/mem.h>

// int main(void)
// {
// #ifdef CONFIG_CPU_HAS_INTERRUPT
// 	irq_setmask(0);
// 	irq_setie(1);
// #endif

// 	while (1)
// 	{
// 		uint32_t output_host = mailbox_from_host_read();
// 		mailbox_to_host_write(output_host * 3);

// 		// Wait for a command
// 		// if (main_cmd_valid_read() && !main_cmd_ack_read())
// 		// {
// 		// 	uint32_t cmd = main_cmd_value_read();
// 		// 	uint32_t response = cmd * 2;
// 		// 	main_rsp_value_write(response);
// 		// 	main_rsp_valid_write(1);
// 		// 	main_cmd_ack_write(1);
// 		// }

// 		// // Wait for host to clear valid, then clear ack
// 		// if (!main_cmd_valid_read() && main_cmd_ack_read())
// 		// {
// 		// 	main_cmd_ack_write(0);
// 		// }

// 		// // Wait for host to ack response, then clear valid
// 		// if (main_rsp_valid_read() && main_rsp_ack_read())
// 		// {
// 		// 	main_rsp_valid_write(0);
// 		// }
// 	}

// 	return 0;
// }

/*-----------------------------------------------------------------------*/
/* Uart                                                                  */
/*-----------------------------------------------------------------------*/

// static char *readstr(void)
// {
// 	char c[2];
// 	static char s[64];
// 	static int ptr = 0;

// 	if (readchar_nonblock())
// 	{
// 		c[0] = getchar();
// 		c[1] = 0;
// 		switch (c[0])
// 		{
// 		case 0x7f:
// 		case 0x08:
// 			if (ptr > 0)
// 			{
// 				ptr--;
// 				fputs("\x08 \x08", stdout);
// 			}
// 			break;
// 		case 0x07:
// 			break;
// 		case '\r':
// 		case '\n':
// 			s[ptr] = 0x00;
// 			fputs("\n", stdout);
// 			ptr = 0;
// 			return s;
// 		default:
// 			if (ptr >= (sizeof(s) - 1))
// 				break;
// 			fputs(c, stdout);
// 			s[ptr] = c[0];
// 			ptr++;
// 			break;
// 		}
// 	}

// 	return NULL;
// }

// static char *get_token(char **str)
// {
// 	char *c, *d;

// 	c = (char *)strchr(*str, ' ');
// 	if (c == NULL)
// 	{
// 		d = *str;
// 		*str = *str + strlen(*str);
// 		return d;
// 	}
// 	*c = 0;
// 	d = *str;
// 	*str = c + 1;
// 	return d;
// }

// static void prompt(void)
// {
// 	printf("\e[92;1mlitex-demo-app\e[0m> ");
// }

// static void help(void)
// {
// 	puts("\nLiteX minimal demo app built " __DATE__
// 		 " " __TIME__
// 		 "\n");
// }

// static void reboot_cmd(void)
// {
// 	ctrl_reset_write(1);
// }

// static void send_command(uint32_t value)
// {
// 	printf("Writing value...\n");
// 	petalite_cmd_value_write(value);
// 	petalite_cmd_valid_write(1);
// 	printf("Wrote: %u\n", value);
// 	printf("Awaiting petalite acknowledge...\n");

// 	// Wait for petalite to acknowledge
// 	while (!petalite_cmd_ack_read())
// 		;

// 	printf("Petalite acknowledged!\n");

// 	// Clear valid
// 	petalite_cmd_valid_write(0);

// 	printf("Host cleared valid...\n");

// 	// Wait for petalite to clear ack
// 	while (petalite_cmd_ack_read())
// 		;

// 	printf("Petalite cleared ack...\n");
// }

// static uint32_t receive_response(void)
// {
// 	// Wait for valid response
// 	printf("Host waiting for valid rsp...\n");
// 	while (!petalite_rsp_valid_read())
// 		;

// 	uint32_t response = petalite_rsp_value_read();
// 	printf("Host received response: %u\n", response);

// 	// Acknowledge and wait for petalite to clear
// 	petalite_rsp_ack_write(1);

// 	printf("AAAAAAAAAA");
// 	while (petalite_rsp_valid_read())
// 		;
// 	petalite_rsp_ack_write(0);

// 	return response;
// }

// static void test_cmd(void)
// {
// 	send_command(42);
// 	uint32_t res = receive_response(); // should be 84

// 	send_command(7);
// 	res = receive_response(); // should be 14
// }

// static void test_cmd(void)
// {
// 	uint32_t input_host = host_mailbox_to_petalite_read();
// 	host_mailbox_to_petalite_write(input_host + 2);
// }

// static void test_cmd2(void)
// {
// 	uint32_t output_device = host_mailbox_from_petalite_read();
// 	printf("Host received response: %u\n", output_device);
// }

// static void test_cmd3(void)
// {
// 	printf("BB");
// }

// static void console_service(void)
// {
// 	char *str;
// 	char *token;

// 	str = readstr();
// 	if (str == NULL)
// 		return;
// 	token = get_token(&str);
// 	if (strcmp(token, "help") == 0)
// 		help();
// 	else if (strcmp(token, "reboot") == 0)
// 		reboot_cmd();
// 	// else if (strcmp(token, "test") == 0)
// 	// 	test_cmd();
// 	// else if (strcmp(token, "test2") == 0)
// 	// 	test_cmd2();
// 	else if (strcmp(token, "test3") == 0)
// 		test_cmd3();
// 	prompt();
// }

// int main(void)
// {
// #ifdef CONFIG_CPU_HAS_INTERRUPT
// 	irq_setmask(0);
// 	irq_setie(1);
// #endif
// 	uart_init();
// 	help();
// 	prompt();

// 	while (1)
// 	{
// 		console_service();
// 	}

// 	return 0;
// }

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include <irq.h>
#include <libbase/uart.h>
#include <libbase/console.h>
#include <generated/csr.h>
#include <generated/mem.h>

int main(void)
{
	volatile uint32_t *debug = (volatile uint32_t *)DEBUG_BASE;

	// Signal that firmware started
	debug[0] = 0x11111111;
	debug[1] = 0x00000001;

	int counter = 0;
	while (1)
	{
		// Update heartbeat
		debug[0] = counter++;
		debug[1] = 0x22222222;

		// Your actual firmware logic here

		// Simple delay
		for (volatile int i = 0; i < 100000; i++)
			;
	}
}