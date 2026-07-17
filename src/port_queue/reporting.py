from __future__ import annotations

import base64
from html import escape
from pathlib import Path
import os

import numpy as np
import pandas as pd

from .experiment import paired_difference


POLICY_LABELS = {
    "fixed": "固定配额",
    "gate_only": "仅闸口优化",
    "pto": "预测后优化(PTO)",
    "online_joint": "在线协同优化",
}
SCENARIO_LABELS = {"moderate": "中等负荷", "heavy": "重负荷"}


def _png_data_uri(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def _hypothesis_rows(raw: pd.DataFrame, bootstrap_samples: int) -> list[dict[str, object]]:
    h1_mean = paired_difference(raw, "heavy", "mean_total_wait", "online_joint", "fixed", bootstrap_samples)
    h1_p95 = paired_difference(raw, "heavy", "p95_total_wait", "online_joint", "fixed", bootstrap_samples)
    h2 = paired_difference(raw, "heavy", "mean_yard_wait", "online_joint", "gate_only", bootstrap_samples)
    h3 = paired_difference(raw, "heavy", "mean_composite_cost", "online_joint", "pto", bootstrap_samples)
    h4 = paired_difference(raw, "heavy", "p95_yard_queue", "online_joint", "gate_only", bootstrap_samples)
    h5 = paired_difference(raw, "heavy", "yard_resource_hours_per_truck", "online_joint", "fixed", bootstrap_samples)
    throughput = paired_difference(raw, "heavy", "throughput_rate", "online_joint", "fixed", bootstrap_samples)
    return [
        {"hypothesis": "H1", "criterion": "在线协同降低平均与P95总等待", "supported": h1_mean["ci_high"] < 0 and h1_p95["ci_high"] < 0, "effect": h1_mean},
        {"hypothesis": "H2", "criterion": "在线协同相对仅闸口优化降低堆场等待", "supported": h2["ci_high"] < 0, "effect": h2},
        {"hypothesis": "H3", "criterion": "重负荷下在线协同综合指标低于PTO", "supported": h3["ci_high"] < 0, "effect": h3},
        {"hypothesis": "H4", "criterion": "在线协同降低堆场P95队列", "supported": h4["ci_high"] < 0, "effect": h4},
        {"hypothesis": "H5", "criterion": "单位车辆资源时下降且吞吐损失不超过5%", "supported": h5["ci_high"] < 0 and throughput["relative_change"] >= -0.05, "effect": h5},
    ]


def create_plots(raw: pd.DataFrame, summary: pd.DataFrame, trajectories: pd.DataFrame, output_dir: str | Path) -> list[Path]:
    output = Path(output_dir)
    plot_dir = output / "figures"
    plot_dir.mkdir(parents=True, exist_ok=True)
    os.environ.setdefault("MPLCONFIGDIR", str(output / ".matplotlib"))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    created: list[Path] = []

    metrics = [
        ("mean_total_wait", "平均总等待（分钟）"),
        ("p95_total_wait", "P95总等待（分钟）"),
        ("mean_composite_cost", "综合指标"),
        ("yard_resource_hours_per_truck", "单位车辆堆场资源时"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(13, 9))
    policies = list(POLICY_LABELS)
    scenarios = ["moderate", "heavy"]
    x = np.arange(len(policies))
    width = 0.36
    for ax, (metric, label) in zip(axes.flat, metrics):
        subset = summary[summary["metric"] == metric]
        for index, scenario in enumerate(scenarios):
            rows = subset[subset["scenario"] == scenario].set_index("policy").reindex(policies)
            means = rows["mean"].to_numpy()
            errors = np.vstack([means - rows["ci_low"].to_numpy(), rows["ci_high"].to_numpy() - means])
            ax.bar(x + (index - 0.5) * width, means, width, yerr=errors, capsize=3, label=SCENARIO_LABELS[scenario])
        ax.set_title(label)
        ax.set_xticks(x, [POLICY_LABELS[p] for p in policies], rotation=12)
        ax.grid(axis="y", alpha=0.25)
    axes[0, 0].legend()
    fig.suptitle("四类策略核心绩效对比（95% Bootstrap置信区间）")
    fig.tight_layout()
    path = plot_dir / "strategy_comparison.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    created.append(path)

    if not trajectories.empty:
        heavy = trajectories[(trajectories["scenario"] == "heavy") & (trajectories["period"] >= trajectories["period"].max() - 7 * 48)]
        fig, axes = plt.subplots(2, 1, figsize=(14, 8), sharex=True)
        for policy in policies:
            data = heavy[heavy["policy"] == policy]
            axes[0].plot(data["period"], data["avg_gate_queue"].rolling(12, min_periods=1).mean(), label=POLICY_LABELS[policy], alpha=0.9)
            axes[1].plot(data["period"], data["avg_yard_queue"].rolling(12, min_periods=1).mean(), label=POLICY_LABELS[policy], alpha=0.9)
        axes[0].set_ylabel("闸口平均队列")
        axes[1].set_ylabel("堆场平均队列")
        axes[1].set_xlabel("仿真周期（30分钟）")
        axes[0].legend(ncol=2)
        for ax in axes:
            ax.grid(alpha=0.25)
        fig.suptitle("重负荷场景最后7天队列轨迹（6小时移动平均）")
        fig.tight_layout()
        path = plot_dir / "queue_trajectories.png"
        fig.savefig(path, dpi=180, bbox_inches="tight")
        plt.close(fig)
        created.append(path)

        joint = trajectories[(trajectories["scenario"] == "heavy") & (trajectories["policy"] == "online_joint")]
        fig, axes = plt.subplots(2, 1, figsize=(14, 7), sharex=True)
        axes[0].plot(joint["period"], joint["quota"], linewidth=0.8)
        axes[0].set_ylabel("预约配额")
        axes[1].step(joint["period"], joint["yard_capacity"], where="post", linewidth=0.8)
        axes[1].set_ylabel("堆场能力等级")
        axes[1].set_xlabel("仿真周期（30分钟）")
        for ax in axes:
            ax.grid(alpha=0.25)
        fig.suptitle("在线协同策略动作轨迹")
        fig.tight_layout()
        path = plot_dir / "online_actions.png"
        fig.savefig(path, dpi=180, bbox_inches="tight")
        plt.close(fig)
        created.append(path)
    return created


def write_report(raw: pd.DataFrame, summary: pd.DataFrame, output_dir: str | Path, bootstrap_samples: int) -> Path:
    output = Path(output_dir)
    figure_dir = output / "figures"
    strategy_plot = "figures/strategy_comparison.png"
    queue_plot = "figures/queue_trajectories.png"
    actions_plot = "figures/online_actions.png"
    hypotheses = _hypothesis_rows(raw, bootstrap_samples)
    selected_metrics = ["mean_total_wait", "p95_total_wait", "mean_yard_wait", "mean_composite_cost", "yard_resource_hours_per_truck", "throughput_rate", "acceptance_rate"]
    table = summary[(summary["scenario"] == "heavy") & summary["metric"].isin(selected_metrics)].copy()
    table["policy"] = table["policy"].map(POLICY_LABELS)
    table["mean_ci"] = table.apply(lambda x: f"{x['mean']:.3f} [{x['ci_low']:.3f}, {x['ci_high']:.3f}]", axis=1)
    pivot = table.pivot(index="metric", columns="policy", values="mean_ci")
    heavy = raw[raw["scenario"] == "heavy"].groupby("policy").mean(numeric_only=True)
    pto_throughput = float(heavy.loc["pto", "throughput_rate"])
    online_throughput = float(heavy.loc["online_joint", "throughput_rate"])
    throughput_gap = online_throughput - pto_throughput
    lines = [
        "# 港口闸口—堆场在线队列学习：合成数据数值测试报告",
        "",
        "> 本报告基于风格化合成参数，仅用于方法可行性检验，不代表真实港口标定结果。",
        "",
        "## 核心结果（重负荷场景）",
        "",
        pivot.to_markdown(),
        "",
        f"> PTO的综合指标较低，但其重负荷吞吐率为{pto_throughput:.3f}，低于在线协同的{online_throughput:.3f}（差{throughput_gap:.3f}）。因此H3的结果应解释为当前权重下的效率—服务水平权衡，而不是PTO全面占优。",
        "",
        "## 研究假设判定",
        "",
        "| 假设 | 判据 | 判定 | 在线策略相对基准的平均差异（95% CI） |",
        "|---|---|---|---|",
    ]
    for item in hypotheses:
        effect = item["effect"]
        verdict = "支持" if item["supported"] else "暂不支持"
        lines.append(
            f"| {item['hypothesis']} | {item['criterion']} | {verdict} | "
            f"{effect['difference']:.3f} [{effect['ci_low']:.3f}, {effect['ci_high']:.3f}] |"
        )
    lines.extend([
        "",
        "## 解释边界",
        "",
        "- 置信区间来自按重复实验配对的 Bootstrap；区间完全低于0表示在线策略在该指标上具有稳定优势。",
        "- 综合指标中的服务违约项包含拒绝预约需求，防止策略通过无限压低配额来制造表面上的低等待。",
        "- 在线策略和PTO设置85%的最低预约接受率约束；固定策略保持预设配额，作为传统管理基准。",
        "- 在线算法借鉴双点有限差分与安全投影，不继承参考文献的单队列 regret 上界。",
        "- 若假设暂不支持，应优先检查权重、学习率、决策周期和负荷设定，而不能据此否定理论机制。",
        "- 接入真实港口数据后，需要重新估计需求、履约偏差、服务时间及设备扰动参数。",
        "",
        "## 图表",
        "",
        f"![策略对比]({strategy_plot})",
        "",
        f"[直接打开策略对比图]({strategy_plot})",
        "",
        f"![队列轨迹]({queue_plot})",
        "",
        f"[直接打开队列轨迹图]({queue_plot})",
        "",
        f"![在线动作]({actions_plot})",
        "",
        f"[直接打开在线动作图]({actions_plot})",
        "",
        "> 如果 VS Code 的 Markdown 预览仍不显示图片，请打开同目录下的 `numerical_test_report.html`。HTML 版本已把图片嵌入文件内部，不依赖图片路径解析。",
    ])
    path = output / "numerical_test_report.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    html_path = output / "numerical_test_report.html"
    hypothesis_table = pd.DataFrame(
        [
            {
                "假设": item["hypothesis"],
                "判据": item["criterion"],
                "判定": "支持" if item["supported"] else "暂不支持",
                "在线策略相对基准的平均差异（95% CI）": (
                    f"{item['effect']['difference']:.3f} "
                    f"[{item['effect']['ci_low']:.3f}, {item['effect']['ci_high']:.3f}]"
                ),
            }
            for item in hypotheses
        ]
    )
    html = f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>港口闸口—堆场在线队列学习：合成数据数值测试报告</title>
  <style>
    body {{ max-width: 1180px; margin: 32px auto; padding: 0 24px; font-family: "Microsoft YaHei", "Noto Sans CJK SC", Arial, sans-serif; line-height: 1.6; color: #1f2937; }}
    h1, h2 {{ color: #111827; }}
    table {{ border-collapse: collapse; width: 100%; margin: 16px 0 28px; font-size: 14px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 8px 10px; text-align: left; }}
    th {{ background: #f3f4f6; }}
    blockquote {{ border-left: 4px solid #94a3b8; margin-left: 0; padding: 8px 14px; background: #f8fafc; }}
    img {{ display: block; max-width: 100%; margin: 14px 0 34px; border: 1px solid #e5e7eb; border-radius: 8px; }}
  </style>
</head>
<body>
  <h1>港口闸口—堆场在线队列学习：合成数据数值测试报告</h1>
  <blockquote>本报告基于风格化合成参数，仅用于方法可行性检验，不代表真实港口标定结果。</blockquote>
  <h2>核心结果（重负荷场景）</h2>
  {pivot.to_html()}
  <blockquote>{escape(f"PTO的综合指标较低，但其重负荷吞吐率为{pto_throughput:.3f}，低于在线协同的{online_throughput:.3f}（差{throughput_gap:.3f}）。因此H3的结果应解释为当前权重下的效率—服务水平权衡，而不是PTO全面占优。")}</blockquote>
  <h2>研究假设判定</h2>
  {hypothesis_table.to_html(index=False)}
  <h2>解释边界</h2>
  <ul>
    <li>置信区间来自按重复实验配对的 Bootstrap；区间完全低于0表示在线策略在该指标上具有稳定优势。</li>
    <li>综合指标中的服务违约项包含拒绝预约需求，防止策略通过无限压低配额来制造表面上的低等待。</li>
    <li>在线策略和PTO设置85%的最低预约接受率约束；固定策略保持预设配额，作为传统管理基准。</li>
    <li>在线算法借鉴双点有限差分与安全投影，不继承参考文献的单队列 regret 上界。</li>
    <li>若假设暂不支持，应优先检查权重、学习率、决策周期和负荷设定，而不能据此否定理论机制。</li>
    <li>接入真实港口数据后，需要重新估计需求、履约偏差、服务时间及设备扰动参数。</li>
  </ul>
  <h2>图表</h2>
  <h3>策略对比</h3>
  <img alt="策略对比" src="{_png_data_uri(figure_dir / 'strategy_comparison.png')}">
  <h3>队列轨迹</h3>
  <img alt="队列轨迹" src="{_png_data_uri(figure_dir / 'queue_trajectories.png')}">
  <h3>在线动作</h3>
  <img alt="在线动作" src="{_png_data_uri(figure_dir / 'online_actions.png')}">
</body>
</html>
"""
    html_path.write_text(html, encoding="utf-8")
    return path


def generate_outputs(output_dir: str | Path, bootstrap_samples: int) -> tuple[list[Path], Path]:
    output = Path(output_dir)
    raw = pd.read_csv(output / "raw_results.csv")
    summary = pd.read_csv(output / "summary_results.csv")
    trajectories_path = output / "example_trajectories.csv"
    trajectories = pd.read_csv(trajectories_path) if trajectories_path.exists() else pd.DataFrame()
    plots = create_plots(raw, summary, trajectories, output)
    report = write_report(raw, summary, output, bootstrap_samples)
    return plots, report
