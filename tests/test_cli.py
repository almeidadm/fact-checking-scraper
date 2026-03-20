from factcheck_scrape.cli import build_parser


def test_cli_parse_run():
    parser = build_parser()
    args = parser.parse_args(["run", "--spider", "reuters_fact_check"])
    assert args.command == "run"
    assert args.spider == "reuters_fact_check"


def test_cli_parse_run_with_ignore_existing_seen_state():
    parser = build_parser()
    args = parser.parse_args(["run", "--spider", "observador", "--ignore-existing-seen-state"])

    assert args.command == "run"
    assert args.spider == "observador"
    assert args.ignore_existing_seen_state is True
