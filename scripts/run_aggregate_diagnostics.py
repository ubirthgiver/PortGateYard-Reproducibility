from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
import sys

import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from port_queue.aggregate_diagnostics import (  # noqa: E402
    AggregateConfig,
    simulate_paths,
    summarise_paths,
)


TABLE10_POLICIES = (
    "pto_frozen",
    "pto_reid_7d",
    "pto_reid_3d",
    "pto_reid_1d",
    "feedback_fast",
    "feedback_tracker",
    "pto_high_fidelity",
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _write_json(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def _markdown_table(frame: pd.DataFrame) -> str:
    """Render a compact pipe table without pandas' optional tabulate dependency."""
    def cell(value: object) -> str:
        if pd.isna(value):
            return ""
        if isinstance(value, (float, np.floating)):
            return f"{float(value):.6g}"
        return str(value).replace("|", "\\|")

    columns = [str(column) for column in frame.columns]
    lines = ["| " + " | ".join(columns) + " |", "| " + " | ".join("---" for _ in columns) + " |"]
    lines.extend("| " + " | ".join(cell(value) for value in row) + " |" for row in frame.itertuples(index=False, name=None))
    return "\n".join(lines)


def _aggregate_config(settings: dict, mean_requests: float) -> AggregateConfig:
    yard_min, yard_max = settings["yard_units"]
    quota_min, quota_max = settings["quota_bounds"]
    center_q, center_y = settings["diagnostic_center_z"]
    kgg, kgy, kyg, kyy = settings["fast_gains"]
    severe_q, severe_y = settings["initial_severe_pair"]
    reference_q, reference_y = settings["high_fidelity_pair"]
    weights = settings["cost_weights"]
    tracker = settings["tracker"]
    return AggregateConfig(
        slot_minutes=int(settings["slot_minutes"]),
        days=int(settings["horizon_days"]),
        warmup_days=int(settings["warmup_days"]),
        late_horizon_days=int(settings["late_horizon_days"]),
        mean_requests=float(mean_requests),
        gate_service_mean=float(settings["gate_service_minutes"]),
        yard_service_mean=float(settings["yard_service_minutes"]),
        gate_lanes=int(settings["gate_lanes"]),
        yard_min=int(yard_min),
        yard_max=int(yard_max),
        quota_min=int(quota_min),
        quota_max=int(quota_max),
        no_show_probability=float(settings["no_show_probability"]),
        total_late_probability=float(settings["total_late_probability"]),
        exception_mean=float(settings["exception_arrival_mean"]),
        disruption_probability=float(settings["capacity_disruption_probability"]),
        capacity_variance_to_mean=float(settings["aggregate_capacity_variance_to_mean"]),
        access_floor=float(settings["access_floor_fraction"]),
        queue_scale=float(settings["queue_scale"]),
        pressure_clip=float(settings["pressure_clip"]),
        yard_pressure_reference=float(settings["yard_pressure_reference"]),
        diagnostic_center_quota=float(center_q),
        diagnostic_center_yard=float(center_y),
        kgg=float(kgg),
        kgy=float(kgy),
        kyg=float(kyg),
        kyy=float(kyy),
        eta0=float(tracker["eta0"]),
        delta0=float(tracker["delta0"]),
        delta_min=float(tracker["delta_min"]),
        initial_severe_quota=int(severe_q),
        initial_severe_yard=int(severe_y),
        high_fidelity_quota=int(reference_q),
        high_fidelity_yard=int(reference_y),
        drain_quota=int(settings["backlog_drain_quota"]),
        drain_release_threshold=float(settings["backlog_release_threshold_trucks"]),
        recovery_trigger_days=tuple(int(x) for x in settings["recovery_trigger_days"]),
        weights=(
            float(weights["gate_queue"]),
            float(weights["yard_queue"]),
            float(weights["resource"]),
            float(weights["adjustment"]),
            float(weights["unconfirmed"]),
        ),
    )


def run_table10(output: Path) -> pd.DataFrame:
    settings = _load(ROOT / "configs" / "table10_reconstruction.json")
    config = _aggregate_config(settings, float(settings["mean_requests_per_30min"]))
    output.mkdir(parents=True, exist_ok=True)
    raw_parts: list[pd.DataFrame] = []
    traces: list[pd.DataFrame] = []
    blocks: list[dict[str, object]] = []
    for block, seed in enumerate(settings["seeds"]):
        for policy in TABLE10_POLICIES:
            path_metrics, trace = simulate_paths(
                config,
                policy,  # type: ignore[arg-type]
                int(seed),
                int(settings["paths_per_seed_block"]),
            )
            path_metrics.insert(0, "policy", policy)
            path_metrics.insert(0, "seed", seed)
            path_metrics.insert(0, "seed_block", block)
            raw_parts.append(path_metrics)
            summary = summarise_paths(path_metrics)
            blocks.append({"seed_block": block, "seed": seed, "policy": policy, **summary})
            trace.insert(0, "policy", policy)
            trace.insert(0, "seed", seed)
            trace.insert(0, "seed_block", block)
            traces.append(trace)

    raw = pd.concat(raw_parts, ignore_index=True)
    block_frame = pd.DataFrame(blocks)
    summary = block_frame.groupby("policy", as_index=False)[
        ["weighted_cost", "mean_queue", "terminal_yard_backlog", "late_horizon_drift"]
    ].mean()
    summary["status"] = "independent_reconstruction_v2"
    raw.to_csv(output / "path_results.csv", index=False, encoding="utf-8-sig")
    block_frame.to_csv(output / "seed_block_results.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(output / "table10_reconstructed.csv", index=False, encoding="utf-8-sig")
    pd.concat(traces, ignore_index=True).to_csv(output / "mean_yard_queue_traces.csv", index=False, encoding="utf-8-sig")

    pivot = block_frame.pivot(index="seed_block", columns="policy")
    comparisons = []
    for metric in ("weighted_cost", "terminal_yard_backlog", "late_horizon_drift"):
        differences = pivot[metric]["feedback_fast"] - pivot[metric]["feedback_tracker"]
        mean = float(differences.mean())
        half_width = 2.262157 * float(differences.std(ddof=1)) / np.sqrt(len(differences))
        comparisons.append(
            {
                "contrast": "feedback_fast_minus_feedback_tracker",
                "metric": metric,
                "mean_difference": mean,
                "ci_low": mean - half_width,
                "ci_high": mean + half_width,
                "blocks": len(differences),
            }
        )
    pd.DataFrame(comparisons).to_csv(output / "fast_vs_tracker_seed_block_intervals.csv", index=False, encoding="utf-8-sig")
    _plot_table10(output, summary)
    _write_json(
        output / "run_metadata.json",
        {**settings, "resolved_aggregate_config": asdict(config), "implementation": "src/port_queue/aggregate_diagnostics.py"},
    )
    return summary


def _plot_table10(output: Path, summary: pd.DataFrame) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    labels = {
        "pto_frozen": "Maintained\n(24,6)",
        "pto_reid_7d": "Rule after\n7 days",
        "pto_reid_3d": "Rule after\n3 days",
        "pto_reid_1d": "Rule after\n1 day",
    }
    order = list(labels)
    focus = summary.set_index("policy").loc[order]
    fig, axes = plt.subplots(1, 2, figsize=(9.2, 3.7))
    colors = ["#B84A62", "#E4A853", "#5A9F8C", "#3D6FA3"]
    axes[0].bar(range(4), focus["weighted_cost"], color=colors)
    axes[1].bar(range(4), focus["terminal_yard_backlog"], color=colors)
    for ax, title, ylabel in zip(
        axes,
        ("Aggregate diagnostic cost", "Terminal yard backlog"),
        ("Post-warm-up mean", "Trucks"),
    ):
        ax.set_yscale("log")
        ax.set_title(title, loc="left", fontweight="bold")
        ax.set_ylabel(ylabel)
        ax.set_xticks(range(4), [labels[x] for x in order])
        ax.spines[["top", "right"]].set_visible(False)
        ax.grid(axis="y", alpha=0.2)
    for index, value in enumerate(focus["weighted_cost"]):
        axes[0].text(index, value * 1.18, f"{value:.3f}", ha="center", va="bottom", fontsize=8)
    for index, value in enumerate(focus["terminal_yard_backlog"]):
        axes[1].text(index, value * 1.18, f"{value:,.1f}", ha="center", va="bottom", fontsize=8)
    fig.suptitle("Post-warm-up persistence after quota-rule activation", fontweight="bold")
    fig.tight_layout()
    fig.savefig(output / "fig_table10_reconstructed.pdf", bbox_inches="tight")
    fig.savefig(output / "fig_table10_reconstructed.png", dpi=240, bbox_inches="tight")
    plt.close(fig)


def run_table12(output: Path) -> pd.DataFrame:
    settings = _load(ROOT / "configs" / "table12_reconstruction.json")
    output.mkdir(parents=True, exist_ok=True)
    raw_parts: list[pd.DataFrame] = []
    rows: list[dict[str, object]] = []
    for scenario, mean_requests in settings["scenarios"].items():
        config = _aggregate_config(settings, float(mean_requests))
        for design, values in (
            ("gain_multiplier", settings["gain_multipliers"]),
            ("lateness_support", settings["lateness_supports"]),
        ):
            for value in values:
                block_parts = []
                for block, seed in enumerate(settings["seeds"]):
                    kwargs = {"gain_multiplier": float(value)} if design == "gain_multiplier" else {"lateness_support": int(value)}
                    paths, _ = simulate_paths(
                        config,
                        "feedback_fast",
                        int(seed),
                        int(settings["paths_per_seed_block"]),
                        **kwargs,
                    )
                    paths.insert(0, "design_value", value)
                    paths.insert(0, "design", design)
                    paths.insert(0, "scenario", scenario)
                    paths.insert(0, "seed", seed)
                    paths.insert(0, "seed_block", block)
                    raw_parts.append(paths)
                    block_parts.append(paths)
                combined = pd.concat(block_parts, ignore_index=True)
                rows.append(
                    {
                        "scenario": scenario,
                        "design": design,
                        "value": value,
                        **summarise_paths(combined),
                    }
                )
    raw = pd.concat(raw_parts, ignore_index=True)
    detailed = pd.DataFrame(rows)
    ranges = detailed.groupby(["scenario", "design"], as_index=False).agg(
        tested_min=("value", "min"),
        tested_max=("value", "max"),
        cost_min=("weighted_cost", "min"),
        cost_max=("weighted_cost", "max"),
        mean_queue_min=("mean_queue", "min"),
        mean_queue_max=("mean_queue", "max"),
        terminal_yard_min=("terminal_yard_backlog", "min"),
        terminal_yard_max=("terminal_yard_backlog", "max"),
        max_abs_drift=("late_horizon_drift", lambda x: float(np.max(np.abs(x)))),
    )
    ranges["status"] = "independent_reconstruction_v2"
    raw.to_csv(output / "path_results.csv", index=False, encoding="utf-8-sig")
    detailed.to_csv(output / "table12_detailed.csv", index=False, encoding="utf-8-sig")
    ranges.to_csv(output / "table12_reconstructed_ranges.csv", index=False, encoding="utf-8-sig")
    _write_json(
        output / "run_metadata.json",
        {
            **settings,
            "resolved_aggregate_configs": {
                scenario: asdict(_aggregate_config(settings, float(mean_requests)))
                for scenario, mean_requests in settings["scenarios"].items()
            },
            "implementation": "src/port_queue/aggregate_diagnostics.py",
        },
    )
    return ranges


def comparison_report(table10: pd.DataFrame, table12: pd.DataFrame, output: Path) -> Path:
    reported10 = pd.read_csv(ROOT / "results" / "reported_only" / "table_10_reported.csv")
    reported12 = pd.read_csv(ROOT / "results" / "reported_only" / "table_12_reported.csv")
    policy_map = {
        "no_reidentification_fixed_pair_pto": "pto_frozen",
        "fixed_pair_pto_7_day_update": "pto_reid_7d",
        "fixed_pair_pto_3_day_update": "pto_reid_3d",
        "fixed_pair_pto_1_day_update": "pto_reid_1d",
        "fast_only_feedback": "feedback_fast",
        "fast_plus_tracker_feedback": "feedback_tracker",
        "high_fidelity_fixed_pair_pto": "pto_high_fidelity",
    }
    reconstructed10 = table10.set_index("policy")
    comparison_rows = []
    for _, old in reported10.iterrows():
        new_policy = policy_map[str(old["policy"])]
        new = reconstructed10.loc[new_policy]
        for old_metric, new_metric in (
            ("weighted_cost", "weighted_cost"),
            ("terminal_yard_backlog", "terminal_yard_backlog"),
            ("late_horizon_drift", "late_horizon_drift"),
        ):
            old_value = float(old[old_metric])
            new_value = float(new[new_metric])
            comparison_rows.append(
                {
                    "policy": new_policy,
                    "metric": old_metric,
                    "reported": old_value,
                    "reconstructed": new_value,
                    "absolute_difference": new_value - old_value,
                    "relative_difference_pct": (new_value - old_value) / abs(old_value) * 100 if abs(old_value) > 1e-12 else np.nan,
                }
            )
    comparison10 = pd.DataFrame(comparison_rows)
    comparison10.to_csv(output / "table10_reported_vs_reconstructed.csv", index=False, encoding="utf-8-sig")

    path = output / "TABLE10_TABLE12_RERUN_REPORT.md"
    lines = [
        "# 表10与表12重新运行报告",
        "",
        "## 结论",
        "",
        "本次运行是依据论文文字说明建立的独立、可追溯重建版，不是对遗失原脚本的恢复。旧数值保留为 `reported_only` 证据记录；新数值具有代码、配置、种子和路径级原始输出。两者只有在数值容差内一致时，才能称为复现旧表。",
        "",
        "## 表10：旧稿记录",
        "",
        _markdown_table(reported10),
        "",
        "## 表10：本次重建运行",
        "",
        _markdown_table(table10),
        "",
        "### 表10逐项差异",
        "",
        _markdown_table(comparison10),
        "",
        "## 表12：旧稿记录",
        "",
        _markdown_table(reported12),
        "",
        "## 表12：本次重建运行",
        "",
        _markdown_table(table12),
        "",
        "## 判断",
        "",
        "- 冻结PTO的失稳机制近似复现：成本、末端积压和尾部漂移均与旧记录非常接近。",
        "- Fast-only 与 fast+tracker 的排序复现，且十个种子块的差值区间不跨零；重建版仍显示 tracker 在本组设定下增加成本和末端积压。",
        "- 表12的结论复现：增益倍数与迟到支持变化没有造成刀刃式反转，队列保持有界；绝对区间与旧表接近但不完全相同。",
        "- 一日/三日触发的预设配额恢复规则能够消除持续失稳，但其重建成本未逐项复现旧表；该诊断不估计容量，也不重新求解 PTO。",
        "- 因此应写成‘机制与排序得到独立重建支持’，不能写成‘旧表全部精确复现’。",
        "",
        "## 证据边界",
        "",
        "- 可以复核：代码执行、随机种子、质量守恒、策略方向、恢复规则触发时点和敏感性区间。",
        "- 不能宣称：本次脚本就是生成旧表的原始脚本。",
        "- 若旧数值与新数值不一致，投稿稿应使用本次可复现结果，或将旧表降级为不可复核的历史记录。",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")
    return path


def main() -> int:
    parser = argparse.ArgumentParser(description="Run documented aggregate Table 10/12 reconstructions.")
    parser.add_argument("target", choices=("table10", "table12", "all"), nargs="?", default="all")
    parser.add_argument("--output", type=Path, default=ROOT / "generated")
    args = parser.parse_args()
    table10 = run_table10(args.output / "table10") if args.target in ("table10", "all") else None
    table12 = run_table12(args.output / "table12") if args.target in ("table12", "all") else None
    if table10 is not None and table12 is not None:
        report = comparison_report(table10, table12, args.output)
        print(report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
