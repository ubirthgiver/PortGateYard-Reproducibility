from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]


def max_numeric_difference(left: Path, right: Path, keys: list[str]) -> tuple[int, float]:
    a = pd.read_csv(left)
    b = pd.read_csv(right)
    common = [c for c in a.columns if c in b.columns]
    numeric = [c for c in common if c not in keys and pd.api.types.is_numeric_dtype(a[c])]
    merged = a[keys + numeric].merge(b[keys + numeric], on=keys, suffixes=("_a", "_b"), validate="one_to_one")
    values = []
    for column in numeric:
        delta = np.abs(merged[f"{column}_a"] - merged[f"{column}_b"])
        values.append(float(np.nanmax(delta)) if len(delta) else 0.0)
    return len(merged), max(values, default=0.0)


def main() -> int:
    rows = []
    checks = [
        (
            "E1",
            ROOT / "results" / "e1" / "raw_results.csv",
            ROOT / "generated" / "e1" / "raw_results.csv",
            ["scenario", "policy", "replication"],
        ),
        (
            "E2",
            ROOT / "results" / "e2" / "model_fidelity_raw_results.csv",
            ROOT / "generated" / "e2" / "model_fidelity_raw_results.csv",
            ["scenario", "fidelity_level", "policy", "replication"],
        ),
        (
            "E3",
            ROOT / "results" / "e3" / "raw_results.csv",
            ROOT / "generated" / "e3" / "raw_results.csv",
            ["weight_set", "scenario", "policy", "replication"],
        ),
        (
            "Table 8",
            ROOT / "results" / "table8" / "adaptive_pto_raw_results.csv",
            ROOT / "generated" / "table8" / "adaptive_pto_raw_results.csv",
            ["scenario", "policy", "replication"],
        ),
    ]
    for name, archived, rerun, keys in checks:
        if not rerun.exists():
            rows.append(
                {
                    "experiment": name,
                    "matched_rows": 0,
                    "maximum_numeric_difference": np.nan,
                    "status": "not_rerun_in_this_clone",
                }
            )
            continue
        matched, difference = max_numeric_difference(archived, rerun, keys)
        rows.append(
            {
                "experiment": name,
                "matched_rows": matched,
                "maximum_numeric_difference": difference,
                "status": "exact" if difference <= 1e-12 else "different",
            }
        )
    rows.extend(
        [
            {"experiment": "Table 10", "matched_rows": 0, "maximum_numeric_difference": np.nan, "status": "script_missing"},
            {"experiment": "Table 12", "matched_rows": 0, "maximum_numeric_difference": np.nan, "status": "script_missing"},
        ]
    )
    out = ROOT / "generated" / "rerun_comparison.csv"
    out.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(out, index=False, encoding="utf-8-sig")
    print(pd.DataFrame(rows).to_string(index=False))
    allowed = ("exact", "script_missing", "not_rerun_in_this_clone")
    return 0 if all(row["status"] in allowed for row in rows) else 1


if __name__ == "__main__":
    raise SystemExit(main())
