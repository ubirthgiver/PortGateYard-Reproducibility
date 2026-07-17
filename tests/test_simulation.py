from dataclasses import replace

import numpy as np

from port_queue.config import ScenarioConfig, SimulationConfig
from port_queue.policies import FixedPolicy
from port_queue.randomness import PotentialTruck, ScenarioRandomness, generate_randomness
from port_queue.simulation import run_simulation


def small_config() -> SimulationConfig:
    return replace(
        SimulationConfig(),
        days=1,
        warmup_days=0,
        gate_lanes=1,
        quota_min=1,
        quota_max=5,
        yard_capacity_min=1,
        yard_capacity_max=2,
        replications=1,
    )


def test_reproducibility_and_flow_conservation():
    config = small_config()
    scenario = ScenarioConfig("test", 2.0)
    randomness = generate_randomness(config, scenario, 123)
    first = run_simulation(config, scenario, FixedPolicy(config), randomness, 0, 999)
    second = run_simulation(config, scenario, FixedPolicy(config), randomness, 0, 999)
    assert first.summary == second.summary
    assert first.summary["terminal_system"] == 0
    assert first.summary["total_generated_arrivals"] == len(first.trucks)
    assert (first.periods[["avg_gate_queue", "avg_yard_queue"]].to_numpy() >= 0).all()


def test_fcfs_order_for_two_trucks():
    config = small_config()
    scenario = ScenarioConfig("test", 0.0)
    periods = config.periods
    appointments = [[] for _ in range(periods)]
    appointments[0] = [
        PotentialTruck(0, 0, 0, 0.0, 5, 2),
        PotentialTruck(0, 1, 0, 1.0, 5, 2),
    ]
    randomness = ScenarioRandomness(
        requests=np.array([2] + [0] * (periods - 1)),
        appointment_trucks=appointments,
        exception_trucks=[[] for _ in range(periods)],
        capacity_disruptions=np.zeros(periods, dtype=bool),
    )
    result = run_simulation(config, scenario, FixedPolicy(config), randomness, 0, 5)
    trucks = result.trucks.set_index("truck_id")
    assert trucks.loc["a-0-0", "gate_start"] <= trucks.loc["a-0-1", "gate_start"]
    assert trucks.loc["a-0-0", "gate_end"] <= trucks.loc["a-0-1", "gate_start"]


def test_zero_arrival_boundary():
    config = small_config()
    scenario = ScenarioConfig("zero", 0.0)
    periods = config.periods
    randomness = ScenarioRandomness(
        requests=np.zeros(periods, dtype=int),
        appointment_trucks=[[] for _ in range(periods)],
        exception_trucks=[[] for _ in range(periods)],
        capacity_disruptions=np.zeros(periods, dtype=bool),
    )
    result = run_simulation(config, scenario, FixedPolicy(config), randomness, 0, 1)
    assert result.summary["arrivals"] == 0
    assert result.summary["completed"] == 0
    assert result.summary["terminal_system"] == 0
