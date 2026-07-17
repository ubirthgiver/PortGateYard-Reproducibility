# Raw public-data download record

The files in this directory were downloaded again from the public sources on
2026-07-17 (Asia/Shanghai). Run:

```powershell
python scripts/download_public_data.py --overwrite
```

`download_manifest.csv` records the source URL, byte count, SHA-256 digest,
download time, and validation status for every file. The three Mendeley ZIP
archives pass a complete ZIP integrity test. PDF and CSV file signatures are
validated by the downloader.

## Coverage

- SC Ports: seven current metrics CSV files.
- Port of Virginia: two discoverable 2023 weekly reports and the current
  2026-07-12 weekly report.
- Port Houston: three 2026 terminal-status reports.
- Mendeley Data: TAS tours, container-terminal capacity-management instances,
  and the container-dwelling event log.

Four previously cached Port of Virginia snapshots from 2025--2026 are retained
elsewhere in the project because their former direct URLs now return 404 and
the site does not currently expose a downloadable archive for those dates.
They must not be described as newly downloaded in this run.

These sources calibrate workload, reservation compliance, yard pressure,
disruption, and process plausibility. They are not a complete vehicle-level
appointment--arrival--gate--yard trajectory dataset.
