from __future__ import annotations

import base64
from dataclasses import replace
from html import escape
from pathlib import Path

import numpy as np
import pandas as pd

from .config import PolicyConfig, ScenarioConfig, SimulationConfig
from .experiment import _bootstrap_ci
from .policies import LiQUARPolicy, Policy, SystemState
from .randomness import generate_randomness
from .simulation import run_simulation


FIDELITY_LEVELS = [
    {
        "level": "high_fidelity",
        "label": "高保真模型",
        "description": "PTO 使用无偏的需求、履约和服务时间估计。",
        "request": 1.00,
        "show": 1.00,
        "gate_service": 1.00,
        "yard_service": 1.00,
    },
    {
        "level": "mild_misspecification",
        "label": "轻度失真",
        "description": "PTO 轻度低估服务时间和实际到港压力。",
        "request": 1.00,
        "show": 0.95,
        "gate_service": 0.90,
        "yard_service": 0.88,
    },
    {
        "level": "medium_misspecification",
        "label": "中度失真",
        "description": "PTO 中度低估闸口与堆场服务时间，因而高估系统处理能力。",
        "request": 1.00,
        "show": 0.92,
        "gate_service": 0.75,
        "yard_service": 0.70,
    },
    {
        "level": "severe_misspecification",
        "label": "严重失真",
        "description": "PTO 严重低估服务时间并高估闸口—堆场处理能力。",
        "request": 1.00,
        "show": 0.90,
        "gate_service": 0.58,
        "yard_service": 0.52,
    },
]


LOWER_IS_BETTER = {
    "mean_composite_cost": "综合成本",
    "mean_total_wait": "平均总等待",
    "p95_total_wait": "P95总等待",
    "mean_yard_wait": "平均堆场等待",
    "p95_yard_queue": "堆场P95队列",
    "yard_resource_hours_per_truck": "单位车辆堆场资源时",
}
HIGHER_IS_BETTER = {
    "throughput_rate": "吞吐率",
    "acceptance_rate": "预约接受率",
}


class _ChosenFixedPolicy(Policy):
    name = "pto"

    def __init__(self, quota: int, yard_capacity: int):
        self.quota = quota
        self.yard_capacity = yard_capacity

    def decide(self, state: SystemState) -> tuple[int, int]:
        del state
        return self.quota, self.yard_capacity


def _png_data_uri(path: Path) -> str:
    return "data:image/png;base64," + base64.b64encode(path.read_bytes()).decode("ascii")


def _biased_policy_config(base: PolicyConfig, level: dict[str, object]) -> PolicyConfig:
    return replace(
        base,
        pto_request_multiplier=float(level["request"]),
        pto_show_multiplier=float(level["show"]),
        pto_gate_service_multiplier=float(level["gate_service"]),
        pto_yard_service_multiplier=float(level["yard_service"]),
    )


def _model_config_for_level(
    config: SimulationConfig,
    scenario: ScenarioConfig,
    level: dict[str, object],
) -> tuple[SimulationConfig, ScenarioConfig]:
    demand_multiplier = float(level["request"]) * float(level["show"])
    model_scenario = replace(
        scenario,
        mean_requests=scenario.mean_requests * demand_multiplier,
    )
    model_config = replace(
        config,
        scenarios=(model_scenario,),
        gate_service_mean=config.gate_service_mean * float(level["gate_service"]),
        yard_service_mean=config.yard_service_mean * float(level["yard_service"]),
        policy=_biased_policy_config(config.policy, level),
    )
    model_config.validate()
    return model_config, model_scenario


def _candidate_actions(config: SimulationConfig) -> list[tuple[int, int]]:
    return [
        (quota, yard)
        for quota in range(config.quota_min, config.quota_max + 1)
        for yard in range(config.yard_capacity_min, config.yard_capacity_max + 1)
    ]


def select_oracle_pto_actions(
    config: SimulationConfig,
    output_dir: str | Path,
    model_samples: int = 4,
) -> dict[tuple[str, str], tuple[int, int]]:
    """Select a fixed PTO action under each belief model."""
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    rows: list[dict[str, object]] = []
    selected: dict[tuple[str, str], tuple[int, int]] = {}
    for scenario_index, scenario in enumerate(config.scenarios):
        for level_index, level in enumerate(FIDELITY_LEVELS):
            model_config, model_scenario = _model_config_for_level(config, scenario, level)
            model_randomness = [
                generate_randomness(
                    model_config,
                    model_scenario,
                    70_000 + 10_000 * scenario_index + 1_000 * level_index + sample,
                )
                for sample in range(model_samples)
            ]
            best: tuple[float, int, int] | None = None
            for quota, yard in _candidate_actions(config):
                costs: list[float] = []
                for sample, randomness in enumerate(model_randomness):
                    result = run_simulation(
                        model_config,
                        model_scenario,
                        _ChosenFixedPolicy(quota, yard),
                        randomness,
                        sample,
                        policy_seed=91_000 + sample,
                    )
                    costs.append(float(result.summary["mean_composite_cost"]))
                mean_cost = float(np.mean(costs))
                rows.append(
                    {
                        "scenario": scenario.name,
                        "fidelity_level": level["level"],
                        "fidelity_label": level["label"],
                        "quota": quota,
                        "yard_capacity": yard,
                        "model_mean_composite_cost": mean_cost,
                        "model_samples": model_samples,
                    }
                )
                candidate = (mean_cost, quota, yard)
                if best is None or candidate < best:
                    best = candidate
            assert best is not None
            selected[(scenario.name, str(level["level"]))] = (best[1], best[2])
    action_frame = pd.DataFrame(rows)
    action_frame["selected"] = False
    for (scenario, fidelity), (quota, yard) in selected.items():
        mask = (
            (action_frame["scenario"] == scenario)
            & (action_frame["fidelity_level"] == fidelity)
            & (action_frame["quota"] == quota)
            & (action_frame["yard_capacity"] == yard)
        )
        action_frame.loc[mask, "selected"] = True
    action_frame.to_csv(output / "oracle_pto_action_search.csv", index=False, encoding="utf-8-sig")
    return selected


def run_fidelity_raw(
    config: SimulationConfig,
    output_dir: str | Path,
    replications: int | None = None,
    model_samples: int = 4,
) -> pd.DataFrame:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    n_rep = replications or config.replications
    selected_actions = select_oracle_pto_actions(config, output, model_samples=model_samples)
    summaries: list[dict[str, object]] = []
    examples: list[pd.DataFrame] = []

    for scenario_index, scenario in enumerate(config.scenarios):
        for replication in range(n_rep):
            scenario_seed = 30_000 * (scenario_index + 1) + replication
            randomness = generate_randomness(config, scenario, scenario_seed)
            online_result = run_simulation(
                config,
                scenario,
                LiQUARPolicy(config),
                randomness,
                replication,
                policy_seed=scenario_seed + 200_000,
            )
            for level_index, level in enumerate(FIDELITY_LEVELS):
                quota, yard = selected_actions[(scenario.name, str(level["level"]))]
                pto_result = run_simulation(
                    config,
                    scenario,
                    _ChosenFixedPolicy(quota, yard),
                    randomness,
                    replication,
                    policy_seed=scenario_seed + 100_000 + 10_000 * level_index,
                )
                for result in [pto_result, online_result]:
                    row = result.summary.copy()
                    row["fidelity_level"] = level["level"]
                    row["fidelity_label"] = level["label"]
                    row["fidelity_description"] = level["description"]
                    row["pto_request_multiplier"] = level["request"]
                    row["pto_show_multiplier"] = level["show"]
                    row["pto_gate_service_multiplier"] = level["gate_service"]
                    row["pto_yard_service_multiplier"] = level["yard_service"]
                    row["oracle_pto_quota"] = quota
                    row["oracle_pto_yard_capacity"] = yard
                    summaries.append(row)
                    if replication == 0:
                        frame = result.periods.copy()
                        frame.insert(0, "policy", result.policy)
                        frame.insert(0, "fidelity_label", str(level["label"]))
                        frame.insert(0, "fidelity_level", str(level["level"]))
                        frame.insert(0, "scenario", result.scenario)
                        examples.append(frame)

    raw = pd.DataFrame(summaries)
    raw.to_csv(output / "model_fidelity_raw_results.csv", index=False, encoding="utf-8-sig")
    if examples:
        pd.concat(examples, ignore_index=True).to_csv(
            output / "model_fidelity_example_trajectories.csv",
            index=False,
            encoding="utf-8-sig",
        )
    return raw


def _paired_advantage(
    raw: pd.DataFrame,
    scenario: str,
    fidelity: str,
    metric: str,
    higher_is_better: bool,
    samples: int,
) -> dict[str, float]:
    subset = raw[(raw["scenario"] == scenario) & (raw["fidelity_level"] == fidelity)]
    pivot = subset.pivot(index="replication", columns="policy", values=metric).dropna()
    diff = (pivot["online_joint"] - pivot["pto"]).to_numpy(dtype=float)
    low, high = _bootstrap_ci(diff, samples, seed=871)
    if higher_is_better:
        return {"advantage": float(diff.mean()), "ci_low": low, "ci_high": high, "online_minus_pto": float(diff.mean())}
    return {"advantage": float(-diff.mean()), "ci_low": -high, "ci_high": -low, "online_minus_pto": float(diff.mean())}


def _mean_ci(raw: pd.DataFrame, scenario: str, fidelity: str, policy: str, metric: str, samples: int, seed: int) -> str:
    values = raw[
        (raw["scenario"] == scenario)
        & (raw["fidelity_level"] == fidelity)
        & (raw["policy"] == policy)
    ][metric].to_numpy(dtype=float)
    low, high = _bootstrap_ci(values, samples, seed)
    return f"{np.nanmean(values):.3f} [{low:.3f}, {high:.3f}]"


def summarize_fidelity_advantage(config: SimulationConfig, raw: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    seed = 991
    for scenario in [item.name for item in config.scenarios]:
        for level in FIDELITY_LEVELS:
            fidelity = str(level["level"])
            for metric, label in LOWER_IS_BETTER.items():
                advantage = _paired_advantage(raw, scenario, fidelity, metric, False, config.bootstrap_samples)
                rows.append(
                    {
                        "scenario": scenario,
                        "fidelity_level": fidelity,
                        "fidelity_label": level["label"],
                        "metric": metric,
                        "metric_label": label,
                        "direction": "lower_is_better",
                        "pto": _mean_ci(raw, scenario, fidelity, "pto", metric, config.bootstrap_samples, seed),
                        "online_joint": _mean_ci(raw, scenario, fidelity, "online_joint", metric, config.bootstrap_samples, seed + 1),
                        "online_advantage": advantage["advantage"],
                        "ci_low": advantage["ci_low"],
                        "ci_high": advantage["ci_high"],
                        "online_minus_pto": advantage["online_minus_pto"],
                    }
                )
                seed += 2
            for metric, label in HIGHER_IS_BETTER.items():
                advantage = _paired_advantage(raw, scenario, fidelity, metric, True, config.bootstrap_samples)
                rows.append(
                    {
                        "scenario": scenario,
                        "fidelity_level": fidelity,
                        "fidelity_label": level["label"],
                        "metric": metric,
                        "metric_label": label,
                        "direction": "higher_is_better",
                        "pto": _mean_ci(raw, scenario, fidelity, "pto", metric, config.bootstrap_samples, seed),
                        "online_joint": _mean_ci(raw, scenario, fidelity, "online_joint", metric, config.bootstrap_samples, seed + 1),
                        "online_advantage": advantage["advantage"],
                        "ci_low": advantage["ci_low"],
                        "ci_high": advantage["ci_high"],
                        "online_minus_pto": advantage["online_minus_pto"],
                    }
                )
                seed += 2
    return pd.DataFrame(rows)


def _plot_scenario_name(config: SimulationConfig) -> str:
    scenario_names = [item.name for item in config.scenarios]
    preferred = ["peak_real_month", "high_real_month", "port_uncertain_operation"]
    for name in preferred:
        if name in scenario_names:
            return name
    return scenario_names[0]


def create_fidelity_plots(
    config: SimulationConfig,
    raw: pd.DataFrame,
    advantage: pd.DataFrame,
    output_dir: str | Path,
) -> list[Path]:
    output = Path(output_dir)
    plot_dir = output / "figures"
    plot_dir.mkdir(parents=True, exist_ok=True)
    import os

    os.environ.setdefault("MPLCONFIGDIR", str(output / ".matplotlib"))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False

    levels = [str(item["level"]) for item in FIDELITY_LEVELS]
    labels = [str(item["label"]) for item in FIDELITY_LEVELS]
    x = np.arange(len(levels))
    scenario = _plot_scenario_name(config)
    created: list[Path] = []

    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    for ax, metric, title in [
        (axes[0, 0], "mean_composite_cost", "综合成本"),
        (axes[0, 1], "throughput_rate", "吞吐率"),
        (axes[1, 0], "acceptance_rate", "预约接受率"),
        (axes[1, 1], "p95_total_wait", "P95总等待"),
    ]:
        subset = raw[raw["scenario"] == scenario]
        pto = [subset[(subset["fidelity_level"] == level) & (subset["policy"] == "pto")][metric].mean() for level in levels]
        online = [
            subset[(subset["fidelity_level"] == level) & (subset["policy"] == "online_joint")][metric].mean()
            for level in levels
        ]
        width = 0.35
        ax.bar(x - width / 2, pto, width, label="PTO")
        ax.bar(x + width / 2, online, width, label="在线协同")
        ax.set_title(title)
        ax.set_xticks(x, labels, rotation=10)
        ax.grid(axis="y", alpha=0.25)
    axes[0, 0].legend()
    fig.suptitle(f"PTO模型保真度下降下的策略表现：{scenario}")
    fig.tight_layout()
    path = plot_dir / "model_fidelity_strategy_comparison.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    created.append(path)

    fig, ax = plt.subplots(figsize=(12, 6))
    for metric in ["mean_composite_cost", "throughput_rate", "acceptance_rate"]:
        group = (
            advantage[(advantage["scenario"] == scenario) & (advantage["metric"] == metric)]
            .set_index("fidelity_level")
            .reindex(levels)
        )
        y = group["online_advantage"].to_numpy(dtype=float)
        err = np.vstack([y - group["ci_low"].to_numpy(dtype=float), group["ci_high"].to_numpy(dtype=float) - y])
        ax.errorbar(x, y, yerr=err, marker="o", capsize=4, label=str(group["metric_label"].iloc[0]))
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(x, labels, rotation=10)
    ax.set_ylabel("在线协同相对 PTO 的优势值")
    ax.set_title(f"PTO模型保真度下降时在线协同优势变化：{scenario}")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    path = plot_dir / "online_advantage_by_model_fidelity.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    created.append(path)
    return created


def write_fidelity_report(config: SimulationConfig, advantage: pd.DataFrame, output_dir: str | Path) -> Path:
    output = Path(output_dir)
    selected_metrics = ["mean_composite_cost", "throughput_rate", "acceptance_rate", "p95_total_wait", "p95_yard_queue"]
    table = advantage[advantage["metric"].isin(selected_metrics)].copy()
    table["在线优势（95% CI）"] = table.apply(
        lambda x: f"{x['online_advantage']:.3f} [{x['ci_low']:.3f}, {x['ci_high']:.3f}]",
        axis=1,
    )
    display_cols = ["scenario", "fidelity_label", "metric_label", "pto", "online_joint", "在线优势（95% CI）"]
    display = table[display_cols].rename(
        columns={
            "scenario": "场景",
            "fidelity_label": "PTO模型状态",
            "metric_label": "指标",
            "pto": "PTO",
            "online_joint": "在线协同",
        }
    )
    focus = advantage[
        advantage["metric"].isin(["mean_composite_cost", "throughput_rate", "acceptance_rate"])
    ].pivot_table(
        index=["scenario", "fidelity_label"],
        columns="metric",
        values="online_advantage",
        aggfunc="mean",
    )

    lines = [
        "# PTO模型保真度下降实验报告",
        "",
        "## 测试目的",
        "",
        "本实验用于检验：在固定候选动作类和有限规划样本下，高保真 PTO 是强基准；当 PTO 使用的规划模型失真时，维持所选动作会如何改变与工作负荷反馈的比较。",
        "",
        "实验中，真实港口运行环境保持不变，只逐步降低 PTO 规划时使用的模型保真度。每个候选固定配额--堆场能力组合由四条共同规划路径估计成本，再按估计均值选择；因此高保真情形是 Monte Carlo-selected fixed-pair benchmark，而不是已知真实期望成本的 oracle。工作负荷反馈策略不使用这些失真模型，而是依据实时队列更新决策。",
        "",
        "## PTO模型失真设置",
        "",
    ]
    for level in FIDELITY_LEVELS:
        lines.append(f"- {level['label']}：{level['description']}")
    lines.extend(
        [
            "",
            "PTO 每个保真度等级下搜索得到的固定动作保存在旧文件名 `oracle_pto_action_search.csv` 中；该文件名不表示真实成本 oracle。",
            "",
            "## PTO 与在线协同策略对比",
            "",
            display.to_markdown(index=False),
            "",
            "说明：综合成本、等待和队列指标中，“在线优势”为 PTO 减去在线协同；吞吐率和预约接受率中，“在线优势”为在线协同减去 PTO。因此，优势值大于 0 表示在线协同更好。",
            "",
            "## 关键结论",
            "",
        ]
    )
    for scenario in [item.name for item in config.scenarios]:
        lines.append(f"### {scenario}")
        for level in FIDELITY_LEVELS:
            key = (scenario, str(level["label"]))
            if key not in focus.index:
                continue
            row = focus.loc[key]
            lines.append(
                f"- {level['label']}：综合成本优势 {row['mean_composite_cost']:.3f}，"
                f"吞吐率优势 {row['throughput_rate']:.3f}，预约接受率优势 {row['acceptance_rate']:.3f}。"
            )
        lines.append("")

    lines.extend(
        [
            "总体解释：高保真模型下，PTO 往往保持竞争力；当需求、履约或服务能力模型失真时，固定 PTO 方案会出现失配，在线协同可以通过实时反馈保持更稳健的服务水平和综合表现。",
            "",
            "## 图表",
            "",
            "![模型保真度策略对比](figures/model_fidelity_strategy_comparison.png)",
            "",
            "![在线优势随模型保真度变化](figures/online_advantage_by_model_fidelity.png)",
            "",
            "> 如果 VS Code 的 Markdown 预览不显示图片，请打开同目录下的 `model_fidelity_report.html`。",
        ]
    )
    report = output / "model_fidelity_report.md"
    report.write_text("\n".join(lines), encoding="utf-8")

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>PTO模型保真度下降实验报告</title>
  <style>
    body {{ max-width: 1180px; margin: 32px auto; padding: 0 24px; font-family: "Microsoft YaHei", Arial, sans-serif; line-height: 1.6; color: #1f2937; }}
    table {{ border-collapse: collapse; width: 100%; margin: 16px 0 28px; font-size: 14px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 8px 10px; text-align: left; }}
    th {{ background: #f3f4f6; }}
    img {{ display: block; max-width: 100%; margin: 16px 0 32px; border: 1px solid #e5e7eb; border-radius: 8px; }}
  </style>
</head>
<body>
  <h1>PTO模型保真度下降实验报告</h1>
  <p>{escape("本实验检验在线协同学习的 model-free 优势是否会随着 PTO 模型保真度下降而增强。")}</p>
  <h2>PTO 与在线协同策略对比</h2>
  {display.to_html(index=False)}
  <h2>图表</h2>
  <img alt="模型保真度策略对比" src="{_png_data_uri(output / 'figures' / 'model_fidelity_strategy_comparison.png')}">
  <img alt="在线优势随模型保真度变化" src="{_png_data_uri(output / 'figures' / 'online_advantage_by_model_fidelity.png')}">
</body>
</html>
"""
    (output / "model_fidelity_report.html").write_text(html, encoding="utf-8")
    return report


def run_model_fidelity_experiment(
    config: SimulationConfig,
    output_dir: str | Path,
    replications: int | None = None,
    model_samples: int = 4,
) -> tuple[pd.DataFrame, pd.DataFrame, Path]:
    raw = run_fidelity_raw(config, output_dir, replications, model_samples=model_samples)
    output = Path(output_dir)
    advantage = summarize_fidelity_advantage(config, raw)
    advantage.to_csv(output / "online_vs_pto_by_fidelity.csv", index=False, encoding="utf-8-sig")
    create_fidelity_plots(config, raw, advantage, output)
    report = write_fidelity_report(config, advantage, output)
    return raw, advantage, report
