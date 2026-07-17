from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from .config import ScenarioConfig, SimulationConfig
from .policies import make_policies
from .randomness import generate_randomness
from .simulation import SimulationResult, run_simulation


METRICS = [
    "mean_gate_wait", "mean_yard_wait", "mean_total_wait", "p95_total_wait",
    "mean_turnaround", "mean_gate_queue", "mean_yard_queue", "p95_yard_queue",
    "throughput_rate", "completion_rate", "acceptance_rate", "gate_utilization", "yard_utilization",
    "yard_resource_hours_per_truck", "mean_composite_cost", "mean_quota",
    "mean_yard_capacity", "unstable", "queue_tail_slope", "terminal_system",
    "uncompleted_at_drain_limit", "drain_truncated", "drain_minutes",
    "first_queue_threshold_period", "mean_net_queue_drift", "tail_net_queue_drift",
    "service_floor_binding_rate", "projection_binding_rate",
]


def run_experiments(
    config: SimulationConfig,
    output_dir: str | Path,
    replications: int | None = None,
    keep_example_trajectories: bool = True,
    policy_names: list[str] | tuple[str, ...] | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    n_rep = replications or config.replications
    summaries: list[dict[str, object]] = []
    examples: list[pd.DataFrame] = []
    for scenario_index, scenario in enumerate(config.scenarios):
        for replication in range(n_rep):
            scenario_seed = 10_000 * (scenario_index + 1) + replication
            randomness = generate_randomness(config, scenario, scenario_seed)
            for policy_index, policy in enumerate(make_policies(config, policy_names)):
                result = run_simulation(
                    config,
                    scenario,
                    policy,
                    randomness,
                    replication,
                    policy_seed=scenario_seed + 100_000 * (policy_index + 1),
                )
                summaries.append(result.summary)
                if keep_example_trajectories and replication == 0:
                    frame = result.periods.copy()
                    frame.insert(0, "policy", result.policy)
                    frame.insert(0, "scenario", result.scenario)
                    examples.append(frame)
    raw = pd.DataFrame(summaries)
    raw.to_csv(output / "raw_results.csv", index=False, encoding="utf-8-sig")
    if examples:
        pd.concat(examples, ignore_index=True).to_csv(output / "example_trajectories.csv", index=False, encoding="utf-8-sig")
    summary = summarize_results(raw, config.bootstrap_samples)
    summary.to_csv(output / "summary_results.csv", index=False, encoding="utf-8-sig")
    return raw, summary


def _bootstrap_ci(values: np.ndarray, samples: int, seed: int) -> tuple[float, float]:
    values = values[np.isfinite(values)]
    if len(values) == 0:
        return float("nan"), float("nan")
    if len(values) == 1:
        return float(values[0]), float(values[0])
    rng = np.random.default_rng(seed)
    means = np.empty(samples)
    chunk = 250
    written = 0
    while written < samples:
        size = min(chunk, samples - written)
        idx = rng.integers(0, len(values), size=(size, len(values)))
        means[written:written + size] = values[idx].mean(axis=1)
        written += size
    return float(np.quantile(means, 0.025)), float(np.quantile(means, 0.975))


def summarize_results(raw: pd.DataFrame, bootstrap_samples: int) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    seed = 7
    for (scenario, policy), group in raw.groupby(["scenario", "policy"], sort=False):
        for metric in METRICS:
            values = group[metric].to_numpy(dtype=float)
            low, high = _bootstrap_ci(values, bootstrap_samples, seed)
            seed += 1
            rows.append({
                "scenario": scenario,
                "policy": policy,
                "metric": metric,
                "mean": float(np.nanmean(values)),
                "ci_low": low,
                "ci_high": high,
                "n": int(np.isfinite(values).sum()),
            })
    return pd.DataFrame(rows)


def paired_difference(raw: pd.DataFrame, scenario: str, metric: str, online: str, baseline: str, samples: int = 2000) -> dict[str, float]:
    pivot = raw[raw["scenario"] == scenario].pivot(index="replication", columns="policy", values=metric).dropna()
    differences = (pivot[online] - pivot[baseline]).to_numpy(dtype=float)
    low, high = _bootstrap_ci(differences, samples, seed=391)
    base_mean = float(pivot[baseline].mean())
    return {
        "difference": float(differences.mean()),
        "ci_low": low,
        "ci_high": high,
        "relative_change": float(differences.mean() / base_mean) if abs(base_mean) > 1e-12 else float("nan"),
    }
