# Port gate–yard workload correction: reproducibility package

This repository accompanies the manuscript **“Predictive Planning with Workload-Responsive Correction for Port Gate–Yard Coordination.”** It contains the vehicle-level discrete-event simulator, aggregate diagnostic model, experiment configurations, deterministic seed rules, processed public-data calibration inputs, archived replication outputs, tests, and table-generation scripts.

## Evidence status

| Paper block | Reproducibility status |
|---|---|
| E0 calibration | Exact raw-to-processed replay from the retained paper-date snapshot; live downloads are date-sensitive |
| E1 / Table 7 | Exact: 800 rows matched |
| Table 8 | Exact: 600 rows matched |
| E2 / Table 9 | Exact: 400 rows and selected PTO actions matched |
| E3 / Table 11 | Exact: 288 rows matched |
| Table 10 / Figure 3 | Documented independent aggregate reconstruction; not an exact recovery of the historical script |
| Table 12 | Documented independent aggregate reconstruction; not an exact recovery of the historical script |

The current manuscript should use the reconstructed Table 10, Table 12, and Figure 3 values under `generated/`. Historical entries are retained under `results/reported_only/` only for provenance and must not be presented as current reproducible results.

## Quick start

Windows PowerShell:

```powershell
python -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -r requirements.txt
.venv\Scripts\python.exe -m pytest -q
```

Linux or macOS:

```bash
python -m venv .venv
.venv/bin/python -m pip install --upgrade pip
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python -m pytest -q
```

Expected test result: `11 passed`.

## Reproduce the experiments

```powershell
# Exact vehicle-level experiment blocks
.venv\Scripts\python.exe scripts\reproduce.py e1
.venv\Scripts\python.exe scripts\reproduce.py e2
.venv\Scripts\python.exe scripts\reproduce.py e3
.venv\Scripts\python.exe scripts\reproduce.py table8

# Documented aggregate reconstructions
.venv\Scripts\python.exe scripts\run_aggregate_diagnostics.py all --output generated

# Rebuild paper tables from archived results
.venv\Scripts\python.exe scripts\build_paper_tables.py
```

Full vehicle-level runs use 30 simulated days and can take several minutes. The aggregate Table 10/12 reconstruction takes less than one minute on the audited machine.

## Repository map

- `src/port_queue/`: vehicle-level DES, policies, aggregate diagnostics, fidelity experiment, and calibration functions;
- `scripts/`: reproduction, data-download, audit, plotting, and table-building entry points;
- `configs/`: disclosed experiment and reconstruction settings;
- `tests/`: conservation, FCFS, reproducibility, projection, fidelity, and aggregate-diagnostic tests;
- `data/processed/`: paper-date calibration inputs used by the simulations;
- `results/`: archived exact vehicle-level outputs and historical provenance records;
- `generated/table10/`, `generated/table12/`: current reproducible aggregate reconstruction outputs;
- `generated/e0_raw_replay/`: raw-source audit comparisons without redistributed source files;
- `paper/`: audited manuscript snapshot and source hash record.

## Data policy

Third-party raw port reports and benchmark archives are not committed. `data/SOURCES.csv` records their sources and roles; `scripts/download_public_data.py` downloads currently available files and writes `data/raw/download_manifest.csv` with dates, sizes, and SHA-256 hashes. Public dashboards roll forward, so a future download is not expected to reproduce the paper-date bytes.

The retained paper-date snapshot reproduced all eight archived E0 outputs and all 24 scenario parameters exactly. Whether that snapshot can be redistributed with the public repository depends on the source licences. Processed calibration files needed by the experiments are included.

## Evidence boundaries

This is a public-data-calibrated simulation study, not vehicle-level field validation or a causal evaluation of an implemented port policy. E2 is a fixed-pair no-reidentification stress test, not evidence that feedback dominates promptly updated PTO. Tables 10 and 12 use a separately documented aggregate pipeline and are not pooled numerically with the vehicle-level E2 results.

See `REPRODUCE.md`, `REPRODUCIBILITY_STATUS.md`, `MANIFEST.csv`, and `AUDIT_REPORT.md` for the complete evidence map.

## Licence

The software and original repository materials are released under the MIT License; see `LICENSE`. Third-party data remain governed by their source licences and are not relicensed by the repository's MIT License.
