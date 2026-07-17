from __future__ import annotations

from dataclasses import replace
from html import unescape
from pathlib import Path
import re
from urllib.request import Request, urlopen

import numpy as np
import pandas as pd

from .config import ScenarioConfig, SimulationConfig
from .fidelity import run_model_fidelity_experiment


POLA_BASE = "https://www.portoflosangeles.org/Business/statistics/Container-Statistics/Historical-TEU-Statistics-{year}"
MONTHS = {
    "January": 1,
    "February": 2,
    "March": 3,
    "April": 4,
    "May": 5,
    "June": 6,
    "July": 7,
    "August": 8,
    "September": 9,
    "October": 10,
    "November": 11,
    "December": 12,
}


def _read_url(url: str) -> str:
    request = Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urlopen(request, timeout=30) as response:
        return response.read().decode("utf-8", errors="replace")


def _clean_cell(value: str) -> str:
    value = re.sub(r"<[^>]+>", "", value)
    value = unescape(value).replace("\xa0", " ").strip()
    return value


def _to_float(value: str) -> float:
    value = value.replace(",", "").replace("%", "").strip()
    return float(value)


def fetch_pola_monthly_teu(years: list[int] | range, output_dir: str | Path) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for year in years:
        url = POLA_BASE.format(year=year)
        html = _read_url(url)
        for match in re.finditer(r"<tr[^>]*MonthRow[^>]*>(.*?)</tr>", html, flags=re.IGNORECASE | re.DOTALL):
            cells = re.findall(r"<td[^>]*>(.*?)</td>", match.group(1), flags=re.IGNORECASE | re.DOTALL)
            cleaned = [_clean_cell(cell) for cell in cells]
            if len(cleaned) < 9 or cleaned[0] not in MONTHS:
                continue
            rows.append(
                {
                    "source": "Port of Los Angeles official container statistics",
                    "source_url": url,
                    "year": int(year),
                    "month": MONTHS[cleaned[0]],
                    "month_name": cleaned[0],
                    "loaded_imports_teu": _to_float(cleaned[1]),
                    "empty_imports_teu": _to_float(cleaned[2]),
                    "total_imports_teu": _to_float(cleaned[3]),
                    "loaded_exports_teu": _to_float(cleaned[4]),
                    "empty_exports_teu": _to_float(cleaned[5]),
                    "total_exports_teu": _to_float(cleaned[6]),
                    "total_teu": _to_float(cleaned[7]),
                    "prior_year_change_pct": _to_float(cleaned[8]),
                }
            )
    frame = pd.DataFrame(rows).sort_values(["year", "month"]).reset_index(drop=True)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    frame.to_csv(output / "pola_monthly_teu.csv", index=False, encoding="utf-8-sig")
    return frame


def representative_teu_scenarios(
    teu: pd.DataFrame,
    base_mean_requests: float = 23.0,
) -> tuple[pd.DataFrame, tuple[ScenarioConfig, ...]]:
    data = teu.copy()
    median_teu = float(data["total_teu"].median())
    targets = [
        ("low_real_month", "真实低吞吐月份", 0.25),
        ("median_real_month", "真实中位吞吐月份", 0.50),
        ("high_real_month", "真实高吞吐月份", 0.75),
        ("peak_real_month", "真实峰值吞吐月份", 1.00),
    ]
    selected_rows: list[dict[str, object]] = []
    scenarios: list[ScenarioConfig] = []
    for name, label, quantile in targets:
        if quantile >= 1:
            row = data.loc[data["total_teu"].idxmax()]
        else:
            target = float(data["total_teu"].quantile(quantile))
            row = data.iloc[(data["total_teu"] - target).abs().argsort().iloc[0]]
        multiplier = float(row["total_teu"] / median_teu)
        mean_requests = base_mean_requests * multiplier
        description = f"{label}: {int(row['year'])}-{int(row['month']):02d}, {row['total_teu']:.0f} TEU"
        selected_rows.append(
            {
                "scenario": name,
                "description": description,
                "year": int(row["year"]),
                "month": int(row["month"]),
                "total_teu": float(row["total_teu"]),
                "teu_to_median_multiplier": multiplier,
                "mean_requests": mean_requests,
            }
        )
        scenarios.append(
            ScenarioConfig(
                name=name,
                mean_requests=mean_requests,
                show_probabilities=(0.75, 0.10, 0.05, 0.10),
                exception_arrival_mean=0.5,
                arrival_shock_probability=0.10,
                arrival_shock_multiplier=1.25,
                normalize_arrival_shocks=True,
                capacity_disruption_probability=0.05,
                gate_service_cv=0.35,
                yard_service_cv=0.50,
                description=description,
            )
        )
    scenario_frame = pd.DataFrame(selected_rows)
    return scenario_frame, tuple(scenarios)


def describe_real_teu(teu: pd.DataFrame) -> pd.DataFrame:
    values = teu["total_teu"].to_numpy(dtype=float)
    monthly_change = teu["total_teu"].pct_change().dropna().to_numpy(dtype=float)
    return pd.DataFrame(
        [
            {"metric": "months", "value": len(teu)},
            {"metric": "mean_total_teu", "value": float(np.mean(values))},
            {"metric": "median_total_teu", "value": float(np.median(values))},
            {"metric": "min_total_teu", "value": float(np.min(values))},
            {"metric": "max_total_teu", "value": float(np.max(values))},
            {"metric": "coefficient_of_variation", "value": float(np.std(values, ddof=1) / np.mean(values))},
            {"metric": "mean_abs_monthly_change", "value": float(np.mean(np.abs(monthly_change)))},
        ]
    )


def _key_advantage_table(advantage: pd.DataFrame | None) -> pd.DataFrame | None:
    if advantage is None or advantage.empty:
        return None
    selected = advantage[
        advantage["metric"].isin(["mean_composite_cost", "throughput_rate", "acceptance_rate", "p95_total_wait"])
    ].copy()
    selected["online_advantage_ci"] = selected.apply(
        lambda x: f"{x['online_advantage']:.3f} [{x['ci_low']:.3f}, {x['ci_high']:.3f}]",
        axis=1,
    )
    return selected[
        ["scenario", "fidelity_label", "metric_label", "pto", "online_joint", "online_advantage_ci"]
    ].rename(
        columns={
            "scenario": "场景",
            "fidelity_label": "PTO模型状态",
            "metric_label": "指标",
            "pto": "PTO",
            "online_joint": "在线协同",
            "online_advantage_ci": "在线优势（95% CI）",
        }
    )


def write_real_data_report(
    teu: pd.DataFrame,
    scenarios: pd.DataFrame,
    output_dir: str | Path,
    advantage: pd.DataFrame | None = None,
) -> Path:
    output = Path(output_dir)
    summary = describe_real_teu(teu)
    key_table = _key_advantage_table(advantage)
    report = output / "real_data_driven_test_report.md"
    lines = [
        "# 真实港口公开数据驱动测试报告",
        "",
        "## 数据来源",
        "",
        "本测试使用 Port of Los Angeles 官方公开的月度 Container Statistics / Historical TEU Statistics。该数据是月度 TEU 吞吐统计，不是车辆级闸口排队或堆场作业明细。",
        "",
        "因此，本测试的性质是：用真实港口吞吐波动校准需求强度，再运行真实数据驱动的压力测试。它可以增强外部有效性，但不能替代车辆级真实排队验证。",
        "",
        "数据来源页面：https://www.portoflosangeles.org/business/statistics/container-statistics",
        "",
        "## 真实数据描述",
        "",
        summary.to_markdown(index=False),
        "",
        "## 由真实 TEU 选择的代表性场景",
        "",
        scenarios.to_markdown(index=False),
        "",
        "## 策略测试结果",
        "",
    ]
    if key_table is not None:
        lines.extend(
            [
                "下表中的“在线优势”含义是：对成本、等待类指标，PTO 减去在线协同；对吞吐率和接受率，在线协同减去 PTO。因此大于 0 表示在线协同更好。",
                "",
                key_table.to_markdown(index=False),
                "",
            ]
        )
    else:
        lines.extend(
            [
                "策略测试结果请见 `model_fidelity_report.md` 和 `online_vs_pto_by_fidelity.csv`。",
                "",
            ]
        )
    lines.extend(
        [
            "## 使用方式",
            "",
            "- `pola_monthly_teu.csv`：官方月度 TEU 数据整理结果；",
            "- `real_teu_scenarios.csv`：由真实 TEU 选出的低/中/高/峰值代表场景；",
            "- `online_vs_pto_by_fidelity.csv`：在线协同与 PTO 在不同模型保真度下的成对比较；",
            "- `model_fidelity_report.md` / `model_fidelity_report.html`：完整模型保真度报告和图表。",
            "",
            "## 论文解释边界",
            "",
            "如果后续能获得真实车辆级预约、到达、闸口等待和堆场作业时间数据，应替换当前的合成微观过程。当前测试证明的是：核心机制在真实港口吞吐波动校准下仍可运行，并检验结论方向是否稳健。",
        ]
    )
    report.write_text("\n".join(lines), encoding="utf-8")
    return report


def run_real_data_driven_test(
    config: SimulationConfig,
    output_dir: str | Path,
    years: list[int] | range = range(2022, 2026),
    replications: int = 10,
    model_samples: int = 2,
) -> tuple[pd.DataFrame, pd.DataFrame, Path]:
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    teu = fetch_pola_monthly_teu(years, output)
    scenario_frame, scenarios = representative_teu_scenarios(teu)
    scenario_frame.to_csv(output / "real_teu_scenarios.csv", index=False, encoding="utf-8-sig")
    real_config = replace(config, scenarios=scenarios, replications=replications)
    real_config.validate()
    _, advantage, _ = run_model_fidelity_experiment(
        real_config,
        output,
        replications=replications,
        model_samples=model_samples,
    )
    report = write_real_data_report(teu, scenario_frame, output, advantage)
    return teu, scenario_frame, report
