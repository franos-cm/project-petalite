#include "shared.h"

uint16_t inline be16(const uint8_t *p) { return (p[0] << 8) | p[1]; }
uint32_t inline be32(const uint8_t *p) { return (p[0] << 24) | (p[1] << 16) | (p[2] << 8) | p[3]; }