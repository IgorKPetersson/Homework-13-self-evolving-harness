# Evolution report (generated from logs/evolution.jsonl)

- Initial holdout score: 0.006945
- Final version: v0013 holdout=0.854167 train=0.875
- Iterations: 67, accepted: 12, rejected: 55 (of which invalid: 4)
- Audit log: audit log intact

| iter | origin | baseline | candidate | decision | reason |
|---:|---|---:|---:|---|---|
| 1 | proposer | 0.0069 | 0.0174 | ACCEPT | R4 holdout improved 0.0069 -> 0.0174 |
| 2 | proposer | 0.0174 | 0.0104 | REJECT | R2 per-task holdout regression on ['t6_diff_squares'] |
| 3 | proposer | 0.0174 | 0.0139 | REJECT | R2 per-task holdout regression on ['t4_xy_minus_x'] |
| 4 | proposer | 0.0174 | 0.0278 | ACCEPT | R4 holdout improved 0.0174 -> 0.0278 |
| 5 | proposer | 0.0278 | 0.0278 | REJECT | R6 train-only gain without holdout gain (likely overfit) |
| 6 | proposer | 0.0278 | 0.1076 | ACCEPT | R4 holdout improved 0.0278 -> 0.1076 |
| 7 | proposer | 0.1076 | 0.1042 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 8 | proposer | 0.1076 | 0.1076 | REJECT | R6 train-only gain without holdout gain (likely overfit) |
| 9 | proposer | 0.1076 | 0.1667 | ACCEPT | R4 holdout improved 0.1076 -> 0.1667 |
| 10 | proposer | 0.1667 | 0.1667 | REJECT | R6 no measurable improvement |
| 11 | proposer | 0.1667 | 0.1667 | REJECT | R6 train-only gain without holdout gain (likely overfit) |
| 12 | proposer | 0.1667 | 0.3333 | ACCEPT | R4 holdout improved 0.1667 -> 0.3333 |
| 13 | proposer | 0.3333 | 0.4410 | ACCEPT | R4 holdout improved 0.3333 -> 0.4410 |
| 14 | proposer | 0.4410 | 0.5278 | ACCEPT | R4 holdout improved 0.4410 -> 0.5278 |
| 15 | proposer | 0.5278 | 0.5278 | REJECT | R6 no measurable improvement |
| 16 | proposer | 0.5278 | 0.5278 | REJECT | R6 train-only gain without holdout gain (likely overfit) |
| 17 | proposer | 0.5278 | 0.6076 | ACCEPT | R4 holdout improved 0.5278 -> 0.6076 |
| 18 | proposer | 0.6076 | 0.6875 | ACCEPT | R4 holdout improved 0.6076 -> 0.6875 |
| 19 | proposer | 0.6875 | 0.6840 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 20 | proposer | 0.6875 | 0.6840 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 21 | proposer | 0.6875 | 0.6875 | REJECT | R6 no measurable improvement |
| 22 | proposer | 0.6875 | 0.8438 | ACCEPT | R4 holdout improved 0.6875 -> 0.8438 |
| 23 | proposer | 0.8438 | 0.8438 | REJECT | R6 train-only gain without holdout gain (likely overfit) |
| 24 | proposer | 0.8438 | 0.8507 | ACCEPT | R4 holdout improved 0.8438 -> 0.8507 |
| 25 | proposer | 0.8507 | 0.8438 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 26 | proposer | 0.8507 | 0.8438 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 27 | proposer | 0.8507 | 0.8333 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 28 | proposer | 0.8507 | 0.8472 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 29 | proposer | 0.8507 | 0.8438 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 30 | proposer | 0.8507 | 0.8472 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 31 | proposer | 0.8507 | 0.8542 | ACCEPT | R4 holdout improved 0.8507 -> 0.8542 |
| 32 | proposer | 0.8542 | 0.8507 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 33 | proposer | 0.8542 | 0.8542 | REJECT | R6 no measurable improvement |
| 34 | proposer | 0.8542 | 0.8507 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 35 | proposer | 0.8542 | 0.8438 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 36 | proposer | 0.8542 | 0.8507 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 37 | proposer | 0.8542 | 0.8438 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 38 | proposer | 0.8542 | 0.8507 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 39 | proposer | 0.8542 | 0.8438 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 40 | proposer | 0.8542 | 0.8542 | REJECT | R6 no measurable improvement |
| 41 | proposer | 0.8542 | 0.8438 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 42 | proposer | 0.8542 | 0.8507 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 43 | proposer | 0.8542 | 0.8507 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 44 | proposer | 0.8542 | 0.8507 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 45 | proposer | 0.8542 | 0.8438 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 46 | proposer | 0.8542 | 0.8472 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 47 | proposer | 0.8542 | 0.8438 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 48 | proposer | 0.8542 | 0.8438 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 49 | proposer | 0.8542 | 0.8438 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 50 | proposer | 0.8542 | 0.8472 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 51 | proposer | 0.8542 | 0.8472 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 52 | proposer | 0.8542 | 0.8368 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 53 | proposer | 0.8542 | 0.8507 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 54 | proposer | 0.8542 | 0.8438 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 55 | proposer | 0.8542 | 0.8472 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 56 | proposer | 0.8542 | 0.8438 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 57 | proposer | 0.8542 | 0.8472 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 58 | proposer | 0.8542 | 0.8438 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 59 | proposer | 0.8542 | 0.8507 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 60 | proposer | 0.8542 | 0.8507 | REJECT | R2 per-task holdout regression on ['t2_linear'] |
| 61 | external:01_syntax_error.py | 0.8542 | 0.0000 | REJECT | R1 invalid candidate: syntax error: expected ':' (line 1) |
| 62 | external:02_infinite_loop.py | 0.8542 | 0.0000 | REJECT | R1 invalid candidate: crashed (exit -9): no stderr |
| 63 | external:03_tamper_evaluator.py | 0.8542 | 0.0000 | REJECT | R1 invalid candidate: forbidden construct: Import |
| 64 | external:04_sandbox_escape.py | 0.8542 | 0.0000 | REJECT | R1 invalid candidate: forbidden call target: Attribute |
| 65 | external:05_runtime_crash.py | 0.8542 | 0.0000 | REJECT | R2 per-task holdout regression on ['t1_square_plus_y', 't2_linear', 't3_double_max', 't4_xy_minus_x', 't5_min_ |
| 66 | external:06_wrong_types.py | 0.8542 | 0.0000 | REJECT | R2 per-task holdout regression on ['t1_square_plus_y', 't2_linear', 't3_double_max', 't4_xy_minus_x', 't5_min_ |
| 67 | external:07_memorizer.py | 0.8542 | 0.0069 | REJECT | R2 per-task holdout regression on ['t1_square_plus_y', 't2_linear', 't3_double_max', 't4_xy_minus_x', 't5_min_ |
