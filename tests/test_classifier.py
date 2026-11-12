from javadoc_classifier.analyzer import Analyzer
from javadoc_classifier.classifier import Category, classify, register_tag, split_summary, CATEGORY_REGISTRY
from javadoc_classifier.parser import parse_javadoc


def test_最初の1文を概要_残りを詳細に分ける():
    assert split_summary("注文を管理する。<p>登録と取消を行う。") == ("注文を管理する。", "登録と取消を行う。")
    assert split_summary("Returns the size. Never negative.") == ("Returns the size.", "Never negative.")
    assert split_summary("") == ("", "")


def test_タグを分類する():
    jd = parse_javadoc("""/**
     * 検索する。{@link Repo} を使う。
     * @param q 条件
     * @return 結果
     * @throws IOException 読めないとき
     * @see Other
     * @since 1.2
     * @apiNote 独自タグ
     */""")
    c = classify(jd)

    assert [i.text for i in c.of(Category.SUMMARY)] == ["検索する。"]
    assert c.of(Category.PARAMETER)[0].target == "q"
    assert len(c.of(Category.RETURN)) == 1
    assert c.of(Category.EXCEPTION)[0].target == "IOException"
    assert {i.text for i in c.of(Category.REFERENCE)} == {"Other", "Repo"}
    assert len(c.of(Category.META)) == 1
    assert len(c.of(Category.OTHER)) == 1
    assert c.inline_tags["link"] == 1


def test_独自タグの分類を登録できる():
    jd = parse_javadoc("/** 説明。\n * @implNote 実装メモ\n */")
    try:
        register_tag("implNote", Category.DETAIL)
        assert len(classify(jd).of(Category.DETAIL)) == 1
    finally:
        CATEGORY_REGISTRY.pop("implNote")
    assert len(classify(jd).of(Category.OTHER)) == 1


def test_カバレッジは公開APIだけで数え_Overrideは除く(order_service):
    _, stats = Analyzer().analyze_source(order_service)

    # 公開 API 13 件（toString は @Override なので除外、private の fail も除外）
    assert stats.api_declarations == 13
    assert stats.documented == 9
    assert round(stats.coverage, 1) == 69.2
    assert stats.categories[Category.META] == 2
