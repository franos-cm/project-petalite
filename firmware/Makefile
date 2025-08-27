# =========================
# Configs
# =========================
ROOT_DIR             := $(abspath ..)
FIRMWARE_NAME        ?= firmware
SOC_BUILD_DIR        ?= $(ROOT_DIR)/builds/soc
WOLFSSL_BUILD_DIR    ?= $(ROOT_DIR)/builds/wolfssl
FIRMWARE_BUILD_DIR   ?= $(ROOT_DIR)/builds/firmware
LINKER_SCRIPT        ?= $(abspath linker.ld)
APP_DIR              ?= $(abspath src)
WOLFSSL_SRC_DIR      ?= $(abspath wolfssl)
TPM_SRC_DIR          := $(abspath ms-tpm-20-ref/TPMCmd/tpm)
WOLFSSL_INSTALL_DIR  := $(abspath $(SOC_BUILD_DIR)/software/wolfssl)

# =========================
# Paths in the project tree
# =========================
COMPAT_DIR     := $(APP_DIR)/compat
CONFIG_DIR     := $(APP_DIR)/config
PLATFORM_DIR   := $(APP_DIR)/platform
WOLFSSL_INC    := $(WOLFSSL_INSTALL_DIR)/include
WOLFSSL_LIB_A  := $(WOLFSSL_INSTALL_DIR)/lib/libwolfssl.a
TPM_INC        := $(TPM_SRC_DIR)/include
FIRMWARE_ELF   := $(FIRMWARE_BUILD_DIR)/$(FIRMWARE_NAME).elf
FIRMWARE_BIN   := $(FIRMWARE_BUILD_DIR)/$(FIRMWARE_NAME).bin
FIRMWARE_MAP   := $(FIRMWARE_ELF).map

# =========================
# C source files
# =========================
TPM_SOURCES     := $(foreach d,$(TPM_SRC_DIR),$(wildcard $(d)/*.c))
COMPAT_SOURCES  := $(foreach d,$(COMPAT_DIR),$(wildcard $(d)/*.c))
PLAT_SOURCES    := $(foreach d,$(PLATFORM_DIR),$(wildcard $(d)/*.c))
SOURCES         := $(PLAT_SOURCES) $(TPM_SOURCES) $(COMPAT_SOURCES)

# ------------------------------------------------------------
# Targets that REQUIRE the APP_DIR var or LiteX env vars
# ------------------------------------------------------------
NEED_APP_DIR_GOALS := all $(FIRMWARE_ELF) $(FIRMWARE_BIN) check-no-openssl
ifneq (,$(filter $(NEED_APP_DIR_GOALS),$(MAKECMDGOALS)))
  ifeq ($(wildcard $(APP_DIR)),)
    $(error APP_DIR '$(APP_DIR)' not found. Override with APP_DIR=... or create it)
  endif
endif

REQUIRE_SOC_GOALS := all $(FIRMWARE_ELF) $(FIRMWARE_BIN) wolfssl-build show show-includes show-cflags cc-include-search
SOC_VARS := $(abspath $(SOC_BUILD_DIR))/software/include/generated/variables.mak

ifneq (,$(filter $(REQUIRE_SOC_GOALS),$(MAKECMDGOALS)))
  ifeq ($(wildcard $(SOC_VARS)),)
    $(error Missing $(SOC_VARS) (did you build the SoC?). Override SOC_BUILD_DIR or run the SoC build)
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
ifneq (,$(filter all $(FIRMWARE_ELF) $(FIRMWARE_BIN),$(MAKECMDGOALS)))
  ifeq ($(wildcard $(COMPAT_DIR)),)
    $(warning Note: $(COMPAT_DIR) not found. If you use <openssl/...> forwarders, create it.)
  endif
  ifeq ($(wildcard $(CONFIG_DIR)/wolfssl_user_settings.h)),)
    $(warning Note: $(CONFIG_DIR)/wolfssl_user_settings.h missing. Define your wolfSSL options there.)
  endif

  ifeq ($(wildcard $(WOLFSSL_INC)/wolfssl/options.h),)
    $(error Missing wolfSSL headers in $(WOLFSSL_INC). Run 'make wolfssl-build' or set WOLFSSL_INSTALL_DIR)
  endif
  ifeq ($(wildcard $(WOLFSSL_LIB_A)),)
    $(error Missing $(WOLFSSL_LIB_A). Run 'make wolfssl-build')
  endif

  ifeq ($(strip $(TPM_SOURCES)),)
    $(error No TPM sources found in $(TPM_SRC_DIR). Did you set the right path?)
  endif
endif

# =========================
# Include paths
# =========================
INCLUDES += \
	-I$(CONFIG_DIR) \
	-I$(WOLFSSL_INC) \
	-I$(COMPAT_DIR) \
	-I$(PLATFORM_DIR) \
	-I$(TPM_INC)

# =========================
# C / LD flags
# =========================
CFLAGS += \
	-DWOLFSSL_USER_SETTINGS \
	-DHASH_LIB=Ossl -DSYM_LIB=Ossl -DBN_MATH_LIB=Ossl \
	-nostdinc -ffreestanding -fno-builtin \
	-ffunction-sections -fdata-sections \
	-Os -g -std=gnu11 -Wall -Wextra -Werror
CFLAGS += -fno-unwind-tables -fno-asynchronous-unwind-tables

# Ensure the map file goes under FIRMWARE_BUILD_DIR
LDFLAGS := $(filter-out -Wl,-Map=%,$(LDFLAGS)) -Wl,--gc-sections -Wl,-Map,$(FIRMWARE_MAP)

LTO ?= 1
ifeq ($(LTO),1)
  CFLAGS  += -flto
  LDFLAGS += -flto
endif

# =========================
# Object mapping to FIRMWARE_BUILD_DIR
# =========================
PLAT_OBJECTS   := $(patsubst $(PLATFORM_DIR)/%.c,$(FIRMWARE_BUILD_DIR)/platform/%.o,$(PLAT_SOURCES))
COMPAT_OBJECTS := $(patsubst $(COMPAT_DIR)/%.c,$(FIRMWARE_BUILD_DIR)/compat/%.o,$(COMPAT_SOURCES))
TPM_OBJECTS    := $(patsubst $(TPM_SRC_DIR)/%.c,$(FIRMWARE_BUILD_DIR)/tpm/%.o,$(TPM_SOURCES))
OBJECTS := $(PLAT_OBJECTS) $(COMPAT_OBJECTS) $(TPM_OBJECTS)
DEPS    := $(OBJECTS:.o=.d)

# =========================
# Default target
# =========================
.PHONY: all
all: $(FIRMWARE_BIN)

# Pattern rules to write objects into FIRMWARE_BUILD_DIR
$(FIRMWARE_BUILD_DIR)/platform/%.o: $(PLATFORM_DIR)/%.c
	@mkdir -p $(dir $@)
	$(compile) -MMD -MP -c $< -o $@

$(FIRMWARE_BUILD_DIR)/compat/%.o: $(COMPAT_DIR)/%.c
	@mkdir -p $(dir $@)
	$(compile) -MMD -MP -c $< -o $@

$(FIRMWARE_BUILD_DIR)/tpm/%.o: $(TPM_SRC_DIR)/%.c
	@mkdir -p $(dir $@)
	$(compile) -MMD -MP -c $< -o $@

# If you have crt0.S (adjust path or delete this rule if not used)
$(FIRMWARE_BUILD_DIR)/crt0.o: $(APP_DIR)/crt0.S
	@mkdir -p $(dir $@)
	$(assemble) -MMD -MP -c $< -o $@

# Link inside FIRMWARE_BUILD_DIR
$(FIRMWARE_ELF): $(OBJECTS) $(LINKER_SCRIPT) $(WOLFSSL_LIB_A)
	@mkdir -p $(dir $@)
	$(CC) $(LDFLAGS) -T $(LINKER_SCRIPT) -N -o $@ \
	    $(OBJECTS) \
	    $(LIBS:lib%=-l%) \
	    $(WOLFSSL_LIB_A)

# Convert to .bin in FIRMWARE_BUILD_DIR
$(FIRMWARE_BIN): $(FIRMWARE_ELF)
	$(OBJCOPY) -O binary $< $@
ifneq ($(OS),Windows_NT)
	chmod -x $@
endif

# Include dep files from FIRMWARE_BUILD_DIR
-include $(DEPS)

# =========================
# wolfSSL build
# =========================
.PHONY: wolfssl-build wolfssl-clean
ifneq (,$(filter wolfssl-build wolfssl-clean show-wolfssl-cflags,$(MAKECMDGOALS)))

ifeq ($(strip $(TARGET_PREFIX)),)
  $(error TARGET_PREFIX is empty; did you include LiteX's common.mak?)
endif

# Tool paths (absolute)
W_CC_PATH     := $(shell command -v $(TARGET_PREFIX)gcc)
W_AR_PATH     := $(shell command -v $(TARGET_PREFIX)gcc-ar)
W_RANLIB_PATH := $(shell command -v $(TARGET_PREFIX)gcc-ranlib)
ifeq ($(strip $(W_CC_PATH)$(W_AR_PATH)$(W_RANLIB_PATH)),)
  $(error Could not find $(TARGET_PREFIX){gcc,gcc-ar,gcc-ranlib} on PATH)
endif

# Discover the cross toolchain’s built-in include folders (safe for bare-metal).
GCC_INC      := $(shell $(W_CC_PATH) -print-file-name=include)
GCC_INCFIX   := $(shell $(W_CC_PATH) -print-file-name=include-fixed)
# Some toolchains use a sysroot; adding it (if present) is harmless.
GCC_SYSROOT  := $(shell $(W_CC_PATH) --print-sysroot)

# Keep wolfSSL compile flags minimal and freestanding; avoid firmware LDFLAGS
WOLFSSL_CFG_DIR := $(CONFIG_DIR)
WOLFSSL_CFLAGS  := $(CFLAGS) -I$(WOLFSSL_CFG_DIR) \
                   -DWOLFSSL_USER_SETTINGS -DHAVE_SYS_TIME_H -Wno-error=cpp \
				   -isystem $(GCC_INC) -isystem $(GCC_INCFIX) \
				   $(if $(GCC_SYSROOT),-isystem $(GCC_SYSROOT)/include)

# TODO: revise LDFLAGS, and see if I need base ones
# WOLFSSL_LDFLAGS := $(LDFLAGS)
#WOLFSSL_LDFLAGS  := 
WOLFSSL_LDFLAGS := -Wl,--gc-sections -Wl,--icf=all

wolfssl-build:
	@rm -rf "$(WOLFSSL_BUILD_DIR)"
	@mkdir -p "$(WOLFSSL_BUILD_DIR)" "$(WOLFSSL_INSTALL_DIR)"
	cd "$(WOLFSSL_BUILD_DIR)" && \
	  CC="$(W_CC_PATH)" AR="$(W_AR_PATH)" RANLIB="$(W_RANLIB_PATH)" \
	  CFLAGS="$(WOLFSSL_CFLAGS)" LDFLAGS="$(WOLFSSL_LDFLAGS)" \
	  cmake -S "$(WOLFSSL_SRC_DIR)" -B . \
	    -DCMAKE_SYSTEM_NAME=Generic \
	    -DCMAKE_C_COMPILER="$(W_CC_PATH)" \
	    -DCMAKE_AR="$(W_AR_PATH)" \
	    -DCMAKE_RANLIB="$(W_RANLIB_PATH)" \
	    -DCMAKE_ASM_COMPILER="$(W_CC_PATH)" \
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
	$(RM) -r "$(WOLFSSL_BUILD_DIR)" "$(WOLFSSL_INSTALL_DIR)"

endif

# =========================
# Utilities
# =========================
.PHONY: clean show help check-no-openssl show-includes cc-include-search show-cflags

clean:
	$(RM) -r $(FIRMWARE_BUILD_DIR) \
	       $(WOLFSSL_BUILD_DIR) $(WOLFSSL_INSTALL_DIR) \
	       .*~ *~

show:
	@echo "APP_DIR        = $(APP_DIR) $(if $(wildcard $(APP_DIR)),(ok),(missing))"
	@echo "SOC_BUILD_DIR      = $(SOC_BUILD_DIR)"
	@echo "FIRMWARE_BUILD_DIR   = $(FIRMWARE_BUILD_DIR)"
	@echo "FIRMWARE_NAME  = $(FIRMWARE_NAME)"
	@echo "PLATFORM_DIR   = $(PLATFORM_DIR)"
	@echo "TPM_SRC_DIR    = $(TPM_SRC_DIR)"
	@echo "WOLFSSL_INC    = $(WOLFSSL_INC)"
	@echo "WOLFSSL_LIB_A  = $(WOLFSSL_LIB_A)"
	@echo "CPPFLAGS       = $(CPPFLAGS)"
	@echo "CFLAGS         = $(CFLAGS)"
	@echo "LDFLAGS        = $(LDFLAGS)"

help:
	@echo "Usage:"
	@echo "  make [all]                     Build firmware ($(FIRMWARE_BIN))"
	@echo "  make wolfssl-build             Build wolfSSL (static) into $(WOLFSSL_INSTALL_DIR)"
	@echo "  make wolfssl-clean             Clean wolfSSL build/install dirs"
	@echo "  make check-no-openssl          Verify no OpenSSL symbols linked"
	@echo "  make show / show-includes      Show settings / include search"
	@echo "  make clean                     Remove build artifacts"

check-no-openssl: $(FIRMWARE_ELF)
	@nm -A $< | grep -i -E 'OPENSSL|libcrypto' && \
	  (echo "!! Found OpenSSL symbols"; exit 1) || \
	  echo "OK: no OpenSSL symbols found"

show-includes:
	@echo "INCLUDES (Makefile -I dirs):"
	@echo $(INCLUDES) | tr ' ' '\n' | sed -n 's/^-I//p'

cc-include-search:
	@echo | $(CC) -v -x c -E - 2>&1 | sed -n '/search starts here:/,/End of search list./p'

show-cflags:
	@echo "CFLAGS (split lines):"
	@printf "%s\n" $(CFLAGS)

show-wolfssl-cflags:
	@echo "WOLFSSL_CFLAGS (split lines):"
	@printf "%s\n" $(WOLFSSL_CFLAGS)