from __future__ import annotations

import argparse
import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
sys.path.insert(0, str(ROOT / "scripts"))

from port_queue.config import load_config  # noqa: E402
from port_queue.experiment import run_experiments  # noqa: E402
from port_queue.fidelity import run_model_fidelity_experiment  # noqa: E402
from run_repair_experiments import (  # noqa: E402
    DEFAULT_POLICIES,
    scenario_from_public_row,
)
import run_validation_experiments as validation  # noqa: E402
from run_aggregate_diagnostics import run_table10, run_table12  # noqa: E402


PROCESSED_SCENARIOS = ROOT / "data" / "processed" / "public_data_calibrated_scenarios.csv"
GENERATED = ROOT / "generated"


def public_scenarios(config):
    frame = pd.read_csv(PROCESSED_SCENARIOS)
    return {str(row["scenario"]): scenario_from_public_row(config, row) for _, row in frame.iterrows()}


def run_e1(replications: int = 50) -> None:
    base = load_config(ROOT / "configs" / "fidelity.json")
    scenarios = tuple(public_scenarios(base).values())
    config = replace(base, scenarios=scenarios, replications=replications, bootstrap_samples=2000)
    run_experiments(config, GENERATED / "e1", replications=replications, keep_example_trajectories=False)


def run_e2(replications: int = 50, model_samples: int = 4) -> None:
    config = load_config(ROOT / "configs" / "public_peak_fidelity.json")
    run_model_fidelity_experiment(
        config,
        GENERATED / "e2",
        replications=replications,
        model_samples=model_samples,
    )


def run_e3(replications: int = 12) -> None:
    base = load_config(ROOT / "configs" / "fidelity.json")
    validation.PUBLIC_SCENARIO_FILE = PROCESSED_SCENARIOS
    scenarios = validation._load_public_scenarios(base)
    validation.run_e4(base, scenarios, GENERATED / "e3", replications=replications)


def run_table8(replications: int = 50) -> None:
    base = load_config(ROOT / "configs" / "fidelity.json")
    scenarios_by_name = public_scenarios(base)
    scenarios = tuple(scenarios_by_name[name] for name in ("sc_high_workload", "sc_peak_workload"))
    config = replace(base, scenarios=scenarios, replications=replications, bootstrap_samples=1000)
    output = GENERATED / "table8"
    raw, summary = run_experiments(
        config,
        output,
        replications=replications,
        keep_example_trajectories=False,
        policy_names=DEFAULT_POLICIES,
    )
    raw.to_csv(output / "adaptive_pto_raw_results.csv", index=False, encoding="utf-8-sig")
    summary.to_csv(output / "adaptive_pto_summary_results.csv", index=False, encoding="utf-8-sig")


def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate the reproducible experiments in the paper.")
    parser.add_argument(
        "target",
        choices=("e1", "e2", "e3", "table8", "table10", "table12", "all"),
        help="Experiment block to regenerate.",
    )
    args = parser.parse_args()
    GENERATED.mkdir(exist_ok=True)
    if args.target in ("e1", "all"):
        run_e1()
    if args.target in ("e2", "all"):
        run_e2()
    if args.target in ("e3", "all"):
        run_e3()
    if args.target in ("table8", "all"):
        run_table8()
    if args.target in ("table10", "all"):
        run_table10(GENERATED / "table10")
    if args.target in ("table12", "all"):
        run_table12(GENERATED / "table12")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
