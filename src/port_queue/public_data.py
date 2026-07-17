from __future__ import annotations

from dataclasses import replace
from pathlib import Path
import re
import shutil
import zipfile

import numpy as np
import pandas as pd

from .config import ScenarioConfig, SimulationConfig
from .experiment import run_experiments
from .fidelity import run_model_fidelity_experiment


SC_PORTS_FILES = [
    "chsgatetransactions.csv",
    "chsturntimes.csv",
    "gatemissions.csv",
    "lastweeksturntimes.csv",
    "chscraneproductivity.csv",
    "chsvesselcalls.csv",
    "piermoves.csv",
]


def _number(value: object) -> float:
    if pd.isna(value):
        return float("nan")
    if isinstance(value, (int, float, np.integer, np.floating)):
        return float(value)
    text = str(value).replace(",", "").replace("%", "").strip()
    if not text:
        return float("nan")
    return float(text)


def _safe_read_csv(path: Path) -> pd.DataFrame:
    return pd.read_csv(path, encoding="utf-8-sig")


def _copy_if_exists(source: Path, target_dir: Path) -> Path | None:
    if not source.exists():
        return None
    target_dir.mkdir(parents=True, exist_ok=True)
    target = target_dir / source.name
    if source.resolve() != target.resolve():
        shutil.copy2(source, target)
    return target


def organize_public_data(project_root: str | Path = ".") -> dict[str, list[Path]]:
    """Copy root-level downloaded public data into stable data subfolders.

    The function is intentionally non-destructive: root files are copied, not moved.
    """
    root = Path(project_root)
    data = root / "data"
    sc_dir = data / "sc_ports"
    copied_sc: list[Path] = []
    for name in SC_PORTS_FILES:
        copied = _copy_if_exists(root / name, sc_dir)
        if copied:
            copied_sc.append(copied)

    zip_map = {
        "82zzdkrxx8-1.zip": data / "mendeley_tas_tours",
        "Event Log Dwelling Time Dataset.zip": data / "mendeley_dwelling_time",
        "Data for A decision support system for a capacity management problem at a container terminal (1).zip": data / "mendeley_capacity_management",
    }
    extracted: list[Path] = []
    for name, target in zip_map.items():
        source = root / name
        if not source.exists():
            continue
        target.mkdir(parents=True, exist_ok=True)
        copied = _copy_if_exists(source, target)
        if copied:
            extracted.append(copied)
        marker_files = list(target.rglob("*.xlsx"))
        if not marker_files:
            with zipfile.ZipFile(source) as archive:
                archive.extractall(target)

    return {"sc_ports": copied_sc, "archives": extracted}


def load_sc_ports(data_dir: str | Path) -> dict[str, pd.DataFrame]:
    base = Path(data_dir)
    if (base / "sc_ports").exists():
        base = base / "sc_ports"
    frames: dict[str, pd.DataFrame] = {}
    for name in SC_PORTS_FILES:
        path = base / name
        if not path.exists():
            continue
        key = path.stem
        frame = _safe_read_csv(path)
        frames[key] = frame
    return frames


def clean_sc_ports(frames: dict[str, pd.DataFrame], output_dir: str | Path) -> dict[str, pd.DataFrame]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    cleaned: dict[str, pd.DataFrame] = {}
    for key, frame in frames.items():
        data = frame.copy()
        for column in data.columns:
            if any(token in column.lower() for token in ["transactions", "time", "count", "productivity", "calls"]):
                try:
                    data[column] = data[column].map(_number)
                except ValueError:
                    pass
        for column in data.columns:
            if column.startswith("Month, Day"):
                data[column] = pd.to_datetime(data[column], errors="coerce")
        cleaned[key] = data
        data.to_csv(output / f"clean_{key}.csv", index=False, encoding="utf-8-sig")
    return cleaned


def summarize_sc_ports(cleaned: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[dict[str, object]] = []
    daily_totals = pd.DataFrame()
    for key, frame in cleaned.items():
        numeric = frame.select_dtypes(include=[np.number])
        for column in numeric.columns:
            values = numeric[column].dropna()
            if values.empty:
                continue
            rows.append(
                {
                    "source": f"SC Ports {key}",
                    "metric": column,
                    "n": int(values.size),
                    "mean": float(values.mean()),
                    "median": float(values.median()),
                    "min": float(values.min()),
                    "max": float(values.max()),
                    "cv": float(values.std(ddof=1) / values.mean()) if values.mean() else float("nan"),
                }
            )

    if "gatemissions" in cleaned:
        missions = cleaned["gatemissions"].copy()
        date_col = [c for c in missions.columns if c.startswith("Month, Day")][0]
        missions["Mission Count"] = missions["Mission Count"].map(_number)
        daily_totals = missions.groupby(date_col, as_index=False)["Mission Count"].sum()
        daily_totals = daily_totals.rename(columns={date_col: "date", "Mission Count": "total_gate_missions"})
    return pd.DataFrame(rows), daily_totals


def _pdf_text(path: Path) -> str:
    from pypdf import PdfReader

    return "\n".join(page.extract_text() or "" for page in PdfReader(str(path)).pages)


def _numbers_after(label: str, text: str, stop_labels: list[str], limit: int = 12) -> list[float]:
    normalized = re.sub(r"\s+", " ", text)
    start = normalized.lower().find(label.lower())
    if start < 0:
        return []
    end = len(normalized)
    for stop in stop_labels:
        idx = normalized.lower().find(stop.lower(), start + len(label))
        if idx >= 0:
            end = min(end, idx)
    snippet = normalized[start + len(label) : end]
    values = re.findall(r"\d+(?:,\d{3})*(?:\.\d+)?%?", snippet)
    result: list[float] = []
    for value in values[:limit]:
        result.append(_number(value))
    return result


def parse_virginia_metrics(pdf_dir: str | Path, output_dir: str | Path) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for path in sorted(Path(pdf_dir).glob("*.pdf")):
        text = _pdf_text(path)
        metrics = {
            "gate_moves": _numbers_after("Gate Moves", text, ["Reservation Moves"], limit=8),
            "reservation_moves": _numbers_after("Reservation Moves", text, ["Reservations Missed"], limit=8),
            "reservations_missed": _numbers_after("Reservations Missed", text, ["Reservation %"], limit=8),
            "reservation_share_pct": _numbers_after("Reservation % of Total Moves", text, ["Containers"], limit=8),
            "turn_time": _numbers_after("Turn Time", text, ["Expanded Turn Time"], limit=8),
            "expanded_turn_time": _numbers_after("Expanded Turn Time", text, ["Single Move Turn Time"], limit=8),
            "single_move_turn_time": _numbers_after("Single Move Turn Time", text, ["Dual Move Turn Time"], limit=8),
            "dual_move_turn_time": _numbers_after("Dual Move Turn Time", text, ["Turn Time Goal"], limit=8),
        }
        for metric, values in metrics.items():
            for week_index, value in enumerate(values):
                rows.append({"source_file": path.name, "week_index": week_index, "metric": metric, "value": value})
    frame = pd.DataFrame(rows)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output / "clean_port_virginia_weekly_metrics.csv", index=False, encoding="utf-8-sig")
    return frame


def parse_houston_reports(pdf_dir: str | Path, output_dir: str | Path) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for path in sorted(Path(pdf_dir).glob("*.pdf")):
        text = _pdf_text(path)
        metrics = {
            "truck_turn_time": _numbers_after("Truck Turn Time (min)", text, ["Truck Turn Time (Single/Dual)"], limit=4),
            "completed_transactions": _numbers_after("Total Completed Transactions", text, ["Effective Yard Utilization"], limit=6),
            "yard_utilization_pct": _numbers_after("Effective Yard Utilization", text, ["Loaded Import/Export Ratio"], limit=4),
            "dwell_days": _numbers_after("Dwell (days) - rolling 12 weeks", text, ["% of Imports"], limit=8),
            "imports_over_14_days_pct": _numbers_after("% of Imports on Terminals >=14 days", text, ["Chassis"], limit=2),
        }
        for metric, values in metrics.items():
            for index, value in enumerate(values):
                rows.append({"source_file": path.name, "index": index, "metric": metric, "value": value})
    frame = pd.DataFrame(rows)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output / "clean_port_houston_terminal_reports.csv", index=False, encoding="utf-8-sig")
    return frame


def summarize_tas_benchmark(path: str | Path, output_dir: str | Path) -> pd.DataFrame:
    xlsx = Path(path)
    if not xlsx.exists():
        matches = list(Path("data/mendeley_tas_tours").rglob("TAS_experiments_input_data.xlsx"))
        if not matches:
            return pd.DataFrame()
        xlsx = matches[0]
    excel = pd.ExcelFile(xlsx)
    rows: list[dict[str, object]] = []
    for sheet in excel.sheet_names:
        frame = pd.read_excel(xlsx, sheet_name=sheet, header=None)
        text = "\n".join(map(str, frame.iloc[:, 0].dropna().tolist()))

        def get(pattern: str) -> float:
            match = re.search(pattern, text)
            return float(match.group(1)) if match else float("nan")

        rows.append(
            {
                "sheet": sheet,
                "rows": frame.shape[0],
                "problem_size_jobs": get(r"Problem size \(# of jobs\)=\s*(\d+)"),
                "trucking_companies": get(r"Number of trcuking companies=\s*(\d+)"),
                "time_windows": get(r"Number of time-windows during a day at terminal=\s*(\d+)"),
                "terminal_gate_queue_min": get(r"Terminal gate queuing time \(min\)=\s*(\d+)"),
                "load_unload_min": get(r"Load/unload time \(min\)=\s*(\d+)"),
            }
        )
    summary = pd.DataFrame(rows)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    summary.to_csv(Path(output_dir) / "mendeley_tas_benchmark_summary.csv", index=False, encoding="utf-8-sig")
    return summary


def summarize_capacity_benchmark(data_dir: str | Path, output_dir: str | Path) -> pd.DataFrame:
    files = sorted(Path(data_dir).rglob("*.xlsx"))
    rows: list[dict[str, object]] = []
    for path in files:
        frame = pd.read_excel(path, header=None)
        title = str(frame.iat[0, 1])
        match = re.search(r"\((\d+)t-(\d+)d-(\d+)c\)", title)
        rows.append(
            {
                "file": path.name,
                "title": title,
                "periods": _number(frame.iat[3, 7]),
                "quay_cranes": _number(frame.iat[5, 7]),
                "yard_cranes": _number(frame.iat[6, 7]),
                "yard_crane_productivity": _number(frame.iat[7, 7]),
                "total_containers": int(match.group(1)) if match else np.nan,
                "discharge": int(match.group(2)) if match else np.nan,
                "charge": int(match.group(3)) if match else np.nan,
            }
        )
    summary = pd.DataFrame(rows)
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    summary.to_csv(Path(output_dir) / "mendeley_capacity_benchmark_summary.csv", index=False, encoding="utf-8-sig")
    return summary


def summarize_dwelling_time(data_dir: str | Path, output_dir: str | Path, max_rows: int | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    matches = sorted(Path(data_dir).rglob("*.xlsx"))
    if not matches:
        return pd.DataFrame(), pd.DataFrame()
    frame = pd.read_excel(matches[0], nrows=max_rows)
    frame["Start Timestamp"] = pd.to_datetime(frame["Start Timestamp"], errors="coerce")
    frame["End Timestamp"] = pd.to_datetime(frame["End Timestamp"], errors="coerce")
    frame = frame[frame["Start Timestamp"].dt.year.ge(2021) & frame["End Timestamp"].dt.year.ge(2021)]
    activities = frame["activity"].value_counts().rename_axis("activity").reset_index(name="count")
    case = frame.pivot_table(index="case_id", columns="activity", values=["Start Timestamp", "End Timestamp"], aggfunc="first")
    rows: list[dict[str, object]] = []
    for case_id, row in case.iterrows():
        item: dict[str, object] = {"case_id": case_id}
        try:
            item["truck_visit_minutes"] = (
                row[("End Timestamp", "TRUCK_OUT")] - row[("Start Timestamp", "TRUCK_IN")]
            ).total_seconds() / 60
        except Exception:
            item["truck_visit_minutes"] = np.nan
        try:
            item["stack_to_unstack_hours"] = (
                row[("Start Timestamp", "UNSTACK_TO_TRUCK")] - row[("End Timestamp", "STACK")]
            ).total_seconds() / 3600
        except Exception:
            item["stack_to_unstack_hours"] = np.nan
        rows.append(item)
    case_metrics = pd.DataFrame(rows)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    activities.to_csv(output / "dwelling_activity_counts.csv", index=False, encoding="utf-8-sig")
    case_metrics.to_csv(output / "dwelling_case_metrics.csv", index=False, encoding="utf-8-sig")
    return activities, case_metrics


def make_public_data_scenarios(
    config: SimulationConfig,
    daily_gate_missions: pd.DataFrame,
    virginia: pd.DataFrame,
    houston: pd.DataFrame,
    base_mean_requests: float = 23.0,
) -> tuple[pd.DataFrame, tuple[ScenarioConfig, ...]]:
    active = daily_gate_missions[daily_gate_missions["total_gate_missions"] > 0].copy()
    if active.empty:
        active = pd.DataFrame({"date": ["synthetic"], "total_gate_missions": [base_mean_requests]})
    median_value = float(active["total_gate_missions"].median())
    targets = [
        ("sc_low_workload", "SC Ports 低负荷日", 0.25),
        ("sc_median_workload", "SC Ports 中位负荷日", 0.50),
        ("sc_high_workload", "SC Ports 高负荷日", 0.75),
        ("sc_peak_workload", "SC Ports 峰值负荷日", 1.00),
    ]
    missed = virginia[virginia["metric"] == "reservations_missed"]["value"].astype(float)
    reservation_moves = virginia[virginia["metric"] == "reservation_moves"]["value"].astype(float)
    missed_rate = float(missed.sum() / max(missed.sum() + reservation_moves.sum(), 1.0)) if not missed.empty else 0.10
    missed_rate = float(np.clip(missed_rate, 0.04, 0.18))
    shown = 1.0 - missed_rate
    show_probabilities = (0.82 * shown, 0.12 * shown, 0.06 * shown, missed_rate)
    yard_util = houston[houston["metric"] == "yard_utilization_pct"]["value"].astype(float)
    yard_util_mean = float(yard_util.mean() / 100) if not yard_util.empty else 0.40
    disruption_probability = float(np.clip(0.03 + yard_util_mean * 0.08, 0.03, 0.10))

    rows: list[dict[str, object]] = []
    scenarios: list[ScenarioConfig] = []
    for name, label, quantile in targets:
        if quantile >= 1:
            selected = active.loc[active["total_gate_missions"].idxmax()]
        else:
            q = float(active["total_gate_missions"].quantile(quantile))
            selected = active.iloc[(active["total_gate_missions"] - q).abs().argsort().iloc[0]]
        multiplier = float(selected["total_gate_missions"] / median_value) if median_value else 1.0
        mean_requests = float(np.clip(base_mean_requests * multiplier, config.quota_min * 0.75, config.quota_max * 1.10))
        description = f"{label}: {selected['date']}, gate missions={selected['total_gate_missions']:.0f}"
        rows.append(
            {
                "scenario": name,
                "description": description,
                "source_gate_missions": float(selected["total_gate_missions"]),
                "demand_multiplier": multiplier,
                "mean_requests": mean_requests,
                "missed_reservation_rate_from_virginia": missed_rate,
                "yard_utilization_from_houston": yard_util_mean,
                "capacity_disruption_probability": disruption_probability,
            }
        )
        scenarios.append(
            ScenarioConfig(
                name=name,
                mean_requests=mean_requests,
                show_probabilities=show_probabilities,
                exception_arrival_mean=config.exception_arrival_mean,
                arrival_shock_probability=config.arrival_shock_probability,
                arrival_shock_multiplier=config.arrival_shock_multiplier,
                normalize_arrival_shocks=True,
                capacity_disruption_probability=disruption_probability,
                gate_service_cv=config.gate_service_cv,
                yard_service_cv=config.yard_service_cv,
                description=description,
            )
        )
    return pd.DataFrame(rows), tuple(scenarios)


def create_public_data_plots(output_dir: str | Path, sc_summary: pd.DataFrame, scenarios: pd.DataFrame, raw: pd.DataFrame) -> list[Path]:
    output = Path(output_dir)
    figures = output / "figures"
    figures.mkdir(parents=True, exist_ok=True)
    import os

    os.environ.setdefault("MPLCONFIGDIR", str(output / ".matplotlib"))
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "Arial Unicode MS", "DejaVu Sans"]
    plt.rcParams["axes.unicode_minus"] = False
    created: list[Path] = []

    fig, ax = plt.subplots(figsize=(9, 4))
    ax.bar(scenarios["scenario"], scenarios["mean_requests"], color="#2563eb")
    ax.set_title("真实 SC Ports gate missions 校准的需求强度")
    ax.set_ylabel("mean_requests / 30分钟")
    ax.tick_params(axis="x", rotation=15)
    fig.tight_layout()
    path = figures / "public_data_calibrated_demand.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    created.append(path)

    fig, ax = plt.subplots(figsize=(10, 5))
    focus = raw[raw["policy"].isin(["fixed", "pto", "online_joint"])]
    pivot = focus.pivot_table(index="scenario", columns="policy", values="mean_composite_cost", aggfunc="mean")
    pivot.plot(kind="bar", ax=ax)
    ax.set_title("公开真实数据校准场景下的策略综合成本")
    ax.set_ylabel("mean composite cost")
    ax.tick_params(axis="x", rotation=15)
    ax.grid(axis="y", alpha=0.25)
    fig.tight_layout()
    path = figures / "public_data_strategy_composite_cost.png"
    fig.savefig(path, dpi=180, bbox_inches="tight")
    plt.close(fig)
    created.append(path)
    return created


def write_public_data_report(
    output_dir: str | Path,
    sc_summary: pd.DataFrame,
    daily_gate_missions: pd.DataFrame,
    virginia: pd.DataFrame,
    houston: pd.DataFrame,
    tas_summary: pd.DataFrame,
    capacity_summary: pd.DataFrame,
    dwelling_activities: pd.DataFrame,
    dwelling_cases: pd.DataFrame,
    scenarios: pd.DataFrame,
    raw: pd.DataFrame,
) -> Path:
    output = Path(output_dir)
    focus = raw[raw["policy"].isin(["fixed", "pto", "online_joint"])]
    strategy = focus.pivot_table(
        index=["scenario", "policy"],
        values=["mean_composite_cost", "mean_total_wait", "p95_total_wait", "throughput_rate", "acceptance_rate"],
        aggfunc="mean",
    ).reset_index()
    strategy.to_csv(output / "public_data_strategy_means.csv", index=False, encoding="utf-8-sig")
    report = output / "public_data_test_report.md"
    lines = [
        "# 公开真实数据增强版测试报告",
        "",
        "## 核心结论",
        "",
        "本轮测试没有使用完整车辆级预约—闸口—堆场轨迹数据，而是使用多源公开数据对关键随机过程和运营指标进行校准/外部验证。",
        "",
        "这些数据足以支撑论文的核心机制：真实港口存在需求波动、预约履约偏差、闸口 turn time 波动、堆场利用率和 dwell pressure，因此 PTO 模型保真度下降与在线协同稳健性的讨论有现实基础。",
        "",
        "## 数据源覆盖",
        "",
        f"- SC Ports CSV：{len(sc_summary)} 个数值指标摘要，覆盖 gate transactions、turn time、missions、crane productivity、vessel calls、pier moves。",
        f"- Port Virginia weekly metrics：{virginia['source_file'].nunique() if not virginia.empty else 0} 份 PDF，覆盖 reservation moves、missed reservations、turn time。",
        f"- Port Houston terminal reports：{houston['source_file'].nunique() if not houston.empty else 0} 份 PDF，覆盖 completed transactions、yard utilization、dwell days。",
        f"- Mendeley TAS benchmark：{len(tas_summary)} 个 appointment/drayage benchmark sheet。",
        f"- Mendeley capacity benchmark：{len(capacity_summary)} 个 capacity-management xlsx 实例。",
        f"- Dwelling event log：{int(dwelling_activities['count'].sum()) if not dwelling_activities.empty else 0} 行有效事件，{len(dwelling_cases)} 个 case-level 指标。",
        "",
        "## 真实数据校准场景",
        "",
        scenarios.to_markdown(index=False),
        "",
        "## 策略测试均值",
        "",
        strategy.to_markdown(index=False),
        "",
        "## SC Ports 指标摘要",
        "",
        sc_summary.to_markdown(index=False),
        "",
        "## Port Virginia 预约履约指标摘要",
        "",
        virginia.groupby("metric")["value"].describe().reset_index().to_markdown(index=False) if not virginia.empty else "无可解析指标。",
        "",
        "## Port Houston 堆场与 dwell 指标摘要",
        "",
        houston.groupby("metric")["value"].describe().reset_index().to_markdown(index=False) if not houston.empty else "无可解析指标。",
        "",
        "## Dwelling event log 主要活动",
        "",
        dwelling_activities.head(20).to_markdown(index=False) if not dwelling_activities.empty else "未读取 dwelling event log。",
        "",
        "## 图表",
        "",
        "![真实数据校准需求](figures/public_data_calibrated_demand.png)",
        "",
        "![策略综合成本](figures/public_data_strategy_composite_cost.png)",
        "",
        "## 论文表述边界",
        "",
        "可以写：本文结合公开港口运营指标、预约履约统计、堆场利用率、dwell time 和 benchmark instances，对仿真模型进行多源外部验证。",
        "",
        "不要写：本文使用完整车辆级预约—到闸—入闸—堆场—出闸轨迹数据。",
    ]
    report.write_text("\n".join(lines), encoding="utf-8")
    return report


def run_public_data_test(
    config: SimulationConfig,
    data_dir: str | Path,
    output_dir: str | Path,
    replications: int = 10,
    run_fidelity: bool = True,
    model_samples: int = 1,
    dwelling_max_rows: int | None = None,
) -> tuple[pd.DataFrame, pd.DataFrame, Path]:
    root = Path(".")
    data = Path(data_dir)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    organize_public_data(root)

    sc_frames = load_sc_ports(data)
    cleaned_sc = clean_sc_ports(sc_frames, output)
    sc_summary, daily_gate_missions = summarize_sc_ports(cleaned_sc)
    sc_summary.to_csv(output / "sc_ports_summary.csv", index=False, encoding="utf-8-sig")
    daily_gate_missions.to_csv(output / "sc_ports_daily_gate_missions.csv", index=False, encoding="utf-8-sig")

    virginia = parse_virginia_metrics(data / "port_virginia_weekly_metrics", output)
    houston = parse_houston_reports(data / "port_houston_terminal_reports", output)
    tas_summary = summarize_tas_benchmark(data / "mendeley_tas_tours" / "TAS_experiments_input_data.xlsx", output)
    capacity_summary = summarize_capacity_benchmark(data / "mendeley_capacity_management", output)
    dwelling_activities, dwelling_cases = summarize_dwelling_time(data / "mendeley_dwelling_time", output, max_rows=dwelling_max_rows)

    scenario_frame, scenarios = make_public_data_scenarios(config, daily_gate_missions, virginia, houston)
    scenario_frame.to_csv(output / "public_data_calibrated_scenarios.csv", index=False, encoding="utf-8-sig")
    public_config = replace(config, scenarios=scenarios, replications=replications)
    public_config.validate()
    raw, summary = run_experiments(public_config, output, replications=replications)
    create_public_data_plots(output, sc_summary, scenario_frame, raw)

    if run_fidelity:
        fidelity_dir = output / "model_fidelity"
        run_model_fidelity_experiment(public_config, fidelity_dir, replications=replications, model_samples=model_samples)

    report = write_public_data_report(
        output,
        sc_summary,
        daily_gate_missions,
        virginia,
        houston,
        tas_summary,
        capacity_summary,
        dwelling_activities,
        dwelling_cases,
        scenario_frame,
        raw,
    )
    return raw, summary, report
