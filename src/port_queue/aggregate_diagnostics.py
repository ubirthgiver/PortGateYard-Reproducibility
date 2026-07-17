"""Independent aggregate reconstructions for manuscript Tables 10 and 12."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

import numpy as np
import pandas as pd


PolicyName = Literal[
    "pto_frozen",
    "pto_reid_7d",
    "pto_reid_3d",
    "pto_reid_1d",
    "feedback_fast",
    "feedback_tracker",
    "pto_high_fidelity",
]


@dataclass(frozen=True)
class AggregateConfig:
    slot_minutes: int = 30
    days: int = 30
    warmup_days: int = 7
    late_horizon_days: int = 10
    mean_requests: float = 24.595419847328245
    gate_service_mean: float = 5.0
    yard_service_mean: float = 10.0
    gate_lanes: int = 4
    yard_min: int = 6
    yard_max: int = 10
    quota_min: int = 12
    quota_max: int = 30
    no_show_probability: float = 0.04
    exception_mean: float = 0.5
    disruption_probability: float = 0.0611
    capacity_variance_to_mean: float = 1.8
    access_floor: float = 0.85
    queue_scale: float = 20.0
    pressure_clip: float = 1.5
    yard_pressure_reference: float = 0.20
    diagnostic_center_quota: float = 0.50
    diagnostic_center_yard: float = 0.60
    kgg: float = 0.18
    kgy: float = 0.28
    kyg: float = 0.08
    kyy: float = 0.45
    eta0: float = 0.08
    delta0: float = 0.10
    delta_min: float = 0.03
    initial_severe_quota: int = 24
    initial_severe_yard: int = 6
    high_fidelity_quota: int = 15
    high_fidelity_yard: int = 6
    drain_quota: int = 14
    drain_release_threshold: float = 5.0
    weights: tuple[float, float, float, float, float] = (0.30, 0.30, 0.20, 0.10, 0.10)

    @property
    def periods(self) -> int:
        return self.days * 48

    @property
    def warmup_periods(self) -> int:
        return self.warmup_days * 48

    @property
    def late_horizon_periods(self) -> int:
        return self.late_horizon_days * 48


def lateness_probabilities(support: int) -> np.ndarray:
    """Keep no-shows at 4% and redistribute the 16% late-arrival mass."""
    if support == 1:
        return np.array([0.80, 0.16, 0.04])
    if support == 2:
        return np.array([0.80, 0.13, 0.03, 0.04])
    if support == 4:
        tail = np.array([0.13, 0.03, 0.015, 0.005])
        tail *= 0.16 / tail.sum()
        return np.r_[0.80, tail, 0.04]
    raise ValueError("lateness support must be 1, 2, or 4")


def _physical_actions(config: AggregateConfig, zq: np.ndarray, zy: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    q = np.rint(config.quota_min + np.clip(zq, 0.0, 1.0) * (config.quota_max - config.quota_min)).astype(int)
    y = np.rint(config.yard_min + np.clip(zy, 0.0, 1.0) * (config.yard_max - config.yard_min)).astype(int)
    return q, y


def _sample_cohort(
    rng: np.random.Generator,
    confirmed: np.ndarray,
    probabilities: np.ndarray,
) -> list[np.ndarray]:
    remaining = confirmed.astype(int).copy()
    remaining_probability = 1.0
    draws: list[np.ndarray] = []
    for probability in probabilities[:-1]:
        conditional = probability / remaining_probability
        draw = rng.binomial(remaining, np.clip(conditional, 0.0, 1.0))
        draws.append(draw)
        remaining -= draw
        remaining_probability -= probability
    draws.append(remaining)
    return draws


def _ols_slopes(values: np.ndarray) -> np.ndarray:
    x = np.arange(values.shape[0], dtype=float)
    xc = x - x.mean()
    return (xc[:, None] * values).sum(axis=0) / np.square(xc).sum()


def _sample_capacity(rng: np.random.Generator, mean: np.ndarray | float, variance_to_mean: float, paths: int) -> np.ndarray:
    """Sample completion counts with a gamma--Poisson mixture."""
    mean_array = np.broadcast_to(np.asarray(mean, dtype=float), (paths,))
    if variance_to_mean <= 1.0:
        return rng.poisson(mean_array)
    extra = variance_to_mean - 1.0
    latent_mean = rng.gamma(shape=mean_array / extra, scale=extra)
    return rng.poisson(latent_mean)


def simulate_paths(
    config: AggregateConfig,
    policy: PolicyName,
    seed: int,
    paths: int,
    *,
    lateness_support: int = 2,
    gain_multiplier: float = 1.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    probabilities = lateness_probabilities(lateness_support)
    delayed = [np.zeros(paths, dtype=int) for _ in range(lateness_support)]
    qg = np.zeros(paths, dtype=float)
    qy = np.zeros(paths, dtype=float)
    previous_q = np.full(paths, 21, dtype=int)
    previous_y = np.full(paths, 8, dtype=int)
    zq = np.full(paths, config.diagnostic_center_quota, dtype=float)
    zy = np.full(paths, config.diagnostic_center_yard, dtype=float)
    tracker_iteration = np.zeros(paths, dtype=int)
    tracker_coordinate = rng.integers(0, 2, size=paths)
    tracker_direction = np.full(paths, -1, dtype=int)
    tracker_minus_cost = np.zeros(paths, dtype=float)
    reidentified = np.zeros(paths, dtype=bool)

    eval_cost = np.zeros(paths)
    eval_queue = np.zeros(paths)
    eval_count = 0
    mean_yard_trace = np.zeros(config.periods)
    path_yard_tail = np.zeros((config.late_horizon_periods, paths))

    update_days = {"pto_reid_7d": 7, "pto_reid_3d": 3, "pto_reid_1d": 1}
    update_interval = update_days.get(policy, 0) * 48
    floor_quota = int(np.ceil(config.access_floor * config.mean_requests))

    for t in range(config.periods):
        if policy == "pto_frozen":
            quota = np.full(paths, config.initial_severe_quota, dtype=int)
            yard = np.full(paths, config.initial_severe_yard, dtype=int)
        elif policy == "pto_high_fidelity":
            quota = np.full(paths, config.high_fidelity_quota, dtype=int)
            yard = np.full(paths, config.high_fidelity_yard, dtype=int)
        elif policy in update_days:
            if t > 0 and t % update_interval == 0:
                reidentified[:] = True
            quota = np.where(
                reidentified & (qy > config.drain_release_threshold),
                config.drain_quota,
                np.where(reidentified, config.high_fidelity_quota, config.initial_severe_quota),
            ).astype(int)
            yard = np.full(paths, config.initial_severe_yard, dtype=int)
        else:
            pg = np.clip(qg / config.queue_scale, 0.0, config.pressure_clip)
            py = np.clip(qy / config.queue_scale, 0.0, config.pressure_clip)
            perturb_q = np.zeros(paths)
            perturb_y = np.zeros(paths)
            if policy == "feedback_tracker":
                delta = np.maximum(config.delta_min, config.delta0 * np.power(tracker_iteration + 1, -1.0 / 3.0))
                perturb_q = np.where(tracker_coordinate == 0, tracker_direction * delta, 0.0)
                perturb_y = np.where(tracker_coordinate == 1, tracker_direction * delta, 0.0)
            bq = gain_multiplier * (-config.kgg * pg - config.kgy * py)
            by = gain_multiplier * (config.kyg * pg + config.kyy * (py - config.yard_pressure_reference))
            quota, yard = _physical_actions(config, zq + perturb_q + bq, zy + perturb_y + by)
            quota = np.maximum(quota, floor_quota)

        # Saturated demand fills every offered appointment slot.
        confirmed = quota.copy()
        cohort = _sample_cohort(rng, confirmed, probabilities)
        arrivals = cohort[0] + delayed.pop(0) + rng.poisson(config.exception_mean, size=paths)
        for lag in range(lateness_support):
            if lag < lateness_support - 1:
                delayed[lag] += cohort[lag + 1]
            else:
                delayed.append(cohort[lag + 1])

        disrupted = rng.random(paths) < config.disruption_probability
        effective_yard = np.maximum(config.yard_min, yard - disrupted.astype(int))
        gate_mean_capacity = config.gate_lanes * config.slot_minutes / config.gate_service_mean
        yard_mean_capacity = effective_yard * config.slot_minutes / config.yard_service_mean
        gate_capacity = _sample_capacity(rng, gate_mean_capacity, config.capacity_variance_to_mean, paths)
        yard_capacity = _sample_capacity(rng, yard_mean_capacity, config.capacity_variance_to_mean, paths)

        gate_available = qg + arrivals
        gate_done = np.minimum(gate_available, gate_capacity)
        qg = gate_available - gate_done
        yard_available = qy + gate_done
        yard_done = np.minimum(yard_available, yard_capacity)
        qy = yard_available - yard_done

        w_g, w_y, w_r, w_s, w_l = config.weights
        resource = (yard - config.yard_min) / (config.yard_max - config.yard_min)
        adjustment = 0.5 * (
            np.abs(quota - previous_q) / (config.quota_max - config.quota_min)
            + np.abs(yard - previous_y) / (config.yard_max - config.yard_min)
        )
        unconfirmed = np.maximum(config.mean_requests - confirmed, 0.0) / config.mean_requests
        cost = (
            w_g * qg / config.queue_scale
            + w_y * qy / config.queue_scale
            + w_r * resource
            + w_s * adjustment
            + w_l * unconfirmed
        )

        if policy == "feedback_tracker":
            minus = tracker_direction < 0
            tracker_minus_cost[minus] = cost[minus]
            plus = ~minus
            if np.any(plus):
                delta = np.maximum(config.delta_min, config.delta0 * np.power(tracker_iteration[plus] + 1, -1.0 / 3.0))
                gradient = (cost[plus] - tracker_minus_cost[plus]) / (2.0 * delta)
                eta = config.eta0 * np.power(tracker_iteration[plus] + 1, -0.6)
                plus_indices = np.flatnonzero(plus)
                q_indices = plus_indices[tracker_coordinate[plus] == 0]
                y_indices = plus_indices[tracker_coordinate[plus] == 1]
                zq[q_indices] = np.clip(zq[q_indices] - eta[tracker_coordinate[plus] == 0] * gradient[tracker_coordinate[plus] == 0], 0.0, 1.0)
                zy[y_indices] = np.clip(zy[y_indices] - eta[tracker_coordinate[plus] == 1] * gradient[tracker_coordinate[plus] == 1], 0.0, 1.0)
                tracker_iteration[plus] += 1
                tracker_coordinate[plus] = rng.integers(0, 2, size=plus.sum())
            tracker_direction *= -1

        if t >= config.warmup_periods:
            eval_cost += cost
            eval_queue += qg + qy
            eval_count += 1
        mean_yard_trace[t] = qy.mean()
        tail_start = config.periods - config.late_horizon_periods
        if t >= tail_start:
            path_yard_tail[t - tail_start] = qy
        previous_q, previous_y = quota, yard

    slopes = _ols_slopes(path_yard_tail)
    path_metrics = pd.DataFrame(
        {
            "path": np.arange(paths),
            "weighted_cost": eval_cost / eval_count,
            "mean_queue": eval_queue / eval_count,
            "terminal_yard_backlog": qy,
            "late_horizon_drift": slopes,
        }
    )
    trace = pd.DataFrame({"period": np.arange(config.periods), "mean_yard_queue": mean_yard_trace})
    return path_metrics, trace


def summarise_paths(paths: pd.DataFrame) -> dict[str, float]:
    return {
        "weighted_cost": float(paths["weighted_cost"].mean()),
        "mean_queue": float(paths["mean_queue"].mean()),
        "terminal_yard_backlog": float(paths["terminal_yard_backlog"].mean()),
        "late_horizon_drift": float(paths["late_horizon_drift"].mean()),
    }
