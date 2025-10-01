#!/usr/bin/env bash
# program_fpga.sh — program a Xilinx device via Vivado CLI
# Usage:
#   ./program_fpga.sh /path/to/top.bit           # uses device index 0 by default
#   ./program_fpga.sh /path/to/top.bit 1         # choose another device on the JTAG chain
#   ./program_fpga.sh /path/to/top.bit 0 localhost:3121  # custom hw_server URL

set -euo pipefail

if [[ $# -lt 1 ]]; then
  echo "Usage: $0 <bitstream.bit> [device_index=0] [hw_url=localhost:3121]"
  exit 1
fi

BIT="$1"
DEV_INDEX="${2:-0}"
HW_URL="${3:-localhost:3121}"

if ! command -v vivado >/dev/null 2>&1; then
  echo "ERROR: vivado not found in PATH. Did you source settings64.sh?"
  exit 2
fi

if [[ ! -f "$BIT" ]]; then
  echo "ERROR: Bitstream not found: $BIT"
  exit 3
fi

# Make absolute for cleaner logs
if command -v readlink >/dev/null 2>&1; then
  BIT="$(readlink -f "$BIT" || echo "$BIT")"
fi

# Create a temporary Tcl and run it
TCL="$(mktemp /tmp/program_fpga.XXXXXX.tcl)"
cat > "$TCL" <<'TCL'
# Arguments passed from bash via env:
#   env(BIT), env(DEV_INDEX), env(HW_URL)

proc info_msg {msg} { puts "[clock format [clock seconds] -format {%Y-%m-%d %H:%M:%S}] :: $msg" }

info_msg "Opening hardware manager and connecting to $::env(HW_URL)"
open_hw_manager
connect_hw_server -url $::env(HW_URL)

# Open the first discovered target on that server
set targs [get_hw_targets]
if {[llength $targs] == 0} {
  error "No hw targets found on $::env(HW_URL). Is the cable connected and powered?"
}
open_hw_target [lindex $targs 0]

# Pick device by index (default 0)
set devs [get_hw_devices]
if {[llength $devs] == 0} {
  error "No hw devices found on the target."
}
set idx [expr {int($::env(DEV_INDEX))}]
if {$idx < 0 || $idx >= [llength $devs]} {
  error "DEV_INDEX=$idx out of range. Found devices: $devs"
}
set dev [lindex $devs $idx]
current_hw_device $dev
info_msg "Selected device: $dev"

# Program the bit
set bitfile $::env(BIT)
info_msg "Programming bitstream: $bitfile"
set_property PROGRAM.FILE $bitfile [current_hw_device]
program_hw_devices [current_hw_device]
refresh_hw_device [current_hw_device]

# Done
set status [catch {get_property PROGRAM.FILE [current_hw_device]} progfile]
if {!$status} {
  info_msg "Programmed: $progfile"
}
info_msg "DONE."
exit
TCL

# Export vars for Tcl
BIT="$BIT" DEV_INDEX="$DEV_INDEX" HW_URL="$HW_URL" vivado -mode batch -source "$TCL"
rm -f "$TCL"
