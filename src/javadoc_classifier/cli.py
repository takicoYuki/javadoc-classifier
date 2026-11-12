"""コマンドラインの入口。"""
from __future__ import annotations

import argparse
import sys

from . import __version__
from .analyzer import Analyzer
from .model import Severity
from .reporters import available_formats, create_reporter


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="javadoc-classifier",
        description="Java ソースの Javadoc を分類・集計し、書き漏れや食い違いを報告します。",
    )
    p.add_argument("paths", nargs="+", help="Java ファイルまたはフォルダ（フォルダは配下を再帰的に探す）")
    p.add_argument("-f", "--format", default="text", choices=available_formats(), help="出力形式（既定: text）")
    p.add_argument("-o", "--output", help="出力先ファイル（省略時は標準出力）")
    p.add_argument("--include-private", action="store_true", help="private / パッケージプライベートもチェックする")
    p.add_argument("--fail-on", choices=["error", "warning", "never"], default="error",
                   help="この重要度以上の問題があれば終了コード 1 にする（既定: error）")
    p.add_argument("--min-coverage", type=float, default=0.0,
                   help="カバレッジ（%%）がこの値未満なら終了コード 1 にする")
    p.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        report = Analyzer(include_private=args.include_private).analyze_paths(args.paths)
    except FileNotFoundError as e:
        print(f"エラー: {e}", file=sys.stderr)
        return 2

    text = create_reporter(args.format).render(report)
    if args.output:
        with open(args.output, "w", encoding="utf-8", newline="") as f:
            f.write(text)
    else:
        sys.stdout.write(text)

    severities = {i.severity for i in report.issues}
    failed = (
        (args.fail_on == "error" and Severity.ERROR in severities)
        or (args.fail_on == "warning" and bool(severities))
        or report.statistics.coverage < args.min_coverage
    )
    return 1 if failed else 0
