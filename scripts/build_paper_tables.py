from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results"
OUT = ROOT / "generated" / "paper_tables"


def source(generated_name: str, archived_name: str) -> Path:
    generated = ROOT / "generated" / generated_name
    return generated if generated.exists() else RESULTS / archived_name


def build_table7() -> pd.DataFrame:
    raw = pd.read_csv(source("e1", "e1") / "raw_results.csv")
    policies = ["fixed", "online_joint", "pto"]
    frame = (
        raw[raw["policy"].isin(policies)]
        .groupby("policy", as_index=False)[
            ["mean_composite_cost", "mean_total_wait", "p95_total_wait", "throughput_rate", "acceptance_rate"]
        ]
        .mean()
    )
    order = {name: i for i, name in enumerate(policies)}
    return frame.sort_values("policy", key=lambda s: s.map(order))


def build_table8() -> pd.DataFrame:
    folder = source("table8", "table8")
    path = folder / "adaptive_pto_raw_results.csv"
    if not path.exists():
        path = folder / "raw_results.csv"
    raw = pd.read_csv(path)
    policies = ["pto", "online_fast_only", "online_joint"]
    frame = (
        raw[raw["policy"].isin(policies)]
        .groupby(["scenario", "policy"], as_index=False)[
            ["mean_composite_cost", "p95_total_wait", "tail_net_queue_drift", "unstable"]
        ]
        .mean()
        .rename(columns={"unstable": "threshold_crossing_share"})
    )
    return frame


def build_table9() -> pd.DataFrame:
    folder = source("e2", "e2")
    raw = pd.read_csv(folder / "model_fidelity_raw_results.csv")
    means = (
        raw.groupby(["fidelity_level", "policy"], as_index=False)[["mean_composite_cost", "p95_total_wait"]]
        .mean()
    )
    cost = means.pivot(index="fidelity_level", columns="policy", values="mean_composite_cost")
    p95 = means.pivot(index="fidelity_level", columns="policy", values="p95_total_wait")
    advantages = pd.read_csv(folder / "online_vs_pto_by_fidelity.csv")
    advantages = advantages[advantages["metric"] == "mean_composite_cost"].set_index("fidelity_level")
    levels = ["high_fidelity", "mild_misspecification", "medium_misspecification", "severe_misspecification"]
    rows = []
    for level in levels:
        rows.append(
            {
                "fidelity_level": level,
                "pto_cost": cost.loc[level, "pto"],
                "feedback_cost": cost.loc[level, "online_joint"],
                "pto_p95": p95.loc[level, "pto"],
                "feedback_p95": p95.loc[level, "online_joint"],
                "pto_minus_feedback_cost": advantages.loc[level, "online_advantage"],
                "ci_low": advantages.loc[level, "ci_low"],
                "ci_high": advantages.loc[level, "ci_high"],
            }
        )
    return pd.DataFrame(rows)


def build_table11() -> pd.DataFrame:
    folder = source("e3", "e3")
    path = folder / "W0_current" / "raw_results.csv"
    raw = pd.read_csv(path)
    raw["unconfirmed"] = raw["requested"] - raw["accepted"]
    policies = ["online_joint", "pto"]
    scenarios = ["sc_high_workload", "sc_peak_workload"]
    return (
        raw[raw["policy"].isin(policies) & raw["scenario"].isin(scenarios)]
        .groupby(["scenario", "policy"], as_index=False)[
            ["mean_composite_cost", "acceptance_rate", "throughput_rate", "unconfirmed"]
        ]
        .mean()
    )


def build_table10() -> pd.DataFrame:
    path = ROOT / "generated" / "table10" / "table10_reconstructed.csv"
    if not path.exists():
        raise FileNotFoundError("Run scripts/run_aggregate_diagnostics.py table10 first")
    return pd.read_csv(path)


def build_table12() -> pd.DataFrame:
    path = ROOT / "generated" / "table12" / "table12_reconstructed_ranges.csv"
    if not path.exists():
        raise FileNotFoundError("Run scripts/run_aggregate_diagnostics.py table12 first")
    return pd.read_csv(path)


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    builders = {7: build_table7, 8: build_table8, 9: build_table9, 10: build_table10, 11: build_table11, 12: build_table12}
    for number, builder in builders.items():
        frame = builder()
        frame.to_csv(OUT / f"table_{number}_regenerated.csv", index=False, encoding="utf-8-sig")
        print(f"Table {number}: {len(frame)} rows")
    print("Tables 10 and 12 use the documented independent aggregate reconstruction outputs.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
