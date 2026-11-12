"""Javadoc の書き漏れ・食い違いを見つけるルール群。

各ルールは Rule を継承した小さなクラスで、check() だけを実装する（Strategy パターン）。
ルールを追加するときは新しいクラスを作って DEFAULT_RULES に足すだけでよい。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Iterable, Iterator

from .model import Declaration, Issue, Kind, Severity

# @Override が付いたメソッドは親の Javadoc を引き継ぐので、書かなくてよい
_INHERITS_DOC = "Override"


class Rule(ABC):
    """1 つの観点で宣言をチェックするルール。"""

    #: レポートに出すルール名
    name: str = ""
    severity: Severity = Severity.WARNING

    @abstractmethod
    def check(self, decl: Declaration) -> Iterable[str]:
        """問題があればメッセージを返す（なければ何も返さない）。"""

    def issues(self, file: str, decl: Declaration) -> Iterator[Issue]:
        for message in self.check(decl):
            yield Issue(file, decl.line, f"{decl.kind.value} {decl.name}", self.name, self.severity, message)


class MissingJavadoc(Rule):
    name = "missing-javadoc"
    severity = Severity.WARNING

    def check(self, decl):
        if decl.is_api and decl.javadoc is None and _INHERITS_DOC not in decl.annotations:
            yield "公開されている宣言に Javadoc がありません"


class MissingDescription(Rule):
    name = "missing-description"
    severity = Severity.WARNING

    def check(self, decl):
        if decl.javadoc is not None and not decl.javadoc.description:
            yield "説明文がなく、タグしか書かれていません"


class MissingParam(Rule):
    name = "missing-param"
    severity = Severity.ERROR

    def check(self, decl):
        if decl.javadoc is None or decl.kind not in (Kind.METHOD, Kind.CONSTRUCTOR):
            return
        documented = {t.argument for t in decl.javadoc.tags_named("param")}
        for p in decl.params:
            if p not in documented:
                yield f"引数 {p} の @param がありません"


class UnknownParam(Rule):
    name = "unknown-param"
    severity = Severity.ERROR

    def check(self, decl):
        if decl.javadoc is None or decl.kind not in (Kind.METHOD, Kind.CONSTRUCTOR):
            return
        for tag in decl.javadoc.tags_named("param"):
            if tag.argument.startswith("<"):  # 型パラメータ @param <T>
                continue
            if tag.argument not in decl.params:
                yield f"@param {tag.argument} に対応する引数がありません（引数を消したか、名前を変えた可能性があります）"


class MissingReturn(Rule):
    name = "missing-return"
    severity = Severity.WARNING

    def check(self, decl):
        if (decl.javadoc is not None and decl.kind == Kind.METHOD
                and decl.return_type not in (None, "void")
                and not decl.javadoc.tags_named("return")):
            yield f"戻り値（{decl.return_type}）の @return がありません"


class ReturnOnVoid(Rule):
    name = "return-on-void"
    severity = Severity.ERROR

    def check(self, decl):
        if decl.javadoc is None:
            return
        if (decl.kind == Kind.CONSTRUCTOR or decl.return_type == "void") and decl.javadoc.tags_named("return"):
            yield "戻り値がないのに @return が書かれています"


class MissingThrows(Rule):
    name = "missing-throws"
    severity = Severity.WARNING

    def check(self, decl):
        if decl.javadoc is None:
            return
        documented = {t.argument.split(".")[-1] for t in decl.javadoc.tags_named("throws", "exception")}
        for ex in decl.throws:
            if ex not in documented:
                yield f"throws 宣言されている {ex} の @throws がありません"


class EmptyTagText(Rule):
    name = "empty-tag"
    severity = Severity.WARNING

    def check(self, decl):
        if decl.javadoc is None:
            return
        for tag in decl.javadoc.tags:
            if tag.name in ("param", "return", "throws", "exception", "deprecated") and not tag.text:
                target = f" {tag.argument}" if tag.argument else ""
                yield f"@{tag.name}{target} の説明が空です"


class DeprecatedWithoutAnnotation(Rule):
    name = "deprecated-mismatch"
    severity = Severity.WARNING

    def check(self, decl):
        if decl.javadoc is None:
            return
        has_tag = bool(decl.javadoc.tags_named("deprecated"))
        has_annotation = "Deprecated" in decl.annotations
        if has_tag and not has_annotation:
            yield "@deprecated タグがありますが @Deprecated 注釈がありません"
        elif has_annotation and not has_tag:
            yield "@Deprecated 注釈がありますが、理由や代替手段を書く @deprecated タグがありません"


DEFAULT_RULES: tuple[Rule, ...] = (
    MissingJavadoc(),
    MissingDescription(),
    MissingParam(),
    UnknownParam(),
    MissingReturn(),
    ReturnOnVoid(),
    MissingThrows(),
    EmptyTagText(),
    DeprecatedWithoutAnnotation(),
)


def run_rules(file: str, decls: Iterable[Declaration], rules: Iterable[Rule] = DEFAULT_RULES,
              include_private: bool = False) -> list[Issue]:
    rules = tuple(rules)
    issues = []
    for decl in decls:
        if not include_private and not decl.is_api:
            continue  # 既定では public / protected だけをチェックする
        for rule in rules:
            issues.extend(rule.issues(file, decl))
    return issues
