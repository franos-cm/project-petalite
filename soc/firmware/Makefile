ifndef SRC_DIR
$(error SRC_DIR is not set. Pass it as an environment variable or make argument, e.g., make SRC_DIR=host)
endif

BUILD_DIR?=../build-soc/

# Sources/objects
C_FILES := $(shell find $(SRC_DIR) -name '*.c')
OBJECTS := $(C_FILES:.c=.o) crt0.o

# SOC_DIRECTORY?=../tools/litex/litex/litex/soc/
include $(BUILD_DIR)/software/include/generated/variables.mak
include $(SOC_DIRECTORY)/software/common.mak

# Inherit all subdirs of SRC_DIR in include path
CFLAGS += $(patsubst %,-I%,$(shell find $(SRC_DIR) -type d))

ifdef WITH_CXX
    CFLAGS += -DWITH_CXX
endif

# =========================
# Firmware
# =========================

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

# deps for existing .o
-include $(OBJECTS:.o=.d)

VPATH = $(BIOS_DIRECTORY):$(BIOS_DIRECTORY)/cmds:$(CPU_DIRECTORY)

%.o: %.cpp
	$(compilexx)
%.o: %.c
	$(compile)
%.o: %.S
	$(assemble)

clean:
	$(RM) $(OBJECTS) $(FIRMWARE_NAME).elf $(FIRMWARE_NAME).bin .*~ *~ \
	      -r wolfssl-build $(BUILD_DIR)/software/wolfssl-install
.PHONY: all clean wolfssl wolfssl-clean show-flags


# =========================
# wolfSSL (CMake, bare-metal friendly)
# =========================
# -------------------------
# wolfSSL (CMake, baremetal)
# -------------------------
WOLFSSL_SRC ?= /home/franos/projects/wolfssl
WOLFSSL_BUILD   := $(abspath ./wolfssl-build)
WOLFSSL_INSTALL := $(abspath $(BUILD_DIR)/software/wolfssl-install)

# Derive triplet from OBJCOPY and resolve absolute tool paths
W_OBJCOPY_LAST := $(lastword $(OBJCOPY))
W_TOOL_TRIPLET := $(patsubst %-objcopy,%,$(notdir $(W_OBJCOPY_LAST)))
W_CC     := $(W_TOOL_TRIPLET)-gcc
W_AR     := $(W_TOOL_TRIPLET)-ar
W_RANLIB := $(W_TOOL_TRIPLET)-ranlib
W_CC_PATH     := $(shell command -v $(W_CC))
W_AR_PATH     := $(shell command -v $(W_AR))
W_RANLIB_PATH := $(shell command -v $(W_RANLIB))
WOLFSSL_CFG_DIR := $(abspath wolfssl)


WOLFSSL_CFLAGS  := $(CFLAGS)
WOLFSSL_CFLAGS  += -Os -ffunction-sections -fdata-sections -flto -ffreestanding -fno-builtin
WOLFSSL_CFLAGS  += -DHAVE_SYS_TIME_H -I$(WOLFSSL_CFG_DIR)
WOLFSSL_CFLAGS  += -Wno-error=cpp
WOLFSSL_LDFLAGS ?= $(LDFLAGS)
WOLFSSL_LDFLAGS  += -Wl,--gc-sections -Wl,--icf=all -flto

wolfssl:
	@rm -rf "$(WOLFSSL_BUILD)"  # kill cache so options take effect
	@mkdir -p "$(WOLFSSL_BUILD)" "$(WOLFSSL_INSTALL)"
	cd "$(WOLFSSL_BUILD)" && \
	  CC="$(W_CC_PATH)" AR="$(W_AR_PATH)" RANLIB="$(W_RANLIB_PATH)" \
	  CFLAGS="$(WOLFSSL_CFLAGS)" LDFLAGS="$(WOLFSSL_LDFLAGS)" \
	  cmake -S "$(WOLFSSL_SRC)" -B . \
	    -DCMAKE_SYSTEM_NAME=Generic \
	    -DCMAKE_C_COMPILER="$(W_CC_PATH)" \
	    -DCMAKE_AR="$(W_AR_PATH)" \
	    -DCMAKE_RANLIB="$(W_RANLIB_PATH)" \
	    -DCMAKE_ASM_COMPILER="$(W_CC_PATH)" \
	    -DCMAKE_C_FLAGS="$(WOLFSSL_CFLAGS)" \
	    -DCMAKE_EXE_LINKER_FLAGS="$(WOLFSSL_LDFLAGS)" \
	    -DCMAKE_TRY_COMPILE_TARGET_TYPE=STATIC_LIBRARY \
	    -DCMAKE_INSTALL_PREFIX="$(WOLFSSL_INSTALL)" \
	    -DBUILD_SHARED_LIBS=OFF \
	    -DWOLFSSL_USER_SETTINGS=ON \
		-DWOLFSSL_CRYPT_ONLY=ON \
	    -DWOLFSSL_EXAMPLES=OFF \
		-DWOLFSSL_CRYPT_TESTS=OFF
	cmake --build "$(WOLFSSL_BUILD)" --target wolfssl -j$$(nproc)
	cmake --install "$(WOLFSSL_BUILD)"

wolfssl-clean:
	$(RM) -r "$(WOLFSSL_BUILD)" "$(WOLFSSL_INSTALL)"
	$(RM) -r "wolfssl"

show-flags:
	@echo "CC             = $(CC)"
	@echo "AR             = $(AR)"
	@echo "RANLIB         = $(RANLIB)"
	@echo "OBJCOPY        = $(OBJCOPY)"
	@echo "CFLAGS         = $(CFLAGS)"
	@echo "LDFLAGS        = $(LDFLAGS)"
	@echo "W_OBJCOPY_LAST = $(W_OBJCOPY_LAST)"
	@echo "W_TOOL_TRIPLET = $(W_TOOL_TRIPLET)"
	@echo "W_CC / W_AR / W_RANLIB = $(W_CC) / $(W_AR) / $(W_RANLIB)"
	@echo "WOLFSSL_CFLAGS = $(WOLFSSL_CFLAGS)"
	@echo "WOLFSSL_LDFLAGS= $(WOLFSSL_LDFLAGS)"
