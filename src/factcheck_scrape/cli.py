from __future__ import annotations

import argparse
from pathlib import Path

from .logging import configure_logging, get_logger
from .quality import analyze_run, format_quality_text
from .report import format_report_text, generate_report
from .runner import list_spiders, run_all_spiders, run_spider
from .scheduler import run_schedule
from .utils import generate_run_id


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="factcheck-scrape")
    subparsers = parser.add_subparsers(dest="command", required=True)

    run_parser = subparsers.add_parser("run", help="Executa spiders manualmente")
    run_parser.add_argument("--spider", required=True, help="Nome da spider ou 'all'")
    run_parser.add_argument("--data-dir", default="data", help="Diretorio para dados")
    run_parser.add_argument("--run-id", default=None, help="Run ID (opcional)")
    run_parser.add_argument(
        "--ignore-existing-seen-state",
        action="store_true",
        help="Ignora o estado historico de deduplicacao para permitir uma recolheita completa",
    )

    schedule_parser = subparsers.add_parser("schedule", help="Agenda spiders via APScheduler")
    schedule_parser.add_argument(
        "--config",
        default="configs/schedule.yaml",
        help="Caminho do arquivo de agendamento",
    )
    schedule_parser.add_argument("--data-dir", default="data", help="Diretorio para dados")

    list_parser = subparsers.add_parser("list", help="Lista spiders disponiveis")
    list_parser.add_argument("--data-dir", default="data", help="Diretorio para dados")

    quality_parser = subparsers.add_parser("quality", help="Metricas de qualidade por spider")
    quality_parser.add_argument("--data-dir", default="data", help="Diretorio para dados")
    quality_parser.add_argument(
        "--run-id", default=None, help="Run ID especifico (default: mais recente)"
    )
    quality_parser.add_argument(
        "--json", action="store_true", dest="json_output", help="Saida em formato JSON"
    )

    report_parser = subparsers.add_parser("report", help="Relatorio das ultimas execucoes")
    report_parser.add_argument("--data-dir", default="data", help="Diretorio para dados")
    report_parser.add_argument(
        "--count", type=int, default=1, help="Numero de runs recentes a incluir"
    )
    report_parser.add_argument(
        "--json", action="store_true", dest="json_output", help="Saida em formato JSON"
    )

    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "list":
        configure_logging("list", Path("logs"))
        logger = get_logger("cli")
        names = list_spiders()
        logger.info("spider_list", spiders=names)
        for name in names:
            print(name)
        return

    if args.command == "schedule":
        data_dir = Path(args.data_dir)
        run_schedule(Path(args.config), data_dir)
        return

    if args.command == "quality":
        import json as json_mod

        from .report import find_latest_runs

        data_dir = Path(args.data_dir)
        if args.run_id:
            run_dir = data_dir / "runs" / args.run_id
        else:
            latest = find_latest_runs(data_dir, count=1)
            if not latest:
                print("No runs found.")
                return
            run_dir = latest[0].parent
        quality = analyze_run(run_dir)
        if args.json_output:
            print(json_mod.dumps(
                {k: v.to_dict() for k, v in quality.items()},
                indent=2,
                ensure_ascii=False,
            ))
        else:
            print(format_quality_text(quality))
        return

    if args.command == "report":
        import json as json_mod

        data_dir = Path(args.data_dir)
        reports = generate_report(data_dir, count=args.count)
        if args.json_output:
            print(json_mod.dumps([r.to_dict() for r in reports], indent=2, ensure_ascii=False))
        else:
            print(format_report_text(reports))
        return

    if args.command == "run":
        data_dir = Path(args.data_dir)
        run_id = args.run_id or generate_run_id()
        if args.spider == "all":
            run_all_spiders(
                data_dir=data_dir,
                run_id=run_id,
                ignore_existing_seen_state=args.ignore_existing_seen_state,
            )
        else:
            run_spider(
                args.spider,
                data_dir=data_dir,
                run_id=run_id,
                ignore_existing_seen_state=args.ignore_existing_seen_state,
            )
        return

    parser.print_help()


if __name__ == "__main__":
    main()
