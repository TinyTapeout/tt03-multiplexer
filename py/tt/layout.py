#!/usr/bin/env python3

#
# Tiny Tapeout
#
# Layout Engine
#
# Copyright (c) 2023 Sylvain Munaut <tnt@246tNt.com>
# SPDX-License-Identifier: Apache-2.0
#

import math

from .utils import *


__all__ = [ 'Layout' ]


class Layout:

	def __init__(self, cfg):
		# Save config
		self.cfg = cfg

		# Sub-layouts
		self.global_layout()
		self.user_analog_layout()
		self.userif_layout()
		self.hspine_layout()
		self.vspine_layout()
		self.ctrl_layout()
		self.analog_layout()

	def _align(self, v, layer, dir_, ceil=False):
		# Grab config data for tracks / sites
		tp = self.cfg.pdk.tracks[layer][dir_].pitch
		s  = {
			'x': self.cfg.pdk.site.width,
			'y': self.cfg.pdk.site.height,
		}[dir_]

		# Align to LCM
		a = math.lcm(tp, s)

		# Do alignement
		if ceil:
			v += a - 1

		return int(v // a) * a

	def _align_x(self, x, ceil=False):
		return self._align(x, self.cfg.tt.spine.vlayer, 'x')

	def _align_y(self, y, ceil=False):
		return self._align(y, self.cfg.tt.spine.hlayer, 'y')

	def global_layout(self):
		# Checks
		if self.cfg.tt.grid.x % 4:
			raise RuntimeError("Grid X must be divisible by 4")

		if self.cfg.tt.grid.y % 2:
			raise RuntimeError("Grid Y must be even")

		# Main object
		self.glb = glb = ConfigNode()

		glb.margin = ConfigNode()
		glb.top    = ConfigNode()
		glb.branch = ConfigNode()
		glb.block  = ConfigNode()
		glb.mux    = ConfigNode()
		glb.ctrl   = ConfigNode()
		glb.pg_vdd = ConfigNode()
		glb.pg_vaa = ConfigNode()
		glb.logo   = ConfigNode()

		# Size of the various busses
		self.vspine = ConfigNode({
			'ow': self.cfg.tt.uio.o + self.cfg.tt.uio.io * 2 + 2,
			'iw': self.cfg.tt.uio.i + self.cfg.tt.uio.io     + 9 + 1 + 2,
		})
		self.user = ConfigNode({
			'ow': self.cfg.tt.uio.o + self.cfg.tt.uio.io * 2,
			'iw': self.cfg.tt.uio.i + self.cfg.tt.uio.io,
		})

		# Margins
		glb.margin.x = self.cfg.tt.margin.x * self.cfg.pdk.site.width
		glb.margin.y = self.cfg.tt.margin.y * self.cfg.pdk.site.height

			# We actually need the Y margin to be aligned to keep everything
			# on the grid
		glb.margin.y = self._align_y(glb.margin.y, ceil=True)

		# Horizontal layout
			# Total available space
		avail_width  = self.cfg.pdk.die.width
		avail_width -= self._align_x(self.cfg.pdk.die.margin.left, ceil=True)
		avail_width -= self.cfg.pdk.die.margin.right

			# Reserve space for Spine tracks and IO pad tracks
			# (we keep those tracks twice as far as they strictly need
			#  to be to decrease mutual capacitance)
		vti = self.cfg.pdk.tracks[self.cfg.tt.spine.vlayer]

		vspine_tracks = self.vspine.iw + self.vspine.ow
		iopads_tracks = self.cfg.tt.uio.o + self.cfg.tt.uio.i + 3 * self.cfg.tt.uio.io + 2

		rsvd_width = 2 * vti.x.pitch * (vspine_tracks + iopads_tracks)
		rsvd_width = self._align_x(rsvd_width, ceil=True)

			# Remaining size is for the blocks and margin
		tmp_width = self._align_x((avail_width - rsvd_width) // self.cfg.tt.grid.x)

			# Final X dimensions
		glb.block.width  = tmp_width - glb.margin.x
		glb.block.pitch  = tmp_width
		glb.mux.width    = tmp_width * (self.cfg.tt.grid.x // 2) - glb.margin.x
		glb.branch.width = glb.mux.width
		glb.ctrl.width   = rsvd_width
		glb.top.width    = rsvd_width + 2 * (glb.mux.width + glb.margin.x)

			# Final position
		glb.top.pos_x = self._align_x((self.cfg.pdk.die.width - glb.top.width) // 2)

		# Vertical layout
			# Total available space
		avail_height  = self.cfg.pdk.die.height
		avail_height -= self._align_y(self.cfg.pdk.die.margin.bottom, ceil=True)
		avail_height -= self.cfg.pdk.die.margin.top

			# Divide up assuming blocks are twice as high
			# as the row-mux
		HM_MUX = 1
		HM_BLK = 2

		tmp_height = avail_height // (self.cfg.tt.grid.y // 2)
		tmp_height = tmp_height // (2 * HM_BLK + HM_MUX)
		tmp_height = self._align_y(tmp_height)

			# Final dimensions
		glb.block.height  = tmp_height * HM_BLK - glb.margin.y
		glb.mux.height    = tmp_height * HM_MUX - glb.margin.y
		glb.branch.pitch  = tmp_height * (2 * HM_BLK + HM_MUX)
		glb.branch.height = glb.branch.pitch - glb.margin.y
		glb.ctrl.height   = glb.mux.height * 2 + glb.margin.y
		glb.top.height    = glb.branch.pitch * (self.cfg.tt.grid.y // 2) - glb.margin.y

			# Final position
		glb.top.pos_y = self._align_y((self.cfg.pdk.die.height - glb.top.height) // 2)

			# Check mux is high enough for horizontal spine
		hspine_tracks = self.user.iw + self.user.ow + 6 + 1 + 3

		hti = self.cfg.pdk.tracks[self.cfg.tt.spine.hlayer]
		if glb.mux.height < (hspine_tracks * hti.y.pitch):
			raise RuntimeError("Mux too small for Horizontal Spine")

		# Power gates
		glb.pg_vdd.width  = self.cfg.pdk.pwrgate.vdd.width
		glb.pg_vdd.offset = self._align_x(glb.pg_vdd.width, ceil=True) + glb.margin.x

		glb.pg_vaa.width  = self.cfg.pdk.pwrgate.vaa.width
		glb.pg_vaa.offset = self._align_x(glb.pg_vaa.width, ceil=True) + glb.margin.x

		# Logo & Shuttle ID
		glb.logo.width        = self.cfg.tt.logo.size
		glb.logo.height       = self.cfg.tt.logo.size
		glb.logo.pos_x        = (glb.top.width - glb.logo.width) // 2
		glb.logo.top_pos_y    = glb.top.height - glb.logo.height - glb.margin.y
		glb.logo.bottom_pos_y = glb.margin.y


	def _ply_len(self, ply):
		return sum([x[1] or 1 for x in block_ply])

	def _ply_expand(self, ply):
		rv = []
		for n, c in ply:
			# Single signal ?
			if c is None:
				# Handle 'skips'
				if n is None:
					rv.append(None)

				# Normal signals
				else:
					rv.append(n)

			# [n-1:0] range ?
			elif type(c) is int:
				# Handle 'skips'
				if n is None:
					for i in range(c):
						rv.append(None)

				# Normal signals
				else:
					for i in range(c-1, -1, -1):
						rv.append(n + '[' + str(i) + ']')

			# [o+n-1:o] offset range ?
			elif type(c) is tuple:
				# Handle 'skips'
				if n is None:
					for i in range(c[1]):
						rv.append(None)

				# Normal signals
				else:
					for i in range(c[0]+c[1]-1, c[0]-1, -1):
						rv.append(n + '[' + str(i) + ']')

			# ???
			else:
				raise RuntimeError('Invalid Pin Layout')

		return rv

	def _ply_distribute(self, n_pins, start, end, step=0, layer='met4', axis='x'):
		# Get tracks data
		t_offset = self.cfg.pdk.tracks[layer][axis].offset
		t_pitch  = self.cfg.pdk.tracks[layer][axis].pitch

		# Generate tracks in the interval
		p = (((start - t_offset) // t_pitch) * t_pitch) + t_offset
		if p < 0:
			p = t_offset

		tracks = []
		while p < end:
			tracks.append(p)
			p += t_pitch

		# Pick step if need be
		if n_pins == 1:
			step = 1

		if step <= 0:
			step = (len(tracks) - 1) // (n_pins - 1)

		if step == 0:
			raise RuntimeError('Too many tracks to fit in too small area ...')

		# Pick the center tracks
		tracks_needed = (n_pins - 1) * step + 1
		i_start = (len(tracks) - tracks_needed) // 2
		i_end   = i_start + tracks_needed

		return tracks[i_start:i_end:step]

	def _ply_finalize(self, pins, tracks):
		if len(pins) != len(tracks):
			raise RuntimeError('Mismatch pin/track list')

		return dict([(p,t) for p,t in zip(pins, tracks) if p is not None])

	def user_analog_layout(self):
		# Pin Layouts
		ply = [
			('ua', self.cfg.tt.uio.au),
		]

		# Expand and check consistency
		ply_e = self._ply_expand(ply)

		# Get tracks
			# Available zone
		h_start = self.glb.pg_vdd.offset + self.glb.pg_vaa.offset + self.glb.margin.x
		h_end   = self.glb.block.width + self.glb.margin.x

			# Half-Step
		h_hs = (h_end - h_start) // (2 * len(ply_e) - 1)

			# Find aligned tracks
		tracks = self._ply_distribute(
			n_pins = len(ply_e),
			start  = h_start,
			end    = h_end - h_hs,
			step   = 0,
			layer  = self.cfg.tt.spine.vlayer,
			axis   = 'x',
		)

		# Create pins for control block
		self.ply_block_analog = self._ply_finalize(ply_e, tracks)

	def userif_layout(self):

		# Pin Layouts
		block_ply = [
			(None,      3),	# pg_ena, pg_cscd, k_zero not mapped
			('uio_oe',  self.cfg.tt.uio.io),
			('uio_out', self.cfg.tt.uio.io),
			('uo_out',  self.cfg.tt.uio.o),
			('uio_in',  self.cfg.tt.uio.io),
			('ui_in',   self.cfg.tt.uio.i - 2),
			('rst_n',   None),
			('clk',     None),
			('ena',     None),
		]

		mux_ply = lambda n: [
			('um_pg_ena', (n, 1)),
			(None,        1), # Future pg_cscd reserved
			('um_k_zero', (n, 1)),
			('um_ow',     (n * self.user.ow, self.user.ow)),
			('um_iw',     (n * self.user.iw, self.user.iw)),
			('um_ena',    (n, 1)),
		]

		# Expand and check consistency
		block_ply_e = self._ply_expand(block_ply)
		mux_ply_e   = self._ply_expand(mux_ply(0))

		if len(block_ply_e) != len(mux_ply_e):
			raise RuntimeError('Mux and Block pin layout mismatch !')

		# Get tracks
		tracks_pg = self._ply_distribute(
			n_pins = 2,
			start  = self.glb.margin.x,
			end    = self.glb.pg_vdd.width - self.glb.margin.x,
			step   = 0,
			layer  = self.cfg.tt.spine.vlayer,
			axis   = 'x',
		)

		tracks_um = self._ply_distribute(
			n_pins = len(block_ply_e) - 2,
			start  = self.glb.pg_vdd.offset + self.glb.pg_vaa.offset,
			end    = self.glb.block.width,
			step   = 0,
			layer  = self.cfg.tt.spine.vlayer,
			axis   = 'x',
		)

		tracks = tracks_pg + tracks_um

		# Create pins for user blocks
		self.ply_block = self._ply_finalize(block_ply_e, tracks)

		# Create pins for mux blocks
		mux_tracks  = []
		mux_ply_bot = []
		mux_ply_top = []

		for i in range(self.cfg.tt.grid.x // 2):
			ofs = self.glb.block.pitch * (self.cfg.tt.grid.x // 2 - i - 1)
			mux_tracks.extend([x+ofs for x in tracks])
			mux_ply_bot.extend(self._ply_expand(mux_ply(i*2+1)))
			mux_ply_top.extend(self._ply_expand(mux_ply(i*2+0)))

		self.ply_mux_bot = self._ply_finalize(mux_ply_bot, mux_tracks)
		self.ply_mux_top = self._ply_finalize(mux_ply_top, mux_tracks)

	def hspine_layout(self):

		# Pin Layout
			# We try to match the layout of the horizontal bus
			# with the layout of the input pins since a lot of them
			# are 1:1 connections

		hspine_ply = [
			('bus_gd',  (3,1)),			# so_gh
			('bus_ow',  self.user.ow),	# so_usr
			('bus_gd',  (1,2)),			# so_gl, si_gh
			('bus_iw',  self.user.iw),	# si_usr
			('bus_gd',  (0,1)),			# si_sel[8]
			(None,      3),				# si_sel[7:5]
			('bus_sel', (0,5)),			# si_sel[4:0]
			('bus_ena', None),			# si_ena
			(None,      7),				# si_gl, k_zero, k_one, addr
		]

		vspine_ply = [
			('spine_ow', self.vspine.ow),	# { so_gh, so_usr, so_gl }
			('spine_iw', self.vspine.iw),	# { si_gh, si_usr, si_sel, si_ena, si_gl }
			('k_zero',   None),
			('k_one',    None),
			('addr',     4),
		]

		# Expand and check consistency
		hspine_ply_e = self._ply_expand(hspine_ply)
		vspine_ply_e = self._ply_expand(vspine_ply)

		if len(hspine_ply_e) != len(vspine_ply_e):
			raise RuntimeError('Mux and Spine pin layout mismatch !')

		# Get tracks
		tracks = self._ply_distribute(
			n_pins = len(hspine_ply_e),
			start  = 0,
			end    = self.glb.mux.height,
			step   = 0,
			layer  = self.cfg.tt.spine.hlayer,
			axis   = 'y',
		)

		# Create pins for user blocks
		self.ply_mux_bus  = self._ply_finalize(hspine_ply_e, tracks)
		self.ply_mux_port = self._ply_finalize(vspine_ply_e, tracks)

	def vspine_layout(self):

		# Pin Layout
		ply = [
			('spine_ow', self.vspine.ow),
			(None, 3),	# Leave space for PDN
			('spine_iw', self.vspine.iw),
		]

		# Expand and check consistency
		ply_e = self._ply_expand(ply)

		# Get tracks
		tracks = self._ply_distribute(
			n_pins = len(ply_e),
			start  = 0,
			end    = self.glb.ctrl.width,
			step   = 2,
			layer  = self.cfg.tt.spine.vlayer,
			axis   = 'x',
		)

		# Create pins for control block
		self.ply_ctrl_vspine = self._ply_finalize(ply_e, tracks)

	def ctrl_layout(self):
		# Config for up/down mapping of IO pads
		# FIXME: Part of this should be from config and is sky130 specific

		# Classify and order them up / down
		bot_pads  = [
			( 'o', 7, None ),
			( 'ctrl_ena',       None, None ),
			( 'ctrl_sel_inc',   None, None ),
			( 'ctrl_sel_rst_n', None, None ),
			( 'k_one',          None, None ),
			( 'k_zero',         None, None ),
			( 'i', 2, 8 ),
		]

		top_pads = [
			(  'o', 6, 0 ),
			( 'io', 7, 0 ),
			(  'i', 1, 0 ),
			(  'i', 9, None ),
		]

		# Create expanded pins for each
		def expand(l):
			rv = []
			for t, ts, te in l:
				if ts is None:
					rv.append(t)
					continue

				if te is None:
					indexes = [ts]
				elif ts > te:
					indexes = list(range(ts, te-1, -1))
				else:
					indexes = list(range(ts, te+1))

				for ti in indexes:
					if t == 'i':
						rv.append(f'pad_ui_in[{ti:d}]')

					elif t == 'o':
						rv.append(f'pad_uo_out[{ti:d}]')

					elif t == 'io':
						rv.append(f'pad_uio_oe_n[{ti:d}]')
						rv.append(f'pad_uio_out[{ti:d}]')
						rv.append(f'pad_uio_in[{ti:d}]')
			return rv

		bot_pads = expand(bot_pads)
		top_pads = expand(top_pads)

		# Split into left/right
		bs = len(bot_pads) // 2
		bl_pads = bot_pads[0:bs]
		br_pads = bot_pads[bs:]

		ts = len(top_pads) // 2
		tl_pads = top_pads[0:ts]
		tr_pads = top_pads[ts:]

		# Assign tracks
		def spread(ply, ll, hl):
			tracks = self._ply_distribute(
				n_pins = len(ply),
				start  = ll,
				end    = hl,
				step   = 2,
				layer  = self.cfg.tt.spine.vlayer,
				axis   = 'x',
			)

			return self._ply_finalize(ply, tracks)

		limit_left  = min(self.ply_ctrl_vspine.values())
		limit_right = max(self.ply_ctrl_vspine.values())

		self.ply_ctrl_io_top = {}
		self.ply_ctrl_io_bot = {}
		self.ply_ctrl_io_top.update( spread(tl_pads, 0,           limit_left) )
		self.ply_ctrl_io_bot.update( spread(bl_pads, 0,           limit_left) )
		self.ply_ctrl_io_top.update( spread(tr_pads, limit_right, self.glb.ctrl.width) )
		self.ply_ctrl_io_bot.update( spread(br_pads, limit_right, self.glb.ctrl.width) )

	def analog_layout(self):
		# Generate list of masked muxes
		self.mux_mask = 0

		if hasattr(self.cfg.tt, 'analog'):
			for grp in self.cfg.tt.analog:
				for mux_id in grp['mux_id']:
					self.mux_mask |= 1 << mux_id

	def mux_exists(self, mux_id):
		# Check if a given mux exists or is masked for some reason
		return not ((self.mux_mask >> mux_id) & 1)

