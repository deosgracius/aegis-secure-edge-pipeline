# build_vivado.tcl -- non-interactive synth + implement + report for the Basys 3.
#
# Run from THIS folder:
#     vivado -mode batch -source build_vivado.tcl
#
# Produces ./vivado_out/ with utilization.rpt, timing.rpt, and a .bit bitstream,
# and prints the two numbers that matter to the console: timing (fmax) and
# resource utilization.

set part   xc7a35tcpg236-1
set outdir ./vivado_out
file mkdir $outdir

# --- read the design (order: leaf -> pipeline -> board top) ---
read_verilog ../scorer.v
read_verilog ../scorer_pipe.v
read_verilog ./scorer_top.v
read_xdc     ./scorer.xdc

# --- synthesis ---
synth_design -top scorer_top -part $part

# --- implementation ---
opt_design
place_design
route_design

# --- reports ---
report_utilization     -file $outdir/utilization.rpt
report_timing_summary  -file $outdir/timing.rpt

puts "\n================ TIMING SUMMARY (read WNS at 100 MHz) ================"
report_timing_summary
puts "\n================ RESOURCE UTILIZATION ================"
report_utilization

# --- bitstream (program the board from Hardware Manager) ---
write_bitstream -force $outdir/scorer_top.bit

puts "\nDONE. fmax = 1 / (10ns - WNS).  Reports in $outdir/"
