"""解析・分類・チェックをまとめて呼ぶ入口（Facade パターン）。

CLI やテストは parser / rules / classifier を個別に組み合わせず、ここだけを使う。
"""
from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field
from pathlib import Path

from .classifier import Statistics
from .model import FileReport
from .parser import parse_java
from .rules import DEFAULT_RULES, Rule, run_rules


@dataclass
class ProjectReport:
    files: list[FileReport] = field(default_factory=list)
    statistics: Statistics = field(default_factory=Statistics)

    @property
    def issues(self):
        return [i for f in self.files for i in f.issues]


class Analyzer:

    def __init__(self, rules: Iterable[Rule] = DEFAULT_RULES, include_private: bool = False):
        self.rules = tuple(rules)
        self.include_private = include_private

    def analyze_source(self, source: str, file: str = "<string>") -> tuple[FileReport, Statistics]:
        decls = parse_java(source)
        report = FileReport(file, decls, run_rules(file, decls, self.rules, self.include_private))
        stats = Statistics()
        for d in decls:
            stats.add(d)
        return report, stats

    def analyze_paths(self, paths: Iterable[str | Path]) -> ProjectReport:
        project = ProjectReport()
        for path in _java_files(paths):
            source = path.read_text(encoding="utf-8", errors="replace")
            report, stats = self.analyze_source(source, path.as_posix())
            project.files.append(report)
            project.statistics.merge(stats)
        return project


def _java_files(paths: Iterable[str | Path]) -> list[Path]:
    found: list[Path] = []
    for p in map(Path, paths):
        if p.is_dir():
            found.extend(sorted(p.rglob("*.java")))
        elif p.suffix == ".java" and p.is_file():
            found.append(p)
        else:
            raise FileNotFoundError(f"Java ファイルまたはフォルダではありません: {p}")
    return found
