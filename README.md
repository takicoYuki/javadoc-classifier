# javadoc-classifier

![CI](https://github.com/takicoYuki/javadoc-classifier/actions/workflows/ci.yml/badge.svg)

Java のソースコードから Javadoc を取り出して **中身を種類ごとに分類・集計** し、
**書き漏れや食い違い**（引数を消したのに `@param` が残っている、など）を報告するツールです。
Python 標準ライブラリだけで動きます。

```console
$ javadoc-classifier src/main/java
OrderService.java:21: W [missing-javadoc] field NO_DOC: 公開されている宣言に Javadoc がありません
OrderService.java:63: E [unknown-param] method cancel: @param reason に対応する引数がありません（引数を消したか、名前を変えた可能性があります）
OrderService.java:63: E [return-on-void] method cancel: 戻り値がないのに @return が書かれています
OrderService.java:63: W [missing-throws] method cancel: throws 宣言されている OrderNotFoundException の @throws がありません
OrderService.java:74: E [missing-param] method find: 引数 type の @param がありません
...

ファイル 1 件 / 問題 13 件（エラー 4 件）
Javadoc カバレッジ: 69.2%（公開 API 13 件中 9 件）
内容の内訳: 概要 9, 詳細説明 1, 引数 5, 戻り値 2, 例外 1, 非推奨 1, 参照 1, 作成者・版 2
```

（`tests/fixtures/OrderService.java` を解析した結果です）

## できること

**分類** — Javadoc の中身を次の種類に分けて数えます。

| 分類 | 対象 |
|---|---|
| 概要 / 詳細説明 | 説明文の最初の 1 文 / それ以降（Javadoc の仕様と同じ区切り方） |
| 引数・戻り値・例外 | `@param` / `@return` / `@throws` `@exception` |
| 非推奨 | `@deprecated` |
| 参照 | `@see`、`{@link}` `{@linkplain}` |
| 作成者・版 | `@author` / `@version` / `@since` |
| その他 | 上記以外（`register_tag()` で分類を追加できます） |

**チェック** — 既定では public / protected の宣言が対象です（`--include-private` で全部）。

| ルール | 重要度 | 内容 |
|---|---|---|
| `missing-javadoc` | warning | 公開 API に Javadoc がない（`@Override` は親から引き継ぐので除外） |
| `missing-description` | warning | タグだけで説明文がない |
| `missing-param` | error | 引数に対応する `@param` がない |
| `unknown-param` | error | `@param` に対応する引数がない（型パラメータ `@param <T>` は除外） |
| `missing-return` | warning | 戻り値があるのに `@return` がない |
| `return-on-void` | error | `void` やコンストラクタに `@return` がある |
| `missing-throws` | warning | `throws` 宣言した例外の `@throws` がない |
| `empty-tag` | warning | `@param x` のように説明が空 |
| `deprecated-mismatch` | warning | `@deprecated` タグと `@Deprecated` 注釈の片方しかない |

**集計** — 公開 API のうち Javadoc が書かれている割合（カバレッジ）を出します。

## 使い方

```bash
pip install .            # または: cd src && python -m javadoc_classifier ...
javadoc-classifier src/main/java
javadoc-classifier src/main/java -f markdown -o report.md   # text / markdown / json / csv
javadoc-classifier src/main/java --fail-on warning --min-coverage 80
```

| オプション | 説明 |
|---|---|
| `-f`, `--format` | 出力形式。`text`（既定）/ `markdown` / `json` / `csv` |
| `-o`, `--output` | 出力先ファイル |
| `--include-private` | private / パッケージプライベートもチェックする |
| `--fail-on` | `error`（既定）/ `warning` / `never`。この重要度以上の問題があれば終了コード 1 |
| `--min-coverage` | カバレッジがこの値（%）未満なら終了コード 1 |

終了コードを返すので、CI に組み込んで「Javadoc の書き漏れがあったら落とす」使い方ができます。
このリポジトリの CI でも、サンプルの解析結果（Markdown）をジョブのサマリーに出しています。

## 構成とデザインパターン

もともと Python のデザインパターンの勉強として書いていたものです。
「パターンを使うこと」が目的にならないよう、**変更や追加が起きそうな所にだけ** 使っています。

```
src/javadoc_classifier
├── model.py       宣言・Javadoc・問題を表す dataclass
├── parser.py      Java ソース → 宣言と Javadoc の一覧
├── classifier.py  Javadoc の中身の分類と集計     ← Registry
├── rules.py       チェックルール                 ← Strategy
├── reporters.py   出力形式                       ← Strategy + Factory（デコレーターで登録）
├── analyzer.py    解析・分類・チェックの入口      ← Facade
└── cli.py         コマンドライン
```

| パターン | どこで | 何が楽になるか |
|---|---|---|
| Strategy | `rules.py` の `Rule` | ルール 1 つが小さなクラス 1 つ。追加は `DEFAULT_RULES` に足すだけで、`Analyzer(rules=[...])` で差し替えもできる |
| Strategy + Factory | `reporters.py` の `Reporter` と `@reporter("名前")` | 形式を足してもクラスを書くだけ。CLI の `--format` の選択肢にも自動で並ぶ |
| Registry | `classifier.py` の `CATEGORY_REGISTRY` | タグと分類の対応をデータとして持つので、独自タグ（`@apiNote` など）は `register_tag()` で追加できる |
| Facade | `analyzer.py` の `Analyzer` | CLI やテストは解析・チェック・集計の組み合わせ方を知らなくてよい |

### パーサーについて

Java の構文解析ライブラリは使わず、次の手順で必要な部分だけを読んでいます。

1. 文字列・文字リテラル・コメントを空白に置き換える（改行は残すので行番号がずれない）。Javadoc は中身を保存しておく。
2. 波かっこの入れ子を「型の本体」「メソッドなどのコード」「フィールドの初期化子」に分けて追う。
3. 型の本体の直下で `{` か `;` に達したら、そこまでを宣言の頭部とみなしてクラス・メソッド・フィールドを判定する。

これで、メソッド本体の中の `return foo(x);` や匿名クラスのメソッド、`"a;b{c}"` のような文字列に惑わされません。
ただし完全な Java パーサーではないので、ローカルクラスやラムダの中の宣言は対象外です。

## テスト

```bash
pip install -e ".[test]"
pytest
```

| テスト | 内容 |
|---|---|
| `test_parser.py` | 宣言の種類・行番号・引数・戻り値・throws・注釈の取り出し、メソッド本体や匿名クラス・文字列の除外、ネストしたジェネリクス |
| `test_classifier.py` | 概要と詳細の分け方、タグの分類、独自タグの登録、カバレッジの計算 |
| `test_rules.py` | 各ルールの検出と、正しく書かれた宣言で誤検出しないこと、ルールの差し替え |
| `test_cli.py` | 4 つの出力形式、フォルダの再帰探索、`--fail-on` / `--min-coverage` の終了コード |

CI では Python 3.10 と 3.13 でテストしています。

## ライセンス

MIT
