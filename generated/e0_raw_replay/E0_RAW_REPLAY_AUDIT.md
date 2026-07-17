# E0原始数据全链核验报告

## 结论

- 论文日期快照全链精确匹配：是。
- 2026-07-17当前公开文件与论文日期快照精确匹配：否。
- SC Ports文件是滚动更新的公共仪表板导出，因此当前下载值发生变化不代表原校准错误；可复现论文数值需要保留带日期和哈希的论文期快照。
- 当前下载重放用于检验校准对数据更新的敏感性，不能用来悄悄覆盖论文期校准输入。

## 论文期留存快照与归档处理结果比较

| file                                    |   reference_rows |   candidate_rows | same_columns   | same_shape   |   differing_cells |   max_abs_difference | exact_match   | reference_sha256                                                 | candidate_sha256                                                 |
|:----------------------------------------|-----------------:|-----------------:|:---------------|:-------------|------------------:|---------------------:|:--------------|:-----------------------------------------------------------------|:-----------------------------------------------------------------|
| clean_port_houston_terminal_reports.csv |               48 |               48 | True           | True         |                 0 |                    0 | True          | 87efc19b47e445aa7d705f8d2e26aece7fefe09a9930dfa6eace637251b66473 | 87efc19b47e445aa7d705f8d2e26aece7fefe09a9930dfa6eace637251b66473 |
| clean_port_virginia_weekly_metrics.csv  |              384 |              384 | True           | True         |                 0 |                    0 | True          | c166ec94072a8a68dbebbb24281b8a77f12d8c28b171331528e40ecf943471df | c166ec94072a8a68dbebbb24281b8a77f12d8c28b171331528e40ecf943471df |
| dwelling_activity_counts.csv            |               21 |               21 | True           | True         |                 0 |                    0 | True          | 1852fd2dc2c190659436585c726b279e536a62766a1692b979c9b36d21fc6657 | 1852fd2dc2c190659436585c726b279e536a62766a1692b979c9b36d21fc6657 |
| mendeley_capacity_benchmark_summary.csv |               25 |               25 | True           | True         |                 0 |                    0 | True          | 27c4c00a1f25bd6f25571e4f9aca1d24c2882c9c73c45f90e93ae12b8403fd8f | 27c4c00a1f25bd6f25571e4f9aca1d24c2882c9c73c45f90e93ae12b8403fd8f |
| mendeley_tas_benchmark_summary.csv      |               30 |               30 | True           | True         |                 0 |                    0 | True          | 373418e61639f1b7c9752d788fbb24d1115997a8be301ee0326cb9406a366f9f | 373418e61639f1b7c9752d788fbb24d1115997a8be301ee0326cb9406a366f9f |
| public_data_calibrated_scenarios.csv    |                4 |                4 | True           | True         |                 0 |                    0 | True          | 165af6d54a3774b7144504a203baface79785a215db882e221584f5d9a729596 | 165af6d54a3774b7144504a203baface79785a215db882e221584f5d9a729596 |
| sc_ports_daily_gate_missions.csv        |                7 |                7 | True           | True         |                 0 |                    0 | True          | 24b99b87add8301dea4bb29fdf85eaef3065eebd2c1f0c81071ec06d632c3adb | 24b99b87add8301dea4bb29fdf85eaef3065eebd2c1f0c81071ec06d632c3adb |
| sc_ports_summary.csv                    |               11 |               11 | True           | True         |                 0 |                    0 | True          | 0496edb6f48c949f68aab8fb0b1913a5f257ed678adf792cd02b6490d6d3d9f9 | 0496edb6f48c949f68aab8fb0b1913a5f257ed678adf792cd02b6490d6d3d9f9 |

## 当前重新下载文件与归档处理结果比较

| file                                    |   reference_rows |   candidate_rows | same_columns   | same_shape   |   differing_cells |   max_abs_difference | exact_match   | reference_sha256                                                 | candidate_sha256                                                 |
|:----------------------------------------|-----------------:|-----------------:|:---------------|:-------------|------------------:|---------------------:|:--------------|:-----------------------------------------------------------------|:-----------------------------------------------------------------|
| clean_port_houston_terminal_reports.csv |               48 |               72 | True           | False        |               nan |                  nan | False         | 87efc19b47e445aa7d705f8d2e26aece7fefe09a9930dfa6eace637251b66473 | b66d5aed535f94e23ebe3fb98525792b09b709bb44a99d9b154f90a846c52dd4 |
| clean_port_virginia_weekly_metrics.csv  |              384 |              192 | True           | False        |               nan |                  nan | False         | c166ec94072a8a68dbebbb24281b8a77f12d8c28b171331528e40ecf943471df | 768b94d74b6f64fbfbc83a69ad8f94149be9358a6f4879289e9ed3c2ef1fce40 |
| dwelling_activity_counts.csv            |               21 |               20 | True           | False        |               nan |                  nan | False         | 1852fd2dc2c190659436585c726b279e536a62766a1692b979c9b36d21fc6657 | 5a24f16b57394435e3d59a331f228fe7010111a91bf3bbb73c8967529b52bbbb |
| mendeley_capacity_benchmark_summary.csv |               25 |               25 | True           | True         |                 0 |                    0 | True          | 27c4c00a1f25bd6f25571e4f9aca1d24c2882c9c73c45f90e93ae12b8403fd8f | 27c4c00a1f25bd6f25571e4f9aca1d24c2882c9c73c45f90e93ae12b8403fd8f |
| mendeley_tas_benchmark_summary.csv      |               30 |               30 | True           | True         |                 0 |                    0 | True          | 373418e61639f1b7c9752d788fbb24d1115997a8be301ee0326cb9406a366f9f | 373418e61639f1b7c9752d788fbb24d1115997a8be301ee0326cb9406a366f9f |
| public_data_calibrated_scenarios.csv    |                4 |                4 | True           | True         |                24 |                  310 | False         | 165af6d54a3774b7144504a203baface79785a215db882e221584f5d9a729596 | 7bcd57b7aa508e22cff24899afdc384256457485c2ac8d2efd445ade33f862df |
| sc_ports_daily_gate_missions.csv        |                7 |                7 | True           | True         |                13 |                 2033 | False         | 24b99b87add8301dea4bb29fdf85eaef3065eebd2c1f0c81071ec06d632c3adb | 894dd2dcdc2635cdd4935444cf6bf03524ae0c43c5145433578fb1abb951ef9f |
| sc_ports_summary.csv                    |               11 |               11 | True           | True         |                15 |                  636 | False         | 0496edb6f48c949f68aab8fb0b1913a5f257ed678adf792cd02b6490d6d3d9f9 | a7444e045c350eeca7d1d1d7c378fee243b0cd1c7b2d5e25e99e04e6eb23ca6d |

## 校准参数逐项差异

| replay            | scenario           | metric                                |    archived |     replayed |   difference |
|:------------------|:-------------------|:--------------------------------------|------------:|-------------:|-------------:|
| archival_snapshot | sc_low_workload    | source_gate_missions                  | 5961        | 5961         |   0          |
| archival_snapshot | sc_low_workload    | demand_multiplier                     |    0.989213 |    0.989213  |   0          |
| archival_snapshot | sc_low_workload    | mean_requests                         |   22.7519   |   22.7519    |   0          |
| archival_snapshot | sc_low_workload    | missed_reservation_rate_from_virginia |    0.04     |    0.04      |   0          |
| archival_snapshot | sc_low_workload    | yard_utilization_from_houston         |    0.38875  |    0.38875   |   0          |
| archival_snapshot | sc_low_workload    | capacity_disruption_probability       |    0.0611   |    0.0611    |   0          |
| archival_snapshot | sc_median_workload | source_gate_missions                  | 6026        | 6026         |   0          |
| archival_snapshot | sc_median_workload | demand_multiplier                     |    1        |    1         |   0          |
| archival_snapshot | sc_median_workload | mean_requests                         |   23        |   23         |   0          |
| archival_snapshot | sc_median_workload | missed_reservation_rate_from_virginia |    0.04     |    0.04      |   0          |
| archival_snapshot | sc_median_workload | yard_utilization_from_houston         |    0.38875  |    0.38875   |   0          |
| archival_snapshot | sc_median_workload | capacity_disruption_probability       |    0.0611   |    0.0611    |   0          |
| archival_snapshot | sc_high_workload   | source_gate_missions                  | 6401        | 6401         |   0          |
| archival_snapshot | sc_high_workload   | demand_multiplier                     |    1.06223  |    1.06223   |   0          |
| archival_snapshot | sc_high_workload   | mean_requests                         |   24.4313   |   24.4313    |   0          |
| archival_snapshot | sc_high_workload   | missed_reservation_rate_from_virginia |    0.04     |    0.04      |   0          |
| archival_snapshot | sc_high_workload   | yard_utilization_from_houston         |    0.38875  |    0.38875   |   0          |
| archival_snapshot | sc_high_workload   | capacity_disruption_probability       |    0.0611   |    0.0611    |   0          |
| archival_snapshot | sc_peak_workload   | source_gate_missions                  | 6444        | 6444         |   0          |
| archival_snapshot | sc_peak_workload   | demand_multiplier                     |    1.06937  |    1.06937   |   0          |
| archival_snapshot | sc_peak_workload   | mean_requests                         |   24.5954   |   24.5954    |   0          |
| archival_snapshot | sc_peak_workload   | missed_reservation_rate_from_virginia |    0.04     |    0.04      |   0          |
| archival_snapshot | sc_peak_workload   | yard_utilization_from_houston         |    0.38875  |    0.38875   |   0          |
| archival_snapshot | sc_peak_workload   | capacity_disruption_probability       |    0.0611   |    0.0611    |   0          |
| fresh_download    | sc_low_workload    | source_gate_missions                  | 5961        | 5983         |  22          |
| fresh_download    | sc_low_workload    | demand_multiplier                     |    0.989213 |    0.944585  |  -0.0446286  |
| fresh_download    | sc_low_workload    | mean_requests                         |   22.7519   |   21.7254    |  -1.02646    |
| fresh_download    | sc_low_workload    | missed_reservation_rate_from_virginia |    0.04     |    0.04      |   0          |
| fresh_download    | sc_low_workload    | yard_utilization_from_houston         |    0.38875  |    0.373333  |  -0.0154167  |
| fresh_download    | sc_low_workload    | capacity_disruption_probability       |    0.0611   |    0.0598667 |  -0.00123333 |
| fresh_download    | sc_median_workload | source_gate_missions                  | 6026        | 6064         |  38          |
| fresh_download    | sc_median_workload | demand_multiplier                     |    1        |    0.957373  |  -0.0426271  |
| fresh_download    | sc_median_workload | mean_requests                         |   23        |   22.0196    |  -0.980423   |
| fresh_download    | sc_median_workload | missed_reservation_rate_from_virginia |    0.04     |    0.04      |   0          |
| fresh_download    | sc_median_workload | yard_utilization_from_houston         |    0.38875  |    0.373333  |  -0.0154167  |
| fresh_download    | sc_median_workload | capacity_disruption_probability       |    0.0611   |    0.0598667 |  -0.00123333 |
| fresh_download    | sc_high_workload   | source_gate_missions                  | 6401        | 6631         | 230          |
| fresh_download    | sc_high_workload   | demand_multiplier                     |    1.06223  |    1.04689   |  -0.0153405  |
| fresh_download    | sc_high_workload   | mean_requests                         |   24.4313   |   24.0785    |  -0.352832   |
| fresh_download    | sc_high_workload   | missed_reservation_rate_from_virginia |    0.04     |    0.04      |   0          |
| fresh_download    | sc_high_workload   | yard_utilization_from_houston         |    0.38875  |    0.373333  |  -0.0154167  |
| fresh_download    | sc_high_workload   | capacity_disruption_probability       |    0.0611   |    0.0598667 |  -0.00123333 |
| fresh_download    | sc_peak_workload   | source_gate_missions                  | 6444        | 6754         | 310          |
| fresh_download    | sc_peak_workload   | demand_multiplier                     |    1.06937  |    1.06631   |  -0.00305727 |
| fresh_download    | sc_peak_workload   | mean_requests                         |   24.5954   |   24.5251    |  -0.0703172  |
| fresh_download    | sc_peak_workload   | missed_reservation_rate_from_virginia |    0.04     |    0.04      |   0          |
| fresh_download    | sc_peak_workload   | yard_utilization_from_houston         |    0.38875  |    0.373333  |  -0.0154167  |
| fresh_download    | sc_peak_workload   | capacity_disruption_probability       |    0.0611   |    0.0598667 |  -0.00123333 |

## 可复现性表述

论文期留存快照能够重建归档校准结果时，可以声称E0从归档原始快照到校准场景可复现。对于第三方重新下载，应说明滚动数据可能随下载日期变化；下载脚本、日期与SHA-256用于来源核验，而不是保证未来下载得到相同字节。