// tb_correctness.v -- feed the chip all 500 test vectors and check every answer.
//
// Proves the HARDWARE (scorer.v) gives the exact same verdict/score that the
// Python model wrote into test_vectors.txt. If this passes, your Verilog and
// your Python are the same brain -- bit for bit.

`timescale 1ns/1ps

module tb_correctness;
    reg  [15:0] f0, f1, f2, f3;
    wire        verdict;
    wire [7:0]  score;

    // device under test = the bare combinational scorer
    scorer dut (.f0(f0), .f1(f1), .f2(f2), .f3(f3),
                .verdict(verdict), .score(score));

    integer fd, r, n, errors;
    reg [1023:0] header;
    integer ef0, ef1, ef2, ef3, everdict, escore;

    initial begin
        fd = $fopen("test_vectors.txt", "r");
        if (fd == 0) begin
            $display("ERROR: cannot open test_vectors.txt (run from the scorer folder)");
            $finish;
        end
        r = $fgets(header, fd);   // skip the "# f0 f1 ..." comment line
        n = 0; errors = 0;

        while (!$feof(fd)) begin
            r = $fscanf(fd, "%d %d %d %d %d %d",
                        ef0, ef1, ef2, ef3, everdict, escore);
            if (r == 6) begin
                f0 = ef0[15:0]; f1 = ef1[15:0]; f2 = ef2[15:0]; f3 = ef3[15:0];
                #1;  // let the combinational logic settle
                if (verdict !== everdict[0] || score !== escore[7:0]) begin
                    errors = errors + 1;
                    if (errors <= 5)
                        $display("  MISMATCH vec %0d: got v=%0d s=%0d  expected v=%0d s=%0d",
                                 n, verdict, score, everdict, escore);
                end
                n = n + 1;
            end
        end
        $fclose(fd);

        $display("Checked %0d vectors, %0d mismatches", n, errors);
        if (errors == 0)
            $display(">>> PASS: the hardware matches Python on all %0d vectors.", n);
        else
            $display(">>> FAIL: %0d mismatches.", errors);
        $finish;
    end
endmodule
