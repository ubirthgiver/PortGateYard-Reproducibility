from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, replace
from pathlib import Path

import numpy as np
import pandas as pd

from port_queue.config import ScenarioConfig, SimulationConfig, load_config
from port_queue.experiment import _bootstrap_ci, run_experiments


PUBLIC_SCENARIO_FILE = Path("data/processed/public_data_calibrated_scenarios.csv")
DEFAULT_POLICIES = (
    "fixed",
    "pto",
    "pto_adaptive_slow",
    "pto_adaptive_fast",
    "online_fast_only",
    "online_joint",
)


def scenario_from_public_row(config: SimulationConfig, row: pd.Series) -> ScenarioConfig:
    missed_rate = float(np.clip(row.get("missed_reservation_rate_from_virginia", 0.04), 0.0, 0.35))
    shown = 1.0 - missed_rate
    return ScenarioConfig(
        name=str(row["scenario"]),
        mean_requests=float(row["mean_requests"]),
        show_probabilities=(0.82 * shown, 0.12 * shown, 0.06 * shown, missed_rate),
        exception_arrival_mean=config.exception_arrival_mean,
        arrival_shock_probability=config.arrival_shock_probability,
        arrival_shock_multiplier=config.arrival_shock_multiplier,
        normalize_arrival_shocks=True,
        capacity_disruption_probability=float(row.get("capacity_disruption_probability", config.capacity_disruption_probability)),
        gate_service_cv=config.gate_service_cv,
        yard_service_cv=config.yard_service_cv,
        description=str(row.get("description", "")),
    )


def load_public_scenarios(config: SimulationConfig) -> dict[str, ScenarioConfig]:
    if not PUBLIC_SCENARIO_FILE.exists():
        raise FileNotFoundError(
            f"Missing {PUBLIC_SCENARIO_FILE}. Run public-data calibration before repair experiments."
        )
    frame = pd.read_csv(PUBLIC_SCENARIO_FILE)
    return {str(row["scenario"]): scenario_from_public_row(config, row) for _, row in frame.iterrows()}


def paired_delta(raw: pd.DataFrame, metric: str, baseline: str, target: str, samples: int = 1000) -> dict[str, object]:
    rows = []
    for scenario, group in raw.groupby("scenario", sort=False):
        pivot = group.pivot(index="replication", columns="policy", values=metric).dropna()
        if baseline not in pivot or target not in pivot:
            continue
        diff = pivot[baseline].to_numpy(dtype=float) - pivot[target].to_numpy(dtype=float)
        low, high = _bootstrap_ci(diff, samples=samples, seed=8107)
        rows.append(
            {
                "scenario": scenario,
                "metric": metric,
                "baseline": baseline,
                "target": target,
                "baseline_mean": float(pivot[baseline].mean()),
                "target_mean": float(pivot[target].mean()),
                "baseline_minus_target": float(diff.mean()),
                "ci_low": low,
                "ci_high": high,
                "target_better_if_lower": bool(low > 0),
            }
        )
    return rows


def write_plots(root: Path, raw: pd.DataFrame) -> list[Path]:
    os.environ.setdefault("MPLCONFIGDIR", str(root / ".matplotlib"))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plot_dir = root / "figures"
    plot_dir.mkdir(parents=True, exist_ok=True)
    created: list[Path] = []
    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    policy_order = list(DEFAULT_POLICIES)
    for metric, filename, ylabel, logy in [
        ("mean_composite_cost", "adaptive_pto_cost.png", "Mean composite cost", False),
        ("p95_total_wait", "adaptive_pto_p95_wait_log.png", "P95 total wait (minutes)", True),
        ("tail_net_queue_drift", "tail_queue_drift.png", "Tail net queue drift", False),
        ("service_floor_binding_rate", "service_floor_binding.png", "Service-floor binding rate", False),
    ]:
        summary = raw.groupby(["scenario", "policy"], as_index=False)[metric].mean()
        pivot = summary.pivot_table(index="scenario", columns="policy", values=metric, aggfunc="mean")
        pivot = pivot[[p for p in policy_order if p in pivot.columns]]
        fig, ax = plt.subplots(figsize=(12, 5.5))
        pivot.plot(kind="bar", ax=ax, logy=logy)
        ax.set_ylabel(ylabel)
        ax.grid(axis="y", alpha=0.25)
        ax.tick_params(axis="x", rotation=15)
        ax.legend(loc="best", fontsize=8)
        fig.tight_layout()
        path = plot_dir / filename
        fig.savefig(path, dpi=180, bbox_inches="tight")
        plt.close(fig)
        created.append(path)
    return created


def write_parameter_disclosure(config: SimulationConfig, root: Path) -> Path:
    path = root / "parameter_disclosure.json"
    payload = asdict(config)
    payload["derived"] = {
        "periods": config.periods,
        "warmup_periods": config.warmup_periods,
        "random_seed_rule": "scenario_seed = 10000*(scenario_index+1)+replication; policy_seed = scenario_seed + 100000*(policy_index+1)",
        "new_policy_update_intervals": {
            "pto_adaptive_slow": "48 decision windows (24 hours at 30-minute slots), rolling window 144",
            "pto_adaptive_fast": "6 decision windows (3 hours at 30-minute slots), rolling window 48",
            "online_fast_only": "fast queue feedback only; slow adaptive center frozen",
            "online_joint": "fast queue feedback plus two-point slow adaptive center",
        },
    }
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def write_data_source_table(root: Path) -> Path:
    rows = [
        {
            "source": "SC Ports public dashboard files",
            "local_files": "data/sc_ports/*.csv",
            "variables_used": "gate transactions, turn times, pier moves, crane productivity",
            "role": "calibrate demand intensity and operational workload ranges",
        },
        {
            "source": "Port Virginia weekly metrics",
            "local_files": "data/port_virginia_weekly_metrics/*.pdf",
            "variables_used": "gate transactions, reservation behavior, turn-time indicators",
            "role": "calibrate missed-reservation/compliance and transaction regimes",
        },
        {
            "source": "Port Houston terminal reports",
            "local_files": "data/port_houston_terminal_reports/*.pdf",
            "variables_used": "terminal status, operational delay and yard-condition indicators",
            "role": "calibrate disruption and yard-pressure regimes",
        },
        {
            "source": "Mendeley TAS/tour and capacity-management datasets",
            "local_files": "data/mendeley_*",
            "variables_used": "appointment/tour benchmarks and terminal capacity instances",
            "role": "benchmark queueing and capacity-management ranges",
        },
    ]
    path = root / "data_source_table.csv"
    pd.DataFrame(rows).to_csv(path, index=False, encoding="utf-8-sig")
    return path


def write_data_availability_statement(root: Path) -> Path:
    text = """# Draft Data Availability Statement

This study uses public port operational records and public benchmark datasets to calibrate the simulation regimes. The processed calibration files, configuration files, random seeds, scripts, and generated result tables required to reproduce the reported computational experiments are included in the reproducibility package. Raw third-party source files remain subject to the access terms and availability conditions of the original data providers.
"""
    path = root / "DATA_AVAILABILITY_STATEMENT.md"
    path.write_text(text, encoding="utf-8")
    return path


def write_repro_readme(root: Path, config_path: str, replications: int) -> Path:
    text = f"""# Reproducibility package

## Purpose

This folder is the repair-stage reproducibility package for the OCMA manuscript. It verifies the remaining methodological risks raised in the review notes:

1. whether the reported results can be regenerated from code, fixed parameters, and seeds;
2. whether extreme P95 waits correspond to unstable stress regimes rather than ordinary port performance;
3. whether workload feedback still has value after adding adaptive/rolling PTO benchmarks;
4. whether the fast feedback layer and the full fast+slow online policy differ empirically;
5. whether service-floor and projection constraints bind in the numerical experiments.

## Main command

```powershell
& .\\.venv\\Scripts\\python.exe scripts\\run_repair_experiments.py --config {config_path} --output {root.as_posix()} --replications {replications}
```

## Seeds

The experiment uses common random numbers across policies:

- `scenario_seed = 10000*(scenario_index+1)+replication`
- `policy_seed = scenario_seed + 100000*(policy_index+1)`

## Key output files

- `adaptive_pto_raw_results.csv`
- `adaptive_pto_summary_results.csv`
- `adaptive_pto_pairwise_deltas.csv`
- `p95_instability_diagnostics.csv`
- `floor_safety_diagnostics.csv`
- `parameter_disclosure.json`
- `data_source_table.csv`
- `repair_experiment_report.md`
"""
    path = root / "README_reproducibility.md"
    path.write_text(text, encoding="utf-8")
    return path


def write_report(root: Path, raw: pd.DataFrame, pairwise: pd.DataFrame, p95_diag: pd.DataFrame, safety: pd.DataFrame) -> Path:
    policy_means = raw.groupby(["scenario", "policy"], as_index=False)[
        [
            "mean_composite_cost",
            "mean_total_wait",
            "p95_total_wait",
            "throughput_rate",
            "acceptance_rate",
            "unstable",
            "terminal_system",
            "uncompleted_at_drain_limit",
        ]
    ].mean()
    lines = [
        "# 修理阶段实验报告",
        "",
        "## 这次修了什么",
        "",
        "- 增加 24-hour 与 3-hour rolling-surrogate PTO：内部标识为 `pto_adaptive_slow` 与 `pto_adaptive_fast`；二者均不更新服务能力。",
        "- 增加 fast-only 消融：`online_fast_only`，用于对比完整 `online_joint`。",
        "- 在 summary 中加入 P95 极端值、终端积压、drain 截断、队列漂移、安全下限绑定和投影绑定诊断。",
        "- 落盘参数、种子、数据来源表和 Data Availability Statement 草稿。",
        "",
        "## 策略均值",
        "",
        policy_means.to_markdown(index=False),
        "",
        "## Rolling-surrogate PTO / 反馈消融配对对比",
        "",
        pairwise.to_markdown(index=False),
        "",
        "## P95 与失稳诊断",
        "",
        p95_diag.to_markdown(index=False),
        "",
        "解释口径：如果 `drain_truncated`、`uncompleted_at_drain_limit`、`tail_net_queue_drift` 或 `terminal_system` 较高，则对应 P95 应解释为 unstable stress regime，而不是普通港口 turn-time 指标。",
        "",
        "## Floor-safety / projection 诊断",
        "",
        safety.to_markdown(index=False),
        "",
        "解释口径：Prop. 4 是条件命题。若服务下限或投影频繁绑定，正文应报告这些绑定频率，并避免声称反馈动作总能无约束降低漂移。",
        "",
        "## 图表",
        "",
        "- `figures/adaptive_pto_cost.png`",
        "- `figures/adaptive_pto_p95_wait_log.png`",
        "- `figures/tail_queue_drift.png`",
        "- `figures/service_floor_binding.png`",
    ]
    path = root / "repair_experiment_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="configs/fidelity.json")
    parser.add_argument("--output", default="outputs/repair_20260712")
    parser.add_argument("--replications", type=int, default=8)
    parser.add_argument("--scenarios", nargs="*", default=["sc_high_workload", "sc_peak_workload"])
    args = parser.parse_args()

    base = load_config(args.config)
    public = load_public_scenarios(base)
    scenarios = tuple(public[name] for name in args.scenarios if name in public)
    if not scenarios:
        raise ValueError(f"No requested scenarios found in {PUBLIC_SCENARIO_FILE}: {args.scenarios}")
    config = replace(base, scenarios=scenarios, replications=args.replications, bootstrap_samples=1000)

    root = Path(args.output)
    root.mkdir(parents=True, exist_ok=True)
    raw, summary = run_experiments(
        config,
        root,
        replications=args.replications,
        keep_example_trajectories=True,
        policy_names=DEFAULT_POLICIES,
    )
    raw.to_csv(root / "adaptive_pto_raw_results.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(root / "adaptive_pto_summary_results.csv", index=False, encoding="utf-8-sig")

    rows = []
    for metric in ["mean_composite_cost", "p95_total_wait", "tail_net_queue_drift", "unstable"]:
        rows.extend(paired_delta(raw, metric, "pto", "online_joint"))
        rows.extend(paired_delta(raw, metric, "pto_adaptive_slow", "online_joint"))
        rows.extend(paired_delta(raw, metric, "pto_adaptive_fast", "online_joint"))
        rows.extend(paired_delta(raw, metric, "online_fast_only", "online_joint"))
    pairwise = pd.DataFrame(rows)
    pairwise.to_csv(root / "adaptive_pto_pairwise_deltas.csv", index=False, encoding="utf-8-sig")

    p95_diag = raw.groupby(["scenario", "policy"], as_index=False)[
        [
            "p95_total_wait",
            "mean_total_wait",
            "unstable",
            "queue_tail_slope",
            "terminal_system",
            "uncompleted_at_drain_limit",
            "drain_truncated",
            "drain_minutes",
            "first_queue_threshold_period",
            "tail_net_queue_drift",
        ]
    ].mean()
    p95_diag["unstable_stress_regime"] = (
        (p95_diag["p95_total_wait"] > 1440)
        | (p95_diag["unstable"] > 0)
        | (p95_diag["uncompleted_at_drain_limit"] > 0)
    )
    p95_diag.to_csv(root / "p95_instability_diagnostics.csv", index=False, encoding="utf-8-sig")

    safety = raw.groupby(["scenario", "policy"], as_index=False)[
        ["service_floor_binding_rate", "projection_binding_rate", "mean_net_queue_drift", "tail_net_queue_drift"]
    ].mean()
    safety.to_csv(root / "floor_safety_diagnostics.csv", index=False, encoding="utf-8-sig")

    write_plots(root, raw)
    write_parameter_disclosure(config, root)
    write_data_source_table(root)
    write_data_availability_statement(root)
    write_repro_readme(root, args.config, args.replications)
    report = write_report(root, raw, pairwise, p95_diag, safety)
    print(f"repair report: {report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
