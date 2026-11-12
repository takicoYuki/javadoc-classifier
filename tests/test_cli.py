import csv
import io
import json

import pytest

from javadoc_classifier.cli import main
from javadoc_classifier.reporters import available_formats, create_reporter


def test_既定はtext形式_エラーがあれば終了コード1(order_service_path, capsys):
    assert main([str(order_service_path)]) == 1
    out = capsys.readouterr().out
    assert "[unknown-param] method cancel" in out
    assert "Javadoc カバレッジ: 69.2%" in out


def test_json形式(order_service_path, capsys):
    main([str(order_service_path), "-f", "json", "--fail-on", "never"])
    data = json.loads(capsys.readouterr().out)

    assert data["summary"]["coverage"] == 69.2
    assert data["summary"]["categories"]["summary"] == 9
    assert len(data["issues"]) == 13


def test_csv形式(order_service_path, capsys):
    main([str(order_service_path), "-f", "csv"])
    rows = list(csv.DictReader(io.StringIO(capsys.readouterr().out)))
    assert len(rows) == 13
    assert rows[0].keys() >= {"file", "line", "severity", "rule"}


def test_markdown形式をファイルに出力(order_service_path, tmp_path):
    out = tmp_path / "report.md"
    main([str(order_service_path), "-f", "markdown", "-o", str(out)])
    text = out.read_text(encoding="utf-8")
    assert text.startswith("# Javadoc レポート")
    assert "| 概要 | 9 |" in text


def test_フォルダを再帰的に探す(tmp_path, capsys):
    (tmp_path / "a" / "b").mkdir(parents=True)
    (tmp_path / "a" / "b" / "Ok.java").write_text("/** OK。 */\npublic class Ok {}\n", encoding="utf-8")
    (tmp_path / "a" / "note.txt").write_text("not java", encoding="utf-8")

    assert main([str(tmp_path), "--fail-on", "warning"]) == 0
    assert "ファイル 1 件 / 問題 0 件" in capsys.readouterr().out


@pytest.mark.parametrize("fail_on, expected", [("never", 0), ("error", 1), ("warning", 1)])
def test_fail_on(order_service_path, fail_on, expected):
    assert main([str(order_service_path), "--fail-on", fail_on, "-f", "csv"]) == expected


def test_min_coverage(order_service_path):
    assert main([str(order_service_path), "--fail-on", "never", "--min-coverage", "70", "-f", "csv"]) == 1
    assert main([str(order_service_path), "--fail-on", "never", "--min-coverage", "60", "-f", "csv"]) == 0


def test_存在しないパスは終了コード2(capsys):
    assert main(["no/such/dir"]) == 2
    assert "エラー" in capsys.readouterr().err


def test_出力形式のFactory():
    assert available_formats() == ["csv", "json", "markdown", "text"]
    with pytest.raises(ValueError):
        create_reporter("xml")
