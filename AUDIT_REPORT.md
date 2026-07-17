# Reproducibility audit report

## Outcome

The vehicle-level core of the paper is reproducible. Fresh reruns from the archived source reproduced E1, E2, E3, and the high-fidelity six-policy component diagnostic. All common numerical output fields matched the archived results exactly.

| Block | Rows checked | Maximum numerical difference | Verdict |
|---|---:|---:|---|
| E0 paper-date raw replay | 8 output files; 24 scenario parameters | 0 | Exact from retained snapshot |
| E1 | 800 | 0 | Exact |
| E2 | 400 | 0 | Exact |
| E3 | 288 | 0 | Exact |
| Table 8 | 600 | 0 | Exact |
| Table 10 | 2,800 reconstructed paths | Historical entries differ in part | Independent reconstruction v2; original script missing |
| Table 12 | 6,400 reconstructed paths | Nearby, non-identical ranges | Independent reconstruction v2; original script missing |

The test suite reports `11 passed`.

## E2 planning audit

The exhaustive fixed-pair candidate set contains 95 actions. The reproduced selected actions are:

| PTO belief | Quota | Yard capacity |
|---|---:|---:|
| High fidelity | 20 | 8 |
| Mild misspecification | 23 | 8 |
| Medium misspecification | 28 | 7 |
| Severe misspecification | 30 | 6 |

The selected-action search, evaluation results, and paired cost intervals reproduce the paper's Table 9 values.

## Correct evidence label

The experiments are public-data-calibrated simulations. Public records determine or discipline selected demand, compliance, utilization, and disruption proxies, while the code supplies a synthetic vehicle-level event process where public records are silent. This is stronger than an uncalibrated synthetic example but weaker than vehicle-level field validation.

## Remaining blockers

1. The original aggregate severe-error script and raw JSON outputs behind the historical Table 10/Figure 3 were not found. The current Table 10 branch imposes an overloaded pair and activates a prespecified quota-recovery rule; it does not estimate capacity or re-solve PTO.
2. The original gain-lateness diagnostic script and raw JSON outputs behind Table 12 were not found.
3. Sixteen currently available third-party public files were downloaded again and recorded in `data/raw/download_manifest.csv`. Live dashboard exports are date-sensitive, and several older Port of Virginia snapshots are no longer available from their former direct URLs; the paper-date snapshot or its hashes must therefore be preserved.
4. E2 did not contain a fast-only arm; Table 8 is not a matched fast-only E2 ablation.

The manuscript may claim exact raw-to-processed reproducibility for E0 from the retained paper-date snapshot and exact reproducibility for E1-E3 and Table 8. Tables 10 and 12 should be labelled documented independent reconstructions rather than exact recoveries of their historical entries.
