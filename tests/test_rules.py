from collections import Counter

import pytest

from javadoc_classifier.analyzer import Analyzer
from javadoc_classifier.model import Severity
from javadoc_classifier.rules import MissingJavadoc


@pytest.fixture
def issues(order_service):
    report, _ = Analyzer().analyze_source(order_service, "OrderService.java")
    return report.issues


def found(issues, decl):
    return Counter(i.rule for i in issues if i.declaration == decl)


def test_書き漏れと食い違いを検出する(issues):
    assert found(issues, "method cancel") == {"unknown-param": 1, "return-on-void": 1, "missing-throws": 1}
    assert found(issues, "method find") == {
        "missing-description": 1, "missing-param": 2, "missing-return": 1, "empty-tag": 1}
    assert found(issues, "method search") == {"missing-javadoc": 1}
    assert found(issues, "method isFinal") == {"missing-return": 1}


def test_正しく書かれた宣言は何も報告しない(issues):
    for decl in ("class OrderService", "method register", "constructor OrderService", "field MAX_ITEMS"):
        assert not found(issues, decl), decl


def test_Overrideと非公開の宣言は既定では対象外(issues):
    assert not found(issues, "method toString")
    assert not found(issues, "method fail")
    assert not found(issues, "field repository")


def test_include_privateで非公開もチェックする(order_service):
    report, _ = Analyzer(include_private=True).analyze_source(order_service)
    rules = {(i.declaration, i.rule) for i in report.issues}

    assert ("method fail", "missing-param") in rules
    assert ("field repository", "missing-javadoc") not in rules  # MissingJavadoc 自体は公開 API だけ


def test_重要度と行番号(issues):
    i = next(i for i in issues if i.rule == "unknown-param")
    assert i.severity == Severity.ERROR
    assert i.line == 63
    assert "reason" in i.message


def test_型パラメータの_param_は引数がなくても誤検出しない():
    src = """public class A {
        /**
         * 変換する。
         * @param <T> 型
         * @param v 値
         * @return 結果
         */
        public <T> T conv(T v) { return v; }
    }"""
    report, _ = Analyzer().analyze_source(src)
    assert [i.rule for i in report.issues if "conv" in i.declaration] == []


def test_使うルールを差し替えられる(order_service):
    report, _ = Analyzer(rules=[MissingJavadoc()]).analyze_source(order_service)
    assert {i.rule for i in report.issues} == {"missing-javadoc"}


def test_Deprecated注釈とdeprecatedタグの食い違い():
    src = """/** テスト用。 */
    public class A {
        /**
         * 古い。
         * @deprecated {@link #b()} を使う
         */
        public void a() {}
        /** 古い。 */
        @Deprecated
        public void b() {}
    }"""
    report, _ = Analyzer().analyze_source(src)
    assert {(i.declaration, i.rule) for i in report.issues} == {
        ("method a", "deprecated-mismatch"), ("method b", "deprecated-mismatch")}
