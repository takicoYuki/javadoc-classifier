from javadoc_classifier.model import Kind
from javadoc_classifier.parser import parse_java, parse_javadoc


def by_name(decls):
    """名前 → 宣言。クラスと同名のコンストラクタはクラスを優先する。"""
    result = {}
    for d in decls:
        result.setdefault(d.name, d)
    return result


def test_宣言を種類と行番号つきで取り出す(order_service):
    d = by_name(parse_java(order_service))

    assert (d["OrderService"].kind, d["OrderService"].line) == (Kind.CLASS, 14)
    assert d["register"].kind == Kind.METHOD and d["register"].line == 49
    assert d["Status"].kind == Kind.ENUM
    assert d["Order"].kind == Kind.RECORD
    assert d["Listener"].kind == Kind.INTERFACE
    assert [x.kind for x in parse_java(order_service) if x.name == "OrderService"] == [Kind.CLASS, Kind.CONSTRUCTOR]


def test_メソッド本体や匿名クラスの中身は宣言として拾わない(order_service):
    names = [x.name for x in parse_java(order_service)]

    assert "run" not in names  # 匿名クラスのメソッド
    assert "fail" in names
    assert "save" not in names and "println" not in names


def test_文字列リテラル内の記号に惑わされない(order_service):
    d = by_name(parse_java(order_service))

    assert d["NO_DOC"].kind == Kind.FIELD
    assert "MAX_ITEMS" in d and "PRICES" in d and "task" in d


def test_引数名_戻り値_throwsを取り出す(order_service):
    d = by_name(parse_java(order_service))

    assert d["register"].params == ("customerId", "items")
    assert d["register"].return_type == "long"
    assert d["register"].throws == ("IllegalArgumentException",)
    assert d["search"].params == ("conditions", "keywords")  # ジェネリクス・可変長・注釈つき
    assert d["find"].return_type == "T"
    assert d["cancel"].return_type == "void"


def test_修飾子と注釈(order_service):
    d = by_name(parse_java(order_service))

    assert d["fail"].is_api is False
    assert "Override" in d["toString"].annotations
    assert "Deprecated" in d["find"].annotations
    assert "Deprecated" not in d["search"].annotations  # 引数の注釈は宣言の注釈ではない
    assert d["onRegistered"].is_api  # インターフェースのメンバーは暗黙的に public


def test_Javadocは直前の宣言にだけ結びつく(order_service):
    d = by_name(parse_java(order_service))

    assert d["MAX_ITEMS"].javadoc.description == "1回の注文で登録できる明細の上限"
    assert d["repository"].javadoc is None
    assert d["search"].javadoc is None


def test_Javadocを説明とタグに分ける():
    jd = parse_javadoc("""/**
     * 足し算をする。
     * 複数行の説明。
     *
     * @param a 1つめ
     *          続きの行
     * @param b 2つめ
     * @return 合計（{@code a + b}）
     * @throws ArithmeticException あふれたとき
     */""")

    assert jd.description == "足し算をする。 複数行の説明。"
    assert [(t.name, t.argument) for t in jd.tags] == [
        ("param", "a"), ("param", "b"), ("return", ""), ("throws", "ArithmeticException")]
    assert jd.tags[0].text == "1つめ 続きの行"
    assert jd.tags[2].text == "合計（{@code a + b}）"


def test_コンストラクタとジェネリックメソッド():
    src = """
    public class Box<T> {
        /**
         * 生成する。
         * @param value 値
         */
        public Box(T value) {}
        public static <K, V extends Comparable<V>> Map<K, V> of(K key, V value) { return null; }
        protected int[] values() { return new int[0]; }
    }
    """
    d = by_name(parse_java(src))

    assert d["Box"].kind == Kind.CLASS
    ctor = [x for x in parse_java(src) if x.kind == Kind.CONSTRUCTOR][0]
    assert ctor.params == ("value",)
    assert d["of"].return_type == "Map<K, V>"
    assert d["of"].params == ("key", "value")
    assert d["values"].return_type == "int[]"
