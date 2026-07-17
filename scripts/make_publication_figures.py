from __future__ import annotations

import re
from pathlib import Path

import matplotlib as mpl
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib.patches import FancyArrowPatch, FancyBboxPatch


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "generated" / "figures"
REPAIR = ROOT / "results" / "table8" / "adaptive_pto_summary_results.csv"
FIDELITY = ROOT / "results" / "e2" / "online_vs_pto_by_fidelity.csv"
ABLATION = ROOT / "results" / "e3" / "gate_only_vs_online_joint.csv"


COLORS = {
    "fixed": "#8A8A8A",
    "pto": "#2F5D8C",
    "pto_adaptive_slow": "#4C78A8",
    "pto_adaptive_fast": "#6BAED6",
    "online_fast_only": "#F28E2B",
    "online_joint": "#2CA25F",
    "gate_only": "#B07AA1",
}

LABELS = {
    "fixed": "Fixed rule",
    "pto": "PTO",
    "pto_adaptive_slow": "Rolling PTO\nslow",
    "pto_adaptive_fast": "Rolling PTO\nfast",
    "online_fast_only": "Feedback\nfast-only",
    "online_joint": "Feedback\njoint",
    "gate_only": "Gate-only\nfeedback",
}

SCENARIOS = {
    "sc_high_workload": "High workload",
    "sc_peak_workload": "Peak workload",
}


def setup_style() -> None:
    mpl.rcParams.update(
        {
            "font.family": "DejaVu Sans",
            "font.size": 9,
            "axes.titlesize": 10,
            "axes.labelsize": 9,
            "xtick.labelsize": 8,
            "ytick.labelsize": 8,
            "legend.fontsize": 8,
            "figure.titlesize": 12,
            "axes.spines.top": False,
            "axes.spines.right": False,
            "axes.edgecolor": "#444444",
            "axes.linewidth": 0.8,
            "grid.color": "#D9D9D9",
            "grid.linewidth": 0.55,
            "pdf.fonttype": 42,
            "ps.fonttype": 42,
            "savefig.bbox": "tight",
            "savefig.pad_inches": 0.05,
        }
    )


def save(fig: plt.Figure, name: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / f"{name}.png", dpi=450)
    fig.savefig(OUT / f"{name}.pdf")
    plt.close(fig)


def add_box(
    ax: plt.Axes,
    x: float,
    y: float,
    w: float,
    h: float,
    title: str,
    subtitle: str,
    face: str,
    edge: str,
) -> None:
    box = FancyBboxPatch(
        (x, y),
        w,
        h,
        boxstyle="round,pad=0.018,rounding_size=0.035",
        linewidth=1.2,
        edgecolor=edge,
        facecolor=face,
    )
    ax.add_patch(box)
    ax.text(x + w / 2, y + h * 0.62, title, ha="center", va="center", fontsize=10.5, fontweight="bold", color="#1F2933")
    ax.text(x + w / 2, y + h * 0.30, subtitle, ha="center", va="center", fontsize=8.2, color="#44515C")


def add_arrow(ax: plt.Axes, start: tuple[float, float], end: tuple[float, float], color: str = "#4A5568", lw: float = 1.6) -> None:
    arr = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=12,
        linewidth=lw,
        color=color,
        shrinkA=4,
        shrinkB=4,
        connectionstyle="arc3,rad=0.0",
    )
    ax.add_patch(arr)


def build_service_ecosystem() -> None:
    fig, ax = plt.subplots(figsize=(11.8, 4.4))
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")

    ax.text(
        0.5,
        0.94,
        "Port landside service ecosystem: predictive planning plus feedback correction",
        ha="center",
        va="center",
        fontsize=13,
        color="#1F2933",
    )

    flow_y, box_h, box_w = 0.58, 0.22, 0.17
    xs = [0.055, 0.30, 0.545, 0.79]
    add_box(ax, xs[0], flow_y, box_w, box_h, "Demand layer", "appointments,\nactual arrivals", "#EAF2FB", "#2F5D8C")
    add_box(ax, xs[1], flow_y, box_w, box_h, "Gate service", "admission slots,\nentry queue", "#F0F5FF", "#4C78A8")
    add_box(ax, xs[2], flow_y, box_w, box_h, "Yard service", "equipment capacity,\nyard queue", "#EBF7EF", "#2CA25F")
    add_box(ax, xs[3], flow_y, box_w, box_h, "Outcomes", "wait, throughput,\nqueue drift", "#FFF4E6", "#F28E2B")

    for i in range(3):
        add_arrow(ax, (xs[i] + box_w, flow_y + box_h / 2), (xs[i + 1], flow_y + box_h / 2))

    add_box(ax, 0.105, 0.20, 0.34, 0.19, "Predictive planning / PTO", "open-loop appointment and capacity plan\nunder a belief model", "#F7FAFC", "#2F5D8C")
    add_box(ax, 0.555, 0.20, 0.34, 0.19, "Online collaborative correction", "fast workload feedback + slow model update\nwith safety projection", "#F7FAFC", "#2CA25F")

    add_arrow(ax, (0.275, 0.39), (0.38, flow_y), COLORS["pto"], 1.35)
    add_arrow(ax, (0.275, 0.39), (0.625, flow_y), COLORS["pto"], 1.35)
    add_arrow(ax, (0.875, flow_y), (0.73, 0.39), "#F28E2B", 1.35)
    add_arrow(ax, (0.725, 0.39), (0.395, flow_y), COLORS["online_joint"], 1.35)
    add_arrow(ax, (0.725, 0.39), (0.64, flow_y), COLORS["online_joint"], 1.35)

    ax.text(
        0.50,
        0.08,
        "The paper does not claim feedback always dominates high-fidelity planning; it tests when feedback adds value under workload variation and model-fidelity loss.",
        ha="center",
        va="center",
        fontsize=8.4,
        color="#5B6770",
    )
    fig.tight_layout()
    save(fig, "fig_service_ecosystem")


def parse_mean(cell: str | float) -> float:
    if isinstance(cell, (int, float)):
        return float(cell)
    m = re.match(r"\s*([-+]?\d*\.?\d+)", str(cell))
    if not m:
        raise ValueError(f"Cannot parse numeric mean from {cell!r}")
    return float(m.group(1))


def build_policy_regime_map() -> None:
    df = pd.read_csv(REPAIR)
    policies = ["fixed", "pto", "pto_adaptive_slow", "pto_adaptive_fast", "online_fast_only", "online_joint"]
    metric_specs = [
        ("mean_composite_cost", "Weighted cost", "lower is better", False),
        ("p95_total_wait", "P95 waiting time", "minutes, log scale", True),
        ("tail_net_queue_drift", "Tail queue drift", "trucks/window", False),
        ("unstable", "Unstable share", "share of replications", False),
    ]

    fig, axes = plt.subplots(2, 4, figsize=(12.5, 6.7), sharex=False)
    x = np.arange(len(policies))
    width = 0.66

    for row, scenario in enumerate(["sc_high_workload", "sc_peak_workload"]):
        for col, (metric, title, subtitle, logy) in enumerate(metric_specs):
            ax = axes[row, col]
            sub = (
                df[(df["scenario"] == scenario) & (df["metric"] == metric)]
                .set_index("policy")
                .loc[policies]
                .reset_index()
            )
            vals = sub["mean"].astype(float).to_numpy()
            lows = sub["ci_low"].astype(float).to_numpy()
            highs = sub["ci_high"].astype(float).to_numpy()
            colors = [COLORS[p] for p in policies]
            ax.bar(x, vals, color=colors, width=width, alpha=0.92, edgecolor="none")
            err_low = np.maximum(vals - lows, 0)
            err_high = np.maximum(highs - vals, 0)
            ax.errorbar(x, vals, yerr=[err_low, err_high], fmt="none", ecolor="#333333", elinewidth=0.8, capsize=2)
            ax.axhline(0, color="#555555", lw=0.7)
            if logy:
                ax.set_yscale("log")
                ax.set_ylim(max(1, min(vals) * 0.55), max(vals) * 1.55)
            if metric == "tail_net_queue_drift":
                ax.axhspan(min(-0.08, vals.min() * 1.15), 0, color="#2CA25F", alpha=0.08, zorder=0)
                ax.text(0.02, 0.05, "queue draining", transform=ax.transAxes, color="#2CA25F", fontsize=7)
            ax.grid(axis="y")
            ax.set_axisbelow(True)
            if row == 0:
                ax.set_title(f"{title}\n({subtitle})", pad=8)
            if col == 0:
                ax.set_ylabel(SCENARIOS[scenario], fontweight="bold")
            ax.set_xticks(x)
            if row == 1:
                ax.set_xticklabels([LABELS[p] for p in policies], rotation=40, ha="right")
            else:
                ax.set_xticklabels([])
            if metric in {"mean_composite_cost", "unstable"}:
                ax.set_ylim(bottom=0)
            if metric == "mean_composite_cost":
                pto_idx = policies.index("pto")
                fb_idx = policies.index("online_joint")
                ax.annotate(
                    "planning\nbenchmark",
                    xy=(pto_idx, vals[pto_idx]),
                    xytext=(pto_idx - 0.25, vals[pto_idx] + max(vals) * 0.18),
                    arrowprops=dict(arrowstyle="-", color=COLORS["pto"], lw=0.8),
                    ha="center",
                    va="bottom",
                    fontsize=7,
                    color=COLORS["pto"],
                )
                ax.annotate(
                    "feedback\ncorrection",
                    xy=(fb_idx, vals[fb_idx]),
                    xytext=(fb_idx + 0.35, vals[fb_idx] + max(vals) * 0.18),
                    arrowprops=dict(arrowstyle="-", color=COLORS["online_joint"], lw=0.8),
                    ha="center",
                    va="bottom",
                    fontsize=7,
                    color=COLORS["online_joint"],
                )

    fig.suptitle("Regime-level diagnostics for planning and feedback policies", y=1.02, fontweight="normal")
    fig.text(
        0.01,
        -0.02,
        "Notes: bars show 50-replication means; whiskers are bootstrap 95% confidence intervals. P95 waiting is plotted on a log scale.",
        fontsize=8,
        color="#555555",
    )
    fig.tight_layout()
    save(fig, "fig_policy_regime_map")


def build_fidelity_stress() -> None:
    df = pd.read_csv(FIDELITY)
    order = ["high_fidelity", "mild_misspecification", "medium_misspecification", "severe_misspecification"]
    labels = ["High\nfidelity", "Mild\nmisspec.", "Medium\nmisspec.", "Severe\nmisspec."]
    metrics = [
        ("mean_composite_cost", "Weighted cost", "cost units"),
        ("p95_total_wait", "P95 waiting time", "minutes"),
        ("throughput_rate", "Throughput rate", "share"),
    ]

    fig, axes = plt.subplots(1, 3, figsize=(12.4, 3.9))
    x = np.arange(len(order))

    for ax, (metric, title, ylabel) in zip(axes, metrics):
        sub = df[df["metric"] == metric].set_index("fidelity_level").loc[order].reset_index()
        pto = sub["pto"].map(parse_mean).to_numpy()
        fb = sub["online_joint"].map(parse_mean).to_numpy()
        ax.plot(x, pto, marker="o", lw=2.2, color=COLORS["pto"], label="PTO under belief model")
        ax.plot(x, fb, marker="s", lw=2.2, color=COLORS["online_joint"], label="Feedback correction")
        if metric in {"mean_composite_cost", "p95_total_wait"}:
            ax.set_yscale("log")
        ax.axvspan(1.5, 3.5, color="#F28E2B", alpha=0.08, zorder=0)
        ax.text(2.5, 0.95, "model-fidelity\nstress zone", transform=ax.get_xaxis_transform(), ha="center", va="top", fontsize=8, color="#8A4B08")
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.set_title(title)
        ax.set_ylabel(ylabel)
        ax.grid(axis="y")
        ax.set_axisbelow(True)
        for i in [0, 3]:
            ax.annotate(
                f"{pto[i]:.2f}" if pto[i] < 100 else f"{pto[i]:.0f}",
                (x[i], pto[i]),
                textcoords="offset points",
                xytext=(0, 8),
                ha="center",
                fontsize=7,
                color=COLORS["pto"],
            )
            ax.annotate(
                f"{fb[i]:.2f}" if fb[i] < 100 else f"{fb[i]:.0f}",
                (x[i], fb[i]),
                textcoords="offset points",
                xytext=(0, -12),
                ha="center",
                fontsize=7,
                color=COLORS["online_joint"],
            )

    axes[0].legend(loc="upper left", frameon=False)
    fig.suptitle("Model-fidelity stress test", y=1.04, fontweight="normal")
    fig.text(
        0.01,
        -0.04,
        "Notes: the true peak-workload environment is held fixed; only PTO's belief model is degraded. Log scales are used for cost and P95 waiting.",
        fontsize=8,
        color="#555555",
    )
    fig.tight_layout()
    save(fig, "fig_model_fidelity_stress")


def build_gate_yard_ablation() -> None:
    df = pd.read_csv(ABLATION)
    keep = ["mean_yard_wait", "p95_yard_queue", "mean_yard_queue"]
    metric_names = {
        "mean_yard_wait": "Mean yard wait\n(minutes)",
        "p95_yard_queue": "P95 yard queue\n(trucks)",
        "mean_yard_queue": "Mean yard queue\n(trucks)",
    }
    scenarios = ["sc_high_workload", "sc_peak_workload"]
    fig, axes = plt.subplots(1, 3, figsize=(11.8, 3.9), sharey=False)

    for ax, metric in zip(axes, keep):
        sub = df[df["metric"] == metric].set_index("scenario").loc[scenarios].reset_index()
        x = np.arange(len(scenarios))
        gate = sub["baseline_mean"].astype(float).to_numpy()
        joint = sub["target_mean"].astype(float).to_numpy()
        improve = sub["relative_improvement_pct"].astype(float).to_numpy()
        ax.plot(x, gate, "o-", color=COLORS["gate_only"], lw=2, ms=6, label="Gate-only feedback")
        ax.plot(x, joint, "s-", color=COLORS["online_joint"], lw=2, ms=6, label="Joint gate-yard feedback")
        for i in range(len(x)):
            ax.annotate(
                f"{improve[i]:.0f}% lower",
                xy=(x[i], (gate[i] + joint[i]) / 2),
                xytext=(8, 0),
                textcoords="offset points",
                fontsize=8,
                color=COLORS["online_joint"],
                va="center",
            )
            ax.vlines(x[i], joint[i], gate[i], color="#555555", lw=0.8, alpha=0.55)
        ax.set_xticks(x)
        ax.set_xticklabels([SCENARIOS[s] for s in scenarios])
        ax.set_title(metric_names[metric])
        ax.grid(axis="y")
        ax.set_axisbelow(True)
        ax.set_ylim(bottom=0)
    axes[1].legend(loc="upper center", bbox_to_anchor=(0.5, -0.14), ncol=2, frameon=False)
    fig.suptitle("Gate-only feedback versus joint gate-yard feedback", y=1.04, fontweight="normal")
    fig.text(
        0.01,
        -0.04,
        "Notes: paired comparisons use common random scenarios; labels report relative reductions from gate-only to joint feedback.",
        fontsize=8,
        color="#555555",
    )
    fig.tight_layout()
    save(fig, "fig_gate_yard_ablation")


def main() -> None:
    setup_style()
    build_service_ecosystem()
    build_fidelity_stress()
    print("Figure 3 is not regenerated because the original Table 10 diagnostic script is missing.")


if __name__ == "__main__":
    main()
