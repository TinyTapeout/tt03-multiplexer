/*
 * tt_top.v
 *
 * Top level
 *
 * Copyright (c) 2023 Sylvain Munaut <tnt@246tNt.com>
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none
`include "tt_defs.vh"

module tt_top #(
	parameter integer N_PADS = 44,
	parameter integer G_X  = `TT_G_X,
	parameter integer G_Y  = `TT_G_Y,
	parameter integer N_AE = `TT_N_AE,
	parameter integer N_AU = `TT_N_AU,
	parameter integer N_IO = `TT_N_IO,
	parameter integer N_O  = `TT_N_O,
	parameter integer N_I  = `TT_N_I,
	parameter [G_Y-1:0] MUX_MASK = `TT_MUX_MASK
)(
	// Power
`ifdef USE_POWER_PINS
	input wire VDPWR,
	input wire VAPWR,
	input wire VGND,
`endif

	// IOs
	inout  wire [N_PADS-1:0] io_ana,
	input  wire [N_PADS-1:0] io_in,
	output wire [N_PADS-1:0] io_out,
	output wire [N_PADS-1:0] io_oeb,

	// Convenient constants for top-level tie-offs
	output wire k_zero,
	output wire k_one
);

	localparam integer S_OW = N_O + N_IO * 2 + 2;
	localparam integer S_IW = N_I + N_IO + 9 + 1 + 2;

	localparam integer U_OW = N_O + N_IO * 2;
	localparam integer U_IW = N_I + N_IO;


	// Signals
	// -------

	// Pads
	wire      [5:0] pad_ctl_in;
	wire      [5:0] pad_ctl_out;
	wire      [5:0] pad_ctl_oe_n;

	wire [N_IO-1:0] pad_uio_in;
	wire [N_IO-1:0] pad_uio_out;
	wire [N_IO-1:0] pad_uio_oe_n;

	wire  [N_O-1:0] pad_uo_in;
	wire  [N_O-1:0] pad_uo_out;
	wire  [N_O-1:0] pad_uo_oe_n;

	wire  [N_I-1:0] pad_ui_in;
	wire  [N_I-1:0] pad_ui_out;
	wire  [N_I-1:0] pad_ui_oe_n;

	wire [N_AE-1:0] pad_ana_in;
	wire [N_AE-1:0] pad_ana_out;
	wire [N_AE-1:0] pad_ana_oe_n;
	wire [N_AE-1:0] pad_ana_analog;

	// Vertical spine
	wire  [S_OW-1:0] spine_top_ow;
	wire  [S_IW-1:0] spine_top_iw;

	wire  [S_OW-1:0] spine_bot_ow;
	wire  [S_IW-1:0] spine_bot_iw;

	// Control signals
	wire ctrl_sel_rst_n;
	wire ctrl_sel_inc;
	wire ctrl_ena;


	// Pad connections
	// ---------------

	// Split in groups
	assign {
		pad_ctl_in,
		pad_ana_in[11:6],
		pad_uo_in,
		pad_uio_in,
		pad_ui_in[1],	// u_rst
		pad_ui_in[0],	// u_clk
		pad_ui_in[9],
		pad_ana_in[5:0],
		pad_ui_in[8:2]
	} = io_in;

	assign io_out = {
		pad_ctl_out,
		pad_ana_out[11:6],
		pad_uo_out,
		pad_uio_out,
		pad_ui_out[1],	// u_rst
		pad_ui_out[0],	// u_clk
		pad_ui_out[9],
		pad_ana_out[5:0],
		pad_ui_out[8:2]
	};

	assign io_oeb = {
		pad_ctl_oe_n,
		pad_ana_oe_n[11:6],
		pad_uo_oe_n,
		pad_uio_oe_n,
		pad_ui_oe_n[1],	// u_rst
		pad_ui_oe_n[0],	// u_clk
		pad_ui_oe_n[9],
		pad_ana_oe_n[5:0],
		pad_ui_oe_n[8:2]
	};

	assign pad_ana_analog = {
		io_ana[37:32],
		io_ana[12:7]
	};

	// Tie-offs
		// Control
	assign pad_ctl_oe_n   = { 6{k_one} };
	assign pad_ctl_out    = { 6{k_one} };

	assign ctrl_sel_rst_n = pad_ctl_in[2];
	assign ctrl_sel_inc   = pad_ctl_in[1];
	assign ctrl_ena       = pad_ctl_in[0];

		// Output enables
	assign pad_uo_oe_n  = { N_O{k_zero} };
	assign pad_ui_oe_n  = { N_I{k_one} };
	assign pad_ana_oe_n = { N_AE{k_one} };

		// Output signal
	assign pad_ui_out  = { N_I{k_one} };
	assign pad_ana_out = { N_AE{k_one} };


	// Controller
	// ----------

	(* blackbox *)
	tt_ctrl
`ifdef SIM
	#(
		.N_I  (N_I),
		.N_O  (N_O),
		.N_IO (N_IO)
	)
`endif
	ctrl_I (
`ifdef USE_POWER_PINS
		.VPWR           (VDPWR),
		.VGND           (VGND),
`endif
		.pad_uio_in     (pad_uio_in),
		.pad_uio_out    (pad_uio_out),
		.pad_uio_oe_n   (pad_uio_oe_n),
		.pad_uo_out     (pad_uo_out),
		.pad_ui_in      (pad_ui_in),
		.spine_top_ow   (spine_top_ow),
		.spine_top_iw   (spine_top_iw),
		.spine_bot_ow   (spine_bot_ow),
		.spine_bot_iw   (spine_bot_iw),
		.ctrl_sel_rst_n (ctrl_sel_rst_n),
		.ctrl_sel_inc   (ctrl_sel_inc),
		.ctrl_ena       (ctrl_ena),
		.k_one          (k_one),
		.k_zero         (k_zero)
	);


	// Branches
	// --------

	genvar i, j;

	for (i=0; i<G_Y; i=i+1)
	begin : branch
		if (~MUX_MASK[i])
		begin : check_mask
			// Signals
			wire [S_OW-1:0] l_spine_ow;
			wire [S_IW-1:0] l_spine_iw;

			wire [(U_OW*G_X)-1:0] l_um_ow;
			wire [(U_IW*G_X)-1:0] l_um_iw;
			wire [      G_X -1:0] l_um_ena;
			wire [      G_X -1:0] l_um_k_zero;
			wire [      G_X -1:0] l_um_pg_ena;

			wire [3:0] l_addr;
			wire       l_k_one;
			wire       l_k_zero;

			// Spine connection
			if (i & 1) begin
				assign spine_top_ow = l_spine_ow;
				assign l_spine_iw = spine_top_iw;
			end else begin
				assign spine_bot_ow = l_spine_ow;
				assign l_spine_iw = spine_bot_iw;
			end

			// Branch Mux
			(* blackbox *)
			tt_mux
`ifdef SIM
			#(
				.N_UM (G_X),
				.N_I  (N_I),
				.N_O  (N_O),
				.N_IO (N_IO)
			)
`endif
			mux_I (
`ifdef USE_POWER_PINS
				.VPWR      (VDPWR),
				.VGND      (VGND),
`endif
				.um_ow     (l_um_ow),
				.um_iw     (l_um_iw),
				.um_ena    (l_um_ena),
				.um_k_zero (l_um_k_zero),
				.um_pg_ena (l_um_pg_ena),
				.spine_ow  (l_spine_ow),
				.spine_iw  (l_spine_iw),
				.addr      (l_addr),
				.k_one     (l_k_one),
				.k_zero    (l_k_zero)
			);

			// Branch address tie-offs
			for (j=0; j<4; j=j+1)
				if (i & (2<<j))
					assign l_addr[j] = l_k_one;
				else
					assign l_addr[j] = l_k_zero;

			// Branch User modules
			for (j=0; j<G_X; j=j+1)
			begin : block
				tt_user_module #(
					.MUX_ID (i),
					.BLK_ID (j),
					.N_AE  (N_AE),
					.N_AU  (N_AU),
					.N_I   (N_I),
					.N_O   (N_O),
					.N_IO  (N_IO)
				) um_I (
`ifdef USE_POWER_PINS
					.VDPWR  (VDPWR),
					.VAPWR  (VAPWR),
					.VGND   (VGND),
`endif
					.ana    (pad_ana_analog),
					.ow     (l_um_ow[j*U_OW+:U_OW]),
					.iw     (l_um_iw[j*U_IW+:U_IW]),
					.ena    (l_um_ena[j]),
					.k_zero (l_um_k_zero[j]),
					.pg_ena (l_um_pg_ena[j])
				);
			end
		end
	end


	// Logo & Shuttle ID
	// -----------------

	(* blackbox, keep *)
	tt_logo_top logo_top_I ();

	(* blackbox, keep *)
	tt_logo_bottom logo_bottom_I ();

endmodule // tt_top
