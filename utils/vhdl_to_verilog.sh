#!/bin/bash

# === Configuration ===
SRC_DIR="vhdl"
TOP_ENTITY="clock_consumer"
OUT_FILE="${TOP_ENTITY}.v"

# === Collect VHDL file paths in correct order ===
PKG_LIST=($(find "$SRC_DIR" -iname '*_pkg.vhd' | sort))
SRC_LIST=($(find "$SRC_DIR" -iname '*.vhd' ! -iname '*_pkg.vhd' | sort))
ALL_FILES=("${PKG_LIST[@]}" "${SRC_LIST[@]}")

# === Print info ===
echo "📦 Found packages:"
printf "  %s\n" "${PKG_LIST[@]}"
echo "📁 Found VHDL sources:"
printf "  %s\n" "${SRC_LIST[@]}"
echo "🚀 Target top-level entity: $TOP_ENTITY"

# === Construct file list as a space-separated string ===
FILE_ARGS=$(printf "%s " "${ALL_FILES[@]}")

# === Run yosys with GHDL plugin ===
yosys -m ghdl -p "ghdl -fsynopsys -fexplicit $FILE_ARGS -e $TOP_ENTITY; write_verilog $OUT_FILE" \
    && echo "✅ Conversion successful → $OUT_FILE" \
    || echo "❌ Conversion failed"
