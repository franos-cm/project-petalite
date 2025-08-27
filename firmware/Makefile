# =========================
# Configs
# =========================
FIRMWARE_NAME        ?= firmware
APP_DIR              ?= $(abspath src)
WOLFSSL_SRC_DIR      ?= $(abspath wolfssl)
WOLFSSL_BUILD_DIR    := $(abspath wolfssl-build)
WOLFSSL_INSTALL_DIR  := $(abspath $(BUILD_DIR)/software/wolfssl)
TPM_SRC_DIR          := $(abspath ms-tpm-20-ref/TPMCmd/tpm)
BUILD_DIR            ?= builds/build-soc


# =========================
# Paths in the project tree
# =========================
COMPAT_DIR     := $(APP_DIR)/compat
CONFIG_DIR     := $(APP_DIR)/config
PLATFORM_DIR   := $(APP_DIR)/platform
WOLFSSL_INC    := $(WOLFSSL_INSTALL_DIR)/include
WOLFSSL_LIB_A  := $(WOLFSSL_INSTALL_DIR)/lib/libwolfssl.a
TPM_INC        := $(TPM_SRC_DIR)/include


# =========================
# C source files
# =========================
TPM_SOURCES := $(foreach d,$(TPM_SRC_DIR),$(wildcard $(d)/*.c))
COMPAT_SOURCES := $(foreach d,$(COMPAT_DIR),$(wildcard $(d)/*.c))
PLAT_SOURCES := $(foreach d,$(PLATFORM_DIR),$(wildcard $(d)/*.c))
SOURCES := $(PLAT_SOURCES) $(TPM_SOURCES) $(COMPAT_SOURCES)


# ------------------------------------------------------------
# Targets that REQUIRE the APP_DIR var or Litex env vars
# ------------------------------------------------------------
NEED_APP_DIR_GOALS := all $(FIRMWARE_NAME).elf $(FIRMWARE_NAME).bin check-no-openssl
ifneq (,$(filter $(NEED_APP_DIR_GOALS),$(MAKECMDGOALS)))
  ifeq ($(wildcard $(APP_DIR)),)
    $(error APP_DIR '$(APP_DIR)' not found. Override with APP_DIR=... or create it)
  endif
endif

REQUIRE_SOC_GOALS := all $(FIRMWARE_NAME).elf $(FIRMWARE_NAME).bin wolfssl show show-includes show-cflags cc-include-search
SOC_VARS := $(abspath $(BUILD_DIR))/software/include/generated/variables.mak

ifneq (,$(filter $(REQUIRE_SOC_GOALS),$(MAKECMDGOALS)))
  ifeq ($(wildcard $(SOC_VARS)),)
    $(error Missing $(SOC_VARS) (did you build the SoC?). Override BUILD_DIR or run the SoC build)
  endif
  include $(SOC_VARS)
  ifndef SOC_DIRECTORY
    $(error SOC_DIRECTORY not set in $(SOC_VARS))
  endif
  SOC_COMM := $(SOC_DIRECTORY)/software/common.mak
  ifeq ($(wildcard $(SOC_COMM)),)
    $(error Missing $(SOC_COMM). Check SOC_DIRECTORY or your LiteX tree)
  endif
  include $(SOC_COMM)
else
  -include $(SOC_VARS)
  ifneq ($(strip $(SOC_DIRECTORY)),)
    SOC_COMM := $(SOC_DIRECTORY)/software/common.mak
    -include $(SOC_COMM)
  endif
endif

# --- Early sanity checks for firmware builds ---
ifneq (,$(filter all $(FIRMWARE_NAME).elf $(FIRMWARE_NAME).bin,$(MAKECMDGOALS)))
  ifeq ($(wildcard $(COMPAT_DIR)),)
    $(warning Note: $(COMPAT_DIR) not found. If you use <openssl/...> forwarders, create it.)
  endif
  ifeq ($(wildcard $(CONFIG_DIR)/wolfssl_user_settings.h)),)
    $(warning Note: $(CONFIG_DIR)/wolfssl_user_settings.h missing. Define your wolfSSL options there.)
  endif

  ifeq ($(wildcard $(WOLFSSL_INC)/wolfssl/options.h),)
    $(error Missing wolfSSL headers in $(WOLFSSL_INC). Run 'make wolfssl' or set WOLFSSL_INSTALL_DIR)
  endif
  ifeq ($(wildcard $(WOLFSSL_LIB_A)),)
    $(error Missing $(WOLFSSL_LIB_A). Run 'make wolfssl')
  endif

  ifeq ($(strip $(TPM_SOURCES)),)
    $(error No TPM sources found in $(TPM_SRC_DIR). Did you set the right path?)
  endif
endif


# =========================
# Include paths
# =========================
INCLUDES += \
	-I$(COMPAT_DIR) \
	-I$(CONFIG_DIR) \
	-I$(WOLFSSL_INC) \
	-I$(TPM_INC) \
	-I$(PLATFORM_DIR)


# =========================
# C / LD flags
# =========================
CFLAGS += \
	-DWOLFSSL_USER_SETTINGS \
	-DHASH_LIB=Ossl -DSYM_LIB=Ossl -DBN_MATH_LIB=Ossl \
	-ffreestanding -fno-builtin \
	-ffunction-sections -fdata-sections \
	-Os -g -std=gnu11 -Wall -Wextra -Werror
LDFLAGS += -Wl,--gc-sections -Wl,-Map,$(FIRMWARE_NAME).elf.map
LTO ?= 1

# =========================
# Objects / deps / search path
# =========================
OBJECTS := $(SOURCES:.c=.o) crt0.o
-include $(OBJECTS:.o=.d)

VPATH = $(BIOS_DIRECTORY):$(BIOS_DIRECTORY)/cmds:$(CPU_DIRECTORY)

# =========================
# Default target
# =========================
.PHONY: all
all: $(FIRMWARE_NAME).bin

$(FIRMWARE_NAME).elf: $(OBJECTS) linker.ld $(WOLFSSL_LIB_A)
	$(CC) $(LDFLAGS) -T linker.ld -N -o $@ \
	    $(OBJECTS) \
	    $(LIBS:lib%=-l%) \
	    $(WOLFSSL_LIB_A)

$(FIRMWARE_NAME).bin: $(FIRMWARE_NAME).elf
	$(OBJCOPY) -O binary $< $@
ifneq ($(OS),Windows_NT)
	chmod -x $@
endif

%.o: %.c
	$(compile)
%.o: %.S
	$(assemble)

.PHONY: clean show help check-no-openssl
clean:
	$(RM) $(OBJECTS) $(FIRMWARE_NAME).elf $(FIRMWARE_NAME).bin \
	      $(FIRMWARE_NAME).elf.map .*~ *~ -r \
	      $(WOLFSSL_BUILD_DIR) $(WOLFSSL_INSTALL_DIR)

show:
	@echo "APP_DIR        = $(APP_DIR) $(if $(wildcard $(APP_DIR)),(ok),(missing))"
	@echo "BUILD_DIR      = $(BUILD_DIR)"
	@echo "FIRMWARE_NAME  = $(FIRMWARE_NAME)"
	@echo "APP_DIR        = $(APP_DIR)"
	@echo "PLATFORM_DIR   = $(PLATFORM_DIR)"
	@echo "TPM_SRC_DIR    = $(TPM_SRC_DIR)"
	@echo "WOLFSSL_INC    = $(WOLFSSL_INC)"
	@echo "WOLFSSL_LIB_A  = $(WOLFSSL_LIB_A)"
	@echo "CPPFLAGS       = $(CPPFLAGS)"
	@echo "CFLAGS         = $(CFLAGS)"
	@echo "LDFLAGS        = $(LDFLAGS)"

help:
	@echo "Usage:"
	@echo "  make [all]                     Build firmware ($(FIRMWARE_NAME).bin)"
	@echo "  make check-no-openssl          Verify no OpenSSL symbols linked"
	@echo "  make wolfssl / wolfssl-clean   Build or clean wolfSSL (static)"
	@echo "  make clean                     Remove build artifacts"

check-no-openssl: $(FIRMWARE_NAME).elf
	@nm -A $< | grep -i -E 'OPENSSL|libcrypto' && \
	  (echo "!! Found OpenSSL symbols"; exit 1) || \
	  echo "OK: no OpenSSL symbols found"

# =========================
# wolfSSL build
# =========================
ifneq (,$(filter wolfssl wolfssl-clean,$(MAKECMDGOALS)))

ifeq ($(strip $(TARGET_PREFIX)),)
  $(error TARGET_PREFIX is empty; did you include LiteX's common.mak?)
endif

W_CC     = $(TARGET_PREFIX)gcc
W_AR     = $(TARGET_PREFIX)gcc-ar
W_RANLIB = $(TARGET_PREFIX)gcc-ranlib

WOLFSSL_CFG_DIR := $(CONFIG_DIR)
WOLFSSL_CFLAGS  := -I$(WOLFSSL_CFG_DIR) $(CFLAGS) -DHAVE_SYS_TIME_H -Wno-error=cpp
WOLFSSL_LDFLAGS := $(LDFLAGS)

.PHONY: wolfssl wolfssl-clean
wolfssl:
	@rm -rf "$(WOLFSSL_BUILD_DIR)"
	@mkdir -p "$(WOLFSSL_BUILD_DIR)" "$(WOLFSSL_INSTALL_DIR)"
	cd "$(WOLFSSL_BUILD_DIR)" && \
	  CC="$(W_CC)" AR="$(W_AR)" RANLIB="$(W_RANLIB)" \
	  CFLAGS="$(WOLFSSL_CFLAGS)" LDFLAGS="$(WOLFSSL_LDFLAGS)" \
	  cmake -S "$(WOLFSSL_SRC_DIR)" -B . \
	    -DCMAKE_SYSTEM_NAME=Generic \
	    -DCMAKE_C_COMPILER="$(W_CC)" \
	    -DCMAKE_AR="$(W_AR)" \
	    -DCMAKE_RANLIB="$(W_RANLIB)" \
	    -DCMAKE_ASM_COMPILER="$(W_CC)" \
	    -DCMAKE_C_FLAGS="$(WOLFSSL_CFLAGS)" \
	    -DCMAKE_EXE_LINKER_FLAGS="$(WOLFSSL_LDFLAGS)" \
	    -DCMAKE_TRY_COMPILE_TARGET_TYPE=STATIC_LIBRARY \
	    -DCMAKE_INSTALL_PREFIX="$(WOLFSSL_INSTALL_DIR)" \
	    -DBUILD_SHARED_LIBS=OFF \
	    -DWOLFSSL_USER_SETTINGS=ON \
	    -DWOLFSSL_CRYPT_ONLY=ON \
	    -DWOLFSSL_EXAMPLES=OFF \
	    -DWOLFSSL_CRYPT_TESTS=OFF
	cmake --build "$(WOLFSSL_BUILD_DIR)" --target wolfssl -j$$(nproc)
	cmake --install "$(WOLFSSL_BUILD_DIR)"

wolfssl-clean:
	$(RM) -r "$(WOLFSSL_BUILD_DIR)" "$(WOLFSSL_INSTALL_DIR)" "wolfssl"

endif

.PHONY: show-includes cc-include-search show-cflags

show-includes:
	@echo "INCLUDES (Makefile -I dirs):"
	@echo $(INCLUDES) | tr ' ' '\n' | sed -n 's/^-I//p'

cc-include-search:
	@echo | $(CC) -v -x c -E - 2>&1 | sed -n '/search starts here:/,/End of search list./p'

show-cflags:
	@echo "CFLAGS (split lines):"
	@printf "%s\n" $(CFLAGS)
