from __future__ import annotations

from collections import deque
from dataclasses import dataclass
import math
from typing import Any

import numpy as np
import pandas as pd

from .config import ScenarioConfig, SimulationConfig
from .policies import Policy, SystemState
from .randomness import PotentialTruck, ScenarioRandomness


@dataclass
class TruckRecord:
    truck_id: str
    arrival: float
    gate_service: int
    yard_service: int
    gate_start: float | None = None
    gate_end: float | None = None
    yard_start: float | None = None
    yard_end: float | None = None


@dataclass
class SimulationResult:
    scenario: str
    policy: str
    replication: int
    summary: dict[str, Any]
    periods: pd.DataFrame
    trucks: pd.DataFrame


def _truck_from_potential(item: PotentialTruck) -> TruckRecord:
    prefix = "x" if item.exceptional else "a"
    return TruckRecord(
        truck_id=f"{prefix}-{item.origin_period}-{item.index}",
        arrival=item.arrival_minute,
        gate_service=item.gate_service,
        yard_service=item.yard_service,
    )


def _completed_to_frame(records: dict[str, TruckRecord]) -> pd.DataFrame:
    columns = [
        "truck_id", "arrival", "gate_start", "gate_end", "yard_start", "yard_end",
        "gate_wait", "yard_wait", "total_wait", "turnaround",
    ]
    rows = []
    for truck in records.values():
        if truck.yard_end is None:
            continue
        gate_wait = float(truck.gate_start - truck.arrival)  # type: ignore[operator]
        yard_wait = float(truck.yard_start - truck.gate_end)  # type: ignore[operator]
        rows.append({
            "truck_id": truck.truck_id,
            "arrival": truck.arrival,
            "gate_start": truck.gate_start,
            "gate_end": truck.gate_end,
            "yard_start": truck.yard_start,
            "yard_end": truck.yard_end,
            "gate_wait": gate_wait,
            "yard_wait": yard_wait,
            "total_wait": gate_wait + yard_wait,
            "turnaround": float(truck.yard_end - truck.arrival),
        })
    return pd.DataFrame(rows, columns=columns)


def _summary(
    config: SimulationConfig,
    scenario: ScenarioConfig,
    policy: Policy,
    replication: int,
    period_frame: pd.DataFrame,
    truck_frame: pd.DataFrame,
    total_arrivals: int,
    terminal_system: int,
    drain_minutes: int,
) -> dict[str, Any]:
    start_time = config.warmup_periods * config.slot_minutes
    end_time = config.periods * config.slot_minutes
    trucks = truck_frame[(truck_frame["arrival"] >= start_time) & (truck_frame["arrival"] < end_time)]
    periods = period_frame[period_frame["period"] >= config.warmup_periods]
    eligible_arrivals = int(periods["arrivals"].sum())
    requested = int(periods["requests"].sum())
    accepted = int(periods["accepted"].sum())
    completed = len(trucks)
    tail_n = max(10, len(periods) // 5)
    q_tail = (periods["avg_gate_queue"] + periods["avg_yard_queue"]).tail(tail_n).to_numpy()
    slope = float(np.polyfit(np.arange(len(q_tail)), q_tail, 1)[0]) if len(q_tail) > 1 else 0.0
    system_queue = periods["end_gate_queue"] + periods["end_yard_queue"]
    threshold_hits = periods.loc[system_queue >= 40, "period"]
    first_threshold = int(threshold_hits.iloc[0]) if not threshold_hits.empty else -1

    def mean_or_nan(column: str) -> float:
        return float(trucks[column].mean()) if completed else float("nan")

    def quantile_or_nan(column: str, q: float) -> float:
        return float(trucks[column].quantile(q)) if completed else float("nan")

    active_yard_minutes = float((periods["effective_yard_capacity"] * config.slot_minutes).sum())
    busy_yard_minutes = float(periods["yard_busy_minutes"].sum())
    summary = {
        "scenario": scenario.name,
        "policy": policy.name,
        "replication": replication,
        "arrivals": eligible_arrivals,
        "completed": completed,
        "completion_rate": completed / max(eligible_arrivals, 1),
        "throughput_rate": completed / max(requested, 1),
        "acceptance_rate": accepted / max(requested, 1),
        "mean_gate_wait": mean_or_nan("gate_wait"),
        "mean_yard_wait": mean_or_nan("yard_wait"),
        "mean_total_wait": mean_or_nan("total_wait"),
        "p95_total_wait": quantile_or_nan("total_wait", 0.95),
        "mean_turnaround": mean_or_nan("turnaround"),
        "mean_gate_queue": float(periods["avg_gate_queue"].mean()),
        "mean_yard_queue": float(periods["avg_yard_queue"].mean()),
        "p95_yard_queue": float(periods["avg_yard_queue"].quantile(0.95)),
        "gate_utilization": float(periods["gate_busy_minutes"].sum() / max(config.gate_lanes * len(periods) * config.slot_minutes, 1)),
        "yard_utilization": busy_yard_minutes / max(active_yard_minutes, 1.0),
        "yard_resource_hours_per_truck": active_yard_minutes / 60.0 / max(completed, 1),
        "mean_composite_cost": float(periods["composite_cost"].mean()),
        "mean_quota": float(periods["quota"].mean()),
        "mean_yard_capacity": float(periods["yard_capacity"].mean()),
        "unstable": int(slope > 0.02 or terminal_system > 40),
        "queue_tail_slope": slope,
        "terminal_system": terminal_system,
        "uncompleted_at_drain_limit": terminal_system,
        "drain_truncated": int(terminal_system > 0),
        "drain_minutes": drain_minutes,
        "first_queue_threshold_period": first_threshold,
        "mean_net_queue_drift": float(periods["net_queue_drift"].mean()),
        "tail_net_queue_drift": float(periods["net_queue_drift"].tail(tail_n).mean()),
        "service_floor_binding_rate": float(periods["service_floor_binding"].mean()),
        "projection_binding_rate": float(periods["projection_binding"].mean()),
        "total_generated_arrivals": total_arrivals,
        "requested": requested,
        "accepted": accepted,
    }
    return summary


def run_simulation(
    config: SimulationConfig,
    scenario: ScenarioConfig,
    policy: Policy,
    randomness: ScenarioRandomness,
    replication: int,
    policy_seed: int,
) -> SimulationResult:
    policy.reset(policy_seed)
    pending_appearances: list[list[TruckRecord]] = [[] for _ in range(config.periods)]
    gate_queue: deque[TruckRecord] = deque()
    yard_queue: deque[TruckRecord] = deque()
    gate_servers: list[TruckRecord | None] = [None] * config.gate_lanes
    yard_servers: list[TruckRecord | None] = [None] * config.yard_capacity_max
    records: dict[str, TruckRecord] = {}
    period_rows: list[dict[str, float | int]] = []
    recent_arrivals: deque[int] = deque(maxlen=6)
    recent_requests: deque[int] = deque(maxlen=6)
    previous_quota = config.policy.fixed_quota
    previous_yard = config.policy.fixed_yard_capacity
    total_arrivals = 0

    for period in range(config.periods):
        state = SystemState(
            period=period,
            gate_queue=len(gate_queue),
            yard_queue=len(yard_queue),
            gate_busy=sum(x is not None for x in gate_servers),
            yard_busy=sum(x is not None for x in yard_servers),
            recent_arrivals=float(np.mean(recent_arrivals)) if recent_arrivals else 0.0,
            recent_requests=float(np.mean(recent_requests)) if recent_requests else float(config.policy.fixed_quota),
            previous_quota=previous_quota,
            previous_yard_capacity=previous_yard,
        )
        quota, yard_capacity = policy.decide(state)
        service_floor_quota = int(math.ceil(config.service_level_min * state.recent_requests))
        projection_binding = int(
            quota <= config.quota_min
            or quota >= config.quota_max
            or yard_capacity <= config.yard_capacity_min
            or yard_capacity >= config.yard_capacity_max
        )
        service_floor_binding = int(quota <= max(config.quota_min, service_floor_quota))
        accepted = min(int(randomness.requests[period]), quota)
        for item in randomness.appointment_trucks[period][:accepted]:
            if item.appearance_period >= 0:
                pending_appearances[item.appearance_period].append(_truck_from_potential(item))
        arrivals = pending_appearances[period] + [_truck_from_potential(x) for x in randomness.exception_trucks[period]]
        arrivals.sort(key=lambda x: x.arrival)
        arrivals_by_minute: dict[int, list[TruckRecord]] = {}
        start = period * config.slot_minutes
        for truck in arrivals:
            minute = min(config.slot_minutes - 1, max(0, int(truck.arrival - start)))
            arrivals_by_minute.setdefault(minute, []).append(truck)
            records[truck.truck_id] = truck
        total_arrivals += len(arrivals)
        recent_arrivals.append(len(arrivals))
        recent_requests.append(int(randomness.requests[period]))
        effective_yard = max(
            config.yard_capacity_min,
            yard_capacity - int(bool(randomness.capacity_disruptions[period])),
        )

        gate_q_area = yard_q_area = gate_busy_minutes = yard_busy_minutes = 0
        gate_completions = yard_completions = 0
        start_system = len(gate_queue) + len(yard_queue) + sum(x is not None for x in gate_servers) + sum(x is not None for x in yard_servers)
        for offset in range(config.slot_minutes):
            now = start + offset
            for truck in arrivals_by_minute.get(offset, []):
                gate_queue.append(truck)

            for i, truck in enumerate(gate_servers):
                if truck is not None and truck.gate_end is not None and truck.gate_end <= now:
                    yard_queue.append(truck)
                    gate_servers[i] = None
                    gate_completions += 1
            for i, truck in enumerate(yard_servers):
                if truck is not None and truck.yard_end is not None and truck.yard_end <= now:
                    yard_servers[i] = None
                    yard_completions += 1

            for i in range(config.gate_lanes):
                if gate_servers[i] is None and gate_queue:
                    truck = gate_queue.popleft()
                    truck.gate_start = float(max(now, truck.arrival))
                    truck.gate_end = truck.gate_start + truck.gate_service
                    gate_servers[i] = truck
            for i in range(effective_yard):
                if yard_servers[i] is None and yard_queue:
                    truck = yard_queue.popleft()
                    truck.yard_start = float(max(now, truck.gate_end or now))
                    truck.yard_end = truck.yard_start + truck.yard_service
                    yard_servers[i] = truck

            gate_q_area += len(gate_queue)
            yard_q_area += len(yard_queue)
            gate_busy_minutes += sum(x is not None for x in gate_servers)
            yard_busy_minutes += sum(x is not None for x in yard_servers)

        avg_gate_q = gate_q_area / config.slot_minutes
        avg_yard_q = yard_q_area / config.slot_minutes
        overtime = float(avg_gate_q > 20 or avg_yard_q > 20)
        rejection_rate = max(int(randomness.requests[period]) - accepted, 0) / max(int(randomness.requests[period]), 1)
        service_violation = overtime + 5.0 * rejection_rate
        weights = config.cost_weights
        composite_cost = (
            weights["gate_queue"] * avg_gate_q / 20.0
            + weights["yard_queue"] * avg_yard_q / 20.0
            + weights["resource"] * effective_yard / config.yard_capacity_max
            + weights["quota_change"] * abs(quota - previous_quota) / max(config.quota_max - config.quota_min, 1)
            + weights["overtime"] * service_violation
        )
        gate_cost = avg_gate_q / 20.0 + 0.25 * float(avg_gate_q > 20) + 0.5 * rejection_rate
        row: dict[str, float | int] = {
            "period": period,
            "requests": int(randomness.requests[period]),
            "accepted": accepted,
            "arrivals": len(arrivals),
            "quota": quota,
            "yard_capacity": yard_capacity,
            "effective_yard_capacity": effective_yard,
            "avg_gate_queue": avg_gate_q,
            "avg_yard_queue": avg_yard_q,
            "end_gate_queue": len(gate_queue),
            "end_yard_queue": len(yard_queue),
            "gate_completions": gate_completions,
            "yard_completions": yard_completions,
            "gate_busy_minutes": gate_busy_minutes,
            "yard_busy_minutes": yard_busy_minutes,
            "composite_cost": composite_cost,
            "gate_cost": gate_cost,
            "rejection_rate": rejection_rate,
            "service_violation": service_violation,
            "service_floor_quota": service_floor_quota,
            "service_floor_binding": service_floor_binding,
            "projection_binding": projection_binding,
            "end_system": len(gate_queue) + len(yard_queue) + sum(x is not None for x in gate_servers) + sum(x is not None for x in yard_servers),
            "net_queue_drift": (len(gate_queue) + len(yard_queue) + sum(x is not None for x in gate_servers) + sum(x is not None for x in yard_servers)) - start_system,
        }
        period_rows.append(row)
        policy.observe({k: float(v) for k, v in row.items() if k != "period"})
        previous_quota, previous_yard = quota, yard_capacity

    # Drain without new arrivals so end-of-horizon trucks are not right-censored.
    now = config.periods * config.slot_minutes
    drain_start = now
    drain_limit = now + 2 * 1440
    while (gate_queue or yard_queue or any(gate_servers) or any(yard_servers)) and now < drain_limit:
        for i, truck in enumerate(gate_servers):
            if truck is not None and truck.gate_end is not None and truck.gate_end <= now:
                yard_queue.append(truck)
                gate_servers[i] = None
        for i, truck in enumerate(yard_servers):
            if truck is not None and truck.yard_end is not None and truck.yard_end <= now:
                yard_servers[i] = None
        for i in range(config.gate_lanes):
            if gate_servers[i] is None and gate_queue:
                truck = gate_queue.popleft()
                truck.gate_start = float(max(now, truck.arrival))
                truck.gate_end = truck.gate_start + truck.gate_service
                gate_servers[i] = truck
        for i in range(config.yard_capacity_max):
            if yard_servers[i] is None and yard_queue:
                truck = yard_queue.popleft()
                truck.yard_start = float(max(now, truck.gate_end or now))
                truck.yard_end = truck.yard_start + truck.yard_service
                yard_servers[i] = truck
        now += 1

    period_frame = pd.DataFrame(period_rows)
    truck_frame = _completed_to_frame(records)
    terminal = len(gate_queue) + len(yard_queue) + sum(x is not None for x in gate_servers) + sum(x is not None for x in yard_servers)
    summary = _summary(config, scenario, policy, replication, period_frame, truck_frame, total_arrivals, terminal, now - drain_start)
    return SimulationResult(scenario.name, policy.name, replication, summary, period_frame, truck_frame)
