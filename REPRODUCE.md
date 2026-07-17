# Reproduction instructions

## 1. Environment

The audited environment is recorded in `environment.txt`. Python 3.10 or newer is supported; the exact audit used Python 3.12.13.

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest -q
```

Expected test result: `11 passed`.

## 2. Rebuild manuscript tables from archived raw outputs

This is the quickest audit and does not rerun the simulations:

```powershell
.venv\Scripts\python.exe scripts\build_paper_tables.py
```

It generates Tables 7, 8, 9, and 11 under `generated/paper_tables/`. The historical Tables 10 and 12 cannot be regenerated from their lost original scripts; a separately labelled independent reconstruction is documented below.

## 3. Rerun the vehicle-level experiments

### E1 / Table 7

```powershell
.venv\Scripts\python.exe scripts\reproduce.py e1
```

Design: four public-data-calibrated workload scenarios, four policies, 50 replications, 30 days, seven-day warm-up.

### E2 / Table 9

```powershell
.venv\Scripts\python.exe scripts\reproduce.py e2
```

Design: 95 fixed-pair candidates, four fidelity levels, four planning samples per candidate, and 50 out-of-sample evaluation replications. The deterministic tie-break is lexicographic in `(mean cost, quota, yard capacity)`.

### E3 / Table 11

```powershell
.venv\Scripts\python.exe scripts\reproduce.py e3
```

Design: high and peak calibrated workloads, three access-loss weight vectors, four policies, and 12 replications.

### Table 8 diagnostic

```powershell
.venv\Scripts\python.exe scripts\reproduce.py table8
```

Design: high and peak calibrated workloads, fixed-pair PTO, slow and fast rolling PTO, fast-only feedback, fast-plus-tracker feedback, fixed rule, and 50 replications.

## 4. Randomization

For the vehicle-level comparisons:

```text
scenario_seed = 10000 * (scenario_index + 1) + replication
policy_seed   = scenario_seed + 100000 * (policy_index + 1)
```

Competing policies share the same scenario-level requests, appearance outcomes, service times, exception arrivals, and disruption paths. Policy-specific randomization is deterministic.

E2 planning samples use:

```text
model_seed = 70000 + 10000 * scenario_index + 1000 * fidelity_index + sample
policy_seed = 91000 + sample
```

## 5. Waiting-time and unfinished-job rule

The 30-day arrival horizon is followed by a drain period of at most two days. Waiting statistics include completed trucks whose arrivals fall after the seven-day warm-up and before the end of the arrival horizon. Trucks still unfinished after the two-day drain are excluded from the waiting quantile and separately reported as `uncompleted_at_drain_limit`, `terminal_system`, and `drain_truncated`.

Consequently, the extreme E2 P95 values are stress-regime diagnostics and may understate the unfinished tail; they must not be interpreted as ordinary port turn-time estimates.

## 6. Raw third-party data

The package contains processed calibration inputs. The download command below retrieves the currently available files listed in `data/SOURCES.csv` and records a SHA-256 manifest. Redistribution rights remain with the source providers.

### Download public source files

```powershell
python scripts/download_public_data.py --overwrite
```

The SHA-256 download record is written to `data/raw/download_manifest.csv`.

## 7. Independent aggregate reconstructions (Tables 10 and 12)

```powershell
python scripts/run_aggregate_diagnostics.py all --output generated
```

This command writes path-level results, seed-block summaries, configurations,
the reconstructed Table 10/12 files, and a reported-versus-reconstructed
comparison report. These are documented independent reconstructions, not the
lost original scripts that produced the historical table entries.

## 8. Audit the E0 raw-source chain

```powershell
python scripts/verify_e0_raw_replay.py --output generated/e0_raw_replay
```

The audit performs two replays. The retained paper-date snapshot must reproduce
the eight archived E0 outputs and all 24 scenario parameters exactly. A second
replay uses current live downloads to quantify date-driven changes in rolling
port dashboards. Live files are not expected to remain byte-identical to the
paper-date snapshot.
