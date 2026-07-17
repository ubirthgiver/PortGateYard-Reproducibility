from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
import math

import numpy as np

from .config import SimulationConfig


@dataclass(frozen=True)
class SystemState:
    period: int
    gate_queue: int
    yard_queue: int
    gate_busy: int
    yard_busy: int
    recent_arrivals: float
    recent_requests: float
    previous_quota: int
    previous_yard_capacity: int


class Policy(ABC):
    name: str

    def reset(self, seed: int) -> None:
        self.rng = np.random.default_rng(seed)

    @abstractmethod
    def decide(self, state: SystemState) -> tuple[int, int]:
        raise NotImplementedError

    def observe(self, metrics: dict[str, float]) -> None:
        del metrics


def project_action(config: SimulationConfig, quota: float, yard_capacity: float) -> tuple[int, int]:
    q = int(round(np.clip(quota, config.quota_min, config.quota_max)))
    y = int(round(np.clip(yard_capacity, config.yard_capacity_min, config.yard_capacity_max)))
    return q, y


class FixedPolicy(Policy):
    name = "fixed"

    def __init__(self, config: SimulationConfig):
        self.config = config

    def decide(self, state: SystemState) -> tuple[int, int]:
        del state
        return project_action(self.config, self.config.policy.fixed_quota, self.config.policy.fixed_yard_capacity)


class GateOnlyPolicy(Policy):
    name = "gate_only"

    def __init__(self, config: SimulationConfig):
        self.config = config
        self.center = float(config.policy.fixed_quota)
        self.iteration = 0
        self.minus_cost: float | None = None
        self.direction = -1

    def reset(self, seed: int) -> None:
        super().reset(seed)
        self.center = float(self.config.policy.fixed_quota)
        self.iteration = 0
        self.minus_cost = None
        self.direction = -1

    def _delta(self) -> float:
        span = self.config.quota_max - self.config.quota_min
        k = self.iteration + 1
        return span * max(self.config.policy.liquar_delta_floor, self.config.policy.liquar_delta0 * k ** (-1 / 3))

    def decide(self, state: SystemState) -> tuple[int, int]:
        gate_pressure = np.clip(state.gate_queue / 20.0, 0.0, 1.5)
        quota = self.center + self.direction * self._delta() - 3.0 * gate_pressure
        quota = max(quota, math.ceil(self.config.service_level_min * state.recent_requests))
        return project_action(self.config, quota, self.config.policy.fixed_yard_capacity)

    def observe(self, metrics: dict[str, float]) -> None:
        cost = float(metrics["gate_cost"])
        if self.direction < 0:
            self.minus_cost = cost
            self.direction = 1
            return
        if self.minus_cost is not None:
            gradient = (cost - self.minus_cost) / max(2 * self._delta(), 1e-9)
            eta = (self.config.quota_max - self.config.quota_min) * self.config.policy.liquar_eta0 * (self.iteration + 1) ** (-0.6)
            self.center = float(np.clip(self.center - eta * gradient, self.config.quota_min, self.config.quota_max))
        self.iteration += 1
        self.direction = -1


class PTOPolicy(Policy):
    name = "pto"

    def __init__(self, config: SimulationConfig):
        self.config = config
        self.exploration_periods = max(2, int(config.periods * config.policy.pto_exploration_fraction))
        self.observations: list[dict[str, float]] = []
        self.selected: tuple[int, int] | None = None

    def reset(self, seed: int) -> None:
        super().reset(seed)
        self.observations = []
        self.selected = None

    def decide(self, state: SystemState) -> tuple[int, int]:
        if state.period < self.exploration_periods:
            # Deliberate grid exploration, as in a predict-then-optimize design.
            frac = state.period / max(1, self.exploration_periods - 1)
            quota = self.config.quota_min + frac * (self.config.quota_max - self.config.quota_min)
            yard = self.config.yard_capacity_min + ((state.period // 4) % (self.config.yard_capacity_max - self.config.yard_capacity_min + 1))
            return project_action(self.config, quota, yard)
        if self.selected is None:
            self.selected = self._optimize_surrogate()
        return self.selected

    def observe(self, metrics: dict[str, float]) -> None:
        if len(self.observations) < self.exploration_periods:
            self.observations.append(metrics.copy())

    def _optimize_surrogate(self) -> tuple[int, int]:
        if not self.observations:
            return project_action(self.config, self.config.policy.fixed_quota, self.config.policy.fixed_yard_capacity)
        request_mean = float(np.mean([x["requests"] for x in self.observations])) * self.config.policy.pto_request_multiplier
        show_rate = float(np.mean([x["arrivals"] / max(x["accepted"], 1.0) for x in self.observations])) * self.config.policy.pto_show_multiplier
        show_rate = float(np.clip(show_rate, 0.55, 1.10))
        best: tuple[float, int, int] | None = None
        gate_service_mean = self.config.gate_service_mean * self.config.policy.pto_gate_service_multiplier
        yard_service_mean = self.config.yard_service_mean * self.config.policy.pto_yard_service_multiplier
        gate_capacity = self.config.gate_lanes * self.config.slot_minutes / gate_service_mean
        for quota in range(self.config.quota_min, self.config.quota_max + 1):
            if quota < self.config.service_level_min * request_mean:
                continue
            arrivals = min(request_mean, quota) * show_rate + self.config.exception_arrival_mean
            rho_g = min(arrivals / max(gate_capacity, 1e-9), 0.995)
            gate_penalty = rho_g / max(1.0 - rho_g, 0.005)
            for yard in range(self.config.yard_capacity_min, self.config.yard_capacity_max + 1):
                yard_capacity = yard * self.config.slot_minutes / yard_service_mean
                rho_y = min(arrivals / max(yard_capacity, 1e-9), 0.995)
                yard_penalty = rho_y / max(1.0 - rho_y, 0.005)
                rejection_rate = max(request_mean - quota, 0.0) / max(request_mean, 1.0)
                score = (
                    0.3 * gate_penalty / 20
                    + 0.3 * yard_penalty / 20
                    + 0.2 * yard / self.config.yard_capacity_max
                    + 0.5 * rejection_rate
                )
                candidate = (score, quota, yard)
                if best is None or candidate < best:
                    best = candidate
        assert best is not None
        return best[1], best[2]


class AdaptivePTOPolicy(PTOPolicy):
    """Rolling/receding-horizon PTO benchmark.

    Unlike the frozen PTO benchmark, this policy periodically re-estimates the
    surrogate model from the most recent realized observations. It is still a
    predictive open-loop optimizer between update epochs, but it is no longer a
    stale-model stress test.
    """

    name = "pto_adaptive"

    def __init__(self, config: SimulationConfig, update_interval: int = 48, window: int = 96, name: str | None = None):
        super().__init__(config)
        self.update_interval = max(1, int(update_interval))
        self.window = max(self.update_interval, int(window))
        self.name = name or self.name
        self.last_update_period = -10**9

    def reset(self, seed: int) -> None:
        super().reset(seed)
        self.last_update_period = -10**9

    def decide(self, state: SystemState) -> tuple[int, int]:
        if state.period < self.exploration_periods:
            return super().decide(state)
        needs_update = (
            self.selected is None
            or state.period - self.last_update_period >= self.update_interval
        )
        if needs_update:
            self.selected = self._optimize_surrogate()
            self.last_update_period = state.period
        return self.selected

    def observe(self, metrics: dict[str, float]) -> None:
        self.observations.append(metrics.copy())
        if len(self.observations) > self.window:
            self.observations = self.observations[-self.window :]


class FastOnlyPolicy(Policy):
    """Queue-feedback-only ablation of the online joint policy.

    It uses the same fast workload feedback term as LiQUARPolicy, but freezes
    the slow adaptive center. This isolates whether the slow learning layer adds
    value beyond immediate queue-pressure correction.
    """

    name = "online_fast_only"

    def __init__(self, config: SimulationConfig):
        self.config = config
        self.center = self._initial_center()

    def reset(self, seed: int) -> None:
        super().reset(seed)
        self.center = self._initial_center()

    def _initial_center(self) -> np.ndarray:
        quota_span = max(self.config.quota_max - self.config.quota_min, 1)
        yard_span = max(self.config.yard_capacity_max - self.config.yard_capacity_min, 1)
        return np.array([
            (self.config.policy.fixed_quota - self.config.quota_min) / quota_span,
            (self.config.policy.fixed_yard_capacity - self.config.yard_capacity_min) / yard_span,
        ], dtype=float)

    def _physical(self, x: np.ndarray) -> tuple[int, int]:
        quota = self.config.quota_min + x[0] * (self.config.quota_max - self.config.quota_min)
        yard = self.config.yard_capacity_min + x[1] * (self.config.yard_capacity_max - self.config.yard_capacity_min)
        return project_action(self.config, quota, yard)

    def decide(self, state: SystemState) -> tuple[int, int]:
        gate_pressure = np.clip(state.gate_queue / 20.0, 0.0, 1.5)
        yard_pressure = np.clip((state.yard_queue + state.yard_busy) / 20.0, 0.0, 1.5)
        feedback = np.array([
            -0.18 * gate_pressure - 0.28 * yard_pressure,
            0.45 * (yard_pressure - 0.20) + 0.08 * gate_pressure,
        ])
        quota, yard = self._physical(np.clip(self.center + feedback, 0.0, 1.0))
        quota = max(quota, math.ceil(self.config.service_level_min * state.recent_requests))
        return project_action(self.config, quota, yard)


class LiQUARPolicy(Policy):
    name = "online_joint"

    def __init__(self, config: SimulationConfig):
        self.config = config
        self.center = self._initial_center()
        self.iteration = 0
        self.direction = -1
        self.coordinate = 0
        self.minus_cost: float | None = None

    def reset(self, seed: int) -> None:
        super().reset(seed)
        self.center = self._initial_center()
        self.iteration = 0
        self.direction = -1
        self.coordinate = int(self.rng.integers(0, 2))
        self.minus_cost = None

    def _initial_center(self) -> np.ndarray:
        quota_span = max(self.config.quota_max - self.config.quota_min, 1)
        yard_span = max(self.config.yard_capacity_max - self.config.yard_capacity_min, 1)
        return np.array([
            (self.config.policy.fixed_quota - self.config.quota_min) / quota_span,
            (self.config.policy.fixed_yard_capacity - self.config.yard_capacity_min) / yard_span,
        ], dtype=float)

    def _delta(self) -> float:
        k = self.iteration + 1
        return max(self.config.policy.liquar_delta_floor, self.config.policy.liquar_delta0 * k ** (-1 / 3))

    def _physical(self, x: np.ndarray) -> tuple[int, int]:
        quota = self.config.quota_min + x[0] * (self.config.quota_max - self.config.quota_min)
        yard = self.config.yard_capacity_min + x[1] * (self.config.yard_capacity_max - self.config.yard_capacity_min)
        return project_action(self.config, quota, yard)

    def decide(self, state: SystemState) -> tuple[int, int]:
        perturb = np.zeros(2)
        perturb[self.coordinate] = self.direction * self._delta()
        gate_pressure = np.clip(state.gate_queue / 20.0, 0.0, 1.5)
        yard_pressure = np.clip((state.yard_queue + state.yard_busy) / 20.0, 0.0, 1.5)
        feedback = np.array([
            -0.18 * gate_pressure - 0.28 * yard_pressure,
            0.45 * (yard_pressure - 0.20) + 0.08 * gate_pressure,
        ])
        quota, yard = self._physical(np.clip(self.center + perturb + feedback, 0.0, 1.0))
        quota = max(quota, math.ceil(self.config.service_level_min * state.recent_requests))
        return project_action(self.config, quota, yard)

    def observe(self, metrics: dict[str, float]) -> None:
        cost = float(metrics["composite_cost"])
        if self.direction < 0:
            self.minus_cost = cost
            self.direction = 1
            return
        if self.minus_cost is not None:
            gradient = np.zeros(2)
            gradient[self.coordinate] = (cost - self.minus_cost) / max(2 * self._delta(), 1e-9)
            eta = self.config.policy.liquar_eta0 * (self.iteration + 1) ** (-0.6)
            self.center = np.clip(self.center - eta * gradient, 0.0, 1.0)
        self.iteration += 1
        self.direction = -1
        self.coordinate = int(self.rng.integers(0, 2))


def make_policy(config: SimulationConfig, name: str) -> Policy:
    if name == "fixed":
        return FixedPolicy(config)
    if name == "gate_only":
        return GateOnlyPolicy(config)
    if name == "pto":
        return PTOPolicy(config)
    if name == "pto_adaptive_slow":
        return AdaptivePTOPolicy(config, update_interval=48, window=144, name="pto_adaptive_slow")
    if name == "pto_adaptive_fast":
        return AdaptivePTOPolicy(config, update_interval=6, window=48, name="pto_adaptive_fast")
    if name == "online_fast_only":
        return FastOnlyPolicy(config)
    if name == "online_joint":
        return LiQUARPolicy(config)
    raise ValueError(f"unknown policy name: {name}")


def make_policies(config: SimulationConfig, names: list[str] | tuple[str, ...] | None = None) -> list[Policy]:
    selected = names or ("fixed", "gate_only", "pto", "online_joint")
    return [make_policy(config, name) for name in selected]
