# Usage: make run tb=some_tb.vhd designs="file1.vhd file2.vhd"

tb_name := $(basename $(notdir $(tb)))
compile_only_name := compile_only
vhdl_files := $(filter %.vhd %.vhdl, $(designs))
sv_files   := $(filter %.v %.sv %.svh, $(designs))

run:
	@echo "Running testbench: $(tb)"
	@echo "Design files: $(designs)"
	@echo "Output folder: $(tb_name)"

	# Clean and recreate output folder
	@rm -rf $(tb_name)
	@mkdir -p $(tb_name)

	# Compile all design files and testbench
	@cd $(tb_name) && xvhdl $(addprefix ../, $(designs)) ../$(tb)

	# Elaborate the testbench (assumes entity == 'tb')
	@cd $(tb_name) && xelab work.tb -s sim_snapshot --debug all

	# Run simulation and dump waveform.vcd
	@cd $(tb_name) && xsim sim_snapshot -tclbatch ../utils/gen_wdb.tcl


wave:
	./utils/open_wdb.sh $(tb_name)/sim_snapshot.wdb


compile:
	@echo "Compiling designs: $(designs)"
	@rm -rf compile_only
	@mkdir -p compile_only

	@if [ ! -z "$(vhdl_files)" ]; then \
		echo "Compiling VHDL: $(vhdl_files)"; \
		cd compile_only && xvhdl $(addprefix ../, $(vhdl_files)); \
	fi

	@if [ ! -z "$(sv_files)" ]; then \
		echo "Compiling SystemVerilog: $(sv_files)"; \
		cd compile_only && xvlog --sv $(addprefix ../, $(sv_files)); \
	fi

	# Completed compilation!

	@cd compile_only && xelab work.top -s sim_snapshot --debug all