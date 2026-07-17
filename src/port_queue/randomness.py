from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from .config import ScenarioConfig, SimulationConfig


def _lognormal_parameters(mean: float, cv: float) -> tuple[float, float]:
    sigma2 = math.log(cv * cv + 1.0)
    return math.log(mean) - sigma2 / 2.0, math.sqrt(sigma2)


def _scenario_value(scenario: ScenarioConfig, config: SimulationConfig, name: str):
    value = getattr(scenario, name)
    return getattr(config, name) if value is None else value


@dataclass(frozen=True)
class PotentialTruck:
    origin_period: int
    index: int
    appearance_period: int
    arrival_minute: float
    gate_service: int
    yard_service: int
    exceptional: bool = False


@dataclass
class ScenarioRandomness:
    requests: np.ndarray
    appointment_trucks: list[list[PotentialTruck]]
    exception_trucks: list[list[PotentialTruck]]
    capacity_disruptions: np.ndarray


def generate_randomness(config: SimulationConfig, scenario: ScenarioConfig, seed: int) -> ScenarioRandomness:
    rng = np.random.default_rng(seed)
    periods = config.periods
    show_probabilities = _scenario_value(scenario, config, "show_probabilities")
    exception_arrival_mean = float(_scenario_value(scenario, config, "exception_arrival_mean"))
    arrival_shock_probability = float(_scenario_value(scenario, config, "arrival_shock_probability"))
    arrival_shock_multiplier = float(_scenario_value(scenario, config, "arrival_shock_multiplier"))
    normalize_arrival_shocks = bool(scenario.normalize_arrival_shocks) if scenario.normalize_arrival_shocks is not None else False
    capacity_disruption_probability = float(_scenario_value(scenario, config, "capacity_disruption_probability"))
    gate_service_cv = float(_scenario_value(scenario, config, "gate_service_cv"))
    yard_service_cv = float(_scenario_value(scenario, config, "yard_service_cv"))
    slots_per_day = 1440 // config.slot_minutes
    slot = np.arange(periods) % slots_per_day
    phase = 2 * np.pi * slot / slots_per_day
    profile = 0.82 + 0.22 * np.maximum(0.0, np.sin(phase - 0.7)) + 0.18 * np.maximum(0.0, np.sin(2 * phase + 0.8))
    profile /= profile.mean()
    shocks = np.where(
        rng.random(periods) < arrival_shock_probability,
        arrival_shock_multiplier,
        1.0,
    )
    if normalize_arrival_shocks:
        shocks = shocks / (1.0 + arrival_shock_probability * (arrival_shock_multiplier - 1.0))
    requests = rng.poisson(scenario.mean_requests * profile * shocks)
    max_candidates = max(config.quota_max, int(requests.max(initial=0)))
    mu_g, sigma_g = _lognormal_parameters(config.gate_service_mean, gate_service_cv)
    mu_y, sigma_y = _lognormal_parameters(config.yard_service_mean, yard_service_cv)
    appointment_trucks: list[list[PotentialTruck]] = [[] for _ in range(periods)]
    exception_trucks: list[list[PotentialTruck]] = [[] for _ in range(periods)]
    offsets = np.array([0, 1, 2, -1])

    for t in range(periods):
        draws = rng.choice(offsets, size=max_candidates, p=show_probabilities)
        arrivals = rng.uniform(0, config.slot_minutes, size=max_candidates)
        gate_times = np.maximum(1, np.ceil(rng.lognormal(mu_g, sigma_g, size=max_candidates))).astype(int)
        yard_times = np.maximum(1, np.ceil(rng.lognormal(mu_y, sigma_y, size=max_candidates))).astype(int)
        for i in range(max_candidates):
            if draws[i] < 0 or t + int(draws[i]) >= periods:
                appearance = -1
                minute = -1.0
            else:
                appearance = t + int(draws[i])
                minute = appearance * config.slot_minutes + float(arrivals[i])
            appointment_trucks[t].append(
                PotentialTruck(t, i, appearance, minute, int(gate_times[i]), int(yard_times[i]))
            )

        n_exception = int(rng.poisson(exception_arrival_mean))
        for i in range(n_exception):
            exception_trucks[t].append(
                PotentialTruck(
                    t,
                    i,
                    t,
                    t * config.slot_minutes + float(rng.uniform(0, config.slot_minutes)),
                    int(max(1, math.ceil(rng.lognormal(mu_g, sigma_g)))),
                    int(max(1, math.ceil(rng.lognormal(mu_y, sigma_y)))),
                    True,
                )
            )

    return ScenarioRandomness(
        requests=requests,
        appointment_trucks=appointment_trucks,
        exception_trucks=exception_trucks,
        capacity_disruptions=rng.random(periods) < capacity_disruption_probability,
    )
