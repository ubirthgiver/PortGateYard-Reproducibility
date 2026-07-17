# Completed manuscript reproducibility revisions: audit record

This file preserves the audit trail that motivated the completed manuscript revisions. The current audited source and PDF are `paper/main_snapshot.tex` and `paper/main_snapshot.pdf`; their hashes are recorded in `paper/PAPER_VERSION.md`. Line locators below describe the pre-revision manuscript and are retained only as historical context.

## Overall correction

The pre-revision manuscript understated the reproducibility of E1-E3 and Table 8 while overstating the archive support for Tables 10 and 12. The current snapshot implements the evidence-supported distinction below.

The evidence-supported statement is:

> The vehicle-level E1-E3 experiments and the high-fidelity PTO/feedback-component diagnostic are reproducible from the archived Python source, configurations, deterministic seed rules, processed calibration inputs, and raw replication outputs. Independent reruns matched all common numerical fields exactly. The public source files used for calibration can be downloaded with a SHA-256 manifest, although several historical Port of Virginia snapshots are no longer exposed at their former URLs. The original scripts behind Tables 10 and 12 were not recovered. A separately labelled independent aggregate reconstruction now preserves its code, configurations, seeds, path-level results, and seed-block summaries. It closely reproduces the frozen-PTO instability and the qualitative gain/lateness conclusion, but it is not an exact recovery of every historical table entry.

## Required textual changes

### 1. Vehicle-level simulator — current line 267

Current claim: the original simulator is not retained and its event mechanics cannot be independently verified.

Replace with:

> The archived vehicle-level simulator implements a first-come-first-served discrete-event system. Trucks enter available gate servers, move to the yard queue after gate completion, and then enter available yard servers; residual service times cross decision-window boundaries, and within-window queue areas are accumulated minute by minute. The source code, configurations, deterministic seed rules, and raw replication outputs are included in the reproduction archive. The separate aggregate diagnostics use saturation approximations and must not be pooled numerically with this vehicle-level pipeline.

### 2. Cost normalization — current line 315

Current claim: the exact normalization maps are missing and reported cost cannot be regenerated.

Replace with:

> The archived implementation normalizes the mean gate and yard queues by 20 trucks, yard capacity by the maximum of 10 active units, and quota adjustment by the 18-truck action span. The service-violation term combines a queue-threshold indicator with five times the within-window unconfirmed-request share. The reported vehicle-level weighted costs can therefore be regenerated from the archived source and configurations. They remain normalized performance indices rather than monetary or welfare estimates.

### 3. Tracker execution settings — current line 547

Current claim: coordinate sequence, first pair, ordering, warm-up rule, and coincident-action treatment are unavailable.

Replace with:

> The archived implementation initializes the tracker from the disclosed fixed operating pair, draws the first coordinate from the deterministic policy seed, executes each pair in negative-then-positive order, updates after the positive observation, and applies projection and integer rounding to every executed action. No separate warm-up update rule is used. Coincident actions created by projection or rounding are retained as executed. These details make the reported implementation reproducible but do not establish convergence, stabilization of integer actions, or closed-loop queue stability.

### 4. PTO planning budget and seeds — current line 734

Current claim: the planning budget and seeds are not retained.

Replace with:

> The implemented fixed-pair benchmark enumerates 95 actions: 19 integer appointment quotas from 12 to 30 crossed with five integer yard-capacity levels from 6 to 10. Each candidate is evaluated with four planning samples. Planning seeds are deterministic, and ties are resolved lexicographically by mean simulated cost, quota, and yard capacity. Equation (28a) remains a conditional bound rather than a finite-sample confidence guarantee because no concentration radius is estimated.

### 5. Table 6 — current lines 889-904

Delete the table titled “Vehicle-level implementation items not retained in the present archive.” Its entries are no longer factually correct.

Replace it with an artifact inventory containing:

- cost normalization: source lines and weights available;
- access history: six-window request mean; empty-history initialization is the fixed quota 25;
- tracker: seeded random coordinate, negative-positive order, update after the positive member;
- feedback initializer: physical pair `(25,8)`, normalized center `(13/18, 1/2)`;
- fixed baseline: `(25,8)`;
- PTO search: 95 candidates, four planning samples, lexicographic tie-break;
- scenario and policy seeds: deterministic formulas disclosed in `REPRODUCE.md`;
- raw outputs: E1, E2, E3, and Table 8 replication files included.

Tables 10 and 12 should appear separately as independently reconstructed aggregate diagnostics, not as recovered vehicle-level outputs. The text must not state that their historical entries were exactly regenerated.

### 6. Feedback initializer — current lines 883 and 910

Current claim: the vehicle-level initializer is unavailable or unrecovered.

Replace with:

> The vehicle-level fast-only and fast-plus-tracker policies initialize from the fixed operating pair `(25,8)`, corresponding to the normalized center `z^0=(13/18,1/2)`. The separate aggregate diagnostics use their own stated reference center and are not used to infer the vehicle-level initializer. Robustness to alternative vehicle-level starting centers has not been tested.

### 7. Table 8 note — current line 962

Current claim: raw replication outputs and the initializer are unavailable.

Replace with:

> P95 denotes the 95th percentile. The table reports means over 50 replications. Raw replication outputs, deterministic seeds, and the feedback initializer are included in the reproduction archive; an independent rerun reproduced all 600 policy-replication rows exactly. The diagnostic is high-fidelity and is not a matched fast-only ablation of the E2 misspecification path.

### 8. E2 initializer sentence — current line 971

Delete: “Its unavailable initializer prevents a sensitivity analysis of the feedback starting point.”

Replace with:

> The feedback reference starts from the archived vehicle-level center `(25,8)` and is held fixed across fidelity levels. Sensitivity to alternative feedback starting centers was not evaluated.

### 9. Extreme-P95 treatment — current line 1001

Current claim: the drain and censoring rules cannot be audited.

Replace with:

> After the 30-day arrival horizon, the simulator drains the system for at most two additional days. Waiting statistics use completed trucks that arrived after the seven-day warm-up and before the end of the arrival horizon; trucks unfinished at the drain limit are excluded from the waiting quantile and reported separately through terminal backlog and truncation indicators. The extreme E2 P95 values are therefore auditable stress statistics, but they may understate the unfinished tail and must not be interpreted as ordinary port service-level estimates.

### 10. Fast-only E2 limitation — current line 1120

Current wording incorrectly calls the E2 pipeline unavailable.

Replace with:

> The archived E2 pipeline did not include a fast-only arm. The reported E2 feedback result therefore belongs to fast-plus-tracker feedback, and the current evidence does not provide a matched fast-only ablation on the original misspecification path.

### 11. Conclusion limitation — current line 1142

Replace the claim that E1-E3 lack source, seeds, normalization, and raw outputs with:

> The main limitations concern evidence scope rather than loss of the vehicle-level implementation. Aggregate public records discipline the scenarios but do not provide a linked vehicle-level appointment-arrival-gate-yard trajectory. E1-E3 and the high-fidelity component diagnostic are reproducible from the archived source and outputs, but E2 does not contain a matched fast-only arm or initializer sensitivity analysis. In addition, the generating scripts and raw outputs for the separate aggregate diagnostics in Tables 10 and 12 have not been recovered. A submission-grade extension should place all diagnostics in one documented pipeline, compare fast-only and fast-plus-tracker feedback with adaptive time-varying PTO under bidirectional errors, and add a controlled gate-only-versus-joint-authority ablation.

### 12. Data Availability — current line 1146

The current statement reverses the actual archive status. Replace it entirely with:

> **Data and code availability.** The reproduction archive contains the Python source for the vehicle-level gate-yard simulator, experiment configurations, deterministic seed rules, the fixed-pair PTO candidate set and planning budget, processed public-data calibration inputs, raw replication outputs, and table-generation scripts for E1-E3 and the high-fidelity PTO/feedback-component diagnostic. Independent reruns reproduced the archived E1, E2, E3, and Table 8 numerical outputs exactly. The archive also records the post-horizon drain and unfinished-job treatment used for waiting statistics. Raw third-party public files are not redistributed and remain subject to provider access and licensing terms; source locations and transformations are documented, so E0 is reproducible from the processed inputs but requires re-download for a raw-source replay. The separate aggregate values reported in Tables 10 and 12 are included as reported records only: their original generating scripts and raw JSON outputs have not been recovered and those diagnostics are not independently reproducible from the current archive.

## Statements that should remain

The following limitations remain correct and should not be weakened:

- public-data-calibrated simulation is not terminal-specific field validation;
- E2 is a fixed-pair no-reidentification stress test, not proof that feedback dominates promptly updated PTO;
- the original E2 comparison belongs to fast-plus-tracker feedback, not fast-only feedback;
- normalized cost is not money or social welfare;
- the aggregate diagnostics must not be pooled numerically with the vehicle-level pipeline;
- no asymptotic convergence or closed-loop stability theorem is established for the tracker.
