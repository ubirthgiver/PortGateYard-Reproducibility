from __future__ import annotations

import base64
from html import escape
import os
from pathlib import Path

import numpy as np
import pandas as pd

from .config import SimulationConfig
from .experiment import _bootstrap_ci, paired_difference, run_experiments
from .reporting import POLICY_LABELS


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


def _png_data_uri(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _scenario_labels(config: SimulationConfig) -> dict[str, str]:
    return {scenario.name: scenario.description or scenario.name for scenario in config.scenarios}


def _paired_advantage(raw: pd.DataFrame, scenario: str, metric: str, higher_is_better: bool, samples: int) -> dict[str, float]:
    diff = paired_difference(raw, scenario, metric, "online_joint", "pto", samples)
    if higher_is_better:
        return {
            "advantage": diff["difference"],
            "ci_low": diff["ci_low"],
            "ci_high": diff["ci_high"],
            "online_minus_pto": diff["difference"],
        }
    return {
        "advantage": -diff["difference"],
        "ci_low": -diff["ci_high"],
        "ci_high": -diff["ci_low"],
        "online_minus_pto": diff["difference"],
    }


def _mean_ci(raw: pd.DataFrame, scenario: str, policy: str, metric: str, samples: int, seed: int) -> str:
    values = raw[(raw["scenario"] == scenario) & (raw["policy"] == policy)][metric].to_numpy(dtype=float)
    low, high = _bootstrap_ci(values, samples, seed)
    return f"{np.nanmean(values):.3f} [{low:.3f}, {high:.3f}]"


def summarize_online_vs_pto(config: SimulationConfig, raw: pd.DataFrame) -> pd.DataFrame:
    labels = _scenario_labels(config)
    rows: list[dict[str, object]] = []
    seed = 91
    for scenario in [item.name for item in config.scenarios]:
        for metric, metric_label in LOWER_IS_BETTER.items():
            advantage = _paired_advantage(raw, scenario, metric, False, config.bootstrap_samples)
            rows.append({
                "scenario": scenario,
                "scenario_label": labels[scenario],
                "metric": metric,
                "metric_label": metric_label,
                "direction": "lower_is_better",
                "pto": _mean_ci(raw, scenario, "pto", metric, config.bootstrap_samples, seed),
                "online_joint": _mean_ci(raw, scenario, "online_joint", metric, config.bootstrap_samples, seed + 1),
                "online_advantage": advantage["advantage"],
                "ci_low": advantage["ci_low"],
                "ci_high": advantage["ci_high"],
                "online_minus_pto": advantage["online_minus_pto"],
            })
            seed += 2
        for metric, metric_label in HIGHER_IS_BETTER.items():
            advantage = _paired_advantage(raw, scenario, metric, True, config.bootstrap_samples)
            rows.append({
                "scenario": scenario,
                "scenario_label": labels[scenario],
                "metric": metric,
                "metric_label": metric_label,
                "direction": "higher_is_better",
                "pto": _mean_ci(raw, scenario, "pto", metric, config.bootstrap_samples, seed),
                "online_joint": _mean_ci(raw, scenario, "online_joint", metric, config.bootstrap_samples, seed + 1),
                "online_advantage": advantage["advantage"],
                "ci_low": advantage["ci_low"],
                "ci_high": advantage["ci_high"],
                "online_minus_pto": advantage["online_minus_pto"],
            })
            seed += 2
    return pd.DataFrame(rows)


def create_disturbance_plots(config: SimulationConfig, raw: pd.DataFrame, advantage: pd.DataFrame, output_dir: str | Path) -> list[Path]:
    output = Path(output_dir)
    plot_dir = output / "figures"
    plot_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(output / ".matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    scenarios = [item.name for item in config.scenarios]
    labels = [_scenario_labels(config)[x] for x in scenarios]
    x = np.arange(len(scenarios))
    width = 0.34
    created: list[Path] = []

    metrics = [
        ("mean_composite_cost", "综合成本"),
        ("p95_yard_queue", "堆场P95队列"),
        ("throughput_rate", "吞吐率"),
        ("acceptance_rate", "预约接受率"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(13, 8))
    for ax, (metric, title) in zip(axes.flat, metrics):
        means = {}
        for policy in ["pto", "online_joint"]:
            means[policy] = [
                raw[(raw["scenario"] == scenario) & (raw["policy"] == policy)][metric].mean()
                for scenario in scenarios
            ]
        ax.bar(x - width / 2, means["pto"], width, label=POLICY_LABELS["pto"])
        ax.bar(x + width / 2, means["online_joint"], width, label=POLICY_LABELS["online_joint"])
        ax.set_title(title)
        ax.set_xticks(x, labels, rotation=10)
        ax.grid(axis="y", alpha=0.25)
    axes[0, 0].legend()
    fig.suptitle("扰动强度下 PTO 与在线协同策略对比")
    fig.tight_layout()
    path = plot_dir / "disturbance_strategy_comparison.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    created.append(path)

    selected = advantage[advantage["metric"].isin(["mean_composite_cost", "p95_yard_queue", "throughput_rate"])]
    fig, ax = plt.subplots(figsize=(12, 6))
    for metric, group in selected.groupby("metric", sort=False):
        group = group.set_index("scenario").reindex(scenarios)
        y = group["online_advantage"].to_numpy(dtype=float)
        err = np.vstack([y - group["ci_low"].to_numpy(dtype=float), group["ci_high"].to_numpy(dtype=float) - y])
        ax.errorbar(x, y, yerr=err, marker="o", capsize=4, label=str(group["metric_label"].iloc[0]))
    ax.axhline(0, color="black", linewidth=0.8)
    ax.set_xticks(x, labels, rotation=10)
    ax.set_ylabel("在线相对 PTO 的优势值")
    ax.set_title("在线协同策略相对 PTO 的优势随扰动强度变化")
    ax.grid(alpha=0.25)
    ax.legend()
    fig.tight_layout()
    path = plot_dir / "online_advantage_under_disturbance.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    created.append(path)
    return created


def write_disturbance_report(config: SimulationConfig, raw: pd.DataFrame, advantage: pd.DataFrame, plots: list[Path], output_dir: str | Path) -> Path:
    output = Path(output_dir)
    selected_metrics = ["mean_composite_cost", "p95_yard_queue", "mean_yard_wait", "throughput_rate", "acceptance_rate"]
    table = advantage[advantage["metric"].isin(selected_metrics)].copy()
    table["在线优势（95% CI）"] = table.apply(
        lambda x: f"{x['online_advantage']:.3f} [{x['ci_low']:.3f}, {x['ci_high']:.3f}]",
        axis=1,
    )
    display = table[["scenario_label", "metric_label", "pto", "online_joint", "在线优势（95% CI）"]]
    display = display.rename(columns={
        "scenario_label": "扰动场景",
        "metric_label": "指标",
        "pto": "PTO",
        "online_joint": "在线协同",
    })
    strong_name = config.scenarios[-1].name
    smooth_name = config.scenarios[0].name
    middle_name = config.scenarios[1].name if len(config.scenarios) > 1 else config.scenarios[-1].name
    smooth = advantage[advantage["scenario"] == smooth_name].set_index("metric")
    middle = advantage[advantage["scenario"] == middle_name].set_index("metric")
    strong = advantage[advantage["scenario"] == strong_name].set_index("metric")
    lines = [
        "# 扰动强度敏感性测试报告",
        "",
        "## 测试目的",
        "",
        "本测试用于检验在线协同学习策略的优势是否主要体现在非平稳和扰动环境中，而不是平稳环境下的静态成本最小化。",
        "",
        "核心判断不是“在线协同在任何环境下都比 PTO 便宜”，而是：当到达、履约和服务能力出现扰动时，在线协同是否更能维持吞吐、控制堆场拥堵和降低尾部风险。",
        "",
        "## 场景设置",
        "",
    ]
    for scenario in config.scenarios:
        lines.append(f"- {scenario.description or scenario.name}：平均预约需求 {scenario.mean_requests:.1f} 辆/30分钟。")
    lines.extend([
        "",
        "## PTO 与在线协同策略对比",
        "",
        display.to_markdown(index=False),
        "",
        "说明：等待、队列、综合成本等指标中，“在线优势”为 PTO 减去在线协同；吞吐率和预约接受率中，“在线优势”为在线协同减去 PTO。因此，优势值大于 0 表示在线协同更好。",
        "",
        "## 关键结论",
        "",
        f"- 平稳场景下，在线协同相对 PTO 的综合成本优势为 {smooth.loc['mean_composite_cost', 'online_advantage']:.3f}。该值小于0，说明 PTO 在平稳环境下成本更低。",
        f"- 中等扰动场景下，在线协同相对 PTO 的综合成本优势为 {middle.loc['mean_composite_cost', 'online_advantage']:.3f}，吞吐率优势为 {middle.loc['throughput_rate', 'online_advantage']:.3f}。",
        f"- 强扰动场景下，在线协同相对 PTO 的综合成本优势为 {strong.loc['mean_composite_cost', 'online_advantage']:.3f}，吞吐率优势为 {strong.loc['throughput_rate', 'online_advantage']:.3f}。",
        f"- 但强扰动场景下，在线协同相对 PTO 的堆场P95队列优势为 {strong.loc['p95_yard_queue', 'online_advantage']:.3f}。该值小于0，说明在线协同在当前参数下并没有降低堆场尾部队列，而是用更高堆场排队换取更高服务水平和更低综合违约成本。",
        "",
        "因此，本测试支持的结论是：在线协同策略的优势主要在扰动环境下表现为综合成本和服务水平改善；但它并不自动保证所有拥堵指标都优于 PTO。PTO 更像保守控流，在线协同更像服务维持型动态调度。",
        "",
        "## 图表",
        "",
        "![扰动场景策略对比](figures/disturbance_strategy_comparison.png)",
        "",
        "![在线优势变化](figures/online_advantage_under_disturbance.png)",
        "",
        "> 如果 VS Code 的 Markdown 预览不显示图片，请打开同目录下的 `disturbance_sensitivity_report.html`。",
    ])
    report = output / "disturbance_sensitivity_report.md"
    report.write_text("\n".join(lines), encoding="utf-8")

    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>扰动强度敏感性测试报告</title>
  <style>
    body {{ max-width: 1180px; margin: 32px auto; padding: 0 24px; font-family: "Microsoft YaHei", Arial, sans-serif; line-height: 1.6; color: #1f2937; }}
    table {{ border-collapse: collapse; width: 100%; margin: 16px 0 28px; font-size: 14px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 8px 10px; text-align: left; }}
    th {{ background: #f3f4f6; }}
    img {{ display: block; max-width: 100%; margin: 16px 0 32px; border: 1px solid #e5e7eb; border-radius: 8px; }}
  </style>
</head>
<body>
  <h1>扰动强度敏感性测试报告</h1>
  <p>本测试检验在线协同学习策略是否主要在非平稳和扰动环境中体现优势。</p>
  <h2>PTO 与在线协同策略对比</h2>
  {display.to_html(index=False)}
  <p>{escape("说明：等待、队列、综合成本等指标中，“在线优势”为 PTO 减去在线协同；吞吐率和预约接受率中，“在线优势”为在线协同减去 PTO。优势值大于 0 表示在线协同更好。")}</p>
  <h2>关键结论</h2>
  <ul>
    <li>平稳场景下，在线协同相对 PTO 的综合成本优势为 {smooth.loc['mean_composite_cost', 'online_advantage']:.3f}；PTO 成本更低。</li>
    <li>中等扰动场景下，在线协同相对 PTO 的综合成本优势为 {middle.loc['mean_composite_cost', 'online_advantage']:.3f}，吞吐率优势为 {middle.loc['throughput_rate', 'online_advantage']:.3f}。</li>
    <li>强扰动场景下，在线协同相对 PTO 的综合成本优势为 {strong.loc['mean_composite_cost', 'online_advantage']:.3f}，吞吐率优势为 {strong.loc['throughput_rate', 'online_advantage']:.3f}。</li>
    <li>强扰动场景下，在线协同相对 PTO 的堆场P95队列优势为 {strong.loc['p95_yard_queue', 'online_advantage']:.3f}；该拥堵指标未优于 PTO。</li>
  </ul>
  <h2>图表</h2>
  <img alt="扰动场景策略对比" src="{_png_data_uri(output / 'figures' / 'disturbance_strategy_comparison.png')}">
  <img alt="在线优势变化" src="{_png_data_uri(output / 'figures' / 'online_advantage_under_disturbance.png')}">
</body>
</html>
"""
    (output / "disturbance_sensitivity_report.html").write_text(html, encoding="utf-8")
    return report


def run_disturbance_experiment(config: SimulationConfig, output_dir: str | Path, replications: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame, Path]:
    raw, _summary = run_experiments(config, output_dir, replications=replications)
    output = Path(output_dir)
    advantage = summarize_online_vs_pto(config, raw)
    advantage.to_csv(output / "online_vs_pto_advantage.csv", index=False, encoding="utf-8-sig")
    plots = create_disturbance_plots(config, raw, advantage, output)
    report = write_disturbance_report(config, raw, advantage, plots, output)
    return raw, advantage, report
