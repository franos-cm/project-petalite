#!/bin/bash

. /tools/Xilinx/Vivado/2024.2/settings64.sh

echo vivado -mode tcl -source /dev/null -tclargs "$1"

vivado -mode tcl -tclargs "$1" <<EOF
	start_gui
	open_wave_database [lindex \$argv 0]
	add_wave *

	proc re {} {
		upvar argv fn
		close_sim -force
		open_wave_database [lindex \$fn 0]
		add_wave *
	}
EOF