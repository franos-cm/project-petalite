# =========================
# Configs
# =========================
ROOT_DIR             := $(abspath ..)
BUILDS_DIR           ?= $(ROOT_DIR)/builds
SOC_BUILD_DIR        ?= $(BUILDS_DIR)/soc
WOLFSSL_BUILD_DIR    ?= $(BUILDS_DIR)/wolfssl
TPM_BUILD_DIR        ?= $(BUILDS_DIR)/tpm
FIRMWARE_BUILD_DIR   ?= $(BUILDS_DIR)/firmware
LINKER_SCRIPT        ?= $(abspath linker.ld)
APP_DIR              ?= $(abspath core)
WOLFSSL_SRC_DIR      ?= $(abspath wolfssl)
TPM_ROOT             := $(abspath ms-tpm-20-ref/TPMCmd)
WOLFSSL_INSTALL_DIR  := $(abspath $(SOC_BUILD_DIR)/software/wolfssl)
FIRMWARE_NAME        ?= firmware
.DEFAULT_GOAL        := all

# =========================
# Paths in the project tree
# =========================
COMPAT_DIR     := $(APP_DIR)/compat
CONFIG_DIR     := $(APP_DIR)/config
PLATFORM_DIR   := $(APP_DIR)/platform
WOLFSSL_INC    := $(WOLFSSL_INSTALL_DIR)/include
OSSL_INC       := $(WOLFSSL_INSTALL_DIR)/include/wolfssl
WOLFSSL_LIB_A  := $(WOLFSSL_INSTALL_DIR)/lib/libwolfssl.a
TPM_SRC_DIR    := $(TPM_ROOT)/tpm
TPM_INC_DIR    := $(TPM_SRC_DIR)/include
TPM_CFG_DIR    := $(TPM_ROOT)/TpmConfiguration
SOC_SW_LIB_DIR := $(SOC_BUILD_DIR)/software
FIRMWARE_ELF   := $(FIRMWARE_BUILD_DIR)/$(FIRMWARE_NAME).elf
FIRMWARE_BIN   := $(FIRMWARE_BUILD_DIR)/$(FIRMWARE_NAME).bin
FIRMWARE_MAP   := $(FIRMWARE_ELF).map

# Goals that require the LiteX SoC environment & toolchain at parse time
REQUIRE_SOC_GOALS := all tpm-build wolfssl-build show show-includes show-cflags cc-include-search
SOC_VARS := $(abspath $(SOC_BUILD_DIR))/software/include/generated/variables.mak
EFFECTIVE_GOALS := $(if $(MAKECMDGOALS),$(MAKECMDGOALS),all)
ifneq (,$(filter $(REQUIRE_SOC_GOALS),$(EFFECTIVE_GOALS)))
  # -- Require SoC vars and LiteX common.mak --
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

  # -- Toolchain sanity: TARGET_PREFIX must exist (e.g. riscv64-unknown-elf-) --
  ifeq ($(strip $(TARGET_PREFIX)),)
    $(error TARGET_PREFIX is empty; LiteX did not set the toolchain. Did you build the SoC / set CROSS_COMPILE?)
  endif

  # Absolute tool paths (avoid host fallbacks; needed by CMake and LTO)
  CC_PATH     := $(shell command -v $(TARGET_PREFIX)gcc)
  AR_PATH     := $(shell command -v $(TARGET_PREFIX)gcc-ar)
  RANLIB_PATH := $(shell command -v $(TARGET_PREFIX)gcc-ranlib)
  OBJCOPY_PATH:= $(shell command -v $(TARGET_PREFIX)objcopy)
  ifeq ($(strip $(CC_PATH)$(AR_PATH)$(RANLIB_PATH)$(OBJCOPY_PATH)),)
    $(error Could not find $(TARGET_PREFIX){gcc,gcc-ar,gcc-ranlib,objcopy} on PATH)
  endif

  # GCC builtin include dirs (restore <float.h>, <limits.h>, etc. under -nostdinc)
  GCC_INC     := $(shell $(CC_PATH) -print-file-name=include)
  GCC_INCFIX  := $(shell $(CC_PATH) -print-file-name=include-fixed)
  GCC_SYSROOT := $(shell $(CC_PATH) --print-sysroot)
  BUILTIN_ISYSTEM := -isystem $(GCC_INC) -isystem $(GCC_INCFIX) \
                     $(if $(GCC_SYSROOT),-isystem $(GCC_SYSROOT)/include)
else
  # Optional soft-includes so 'show' targets can still print info without errors
  -include $(SOC_VARS)
  ifneq ($(strip $(SOC_DIRECTORY)),)
    SOC_COMM := $(SOC_DIRECTORY)/software/common.mak
    -include $(SOC_COMM)
  endif
  # Don’t error out on TARGET_PREFIX here—keep 'clean' etc. working even if SoC isn’t built.
endif

# =========================
# C / LD flags
# =========================
CFLAGS += \
	$(BUILTIN_ISYSTEM) \
	-nostdinc -ffreestanding -fno-builtin \
	-ffunction-sections -fdata-sections \
	-fno-unwind-tables -fno-asynchronous-unwind-tables \
	-Os -g -std=gnu11 -Wall -Wextra -Werror \
	-DWOLFSSL_USER_SETTINGS -DNO_OLD_SHA_NAMES -DNO_OLD_WC_NAMES

# Ensure the map file goes under FIRMWARE_BUILD_DIR
# Add wanted linker opts fresh:
RAW_LDFLAGS := $(LDFLAGS)
strip_map = $(foreach w,$(1),$(if $(findstring -Map=,$(w)),,$(w)))
LDFLAGS := $(call strip_map,$(RAW_LDFLAGS))
LDFLAGS := $(filter-out -nodefaultlibs,$(LDFLAGS))
# Ensure gc-sections & final map flag present (avoid duplicates)
ifeq (,$(findstring -Wl,--gc-sections,$(LDFLAGS)))
  LDFLAGS += -Wl,--gc-sections
endif
LDFLAGS += -Wl,-Map=$(FIRMWARE_MAP)

# Override LTO
CFLAGS  += -flto
LDFLAGS += -flto


# =========================
# wolfSSL build
# =========================
.PHONY: wolfssl-build wolfssl-clean wolfssl-ready

# Keep wolfSSL compile flags minimal and freestanding; avoid firmware LDFLAGS
WOLFSSL_CFLAGS  := $(CFLAGS) -I$(CONFIG_DIR) \
                   -DHAVE_SYS_TIME_H -Wno-error=cpp

wolfssl-build:
	@rm -rf "$(WOLFSSL_BUILD_DIR)"
	@mkdir -p "$(WOLFSSL_BUILD_DIR)" "$(WOLFSSL_INSTALL_DIR)"
	cd "$(WOLFSSL_BUILD_DIR)" && \
	  CC="$(CC_PATH)" AR="$(AR_PATH)" RANLIB="$(RANLIB_PATH)" \
	  CFLAGS="$(WOLFSSL_CFLAGS)" \
	  cmake -S "$(WOLFSSL_SRC_DIR)" -B . \
	    -DCMAKE_SYSTEM_NAME=Generic \
	    -DCMAKE_C_COMPILER="$(CC_PATH)" \
	    -DCMAKE_AR="$(AR_PATH)" \
	    -DCMAKE_RANLIB="$(RANLIB_PATH)" \
	    -DCMAKE_ASM_COMPILER="$(CC_PATH)" \
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

$(WOLFSSL_LIB_A):
	$(MAKE) wolfssl-build

wolfssl-ready: $(WOLFSSL_LIB_A)

# =================== Build TPM+Platform+Compat static library ===================
# Sources:
#  - TPM: everything under tpm/
#  - Platform + Compat: all .c in my dirs
TPM_ALL := $(shell find $(TPM_SRC_DIR) -name '*.c' | LC_ALL=C sort)
TPM_EXCLUDE := $(TPM_SRC_DIR)/cryptolibs/Ossl/BnToOsslMath.c $(TPM_SRC_DIR)/cryptolibs/Ossl/TpmToOsslSupport.c
TPM_SOURCES_LIB := $(filter-out $(TPM_EXCLUDE),$(TPM_ALL))
PLAT_SOURCES_LIB   := $(shell find $(PLATFORM_DIR) -name '*.c' | LC_ALL=C sort)

# Object folder under TPM_BUILD_DIR, mirroring source trees
TPM_OBJ_DIR := $(TPM_BUILD_DIR)/obj
TPM_OBJS    := $(patsubst $(TPM_SRC_DIR)/%.c,$(TPM_OBJ_DIR)/tpm/%.o,$(TPM_SOURCES_LIB))
PLAT_OBJS   := $(patsubst $(PLATFORM_DIR)/%.c,$(TPM_OBJ_DIR)/platform/%.o,$(PLAT_SOURCES_LIB))
TPM_CORE_OBJS := $(TPM_OBJS) $(PLAT_OBJS)
TPM_LIB       := $(TPM_BUILD_DIR)/libtpm.a

SOC_SW_LIB_ARCHIVES := $(foreach L,$(LIBS),$(wildcard $(SOC_SW_LIB_DIR)/$(L)/$(L).a))
TPM_DEFS := -DHASH_LIB=Wolf -DSYM_LIB=Wolf -DBN_MATH_LIB=Wolf -DMATH_LIB=TpmBigNum

# Includes needed by TPM core (mirrors upstream) + your platform/compat
TPM_INCLUDES := \
  -I$(CONFIG_DIR) \
  -I$(OSSL_INC) \
  -I$(WOLFSSL_INC) \
  -I$(COMPAT_DIR) \
  -I$(TPM_CFG_DIR) \
  -I$(TPM_INC_DIR) \
  -I$(TPM_INC_DIR)/public \
  -I$(TPM_INC_DIR)/private \
  -I$(TPM_INC_DIR)/private/prototypes \
  -I$(TPM_INC_DIR)/platform_interface \
  -I$(TPM_INC_DIR)/platform_interface/prototypes \
  -I$(TPM_SRC_DIR)/cryptolibs \
  -I$(TPM_SRC_DIR)/cryptolibs/common/include \
  -I$(TPM_SRC_DIR)/cryptolibs/TpmBigNum/include \
  -I$(TPM_SRC_DIR)/cryptolibs/wolf/include \
  -I$(PLATFORM_DIR) \
  -I$(PLATFORM_DIR)/include

# Compile flags specifically for the TPM library build:
TPM_CFLAGS := $(CFLAGS) $(TPM_DEFS) $(TPM_INCLUDES) \
              -DWOLFSSL_USER_SETTINGS \
              -include "$(OSSL_INC)/options.h" \
              -include "$(OSSL_INC)/wolfcrypt/settings.h" \
              -include "$(OSSL_INC)/ssl.h" \
              -include "$(COMPAT_DIR)/wolfssl.h" \
              -Wno-error=cpp -Wno-error=unused-value -Wno-error=unused-parameter \
              -Wno-error=expansion-to-defined -Wno-error=missing-prototypes \
			  -Wno-error=implicit-fallthrough -Wno-error=deprecated-declarations \
			  -Wno-strict-prototypes
# TODO: -Wno-error=expansion-to-defined might break something
# We do this specifically to these files only
$(TPM_OBJ_DIR)/tpm/src/main/CommandDispatcher.o: TPM_CFLAGS += -Wno-cast-function-type
$(TPM_OBJ_DIR)/platform/src/tpm_to_platform_interface.o: TPM_CFLAGS += -Wno-error=old-style-definition
$(TPM_OBJ_DIR)/platform/src/platform_pcr.o: TPM_CFLAGS += -Wno-error=old-style-definition


# Pattern rules (scoped CFLAGS so -I's don't leak anywhere else)
$(TPM_OBJ_DIR)/tpm/%.o: $(TPM_SRC_DIR)/%.c | wolfssl-ready
	@mkdir -p $(dir $@)
	$(CC) -MMD -MP -c $(TPM_CFLAGS) $< -o $@

$(TPM_OBJ_DIR)/platform/%.o: $(PLATFORM_DIR)/%.c | wolfssl-ready
	@mkdir -p $(dir $@)
	$(CC) -MMD -MP -c $(TPM_CFLAGS) $< -o $@

# Archive
$(TPM_LIB): $(TPM_CORE_OBJS)
	@mkdir -p $(dir $@)
	$(AR) rcs $@ $^

.PHONY: tpm-build tpm-clean list-tpm-sources
tpm-build: $(TPM_LIB)
	@echo "Built $(TPM_LIB)"

tpm-clean:
	$(RM) -r $(TPM_BUILD_DIR)

list-tpm-sources:
	@echo "TPM:    $$(echo $(TPM_SOURCES_LIB)    | wc -w) files"
	@echo "PLAT:   $$(echo $(PLAT_SOURCES_LIB)   | wc -w) files"
	@printf "%s\n" $(TPM_SOURCES_LIB)
	@printf "%s\n" $(PLAT_SOURCES_LIB)

# Include depfiles for the lib build (safe if none yet)
-include $(TPM_CORE_OBJS:.o=.d)


# =========================
# Firmware (final image)
# =========================
STARTUP_SRC  := $(CPU_DIRECTORY)/crt0.S
STARTUP_OBJ  := $(FIRMWARE_BUILD_DIR)/crt0.o
FIRMWARE_SRCS := $(APP_DIR)/main.c
FIRMWARE_OBJS := $(patsubst $(APP_DIR)/%.c,$(FIRMWARE_BUILD_DIR)/%.o,$(FIRMWARE_SRCS))

FIRMWARE_CFLAGS := $(CFLAGS) $(TPM_INCLUDES) \
                   -DWOLFSSL_USER_SETTINGS \
                   -include "$(OSSL_INC)/options.h" \
                   -include "$(OSSL_INC)/wolfcrypt/settings.h" \
                   -include "$(OSSL_INC)/ssl.h" \
				   -Wno-error=cpp \
				   -Wno-strict-prototypes

$(FIRMWARE_BUILD_DIR)/%.o: $(APP_DIR)/%.c | wolfssl-ready
	@mkdir -p $(dir $@)
	$(CC) -MMD -MP -c $(FIRMWARE_CFLAGS) $< -o $@


# Startup / crt0 (provides _start)
$(STARTUP_OBJ): $(STARTUP_SRC) | wolfssl-ready
	@mkdir -p $(dir $@)
	$(CC) -MMD -MP -c $(CFLAGS) $< -o $@


# Link final ELF
$(FIRMWARE_ELF): $(STARTUP_OBJ) $(FIRMWARE_OBJS) $(TPM_LIB) $(WOLFSSL_LIB_A) $(LINKER_SCRIPT)
	@mkdir -p $(dir $@)
	@if [ -z "$(SOC_SW_LIB_ARCHIVES)" ]; then \
	  echo "ERROR: No SoC libraries found under $(SOC_SW_LIB_DIR)"; exit 1; \
	fi
	$(CC) -T $(LINKER_SCRIPT) $(LDFLAGS) \
	  $(STARTUP_OBJ) $(FIRMWARE_OBJS) \
	  -Wl,--start-group $(TPM_LIB) $(WOLFSSL_LIB_A) $(SOC_SW_LIB_ARCHIVES) -lgcc -Wl,--end-group \
	  -o $@

# Produce raw binary
$(FIRMWARE_BIN): $(FIRMWARE_ELF)
	$(OBJCOPY_PATH) -O binary $< $@

# Default target
.PHONY: all
all: $(FIRMWARE_BIN)
	@echo "Built $@"

# Track deps of firmware objects too
-include $(FIRMWARE_OBJS:.o=.d) $(STARTUP_OBJ:.o=.d)

# =========================
# Utilities
# =========================
.PHONY: clean show help check-no-openssl show-includes show-soc-libs \
        cc-include-search show-cflags show-wolfssl-cflags show-tpm-cflags

clean:
	$(RM) -r \
		$(WOLFSSL_BUILD_DIR) $(TPM_BUILD_DIR) $(FIRMWARE_BUILD_DIR) $(WOLFSSL_INSTALL_DIR) .*~ *~

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

show-flags:
	@echo "=========CFLAGS========="
	@printf "%s\n" $(CFLAGS)
	@echo "\n=========LDFLAGS=========:"
	@printf "%s\n" $(LDFLAGS)

show-wolfssl-flags:
	@echo "=========WOLFSSL_CFLAGS========="
	@printf "%s\n" $(WOLFSSL_CFLAGS)
	@echo "\n=========WOLFSSL_LDFLAGS========="
	@printf "%s\n" $(WOLFSSL_LDFLAGS)

show-tpm-flags:
	@echo "TPM_CFLAGS (split lines):"
	printf "%s\n" $(TPM_CFLAGS)

show-soc-libs:
	@echo "SOC_SW_LIB_DIR = $(SOC_SW_LIB_DIR)"
	@echo "LIBS = $(LIBS)"
	@echo "Resolved archives:"
	@for a in $(SOC_SW_LIB_ARCHIVES); do echo "  $$a"; done
	@echo "Check memcmp symbol (first matching archive):"
	@nm $(firstword $(filter %/libc.a,$(SOC_SW_LIB_ARCHIVES))) 2>/dev/null | grep -w memcmp || echo "memcmp not found"