#!/usr/bin/env bash

# Automated firmware build flow.
# Steps:
#  1. Activate Python venv (./venv by default or $VENV_DIR if set)
#  2. If builds/soc missing (or FORCE_SOC=1), run SoC build (simulation by default, or board if --board)
#  3. Run firmware.py clean
#  4. Run firmware.py wolfssl-build
#  5. Run firmware.py tpm-build
#  6. Run firmware.py build --fbi

set -euo pipefail

# --------- option parsing ---------
FORCE_WOLFSSL_BUILD=${FORCE_WOLFSSL_BUILD:-0}
FORCE_SOC_BUILD=${FORCE_SOC_BUILD:-0}
FORCE_ALL=${FORCE_ALL:-0}
# Build target selection: default to simulation unless BOARD mode requested
BOARD_BUILD=${BOARD_BUILD:-0}

# Backward compatibility: legacy env FORCE_SOC still respected
if [ "${FORCE_SOC:-0}" = "1" ] && [ "$FORCE_SOC_BUILD" = "0" ]; then
  FORCE_SOC_BUILD=1
fi

usage() {
  cat <<'USAGE'
Usage: ./build.sh [options]

./build.sh --force-all

Options:
  --force-wolfssl-build Force (re)build wolfSSL even if existing library present
  --force-soc-build     Force full SoC rebuild (deletes builds/soc before building)
  --force-all           Shorthand for --force-soc-build and --force-wolfssl-build
  --board               Build SoC for a physical board (no --sim). Default is simulation.
  -h, --help            Show this help

Environment overrides:
  VENV_DIR=<path>       Virtualenv directory (default: ./venv)
  FORCE_SOC_BUILD=1     Force full SoC rebuild (deletes builds/soc)
  FORCE_SOC=1           (deprecated) Same as FORCE_SOC_BUILD=1
  FORCE_WOLFSSL_BUILD=1 Same as --force-wolfssl-build
  FORCE_ALL=1           Same as --force-all
  BOARD_BUILD=1         Same as --board (build for board, not simulation)
USAGE
}

for arg in "$@"; do
  case "$arg" in
  --force-wolfssl-build) FORCE_WOLFSSL_BUILD=1 ;;
  --force-soc-build) FORCE_SOC_BUILD=1 ;;
    --board) BOARD_BUILD=1 ;;
    --force-all) FORCE_WOLFSSL_BUILD=1; FORCE_SOC_BUILD=1; FORCE_ALL=1 ;;
    -h|--help) usage; exit 0 ;;
    *) echo "Unknown option: $arg" >&2; usage; exit 1 ;;
  esac
done

# If FORCE_ALL env set, propagate to individual flags (unless already explicitly set)
if [ "$FORCE_ALL" = "1" ]; then
  FORCE_WOLFSSL_BUILD=1
  FORCE_SOC_BUILD=1
fi

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$REPO_DIR"

VENV_DIR="${VENV_DIR:-$REPO_DIR/venv}"
SOC_BUILD_DIR="$REPO_DIR/builds/soc"
FIRMWARE_HELPER="$REPO_DIR/firmware/firmware.py"
SOC_SCRIPT="$REPO_DIR/soc/petalite.py"

# --------- pretty printing helpers ---------
if command -v tput >/dev/null 2>&1 && [ -n "${TERM:-}" ]; then
  BOLD="$(tput bold)"; RED="$(tput setaf 1)"; GREEN="$(tput setaf 2)"; YELLOW="$(tput setaf 3)"; BLUE="$(tput setaf 4)"; RESET="$(tput sgr0)"
else
  BOLD=""; RED=""; GREEN=""; YELLOW=""; BLUE=""; RESET=""
fi

STEP_NO=0
step() { STEP_NO=$((STEP_NO+1)); echo -e "${BLUE}${BOLD}[STEP $STEP_NO]${RESET} $*"; }
info() { echo -e "${YELLOW}[INFO]${RESET} $*"; }
warn() { echo -e "${YELLOW}[WARN]${RESET} $*"; }
ok() { echo -e "${GREEN}[OK]${RESET} $*"; }
fail() { echo -e "${RED}[FAIL]${RESET} $*" >&2; }

elapsed() { # usage: elapsed <start_epoch> <label>
  local end now label; now=$(date +%s); label="$2"; echo "$(printf '%s (%.1fs)' "$label" "$(echo "$now - $1" | bc -l)")"; }

time_start=$(date +%s)

# --------- 1. Activate venv (only if not already the active one) ---------
step "Activating Python virtual environment (if needed)"
if [ -d "$VENV_DIR" ]; then
  if [ -n "${VIRTUAL_ENV:-}" ]; then
    if [ "$VIRTUAL_ENV" = "$VENV_DIR" ]; then
      ok "Target venv already active ($VIRTUAL_ENV)"
    else
      warn "Different virtual environment currently active ($VIRTUAL_ENV); switching to $VENV_DIR"
      # shellcheck source=/dev/null
      source "$VENV_DIR/bin/activate"
      ok "Switched to venv at $VENV_DIR (python: $(command -v python))"
    fi
  else
    # shellcheck source=/dev/null
    source "$VENV_DIR/bin/activate"
    ok "Activated venv at $VENV_DIR (python: $(command -v python))"
  fi
else
  info "No venv at $VENV_DIR (continuing with system python: $(command -v python || echo 'none'))"
fi

# Sanity check scripts exist
[ -x "$FIRMWARE_HELPER" ] || chmod +x "$FIRMWARE_HELPER" 2>/dev/null || true

if [ ! -f "$FIRMWARE_HELPER" ]; then
  fail "Missing firmware helper at $FIRMWARE_HELPER"; exit 1
fi
if [ ! -f "$SOC_SCRIPT" ]; then
  fail "Missing SoC build script at $SOC_SCRIPT"; exit 1
fi

# --------- 2. Pre-build cleanup (must happen before SoC rebuild) ---------
step "Pre-build cleanup phase"
start=$(date +%s)
if [ "$FORCE_WOLFSSL_BUILD" = "1" ]; then
  info "Forcing wolfSSL rebuild: performing full clean (firmware + wolfSSL artifacts)"
  python "$FIRMWARE_HELPER" clean || { fail "Clean failed"; exit 1; }
else
  info "Skipping full clean (wolfSSL cached). Cleaning TPM objects and firmware artifacts only"
  python "$FIRMWARE_HELPER" tpm-clean || true
  python "$FIRMWARE_HELPER" firmware-clean || true
fi
ok "Cleanup phase done $(elapsed $start 'time')"

# --------- 3. Build SoC if needed (after cleanup) ---------
step "Checking SoC build directory"
if [ ! -d "$SOC_BUILD_DIR" ] || [ "${FORCE_SOC_BUILD:-0}" = "1" ]; then
  if [ "${FORCE_SOC_BUILD:-0}" = "1" ] && [ -d "$SOC_BUILD_DIR" ]; then
    info "--force-soc-build: removing existing $SOC_BUILD_DIR for a clean rebuild"
    rm -rf "$SOC_BUILD_DIR"
  fi
  if [ "$BOARD_BUILD" = "1" ]; then
    info "SoC build dir missing or force flag set; building LiteX SoC for BOARD (no --sim)"
  else
    info "SoC build dir missing or force flag set; building LiteX SoC for SIMULATION"
  fi
  start=$(date +%s)
  set -x
  if [ "$BOARD_BUILD" = "1" ]; then
    python "$SOC_SCRIPT" \
      --build-dir=builds/soc
  else
    python "$SOC_SCRIPT" \
      --sim \
      --io-json=soc/data/io_sim.json \
      --build-dir=builds/soc
  fi
  set +x
  ok "SoC build complete $(elapsed $start 'time')"
else
  ok "Found existing SoC build at $SOC_BUILD_DIR (skip). Use --force-soc-build or FORCE_SOC_BUILD=1 to rebuild."
fi

# --------- 4. wolfSSL build ---------
step "wolfSSL build"
WOLFSSL_LIB_CHECK="$SOC_BUILD_DIR/software/wolfssl/lib/libwolfssl.a"
if [ "$FORCE_WOLFSSL_BUILD" = "1" ]; then
  info "--force-wolfssl-build: rebuilding wolfSSL"
  start=$(date +%s)
  python "$FIRMWARE_HELPER" wolfssl-clean || true
  python "$FIRMWARE_HELPER" wolfssl-build
  ok "wolfSSL force build done $(elapsed $start 'time')"
else
  if [ -f "$WOLFSSL_LIB_CHECK" ]; then
    ok "wolfSSL library present; skipping rebuild (use --force-wolfssl-build to override)"
  else
    info "wolfSSL library missing; building"
    start=$(date +%s)
    python "$FIRMWARE_HELPER" wolfssl-build
    ok "wolfSSL build done $(elapsed $start 'time')"
  fi
fi

# --------- 5. TPM static library build ---------
step "Building TPM + platform static library"
start=$(date +%s)
python "$FIRMWARE_HELPER" tpm-build
ok "TPM build done $(elapsed $start 'time')"

# --------- 6. Firmware final build (with .fbi) ---------
step "Building firmware image (+ .fbi)"
start=$(date +%s)
python "$FIRMWARE_HELPER" build --fbi
ok "Firmware build complete $(elapsed $start 'time')"

echo
ok "All steps finished successfully in $(elapsed $time_start 'total time')"
echo "Artifacts (if build succeeded) should be under: builds/ (e.g. builds/firmware/firmware.bin, builds/firmware/firmware.fbi)"
