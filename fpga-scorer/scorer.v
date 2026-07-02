// scorer.v  -- AUTO-GENERATED from tree_model.py. Do not edit by hand.
//
// AEGIS Stage-4 anomaly scorer (combinational).
// Same decision tree as the Python model, expressed as hardware.
// Each feature arrives as a 16-bit unsigned integer (the quantized value).
//   verdict = 1 means "suspicious", 0 means "normal".
//   score   = 0..255 suspicion level (for the dashboard / threshold tuning).
//
// NOTE: this is purely combinational (no clock yet). Registering the inputs and
// the output turns this into the 2-stage pipeline we characterize for latency.

module scorer (
    input  wire [15:0] f0,   // pkt_rate
    input  wire [15:0] f1,   // pkt_size
    input  wire [15:0] f2,   // seq_gap
    input  wire [15:0] f3,   // iat_var
    output wire        verdict, // 1 = suspicious, 0 = normal
    output wire [7:0]  score    // 0..255 suspicion level
);

    assign verdict = ((f2 <= 16'd3916) ? ((f3 <= 16'd6641) ? ((f0 <= 16'd21717) ? ((f1 <= 16'd15795) ? 1 : 0) : 1) : 1) : ((f2 <= 16'd4183) ? 1 : 1));

    assign score = ((f2 <= 16'd3916) ? ((f3 <= 16'd6641) ? ((f0 <= 16'd21717) ? ((f1 <= 16'd15795) ? 255 : 0) : 255) : 255) : ((f2 <= 16'd4183) ? 191 : 255));

endmodule
