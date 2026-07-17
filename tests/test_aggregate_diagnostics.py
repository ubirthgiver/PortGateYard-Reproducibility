from __future__ import annotations

import numpy as np

from port_queue.aggregate_diagnostics import AggregateConfig, lateness_probabilities, simulate_paths


def test_lateness_probabilities_are_valid() -> None:
    for support in (1, 2, 4):
        probabilities = lateness_probabilities(support, 0.16, 0.04)
        assert len(probabilities) == support + 2
        assert np.isclose(probabilities.sum(), 1.0)
        assert np.isclose(probabilities[-1], 0.04)
        assert np.isclose(probabilities[1:-1].sum(), 0.16)


def test_aggregate_run_is_reproducible_and_nonnegative() -> None:
    config = AggregateConfig(days=2, warmup_days=1, late_horizon_days=1)
    first, _ = simulate_paths(config, "feedback_fast", 1234, 8)
    second, _ = simulate_paths(config, "feedback_fast", 1234, 8)
    assert first.equals(second)
    assert (first[["weighted_cost", "mean_queue", "terminal_yard_backlog"]] >= 0).all().all()


def test_frozen_severe_error_has_positive_drift() -> None:
    config = AggregateConfig(days=8, warmup_days=2, late_horizon_days=3)
    paths, _ = simulate_paths(config, "pto_frozen", 77, 40)
    assert paths["late_horizon_drift"].mean() > 1.0


def test_daily_recovery_rule_reduces_terminal_backlog() -> None:
    config = AggregateConfig(days=10, warmup_days=2, late_horizon_days=3)
    frozen, _ = simulate_paths(config, "pto_frozen", 99, 40)
    daily, _ = simulate_paths(config, "pto_reid_1d", 99, 40)
    assert daily["terminal_yard_backlog"].mean() < frozen["terminal_yard_backlog"].mean()
