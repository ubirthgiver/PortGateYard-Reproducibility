# Data layout

`processed/` contains the paper-date calibration inputs needed to reproduce the simulation scenarios used by E1-E3 and Table 8.

Raw public files are intentionally excluded from Git. `raw/download_manifest.csv` records the files downloaded during the 2026-07-17 source audit. For a raw-source replay, create the following directories and download the corresponding sources listed in `SOURCES.csv`:

```text
data/raw/sc_ports/
data/raw/port_virginia_weekly_metrics/
data/raw/port_houston_terminal_reports/
data/raw/mendeley_tas_tours/
data/raw/mendeley_capacity_management/
data/raw/mendeley_dwelling_time/
```

Data status must be described as **public-data-calibrated**. These files do not provide a linked vehicle-level appointment-arrival-gate-yard trajectory and therefore do not constitute vehicle-level field validation.

The public dashboards are date-sensitive. The retained 2026-07-09 paper snapshot exactly regenerated all eight archived E0 outputs and all 24 scenario parameters. A 2026-07-17 live replay produced updated SC Ports, Virginia, and Houston records, while the TAS and capacity benchmark summaries remained exact. Future downloads should be treated as source updates, not silent replacements for the paper-date snapshot.
