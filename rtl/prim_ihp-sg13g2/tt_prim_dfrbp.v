/*
 * tt_prim_dfrbp.v
 *
 * TT Primitive
 * FF with positive edge clock, inverted reset, complementary outputs
 *
 * Copyright (c) 2024 Sylvain Munaut <tnt@246tNt.com>
 * SPDX-License-Identifier: Apache-2.0
 */

`default_nettype none

module tt_prim_dfrbp (
	input  wire d,
	output wire q,
	output wire q_n,
	input  wire clk,
	input  wire rst_n
);

	sg13g2_dfrbp_2 cell0_I (
		.D       (d),
		.Q       (q),
		.Q_N     (q_n),
		.CLK     (clk),
		.RESET_B (rst_n)
	);

endmodule // tt_prim_dfrbp