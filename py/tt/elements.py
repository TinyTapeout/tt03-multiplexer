#!/usr/bin/env python3

#
# Tiny Tapeout
#
# Layout elements
#
# Copyright (c) 2023 Sylvain Munaut <tnt@246tNt.com>
# SPDX-License-Identifier: Apache-2.0
#

from collections import namedtuple

try:
	import svgwrite as svg
except ModuleNotFoundError:
	pass

from .utils import *


__all__ = [
	'LayoutElement',
	'LayoutElementPlacement',
	'MacroInstance',
	'PowerSwitch',
	'AnalogSwitch',
	'Block',
	'Mux',
	'Branch',
	'Controller',
	'Top',
	'Die',
]


LayoutElementPlacement = namedtuple('LayoutElementPlacement', 'elem pos orient name')

MacroInstance = namedtuple('MacroInstance', 'inst_name mod_name pos orient elem')


class LayoutElement:

	mod_name = None

	color = None

	def __init__(self, layout, width, height, parent=None):
		self.layout = layout
		self.width  = width
		self.height = height
		self.parent = parent
		self.children = {}

	def add_child(self, child, pos, orient='N', name=None):
		# Set parent
		child.parent = self

		# Add to children
		self.children[child] = LayoutElementPlacement(child, pos, orient, name)

	def get_sub_macros(self):
		# Scan children and returned named ones
		rv = []

		for cp in self.children.values():
			# Only named ones
			if cp.name is None:
				continue

			# Get sub macro from the child
			sml = cp.elem.get_sub_macros()

			# If we're not a leaf, we need to transform the return list
			# with whatever transform is applied to that child
			for sm in sml:
				if cp.orient == 'N':
					pos    = cp.pos + sm.pos
					orient = sm.orient

				elif cp.orient == 'S':
					pos = cp.pos + Point(
						cp.elem.width  - (sm.pos.x + sm.elem.width),
						cp.elem.height - (sm.pos.y + sm.elem.height),
					)
					orient = {
						'N':  'S',
						'FS': 'FN',
					}[sm.orient]

				elif cp.orient == 'FN':
					pos = cp.pos + Point(
						cp.elem.width - (sm.pos.x + sm.elem.width),
						sm.pos.y
					)
					orient = {
						'N':  'FN',
						'FS': 'S',
					}[sm.orient]

				elif cp.orient == 'FS':
					pos = cp.pos + Point(
						sm.pos.x,
						cp.elem.height - (sm.pos.y + sm.elem.height),
					)
					orient = {
						'N':  'FS',
						'FS': 'N',
					}[sm.orient]


				else:
					raise RuntimeError('Not implemented')

				rv.append(MacroInstance(
					cp.name + '.' + sm.inst_name,
					sm.mod_name,
					pos,
					orient,
					sm.elem
				))

			# That child is a leaf, so just return it
			else:
				if cp.elem.mod_name is not None:
					rv.append( MacroInstance(cp.name, cp.elem.mod_name, cp.pos, cp.orient, cp.elem) )

		return rv


	def _render(self, dwg):
		# Draw self
		if self.color is not None:
			dwg.add(svg.shapes.Rect(
				( 0, 0 ),
				( self.width, self.height ),
				fill = self.color,
			))

		# Recurse
		for cp in self.children.values():
			# Create group and add to drawing
			cg = svg.container.Group()
			dwg.add(cg)

			# Apply transform placing it in design
			cg.translate(cp.pos[0], cp.pos[1])

			# Apply orientation transform
			if cp.orient == 'N':
				# Nothing to do
				pass

			elif cp.orient == 'S':
				# South
				cg.translate(cp.elem.width, cp.elem.height)
				cg.scale(-1, -1)

			elif cp.orient == 'FS':
				# Flipped South
				cg.translate(0, cp.elem.height)
				cg.scale(1, -1)

			elif cp.orient == 'FN':
				# Flipped North
				cg.translate(cp.elem.width, 0)
				cg.scale(-1, 1)

			else:
				raise RuntimeError('Unsupported orientation')

			# Render
			cp.elem._render(cg)

	def draw_to_svg(self, fn):
		# Create drawing
		dwg = svg.Drawing(
			size = (
				self.layout.cfg.pdk.die.width  / 1e3,
				self.layout.cfg.pdk.die.height / 1e3,
			),
		)

		# Group for invert-y and scaling
		grp = svg.container.Group()
		grp.scale(1e-3, 1e-3)
		grp.translate(0, self.layout.cfg.pdk.die.height)
		grp.scale(1, -1)
		dwg.add(grp)

		# Draw this
		self._render(grp)

		# Save result
		dwg.write(open(fn, 'w'))


class PowerSwitch(LayoutElement):

	color = 'mediumvioletred'

	def __init__(self, layout, mh, width, mod_name):
		# Height
		height = (
			mh * layout.glb.block.height +
			(mh - 1) * layout.glb.margin.y
		)

		# Set mod_name
		self.mod_name = mod_name

		# Super
		super().__init__(
			layout,
			width,
			height,
		)


class VddPowerSwitch(PowerSwitch):

	def __init__(self, layout, mh):
		super().__init__(
			layout,
			mh,
			layout.glb.pg_vdd.width,
			f'tt_pg_1v8_{mh:d}'
		)


class VaaPowerSwitch(PowerSwitch):

	def __init__(self, layout, mh):
		super().__init__(
			layout,
			mh,
			layout.glb.pg_vaa.width,
			f'tt_pg_3v3_{mh:d}'
		)


class AnalogSwitch(LayoutElement):

	color = 'green'

	def __init__(self, layout):
		# Width / Height
		width  = 18400
		height = 21760

		# Set mod_name
		self.mod_name = f'tt_asw_3v3'

		# Super
		super().__init__(
			layout,
			width,
			height,
		)


class Block(LayoutElement):

	def __init__(self, layout, mod_name=None, mw=1, mh=1, pg_vdd=False, pg_vaa=False, analog=False):

		# Save options
		self.pg_vdd = pg_vdd
		self.pg_vaa = pg_vaa
		self.analog = analog

		# Compute module actual width / height
		width = (
			mw * layout.glb.block.width +
			(mw - 1) * layout.glb.margin.x
		)

		height = (
			mh * layout.glb.block.height +
			(mh // 4) * (layout.glb.mux.height + layout.glb.margin.y) +
			(mh - 1) * layout.glb.margin.y
		)

		# Power gating offset
		if pg_vdd:
			width -= layout.glb.pg_vdd.offset

		if pg_vaa:
			width -= layout.glb.pg_vaa.offset

		# Set module name
		self.mod_name = mod_name

		# Super
		super().__init__(
			layout,
			width,
			height,
		)

	def _render(self, dwg):
		# Super call
		super()._render(dwg)

		# Power gating offset
		pin_ofs = 0
		if self.pg_vdd:
			pin_ofs += self.layout.glb.pg_vdd.offset
		if self.pg_vaa:
			pin_ofs += self.layout.glb.pg_vaa.offset

		# Render pins
		for pn, pp in self.layout.ply_block.items():
			# Apply offset
			pp -= pin_ofs

			# Draw pin
			dwg.add(svg.shapes.Rect(
				( pp-150, self.height-1000 ),
				( 300,    1000),
				fill = 'black',
			))

		if not self.analog:
			return

		for pn, pp in self.layout.ply_block_analog.items():
			# Apply offset
			pp -= pin_ofs

			# Draw pin
			dwg.add(svg.shapes.Rect(
				( pp-300, 0),
				( 600,    1000),
				fill = 'black',
			))

	@property
	def color(self):
		return 'orange' if self.analog else 'crimson'


class Mux(LayoutElement):

	mod_name = 'tt_mux'

	color = 'mediumslateblue'

	def __init__(self, layout):
		# Super
		super().__init__(
			layout,
			layout.glb.mux.width,
			layout.glb.mux.height,
		)

	def _render(self, dwg):
		# Super call
		super()._render(dwg)

		# Render pins
			# User blocks bottom
		for pn, pp in self.layout.ply_mux_bot.items():
			dwg.add(svg.shapes.Rect(
				( pp-150, 0 ),
				( 300,    1000),
				fill = 'black',
			))

			# User blocks top
		for pn, pp in self.layout.ply_mux_top.items():
			dwg.add(svg.shapes.Rect(
				( pp-150, self.height-1000 ),
				( 300,    1000),
				fill = 'black',
			))

			# V-Spine connection
		for pn, pp in self.layout.ply_mux_port.items():
			dwg.add(svg.shapes.Rect(
				( self.width-1000, pp-150 ),
				( 1000, 300),
				fill = 'black',
			))


class Branch(LayoutElement):

	def __init__(self, layout, placer, mux_id):
		# Super
		super().__init__(
			layout,
			layout.glb.branch.width,
			layout.glb.branch.height,
		)

		# Create Mux
		self.mux = mux = Mux(layout)

		mux_x = 0
		mux_y = layout.glb.block.height + layout.glb.margin.y

		self.add_child(mux, Point(0, mux_y), 'N', name='mux_I')

		# Create Blocks
		for blk_id in range(layout.cfg.tt.grid.x):
			# Is there anything here ?
			mp = placer.lgrid.get( (mux_id, blk_id) )
			if mp is None:
				continue

			# Block instance
			block = Block(layout,
				mod_name = f'tt_um_{mp.name:s}',
				mw = mp.width,
				mh = mp.height,
				pg_vdd = mp.pg_vdd,
				pg_vaa = mp.pg_vaa,
				analog = mp.analog,
			)

			# Block lower left corner position
			blk_x = ((self.layout.cfg.tt.grid.x // 2) - (blk_id >> 1) - 1) * layout.glb.block.pitch

			if blk_id & 1:
				blk_y = layout.glb.block.height - block.height
			else:
				blk_y = self.height - layout.glb.block.height

			# Name prefix
			name_pfx = f'block[{blk_id:d}].um_I.block_{mux_id:d}_{blk_id:d}.'

			# Analog ?
			if mp.analog:
				for k, v in mp.analog.items():
					# Instance
					ana_sw = AnalogSwitch(layout)

					# Position
					if blk_id & 1:
						pos_y = blk_y - (layout.glb.margin.y + ana_sw.height)
						orient = 'N'
					else:
						pos_y = blk_y + (layout.glb.margin.y + block.height)
						orient = 'FS'

					pos_x = blk_x + layout.ply_block_analog[f'ua[{k:d}]'] - ana_sw.width // 2

					# Add as child
					self.add_child(ana_sw, Point(pos_x, pos_y), orient, name=name_pfx+f'tt_asw_{k:d}_I')

			# Power gating
			if mp.pg_vdd:
				# Power Switch instance
				vdd_sw = VddPowerSwitch(layout, mh=mp.height)

				# Add Power Switch as child
				self.add_child(vdd_sw, Point(blk_x, blk_y), 'N' if (blk_id & 1) else 'FS', name=name_pfx+'tt_pg_vdd_I')

				# Shift the block
				blk_x += layout.glb.pg_vdd.offset

			if mp.pg_vaa:
				# Power Switch instance
				vaa_sw = VaaPowerSwitch(layout, mh=mp.height)

				# Add Power Switch as child
				self.add_child(vaa_sw, Point(blk_x, blk_y), 'N' if (blk_id & 1) else 'FS', name=name_pfx+'tt_pg_vaa_I')

				# Shift the block
				blk_x += layout.glb.pg_vaa.offset

			# Add Block as child
			self.add_child(block, Point(blk_x, blk_y), 'N' if (blk_id & 1) else 'FS', name=name_pfx+'tt_um_I')


class Controller(LayoutElement):

	mod_name = 'tt_ctrl'

	color = 'yellowgreen'

	def __init__(self, layout):
		# Super
		width  = layout.glb.ctrl.width
		height = layout.glb.ctrl.height

		super().__init__(
			layout,
			width,
			height,
		)

	def _render(self, dwg):
		# Super call
		super()._render(dwg)

		# Render pins
			# Vspine connections
		for pn, pp in self.layout.ply_ctrl_vspine.items():
				# Top
			dwg.add(svg.shapes.Rect(
				( pp-150, self.height-1000 ),
				( 300,    1000),
				fill = 'black',
			))

				# Bottom
			dwg.add(svg.shapes.Rect(
				( pp-150, 0 ),
				( 300,    1000),
				fill = 'black',
			))

			# IO top
		for pn, pp in self.layout.ply_ctrl_io_top.items():
			dwg.add(svg.shapes.Rect(
				( pp-150, self.height-1000 ),
				( 300,    1000),
				fill = 'black',
			))

			# IO bottom
		for pn, pp in self.layout.ply_ctrl_io_bot.items():
			dwg.add(svg.shapes.Rect(
				( pp-150, 0 ),
				( 300,    1000),
				fill = 'black',
			))


class Logo(LayoutElement):

	def __init__(self, layout, variant):
		# Set mod_name
		self.mod_name = f'tt_logo_{variant:s}'

		# Super
		super().__init__(
			layout,
			layout.glb.logo.width,
			layout.glb.logo.height,
		)


class Top(LayoutElement):
	"""
	Top level grid aligned area containing all TT elements
	"""

	color = 'lightslategray'

	def __init__(self, layout, placer):
		# Super
		super().__init__(
			layout,
			layout.glb.top.width,
			layout.glb.top.height,
		)

		# Create Branches
		self.branches = []

		for mux_id in range(0, layout.cfg.tt.grid.y):
			# Check if mux exists
			if not layout.mux_exists(mux_id):
				continue

			# Quadrants
			my = layout.cfg.tt.grid.y // 4

			if (mux_id & 3) == 0:
				# Lower Left
				b_x = 0
				b_y = (my - (mux_id >> 2) - 1) * layout.glb.branch.pitch
				ori = 'N'

			elif (mux_id & 3) == 1:
				# Upper Left
				b_x = 0
				b_y = (my + (mux_id >> 2)) * layout.glb.branch.pitch
				ori = 'FS'

			elif (mux_id & 3) == 2:
				# Lower Right
				b_x = self.width - layout.glb.branch.width
				b_y = (my - (mux_id >> 2) - 1) * layout.glb.branch.pitch
				ori = 'FN'

			elif (mux_id & 3) == 3:
				# Upper Right
				b_x = self.width - layout.glb.branch.width
				b_y = (my + (mux_id >> 2)) * layout.glb.branch.pitch
				ori = 'S'

			branch = Branch(layout, placer, mux_id)
			self.branches.append(branch)

			self.add_child(branch, Point(b_x, b_y), ori, name=f'branch[{mux_id:d}].check_mask')

		# Create Controller
		self.ctrl = ctrl = Controller(layout)

		ctrl_x = layout.glb.branch.width + layout.glb.margin.x
		ctrl_y = (layout.cfg.tt.grid.y // 4) * layout.glb.branch.pitch - \
			( layout.glb.mux.height + layout.glb.margin.y )

		self.add_child(ctrl, Point(ctrl_x, ctrl_y), 'N', name='ctrl_I')

		# Add Logo & Shuttle ID
		logo_top = Logo(layout, 'top')
		self.add_child(logo_top, Point(layout.glb.logo.pos_x, layout.glb.logo.top_pos_y), 'N', name='logo_top_I')

		logo_bottom = Logo(layout, 'bottom')
		self.add_child(logo_bottom, Point(layout.glb.logo.pos_x, layout.glb.logo.bottom_pos_y), 'N', name='logo_bottom_I')


class Die(LayoutElement):
	"""
	Full Die User Area Element
	"""

	color = 'silver'

	def __init__(self, layout, placer):
		# Super
		super().__init__(
			layout,
			layout.cfg.pdk.die.width,
			layout.cfg.pdk.die.height,
		)

		# Add 'Top'
		self.top = top = Top(layout, placer)

		top_x = layout.glb.top.pos_x
		top_y = layout.glb.top.pos_y

		self.add_child(top, Point(top_x, top_y), 'N', name='top_I')
