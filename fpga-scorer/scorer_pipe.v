// scorer_pipe.v -- clocked, pipelined wrapper around the combinational scorer.
//
// The bare scorer.v is one big tangle of logic with no clock. To get the
// "exactly N nanoseconds, every time" guarantee, we wrap it in a 2-stage
// pipeline by registering (latching on a clock edge) the inputs and the output:
//
//     in_valid + features --[STAGE 1: register inputs]--> combinational scorer
//                          --[STAGE 2: register verdict/score]--> out_valid + result
//
// Two stages => fixed 2-clock latency. And because each stage is always free to
// take new data on the next clock, it can accept a new message EVERY cycle
// (throughput = 1 result per clock), even though each message takes 2 cycles to
// pass through. That is the laundry-pipeline idea in hardware.

module scorer_pipe (
    input  wire        clk,
    input  wire        in_valid,   // 1 = the features this cycle are real
    input  wire [15:0] f0,
    input  wire [15:0] f1,
    input  wire [15:0] f2,
    input  wire [15:0] f3,
    output reg         out_valid,  // 1 = verdict/score this cycle are real
    output reg         verdict,
    output reg  [7:0]  score
);
    // ---- Stage 1: latch the incoming features and the valid flag ----
    reg [15:0] f0_r, f1_r, f2_r, f3_r;
    reg        v1;

    // Combinational scorer evaluates the latched (stage-1) features.
    wire       comb_verdict;
    wire [7:0] comb_score;
    scorer u_scorer (
        .f0(f0_r), .f1(f1_r), .f2(f2_r), .f3(f3_r),
        .verdict(comb_verdict), .score(comb_score)
    );

    always @(posedge clk) begin
        // Stage 1: capture inputs
        f0_r <= f0;  f1_r <= f1;  f2_r <= f2;  f3_r <= f3;
        v1   <= in_valid;
        // Stage 2: capture the scorer's answer about last cycle's inputs
        verdict   <= comb_verdict;
        score     <= comb_score;
        out_valid <= v1;
    end
endmodule
