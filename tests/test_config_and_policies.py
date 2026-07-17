from dataclasses import replace

import pytest

from port_queue.config import ScenarioConfig, SimulationConfig
from port_queue.randomness import generate_randomness
from port_queue.policies import project_action


def test_default_config_is_valid():
    config = SimulationConfig()
    config.validate()
    assert config.periods == 30 * 48
    assert config.warmup_periods == 3 * 48


def test_projection_and_integer_capacity_mapping():
    config = SimulationConfig()
    assert project_action(config, 99.0, 4.2) == (config.quota_max, config.yard_capacity_min)
    assert project_action(config, 19.6, 8.6) == (20, 9)


def test_invalid_cost_weights_are_rejected():
    config = replace(SimulationConfig(), cost_weights={"gate_queue": 1.0})
    with pytest.raises(ValueError):
        config.validate()


def test_scenario_specific_disturbance_overrides_are_used():
    config = replace(
        SimulationConfig(days=2, warmup_days=1),
        scenarios=(
            ScenarioConfig(
                "smooth",
                25.0,
                show_probabilities=(1.0, 0.0, 0.0, 0.0),
                exception_arrival_mean=0.0,
                arrival_shock_probability=0.0,
                arrival_shock_multiplier=1.0,
                capacity_disruption_probability=0.0,
                gate_service_cv=0.05,
                yard_service_cv=0.05,
            ),
        ),
    )
    randomness = generate_randomness(config, config.scenarios[0], seed=42)
    assert randomness.capacity_disruptions.sum() == 0
    assert sum(len(items) for items in randomness.exception_trucks) == 0
