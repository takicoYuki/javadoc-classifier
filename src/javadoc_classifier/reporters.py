"""結果の出力形式（Strategy パターン + デコレーターによる登録 = Factory）。

新しい形式を足すときは Reporter を継承したクラスに @reporter("名前") を付けるだけで、
CLI の --format の選択肢にも自動で並ぶ。
"""
from __future__ import annotations

import csv
import io
import json
from abc import ABC, abstractmethod
from collections.abc import Callable

from .analyzer import ProjectReport
from .classifier import Category
from .model import Severity

_REPORTERS: dict[str, type[Reporter]] = {}


def reporter(name: str) -> Callable[[type[Reporter]], type[Reporter]]:
    def register(cls: type[Reporter]) -> type[Reporter]:
        _REPORTERS[name] = cls
        return cls
    return register


def create_reporter(name: str) -> Reporter:
    try:
        return _REPORTERS[name]()
    except KeyError:
        raise ValueError(f"未対応の形式です: {name}（{', '.join(available_formats())} から選んでください）") from None


def available_formats() -> list[str]:
    return sorted(_REPORTERS)


class Reporter(ABC):

    @abstractmethod
    def render(self, report: ProjectReport) -> str:
        ...


def _category_rows(report: ProjectReport) -> list[tuple[str, int]]:
    return [(c.value, report.statistics.categories[c]) for c in Category if report.statistics.categories[c]]


@reporter("text")
class TextReporter(Reporter):

    def render(self, report):
        out = []
        for f in report.files:
            for i in f.issues:
                mark = "E" if i.severity == Severity.ERROR else "W"
                out.append(f"{i.file}:{i.line}: {mark} [{i.rule}] {i.declaration}: {i.message}")
        s = report.statistics
        errors = sum(1 for i in report.issues if i.severity == Severity.ERROR)
        out.append("")
        out.append(f"ファイル {len(report.files)} 件 / 問題 {len(report.issues)} 件（エラー {errors} 件）")
        out.append(f"Javadoc カバレッジ: {s.coverage:.1f}%（公開 API {s.api_declarations} 件中 {s.documented} 件）")
        if s.categories:
            out.append("内容の内訳: " + ", ".join(f"{name} {n}" for name, n in _category_rows(report)))
        return "\n".join(out) + "\n"


@reporter("markdown")
class MarkdownReporter(Reporter):

    def render(self, report):
        s = report.statistics
        out = ["# Javadoc レポート", "",
               f"- ファイル: {len(report.files)} 件",
               f"- カバレッジ: **{s.coverage:.1f}%**（公開 API {s.api_declarations} 件中 {s.documented} 件）",
               f"- 問題: {len(report.issues)} 件", ""]
        if s.categories:
            out += ["## 内容の内訳", "", "| 分類 | 件数 |", "|---|---:|"]
            out += [f"| {name} | {n} |" for name, n in _category_rows(report)]
            out.append("")
        if report.issues:
            out += ["## 問題", "", "| 場所 | 重要度 | ルール | 対象 | 内容 |", "|---|---|---|---|---|"]
            for i in report.issues:
                message = i.message.replace("|", r"\|")  # 表が崩れないようにエスケープ
                out.append(f"| `{i.file}:{i.line}` | {i.severity.value} | {i.rule} | `{i.declaration}` | {message} |")
            out.append("")
        return "\n".join(out)


@reporter("json")
class JsonReporter(Reporter):

    def render(self, report):
        s = report.statistics
        data = {
            "summary": {
                "files": len(report.files),
                "api_declarations": s.api_declarations,
                "documented": s.documented,
                "coverage": round(s.coverage, 1),
                "categories": {c.name.lower(): s.categories[c] for c in Category if s.categories[c]},
                "inline_tags": dict(s.inline_tags),
            },
            "issues": [
                {"file": i.file, "line": i.line, "declaration": i.declaration, "rule": i.rule,
                 "severity": i.severity.value, "message": i.message}
                for i in report.issues
            ],
        }
        return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


@reporter("csv")
class CsvReporter(Reporter):

    def render(self, report):
        buf = io.StringIO()
        w = csv.writer(buf, lineterminator="\n")
        w.writerow(["file", "line", "severity", "rule", "declaration", "message"])
        for i in report.issues:
            w.writerow([i.file, i.line, i.severity.value, i.rule, i.declaration, i.message])
        return buf.getvalue()
