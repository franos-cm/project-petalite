import os


def generate_gtkw_savefile(builder, vns, trace_fst):
    from litex.build.sim import gtkwave as gtkw

    dumpfile = os.path.join(
        builder.gateware_dir, "sim.{}".format("fst" if trace_fst else "vcd")
    )
    savefile = os.path.join(builder.gateware_dir, "sim.gtkw")
    soc = builder.soc

    with gtkw.GTKWSave(vns, savefile=savefile, dumpfile=dumpfile) as save:
        save.clocks()
        save.fsm_states(soc)
        if "main_ram" in soc.bus.slaves.keys():
            save.add(
                soc.bus.slaves["main_ram"],
                mappers=[gtkw.wishbone_sorter(), gtkw.wishbone_colorer()],
            )

        if hasattr(soc, "sdrphy"):
            # all dfi signals
            save.add(
                soc.sdrphy.dfi, mappers=[gtkw.dfi_sorter(), gtkw.dfi_in_phase_colorer()]
            )

            # each phase in separate group
            with save.gtkw.group("dfi phaseX", closed=True):
                for i, phase in enumerate(soc.sdrphy.dfi.phases):
                    save.add(
                        phase,
                        group_name="dfi p{}".format(i),
                        mappers=[
                            gtkw.dfi_sorter(phases=False),
                            gtkw.dfi_in_phase_colorer(),
                        ],
                    )

            # only dfi command/data signals
            def dfi_group(name, suffixes):
                save.add(
                    soc.sdrphy.dfi,
                    group_name=name,
                    mappers=[
                        gtkw.regex_filter(gtkw.suffixes2re(suffixes)),
                        gtkw.dfi_sorter(),
                        gtkw.dfi_per_phase_colorer(),
                    ],
                )

            dfi_group("dfi commands", ["cas_n", "ras_n", "we_n"])
            dfi_group("dfi commands", ["wrdata"])
            dfi_group("dfi commands", ["wrdata_mask"])
            dfi_group("dfi commands", ["rddata"])
