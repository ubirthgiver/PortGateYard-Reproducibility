from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ScenarioConfig:
    name: str
    mean_requests: float
    show_probabilities: tuple[float, float, float, float] | None = None
    exception_arrival_mean: float | None = None
    arrival_shock_probability: float | None = None
    arrival_shock_multiplier: float | None = None
    normalize_arrival_shocks: bool | None = None
    capacity_disruption_probability: float | None = None
    gate_service_cv: float | None = None
    yard_service_cv: float | None = None
    description: str = ""


@dataclass(frozen=True)
class PolicyConfig:
    fixed_quota: int = 25
    fixed_yard_capacity: int = 8
    pto_exploration_fraction: float = 0.20
    pto_request_multiplier: float = 1.0
    pto_show_multiplier: float = 1.0
    pto_gate_service_multiplier: float = 1.0
    pto_yard_service_multiplier: float = 1.0
    liquar_eta0: float = 0.08
    liquar_delta0: float = 0.10
    liquar_delta_floor: float = 0.03


@dataclass(frozen=True)
class SimulationConfig:
    slot_minutes: int = 30
    days: int = 30
    warmup_days: int = 3
    replications: int = 50
    bootstrap_samples: int = 2000
    gate_lanes: int = 4
    gate_service_mean: float = 5.0
    gate_service_cv: float = 0.35
    yard_service_mean: float = 10.0
    yard_service_cv: float = 0.50
    quota_min: int = 12
    quota_max: int = 30
    yard_capacity_min: int = 6
    yard_capacity_max: int = 10
    show_probabilities: tuple[float, float, float, float] = (0.75, 0.10, 0.05, 0.10)
    exception_arrival_mean: float = 0.5
    arrival_shock_probability: float = 0.10
    arrival_shock_multiplier: float = 1.25
    capacity_disruption_probability: float = 0.05
    service_level_min: float = 0.85
    scenarios: tuple[ScenarioConfig, ...] = field(
        default_factory=lambda: (ScenarioConfig("moderate", 20.0), ScenarioConfig("heavy", 25.0))
    )
    policy: PolicyConfig = field(default_factory=PolicyConfig)
    cost_weights: dict[str, float] = field(
        default_factory=lambda: {
            "gate_queue": 0.30,
            "yard_queue": 0.30,
            "resource": 0.20,
            "quota_change": 0.10,
            "overtime": 0.10,
        }
    )

    @property
    def periods(self) -> int:
        return self.days * 24 * 60 // self.slot_minutes

    @property
    def warmup_periods(self) -> int:
        return self.warmup_days * 24 * 60 // self.slot_minutes

    def validate(self) -> None:
        if self.slot_minutes <= 0 or 1440 % self.slot_minutes:
            raise ValueError("slot_minutes must be a positive divisor of 1440")
        if not 0 <= self.warmup_days < self.days:
            raise ValueError("warmup_days must be in [0, days)")
        if self.quota_min > self.quota_max or self.yard_capacity_min > self.yard_capacity_max:
            raise ValueError("invalid action bounds")
        if not 0 < self.service_level_min <= 1:
            raise ValueError("service_level_min must be in (0, 1]")
        for attr in [
            "pto_request_multiplier",
            "pto_show_multiplier",
            "pto_gate_service_multiplier",
            "pto_yard_service_multiplier",
        ]:
            if getattr(self.policy, attr) <= 0:
                raise ValueError(f"policy.{attr} must be positive")
        if abs(sum(self.show_probabilities) - 1.0) > 1e-9:
            raise ValueError("show_probabilities must sum to one")
        for scenario in self.scenarios:
            if scenario.mean_requests <= 0:
                raise ValueError(f"scenario {scenario.name} mean_requests must be positive")
            if scenario.show_probabilities is not None and abs(sum(scenario.show_probabilities) - 1.0) > 1e-9:
                raise ValueError(f"scenario {scenario.name} show_probabilities must sum to one")
            for attr in [
                "exception_arrival_mean",
                "arrival_shock_probability",
                "capacity_disruption_probability",
                "gate_service_cv",
                "yard_service_cv",
            ]:
                value = getattr(scenario, attr)
                if value is not None and value < 0:
                    raise ValueError(f"scenario {scenario.name} {attr} must be nonnegative")
            if scenario.arrival_shock_multiplier is not None and scenario.arrival_shock_multiplier < 1:
                raise ValueError(f"scenario {scenario.name} arrival_shock_multiplier must be at least one")
        required_weights = {"gate_queue", "yard_queue", "resource", "quota_change", "overtime"}
        if set(self.cost_weights) != required_weights:
            raise ValueError(f"cost_weights must contain exactly {sorted(required_weights)}")
        if abs(sum(self.cost_weights.values()) - 1.0) > 1e-9:
            raise ValueError("cost_weights must sum to one")


def load_config(path: str | Path) -> SimulationConfig:
    raw: dict[str, Any] = json.loads(Path(path).read_text(encoding="utf-8"))
    scenarios = []
    for name, values in raw.pop("scenarios").items():
        scenario_values = dict(values)
        scenario_values["mean_requests"] = float(scenario_values["mean_requests"])
        if "show_probabilities" in scenario_values and scenario_values["show_probabilities"] is not None:
            scenario_values["show_probabilities"] = tuple(scenario_values["show_probabilities"])
        scenarios.append(ScenarioConfig(name=name, **scenario_values))
    scenarios = tuple(scenarios)
    policy = PolicyConfig(**raw.pop("policy"))
    raw["show_probabilities"] = tuple(raw["show_probabilities"])
    config = SimulationConfig(scenarios=scenarios, policy=policy, **raw)
    config.validate()
    return config
