from enum import StrEnum

BYTE = 1
KBYTE = 1024
MBYTE = 1024**2


class CommProtocol(StrEnum):
    UART = "UART"
    PCIE = "PCIE"
