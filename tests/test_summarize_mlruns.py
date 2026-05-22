from __future__ import annotations

from pathlib import Path

from scripts.summarize_mlruns import collect_runs, format_markdown_table


def write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_metric(path: Path, value: float) -> None:
    write_text(path, f"123 {value} 0\n")


def test_collect_runs_reads_metrics_and_metadata(tmp_path):
    mlruns = tmp_path / "mlruns"
    exp = mlruns / "1"
    run = exp / "abc123"
    failed = exp / "failed456"

    write_text(exp / "meta.yaml", "name: demo_experiment\n")
    write_text(run / "meta.yaml", "status: 3\nstart_time: 100\nend_time: 200\n")
    write_text(run / "params/cmd-sys.argv", "qrun config/demo.yaml")
    write_metric(run / "metrics/IC", 0.0123)
    write_metric(run / "metrics/Rank IC", 0.0234)
    write_metric(run / "metrics/1day.excess_return_with_cost.annualized_return", 0.071)
    write_metric(run / "metrics/1day.excess_return_with_cost.max_drawdown", -0.12)
    write_metric(run / "metrics/1day.excess_return_with_cost.information_ratio", 0.63)

    write_text(failed / "meta.yaml", "status: 4\nstart_time: 100\nend_time: 110\n")

    rows = collect_runs(mlruns)

    assert len(rows) == 2
    first = rows[0]
    assert first.experiment == "demo_experiment"
    assert first.run_id == "abc123"
    assert first.status == "FINISHED"
    assert first.command == "qrun config/demo.yaml"
    assert first.ic == 0.0123
    assert first.rank_ic == 0.0234
    assert first.ann_excess_cost == 0.071
    assert first.max_drawdown_cost == -0.12
    assert first.ir_cost == 0.63

    second = rows[1]
    assert second.status == "FAILED"


def test_format_markdown_table_contains_percentages(tmp_path):
    mlruns = tmp_path / "mlruns"
    exp = mlruns / "1"
    run = exp / "abc123"
    write_text(exp / "meta.yaml", "name: demo_experiment\n")
    write_text(run / "meta.yaml", "status: 3\n")
    write_metric(run / "metrics/1day.excess_return_with_cost.annualized_return", 0.071)
    write_metric(run / "metrics/1day.excess_return_with_cost.max_drawdown", -0.12)

    table = format_markdown_table(collect_runs(mlruns))

    assert "| experiment | status | run_id |" in table
    assert "demo_experiment" in table
    assert "7.10%" in table
    assert "-12.00%" in table

