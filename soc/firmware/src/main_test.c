// #include <stdio.h>
// #include <stdlib.h>
// #include <string.h>

// #include <irq.h>
// #include <libbase/uart.h>
// #include <libbase/console.h>
// #include <generated/csr.h>
// #include <generated/mem.h>

// /*-----------------------------------------------------------------------*/
// /* Uart                                                                  */
// /*-----------------------------------------------------------------------*/

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
// 	printf("\e[92;1mpetalite\e[0m> ");
// }

// /*-----------------------------------------------------------------------*/
// /* Commands                                                              */
// /*-----------------------------------------------------------------------*/

// static void reboot_cmd(void)
// {
// 	ctrl_reset_write(1);
// }

// /*-----------------------------------------------------------------------*/
// /* Console service / Main                                                */
// /*-----------------------------------------------------------------------*/

// static void console_service(void)
// {
// 	char *str;
// 	char *token;

// 	str = readstr();
// 	if (str == NULL)
// 		return;
// 	token = get_token(&str);
// 	if (strcmp(token, "help") == 0)
// 		while (1)
// 		{
// 			printf("AAAAAAA\n");
// 		}
// 	else if (strcmp(token, "reboot") == 0)
// 		reboot_cmd();
// 	else if (strcmp(token, "dilithium") == 0)
// 		printf("BBBBBBB\n");
// 	prompt();
// }

// int main(void)
// {
// #ifdef CONFIG_CPU_HAS_INTERRUPT
// 	irq_setmask(0);
// 	irq_setie(1);
// #endif
// 	uart_init();

// 	while (1)
// 	{
// 		printf("ready");
// 		console_service();
// 	}

// 	return 0;
// }
