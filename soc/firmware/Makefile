ifndef SRC_DIR
$(error SRC_DIR is not set. Pass it as an environment variable or make argument, e.g., make SRC_DIR=host)
endif
BUILD_DIR?=../build-soc/
C_FILES := $(wildcard $(SRC_DIR)/*.c)
OBJECTS := $(C_FILES:.c=.o)
OBJECTS += crt0.o

# SOC_DIRECTORY?=../tools/litex/litex/litex/soc/
include $(BUILD_DIR)/software/include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

ifdef WITH_CXX
	CFLAGS += -DWITH_CXX
endif


all: $(FIRMWARE_NAME).bin

%.bin: %.elf
	$(OBJCOPY) -O binary $< $@
ifneq ($(OS),Windows_NT)
	chmod -x $@
endif

vpath %.a $(PACKAGES:%=../%)

$(FIRMWARE_NAME).elf: $(OBJECTS)
	$(CC) $(LDFLAGS) -T linker.ld -N -o $@ \
		$(OBJECTS) \
		$(PACKAGES:%=-L$(BUILD_DIR)/software/%) \
		-Wl,--whole-archive \
		-Wl,--gc-sections \
		-Wl,-Map,$@.map \
		$(LIBS:lib%=-l%)

ifneq ($(OS),Windows_NT)
	chmod -x $@
endif

# pull in dependency info for *existing* .o files
-include $(OBJECTS:.o=.d)

VPATH = $(BIOS_DIRECTORY):$(BIOS_DIRECTORY)/cmds:$(CPU_DIRECTORY)


%.o: %.cpp
	$(compilexx)

%.o: %.c
	$(compile)

%.o: %.S
	$(assemble)

clean:
	$(RM) $(OBJECTS) $(FIRMWARE_NAME).elf $(FIRMWARE_NAME).bin .*~ *~

.PHONY: all clean