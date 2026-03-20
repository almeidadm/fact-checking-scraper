from __future__ import annotations

import argparse
from pathlib import Path

from .logging import configure_logging, get_logger
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
