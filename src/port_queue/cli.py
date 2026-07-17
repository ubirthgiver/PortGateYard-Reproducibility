from __future__ import annotations

import argparse
from dataclasses import replace

from .config import load_config
from .disturbance import run_disturbance_experiment
from .experiment import run_experiments
from .fidelity import run_model_fidelity_experiment
from .public_data import run_public_data_test
from .real_data import run_real_data_driven_test
from .reporting import generate_outputs


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="港口闸口—堆场队列数值测试")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="运行批量仿真实验")
    run.add_argument("--config", default="configs/core.json")
    run.add_argument("--output", default="outputs")
    run.add_argument("--replications", type=int)
    run.add_argument("--days", type=int)
    run.add_argument("--warmup-days", type=int)
    run.add_argument("--no-report", action="store_true")

    report = sub.add_parser("report", help="从已有 CSV 重新生成图表和报告")
    report.add_argument("--config", default="configs/core.json")
    report.add_argument("--output", default="outputs")

    disturbance = sub.add_parser("disturbance", help="运行扰动强度敏感性实验")
    disturbance.add_argument("--config", default="configs/disturbance.json")
    disturbance.add_argument("--output", default="outputs/disturbance")
    disturbance.add_argument("--replications", type=int)

    fidelity = sub.add_parser("fidelity", help="运行 PTO 模型保真度下降实验")
    fidelity.add_argument("--config", default="configs/fidelity.json")
    fidelity.add_argument("--output", default="outputs/model_fidelity")
    fidelity.add_argument("--replications", type=int)
    fidelity.add_argument("--model-samples", type=int, default=4)

    real = sub.add_parser("real-data", help="抓取公开 TEU 数据并运行真实数据驱动测试")
    real.add_argument("--config", default="configs/fidelity.json")
    real.add_argument("--output", default="outputs/real_data")
    real.add_argument("--start-year", type=int, default=2022)
    real.add_argument("--end-year", type=int, default=2025)
    real.add_argument("--replications", type=int, default=10)
    real.add_argument("--model-samples", type=int, default=2)

    public = sub.add_parser("public-data", help="整理公开真实港口数据，并运行真实数据校准测试")
    public.add_argument("--config", default="configs/fidelity.json")
    public.add_argument("--data", default="data")
    public.add_argument("--output", default="outputs/public_data")
    public.add_argument("--replications", type=int, default=10)
    public.add_argument("--model-samples", type=int, default=1)
    public.add_argument("--dwelling-max-rows", type=int)
    public.add_argument("--no-fidelity", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    config = load_config(args.config)

    if args.command == "run":
        if args.days is not None:
            warmup = args.warmup_days if args.warmup_days is not None else min(config.warmup_days, max(0, args.days - 1))
            config = replace(config, days=args.days, warmup_days=warmup)
        elif args.warmup_days is not None:
            config = replace(config, warmup_days=args.warmup_days)
        raw, summary = run_experiments(config, args.output, args.replications)
        print(f"完成 {len(raw)} 条策略重复实验记录；汇总行数 {len(summary)}。")
        if not args.no_report:
            plots, report = generate_outputs(args.output, config.bootstrap_samples)
            print(f"生成 {len(plots)} 张图表和报告：{report}")
        return 0

    if args.command == "report":
        plots, report = generate_outputs(args.output, config.bootstrap_samples)
        print(f"生成 {len(plots)} 张图表和报告：{report}")
        return 0

    if args.command == "disturbance":
        raw, advantage, report = run_disturbance_experiment(config, args.output, args.replications)
        print(f"完成扰动敏感性实验：{len(raw)} 条策略重复实验记录；在线-PTO对比行数 {len(advantage)}。")
        print(f"生成扰动敏感性报告：{report}")
        return 0

    if args.command == "fidelity":
        raw, advantage, report = run_model_fidelity_experiment(config, args.output, args.replications, args.model_samples)
        print(f"完成模型保真度实验：{len(raw)} 条策略重复实验记录；在线-PTO对比行数 {len(advantage)}。")
        print(f"生成模型保真度报告：{report}")
        return 0

    if args.command == "real-data":
        teu, scenarios, report = run_real_data_driven_test(
            config,
            args.output,
            years=range(args.start_year, args.end_year + 1),
            replications=args.replications,
            model_samples=args.model_samples,
        )
        print(f"下载并整理 {len(teu)} 条月度 TEU 真实数据；生成 {len(scenarios)} 个真实吞吐代表场景。")
        print(f"生成真实数据驱动测试报告：{report}")
        return 0

    if args.command == "public-data":
        raw, summary, report = run_public_data_test(
            config,
            args.data,
            args.output,
            replications=args.replications,
            run_fidelity=not args.no_fidelity,
            model_samples=args.model_samples,
            dwelling_max_rows=args.dwelling_max_rows,
        )
        print(f"完成公开真实数据校准测试：{len(raw)} 条策略重复实验记录；汇总行数 {len(summary)}。")
        print(f"生成公开真实数据测试报告：{report}")
        return 0

    raise ValueError(f"未知命令：{args.command}")


if __name__ == "__main__":
    raise SystemExit(main())
