// main.c

#include <stdio.h>
#include <stdlib.h>

#include <generated/csr.h>
#include <generated/soc.h>
#include <generated/mem.h>

#include <libbase/uart.h>
#include <libbase/console.h>

int main(void)
{
	char c;

	printf("Hello from Project Petalite!\n");
	printf("Type something and press Enter:\n");

	while (1)
	{
		// Wait for a character from UART (blocking)
		c = uart_read();

		// Echo the received character back
		printf("You typed: %c\n", c);
	}

	return 0;
}