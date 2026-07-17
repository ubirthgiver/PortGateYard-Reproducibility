# Reproducibility package changelog

## 2026-07-17

- Independently reran E1, E2, E3, and the Table 8 diagnostic; all common archived numerical fields matched exactly.
- Re-downloaded 16 currently available public source files and recorded URL, timestamp, byte count, and SHA-256.
- Replayed E0 from the retained paper-date raw snapshot; eight processed outputs and 24 scenario parameters matched exactly.
- Added documented aggregate reconstruction scripts for Table 10 and Table 12 with configurations, deterministic seed blocks, path-level results, tests, and a reconstructed Figure 3.
- Preserved the historical Table 10/12 entries under `results/reported_only/` as provenance records. They are not the current reproducible result set.
- Updated the evidence statements to distinguish exact vehicle-level reruns, exact paper-date E0 replay, and independent aggregate reconstructions.

## Historical materials

The original scripts that produced the superseded historical Table 10 and Table 12 entries were not recovered. The manuscript must use the current reconstructed values if it claims those tables are reproducible from this repository.
