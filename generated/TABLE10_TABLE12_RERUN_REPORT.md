# 表10与表12重新运行报告

## 结论

本次运行是依据论文文字说明建立的独立、可追溯重建版，不是对遗失原脚本的恢复。旧数值保留为 `reported_only` 证据记录；新数值具有代码、配置、种子和路径级原始输出。两者只有在数值容差内一致时，才能称为复现旧表。

## 表10：旧稿记录

| setting      | policy                             |   weighted_cost |   terminal_yard_backlog |   late_horizon_drift | reproducibility_status   |
|:-------------|:-----------------------------------|----------------:|------------------------:|---------------------:|:-------------------------|
| severe_error | no_reidentification_fixed_pair_pto |          73.71  |                  7940.2 |               5.509  | script_missing           |
| severe_error | fixed_pair_pto_7_day_update        |           5.475 |                     0.1 |              -0.0014 | script_missing           |
| severe_error | fixed_pair_pto_3_day_update        |           0.21  |                     0.1 |               0      | script_missing           |
| severe_error | fixed_pair_pto_1_day_update        |           0.252 |                     0.1 |               0      | script_missing           |
| reference    | fast_only_feedback                 |           0.218 |                     3   |              -0.0001 | script_missing           |
| reference    | fast_plus_tracker_feedback         |           0.232 |                     4.4 |               0.0007 | script_missing           |
| reference    | high_fidelity_fixed_pair_pto       |           0.067 |                     1   |               0      | script_missing           |

## 表10：本次重建运行

| policy            |   weighted_cost |   mean_queue |   terminal_yard_backlog |   late_horizon_drift | status                        |
|:------------------|----------------:|-------------:|------------------------:|---------------------:|:------------------------------|
| feedback_fast     |       0.226127  |      6.30901 |                  2.4475 |         -8.05117e-05 | independent_reconstruction_v2 |
| feedback_tracker  |       0.237236  |      7.88363 |                  4.365  |          0.000537108 | independent_reconstruction_v2 |
| pto_frozen        |      73.8839    |   4925.43    |               7931.17   |          5.52607     | independent_reconstruction_v2 |
| pto_high_fidelity |       0.0837711 |      2.98387 |                  2.975  |         -4.46806e-06 | independent_reconstruction_v2 |
| pto_reid_1d       |       0.0775233 |      2.49091 |                  2.175  |          0.000253838 | independent_reconstruction_v2 |
| pto_reid_3d       |       0.0937598 |      3.57076 |                  2.335  |          0.000246478 | independent_reconstruction_v2 |
| pto_reid_7d       |       5.92057   |    391.944   |                  2.045  |         -0.000111228 | independent_reconstruction_v2 |

### 表10逐项差异

| policy            | metric                |   reported |   reconstructed |   absolute_difference |   relative_difference_pct |
|:------------------|:----------------------|-----------:|----------------:|----------------------:|--------------------------:|
| pto_frozen        | weighted_cost         |    73.71   |    73.8839      |           0.173859    |                  0.235869 |
| pto_frozen        | terminal_yard_backlog |  7940.2    |  7931.17        |          -9.0275      |                 -0.113694 |
| pto_frozen        | late_horizon_drift    |     5.509  |     5.52607     |           0.0170714   |                  0.309882 |
| pto_reid_7d       | weighted_cost         |     5.475  |     5.92057     |           0.445568    |                  8.13823  |
| pto_reid_7d       | terminal_yard_backlog |     0.1    |     2.045       |           1.945       |               1945        |
| pto_reid_7d       | late_horizon_drift    |    -0.0014 |    -0.000111228 |           0.00128877  |                 92.0552   |
| pto_reid_3d       | weighted_cost         |     0.21   |     0.0937598   |          -0.11624     |                -55.3525   |
| pto_reid_3d       | terminal_yard_backlog |     0.1    |     2.335       |           2.235       |               2235        |
| pto_reid_3d       | late_horizon_drift    |     0      |     0.000246478 |           0.000246478 |                nan        |
| pto_reid_1d       | weighted_cost         |     0.252  |     0.0775233   |          -0.174477    |                -69.2368   |
| pto_reid_1d       | terminal_yard_backlog |     0.1    |     2.175       |           2.075       |               2075        |
| pto_reid_1d       | late_horizon_drift    |     0      |     0.000253838 |           0.000253838 |                nan        |
| feedback_fast     | weighted_cost         |     0.218  |     0.226127    |           0.00812684  |                  3.72791  |
| feedback_fast     | terminal_yard_backlog |     3      |     2.4475      |          -0.5525      |                -18.4167   |
| feedback_fast     | late_horizon_drift    |    -0.0001 |    -8.05117e-05 |           1.94883e-05 |                 19.4883   |
| feedback_tracker  | weighted_cost         |     0.232  |     0.237236    |           0.00523577  |                  2.2568   |
| feedback_tracker  | terminal_yard_backlog |     4.4    |     4.365       |          -0.035       |                 -0.795455 |
| feedback_tracker  | late_horizon_drift    |     0.0007 |     0.000537108 |          -0.000162892 |                -23.2703   |
| pto_high_fidelity | weighted_cost         |     0.067  |     0.0837711   |           0.0167711   |                 25.0315   |
| pto_high_fidelity | terminal_yard_backlog |     1      |     2.975       |           1.975       |                197.5      |
| pto_high_fidelity | late_horizon_drift    |     0      |    -4.46806e-06 |          -4.46806e-06 |                nan        |

## 表12：旧稿记录

| scenario   | design_change    | tested_values   | cost_range    | mean_queue_range   | terminal_yard_range   |   max_abs_drift | reproducibility_status   |
|:-----------|:-----------------|:----------------|:--------------|:-------------------|:----------------------|----------------:|:-------------------------|
| high       | gain_multiplier  | 0.50-1.50       | 0.2193-0.2217 | 5.27-5.84          | 2.73-3.36             |        0.000119 | script_missing           |
| peak       | gain_multiplier  | 0.50-1.50       | 0.2210-0.2232 | 5.36-5.90          | 2.74-3.80             |        0.000145 | script_missing           |
| high       | lateness_support | 1, 2, 4         | 0.2186-0.2208 | 5.43-5.56          | 2.66-3.14             |        0.000164 | script_missing           |
| peak       | lateness_support | 1, 2, 4         | 0.2204-0.2227 | 5.52-5.65          | 3.10-3.60             |        0.000142 | script_missing           |

## 表12：本次重建运行

| scenario   | design           |   tested_min |   tested_max |   cost_min |   cost_max |   mean_queue_min |   mean_queue_max |   terminal_yard_min |   terminal_yard_max |   max_abs_drift | status                        |
|:-----------|:-----------------|-------------:|-------------:|-----------:|-----------:|-----------------:|-----------------:|--------------------:|--------------------:|----------------:|:------------------------------|
| high       | gain_multiplier  |          0.5 |          1.5 |   0.223976 |   0.22616  |           6.0776 |          6.4979  |              2.6675 |              3.3325 |     0.000135325 | independent_reconstruction_v2 |
| high       | lateness_support |          1   |          4   |   0.223976 |   0.22498  |           6.216  |          6.28373 |              2.585  |              3.1075 |     0.000156256 | independent_reconstruction_v2 |
| peak       | gain_multiplier  |          0.5 |          1.5 |   0.224554 |   0.226739 |           6.0776 |          6.4979  |              2.6675 |              3.3325 |     0.000135325 | independent_reconstruction_v2 |
| peak       | lateness_support |          1   |          4   |   0.224554 |   0.225558 |           6.216  |          6.28373 |              2.585  |              3.1075 |     0.000156256 | independent_reconstruction_v2 |

## 判断

- 冻结PTO的失稳机制近似复现：成本、末端积压和尾部漂移均与旧记录非常接近。
- Fast-only 与 fast+tracker 的排序复现，且十个种子块的差值区间不跨零；重建版仍显示 tracker 在本组设定下增加成本和末端积压。
- 表12的结论复现：增益倍数与迟到支持变化没有造成刀刃式反转，队列保持有界；绝对区间与旧表接近但不完全相同。
- 一日/三日重识别能够消除失稳，但其重建成本未逐项复现旧表。旧脚本遗失的规划样本与重新求解规则是主要不可识别项。
- 因此应写成‘机制与排序得到独立重建支持’，不能写成‘旧表全部精确复现’。

## 证据边界

- 可以复核：代码执行、随机种子、质量守恒、策略方向、重识别频率和敏感性区间。
- 不能宣称：本次脚本就是生成旧表的原始脚本。
- 若旧数值与新数值不一致，投稿稿应使用本次可复现结果，或将旧表降级为不可复核的历史记录。