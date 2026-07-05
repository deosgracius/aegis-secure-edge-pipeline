// scorer_top.v -- Basys 3 board wrapper for the AEGIS anomaly scorer.
//
// A self-contained on-board demo: the 3 rightmost switches pick one of five
// preset "messages" (a normal one and one per attack type); the pipelined
// scorer classifies it live at 100 MHz; the result shows on the LEDs.
//   led[0]     = verdict   (lit = SUSPICIOUS)
//   led[8:1]   = score     (0..255 suspicion level, in binary)
//   led[15]    = out_valid (pipeline heartbeat)
//
// On the real system the Pi streams quantized feature vectors in over UART;
// here we drive fixed presets so the design is demonstrable with just the board.
// The preset values are 16-bit quantized features chosen to land on each branch
// of the tree in scorer.v.

module scorer_top (
    input  wire        clk,       // 100 MHz oscillator (Basys 3 pin W5)
    input  wire [2:0]  sel,       // sw[2:0] : preset selector
    output wire [15:0] led
);
    // Preset feature vectors: {pkt_rate, pkt_size, seq_gap, iat_var} (quantized 0..65535)
    reg [15:0] f0, f1, f2, f3;
    always @(*) begin
        case (sel)
            3'd0: begin f0=16'd15000; f1=16'd30000; f2=16'd1000;  f3=16'd2000;  end // normal
            3'd1: begin f0=16'd40000; f1=16'd30000; f2=16'd1000;  f3=16'd2000;  end // flood (high pkt_rate)
            3'd2: begin f0=16'd15000; f1=16'd30000; f2=16'd10000; f3=16'd2000;  end // replay (big seq_gap)
            3'd3: begin f0=16'd15000; f1=16'd30000; f2=16'd1000;  f3=16'd20000; end // bursty timing
            3'd4: begin f0=16'd15000; f1=16'd5000;  f2=16'd1000;  f3=16'd2000;  end // undersized packets
            default: begin f0=16'd15000; f1=16'd30000; f2=16'd1000; f3=16'd2000; end // normal
        endcase
    end

    wire        out_valid, verdict;
    wire [7:0]  score;

    scorer_pipe u_scorer (
        .clk(clk), .in_valid(1'b1),
        .f0(f0), .f1(f1), .f2(f2), .f3(f3),
        .out_valid(out_valid), .verdict(verdict), .score(score)
    );

    assign led[0]     = verdict;    // suspicious indicator
    assign led[8:1]   = score;      // 8-bit suspicion score
    assign led[14:9]  = 6'b0;
    assign led[15]    = out_valid;  // pipeline is producing verdicts
endmodule
