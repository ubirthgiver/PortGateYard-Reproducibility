# Reproducibility status

Authoritative paper audited: `Lijunjipaper1 (2).pdf`, SHA-256 `0FA27B97AF6FE3D5446E98D7091BB790378CE280061E03F5B02F1BD8B1C662F8`.

| Paper block | Evidence status | Audit result | Remaining limitation |
|---|---|---|---|
| E0 calibration | Exact from the retained paper-date snapshot; date-sensitive from live downloads | All eight archived E0 outputs and all 24 scenario parameters were regenerated exactly from the 2026-07-09 retained snapshot | Preserve the paper-date input hashes/snapshots; live public dashboards roll forward and are not expected to remain byte-identical |
| E1 / Table 7 | Reproducible | 800 rows matched exactly; maximum numerical difference 0 | Evidence remains public-data-calibrated simulation, not field validation |
| E2 / Table 9 | Reproducible | 400 evaluation rows matched exactly; 95-candidate action-search output and selected actions matched | It remains a no-reidentification fixed-pair stress test, not a same-information comparison with adaptive PTO |
| E3 / Table 11 | Reproducible | 288 rows across three weight sets matched exactly | Only 12 replications; access valuation is normalized, not monetary |
| Table 8 | Reproducible | The underlying six-policy run contains 600 rows and matched exactly; the paper reports the PTO, fast-only, and fast-plus-tracker subset | This high-fidelity component diagnostic is not a matched fast-only E2 misspecification ablation |
| Table 10 / Figure 3 | Original values not exactly reproducible; independent reconstruction available | The lost original script/raw JSON were not recovered. The documented v2 reconstruction closely matches frozen-PTO instability and feedback ordering, but not every re-identification cost | Use `generated/table10/` and describe the result as independent mechanism reconstruction, not exact recovery |
| Table 12 | Original ranges not exactly reproducible; independent reconstruction available | The documented v2 reconstruction reproduces the bounded/no-reversal sensitivity conclusion with nearby, non-identical ranges | Use `generated/table12/` and disclose the independent reconstruction status |

## Exact checks already completed

- E1: all reported metrics reproduced; only machine-level floating representation below `1e-15` was observed in an earlier comparison, and the packaged audit now reports zero numerical difference on common numeric columns.
- E2: selected pairs are high `(20,8)`, mild `(23,8)`, medium `(28,7)`, and severe `(30,6)`; the common 37 raw columns and all paper-driving metrics match exactly.
- E3: `weight_sensitivity_summary.csv` and `pto_vs_online_by_weight.csv` were regenerated exactly.
- Table 8: all 600 raw policy-replication rows match exactly.

The archived E0 snapshot, E1-E3, and Table 8 are exactly reproducible. Tables 10 and 12 have documented independent reconstructions but are not exact recoveries of their historical entries. The manuscript must distinguish those two evidence statuses.
