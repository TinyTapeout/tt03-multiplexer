#!/usr/bin/env python3

#
# OpenLane2 build script to harden the tt_top macro inside
# the openframe_project_wrapper
#
# Copyright (c) 2023 Sylvain Munaut <tnt@246tNt.com>
# SPDX-License-Identifier: Apache-2.0
#

import argparse
import json
import math
import os
import sys

from typing import List, Type

from openlane.flows.misc import OpenInKLayout
from openlane.flows.sequential import SequentialFlow
from openlane.steps.odb import OdbpyStep
from openlane.steps import (
	Step,
	Yosys,
	OpenROAD,
	Magic,
	Misc,
	KLayout,
	Odb,
	Netgen,
	Checker,
)

sys.path.append('../../py')
import tt


class CustomPower(OdbpyStep):

	id = "TT.Top.CustomPower"
	name = "Custom Power connections for TT Top Level"

	def get_script_path(self):
		return os.path.join(
			os.path.dirname(__file__),
			"odb_power.py"
		)


class CustomRoute(OdbpyStep):

	id = "TT.Top.CustomRoute"
	name = "Custom Pre-Routing for TT Top Level"

	def get_script_path(self):
		return os.path.join(
			os.path.dirname(__file__),
			"odb_route.py"
		)


class TopFlow(SequentialFlow):

	Steps: List[Type[Step]] = [
		Yosys.JsonHeader,
		Yosys.Synthesis,
		Checker.YosysUnmappedCells,
		Checker.YosysSynthChecks,
		OpenROAD.Floorplan,
		Odb.ApplyDEFTemplate,
		Odb.ManualMacroPlacement,
		CustomPower,
		OpenROAD.GeneratePDN,
		OpenROAD.GlobalPlacement,
		OpenROAD.DetailedPlacement,
		CustomRoute,
		OpenROAD.GlobalRouting,
		OpenROAD.DetailedRouting,
		Checker.TrDRC,
		Odb.ReportDisconnectedPins,
		Checker.DisconnectedPins,
		Odb.ReportWireLength,
		Checker.WireLength,
		OpenROAD.RCX,
		OpenROAD.STAPostPNR,
		OpenROAD.IRDropReport,
		Magic.StreamOut,
		KLayout.StreamOut,
		KLayout.XOR,
		Checker.XOR,
		Magic.DRC,
		Checker.MagicDRC,
		Magic.SpiceExtraction,
		Checker.IllegalOverlap,
		Netgen.LVS,
		Checker.LVS,
	]


if __name__ == '__main__':
	# Argument processing
	parser = argparse.ArgumentParser(formatter_class=argparse.ArgumentDefaultsHelpFormatter)
	parser.add_argument("--open-in-klayout", action="store_true", help="Open last run in KLayout")
	parser.add_argument("--skip-xor-checks", action="store_true", help="Skips XOR checks")

	args = parser.parse_args()
	config = vars(args)

	if config['skip_xor_checks']:
		TopFlow.Steps.remove(KLayout.XOR)
		TopFlow.Steps.remove(Checker.XOR)

	# Get PDK root out of environment
	PDK_ROOT = os.getenv('PDK_ROOT')

	# Load TinyTapeout
	tti = tt.TinyTapeout()

	# Generate macros
	macros = { }
	user_modules = []

	for m in tti.die.get_sub_macros():
		if m.mod_name not in macros:
			macros[m.mod_name] = {
				'gds': [ f'dir::gds/{m.mod_name:s}.gds', ],
				'lef': [ f'dir::lef/{m.mod_name:s}.lef', ],
				'instances': { }
			}
			if m.mod_name.startswith('tt_um_'):
				user_modules.append(m.mod_name)
			elif m.mod_name.startswith('tt_pg_') or m.mod_name.startswith('tt_asw_') or m.mod_name.startswith('tt_logo_'):
				macros[m.mod_name].update({
					'nl': f'dir::verilog/{m.mod_name:s}.v',
				})
			else:
				macros[m.mod_name].update({
					'nl':   f'dir::verilog/{m.mod_name:s}.v',
					'spef': {
						"min_*": [ f'dir::spef/{m.mod_name:s}.min.spef' ],
						"nom_*": [ f'dir::spef/{m.mod_name:s}.nom.spef' ],
						"max_*": [ f'dir::spef/{m.mod_name:s}.max.spef' ],
					},
				})

		macros[m.mod_name]['instances'][m.inst_name] = {
			"location": [ m.pos.x / 1000, m.pos.y / 1000 ],
			"orientation": m.orient,
		}

	# Generate dummy for all user modules
	mod_tpl = open('tt_um_tpl.v', 'r').read()
	open('verilog/tt_um_all.v', 'w').write('\n'.join([
		mod_tpl.format(mod_name=m)
			for m in user_modules
	]))

	# Custom config
	flow_cfg = {
		# Main design properties
		"DESIGN_NAME"    : "openframe_project_wrapper",
		"DESIGN_IS_CORE" : False,

		# Sources
		"VERILOG_FILES": [
			"dir::openframe_project_wrapper.v",
			"dir::../../rtl/tt_top.v",
			"dir::../../rtl/tt_gpio.v",
			"dir::../../rtl/tt_user_module.v",
		],

		"VERILOG_POWER_DEFINE": "USE_POWER_PINS",

		# Macros
		"MACROS": macros,
		"EXTRA_VERILOG_MODELS": [
			"dir::verilog/tt_um_all.v",
		],

		# Constraints
		"SIGNOFF_SDC_FILE" : "signoff.sdc",

		# Synthesis
		"SYNTH_ELABORATE_ONLY"      : True,
		"SYNTH_USE_PG_PINS_DEFINES" : "USE_POWER_PINS",

		"SYNTH_EXCLUSION_CELL_LIST" : "dir::no_synth_cells.txt",
		"PNR_EXCLUSION_CELL_LIST"   : "dir::no_drc_cells.txt",
		"DRC_EXCLUDE_CELL_LIST"     : "dir::no_drc_cells.txt",

		"QUIT_ON_SYNTH_CHECKS"      : False,

		# Floorplanning
		"DIE_AREA"  : [  0.00,  0.00, 3166.63, 4766.63 ],
		"CORE_AREA" : [ 85.00, 85.00, 3081.63, 4681.63 ],
		"FP_SIZING" : "absolute",
		"FP_DEF_TEMPLATE" : "dir::openframe_project_wrapper.def",
		"FP_TEMPLATE_COPY_POWER_PINS" : True,

		# PDN
		"VDD_NETS": [ "vdpwr", "vapwr" ],
		"GND_NETS": [ "vgnd",  "vgnd"  ],

		"PDN_CFG": "dir::pdn.tcl",

		"PDN_CONNECT_MACROS_TO_GRID"    : False,
		"PDN_ENABLE_GLOBAL_CONNECTIONS" : False,

		"FP_PDN_CORE_RING"          : True,
		"FP_PDN_CORE_RING_VWIDTH"   : 25,
		"FP_PDN_CORE_RING_HWIDTH"   : 25,
		"FP_PDN_CORE_RING_VOFFSET"  :  0,
		"FP_PDN_CORE_RING_HOFFSET"  :  0,
		"FP_PDN_CORE_RING_VSPACING" :  2.0,
		"FP_PDN_CORE_RING_HSPACING" :  2.0,

		# Routing
		"GRT_ALLOW_CONGESTION"  : True,
		"GRT_REPAIR_ANTENNAS"   : False,
		"GRT_LAYER_ADJUSTMENTS" : [1, 0.95, 0.95, 0, 0, 0],
		"RT_MAX_LAYER"          : "met4",

		# Magic stream
		"MAGIC_ZEROIZE_ORIGIN" : False,

		# DRC
		"MAGIC_DRC_USE_GDS": True,

		# LVS
		"MAGIC_DEF_LABELS" : False,
		"MAGIC_EXT_SHORT_RESISTOR" : True, # Fixes LVS failures when more than two pins are connected to the same net
		"LVS_FLATTEN_CELLS": ["tt_logo_top", "tt_logo_bottom"],
	}

	# Update PDN config
	pdn_width   =  8.75
	pdn_spacing =  2.25
	pdn_pitch   = tti.layout.glb.branch.pitch / 5000
	pdn_offset  = (
		tti.layout.glb.top.pos_y +
		tti.layout.glb.branch.pitch // 10 -
		tti.layout.glb.margin.y // 2
	) / 1000
	pdn_offset -= (pdn_spacing + pdn_width)

	sh = tti.cfg.pdk.site.height / 1000
	if 'CORE_AREA' in flow_cfg:
		pdn_offset -= math.ceil(flow_cfg['CORE_AREA'][1] / sh) * sh
	else:
		pdn_offset -= sh * flow_cfg.get('BOTTOM_MARGIN_MULT', 4)

	while pdn_offset > (pdn_pitch * 1.1):
		pdn_offset -= pdn_pitch

	def pdn_align(x):
		grid = 0.005
		return int(x / grid) * grid

	flow_cfg.update({
		"FP_PDN_HWIDTH"  : pdn_align(pdn_width),
		"FP_PDN_HSPACING": pdn_align(pdn_spacing),
		"FP_PDN_HPITCH"  : pdn_align(pdn_pitch),
		"FP_PDN_HOFFSET" : pdn_align(pdn_offset),
	})

	# Run flow
	flow_kls = OpenInKLayout if args.open_in_klayout else TopFlow
	flow = flow_kls(
		flow_cfg,
		design_dir = ".",
		pdk_root   = PDK_ROOT,
		pdk        = "sky130A",
	)

	flow.start(last_run = args.open_in_klayout)
