// tb_latency.v -- measure the pipeline's latency and jitter.
//
// We run the clock at 100 MHz (10 ns per cycle), exactly like the Basys 3
// board's onboard oscillator. For several DIFFERENT inputs we count how many
// clock edges pass between "message in" (in_valid) and "verdict out"
// (out_valid). The whole point: that count must be the SAME every time.
//   latency  = how long one message takes end-to-end
//   jitter   = how much that latency varies (we want zero)

`timescale 1ns/1ps

module tb_latency;
    reg         clk = 0;
    reg         in_valid = 0;
    reg  [15:0] f0, f1, f2, f3;
    wire        out_valid, verdict;
    wire [7:0]  score;

    scorer_pipe dut (.clk(clk), .in_valid(in_valid),
                     .f0(f0), .f1(f1), .f2(f2), .f3(f3),
                     .out_valid(out_valid), .verdict(verdict), .score(score));

    localparam CLK_NS = 10;            // 10 ns period = 100 MHz
    always #(CLK_NS/2) clk = ~clk;

    integer lat, min_lat, max_lat, i;

    // Send one message, count clock edges until the verdict appears.
    task measure(input [15:0] a, input [15:0] b,
                 input [15:0] c, input [15:0] d, output integer cycles);
        begin
            @(negedge clk);
            f0 = a; f1 = b; f2 = c; f3 = d; in_valid = 1;
            @(posedge clk);            // edge 1: stage-1 latches the inputs
            @(negedge clk);
            in_valid = 0;              // it was a one-cycle pulse
            cycles = 1;
            while (out_valid !== 1'b1) begin
                @(posedge clk);
                #1;                    // let the registered output settle
                cycles = cycles + 1;
            end
        end
    endtask

    initial begin
        min_lat = 1000; max_lat = 0;
        $display("Measuring latency at %0d MHz (%0d ns/cycle)...",
                 1000 / CLK_NS, CLK_NS);

        // six deliberately different inputs that hit different tree branches
        for (i = 0; i < 6; i = i + 1) begin
            measure(i * 9000, 12345, i * 7000, i * 6000, lat);
            $display("  message %0d: latency = %0d cycles = %0d ns   (verdict=%0d, score=%0d)",
                     i, lat, lat * CLK_NS, verdict, score);
            if (lat < min_lat) min_lat = lat;
            if (lat > max_lat) max_lat = lat;
        end

        $display("");
        $display("  min latency = %0d cycles (%0d ns)", min_lat, min_lat * CLK_NS);
        $display("  max latency = %0d cycles (%0d ns)", max_lat, max_lat * CLK_NS);
        $display("  jitter      = %0d cycles", max_lat - min_lat);
        if (max_lat == min_lat)
            $display(">>> Deterministic: every message takes EXACTLY %0d ns. Zero jitter.",
                     min_lat * CLK_NS);
        else
            $display(">>> Warning: latency varies -- not deterministic.");
        $finish;
    end
endmodule
