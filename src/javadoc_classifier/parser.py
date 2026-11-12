"""Java のソースコードから宣言とその Javadoc を取り出す。

正規表現だけで 1 行ずつ見ると、メソッド本体の `return foo(x);` などをメソッド宣言と
誤認してしまう。そこで次の手順で解析する。

1. 文字列リテラル・文字リテラル・通常のコメントを空白に置き換える（改行は残す）。
   Javadoc（/** ... */）は中身を保存したうえで空白に置き換える。
2. 1 文字ずつ読み、波かっこの入れ子を「型の本体」か「コードブロック」かで管理する。
3. 型の本体の直下で `{` か `;` に達したら、そこまでの文字列を宣言の頭部とみなして解析する。
"""
from __future__ import annotations

import re
from dataclasses import dataclass

from .model import Declaration, Javadoc, Kind, Tag

MODIFIERS = {
    "public", "protected", "private", "static", "final", "abstract", "sealed",
    "non-sealed", "strictfp", "synchronized", "native", "transient", "volatile", "default",
}

_TYPE_RE = re.compile(r"\b(class|interface|enum|record)\s+(\w+)")
_ANNOTATION_RE = re.compile(r"@(?!interface\b)([\w.]+)(\s*\([^()]*\))?")
_TAG_RE = re.compile(r"^@(\w+)\s*(.*)$", re.S)


@dataclass
class _RawJavadoc:
    start: int
    end: int
    text: str


@dataclass
class _Block:
    kind: str  # "type" / "code" / "init"
    type_kind: Kind | None = None
    enum_constants_done: bool = True


def parse_java(source: str) -> list[Declaration]:
    """ソースコード全体を解析して、宣言の一覧を出現順に返す。"""
    cleaned, javadocs = _strip_literals_and_comments(source)
    return _Scanner(cleaned, javadocs, source).scan()


def parse_javadoc(raw: str) -> Javadoc:
    """`/** ... */` の中身を説明文とブロックタグに分ける。"""
    body = raw[3:-2] if raw.startswith("/**") and raw.endswith("*/") else raw
    lines = [re.sub(r"^\s*\*? ?", "", line, count=1).rstrip() for line in body.splitlines()]
    text = "\n".join(lines).strip()

    # 行頭の @ から次の行頭の @ までを 1 つのタグとする（{@link ...} のようなインラインタグは除く）
    parts = re.split(r"(?m)^(?=@\w)", text)
    description, tag_parts = parts[0].strip(), parts[1:]

    tags = []
    for part in tag_parts:
        m = _TAG_RE.match(part.strip())
        if not m:
            continue
        name, rest = m.group(1), " ".join(m.group(2).split())
        argument = ""
        if name in ("param", "throws", "exception"):
            arg, _, rest = rest.partition(" ")
            argument = arg
        tags.append(Tag(name=name, argument=argument, text=rest.strip()))
    return Javadoc(description=" ".join(description.split()), tags=tuple(tags))


def _strip_literals_and_comments(src: str) -> tuple[str, list[_RawJavadoc]]:
    out = list(src)
    javadocs: list[_RawJavadoc] = []
    i, n = 0, len(src)

    def blank(a: int, b: int) -> None:
        for k in range(a, b):
            if out[k] != "\n":
                out[k] = " "

    while i < n:
        if src.startswith('"""', i):  # テキストブロック
            j = src.find('"""', i + 3)
            j = n if j < 0 else j + 3
            blank(i + 1, j - 1)
            i = j
        elif src[i] in "\"'":
            q, j = src[i], i + 1
            while j < n and src[j] != q and src[j] != "\n":
                j += 2 if src[j] == "\\" else 1
            blank(i + 1, min(j, n))
            i = j + 1
        elif src.startswith("//", i):
            j = src.find("\n", i)
            j = n if j < 0 else j
            blank(i, j)
            i = j
        elif src.startswith("/*", i):
            j = src.find("*/", i + 2)
            j = n if j < 0 else j + 2
            if src.startswith("/**", i) and not src.startswith("/**/", i):
                javadocs.append(_RawJavadoc(i, j, src[i:j]))
            blank(i, j)
            i = j
        else:
            i += 1
    return "".join(out), javadocs


class _Scanner:

    def __init__(self, text: str, javadocs: list[_RawJavadoc], original: str):
        self.text = text
        self.javadocs = javadocs
        self.line_starts = [0] + [m.end() for m in re.finditer("\n", original)]
        self.result: list[Declaration] = []

    def scan(self) -> list[Declaration]:
        stack: list[_Block] = []
        header_start = 0
        paren = 0
        text = self.text

        for i, ch in enumerate(text):
            in_code = any(b.kind == "code" for b in stack)
            if ch == "(":
                paren += 1
            elif ch == ")":
                paren = max(0, paren - 1)
            elif ch == "{" and paren == 0:
                if in_code or (stack and stack[-1].kind == "init"):
                    stack.append(_Block("code" if in_code else "init"))
                    continue
                header = text[header_start:i]
                if "=" in header.split("(")[0] and not _TYPE_RE.search(header):
                    stack.append(_Block("init"))  # フィールドの初期化子（配列・匿名クラス）
                    continue
                type_kind = self._handle_header(header_start, i, stack, ends_with_body=True)
                if type_kind is not None:
                    stack.append(_Block("type", type_kind, enum_constants_done=type_kind != Kind.ENUM))
                else:
                    stack.append(_Block("code"))
                header_start = i + 1
            elif ch == "}" and paren == 0:
                if stack:
                    popped = stack.pop()
                    if popped.kind == "init":
                        continue  # 初期化子の終わり。フィールド宣言の ; まで頭部を伸ばす
                if not any(b.kind == "code" for b in stack):
                    header_start = i + 1
            elif ch == ";" and paren == 0 and not in_code:
                if stack and stack[-1].kind == "init":
                    continue
                if stack and stack[-1].type_kind == Kind.ENUM and not stack[-1].enum_constants_done:
                    stack[-1].enum_constants_done = True  # ここまでは列挙定数
                else:
                    self._handle_header(header_start, i, stack, ends_with_body=False)
                header_start = i + 1
        return self.result

    def _line_of(self, offset: int) -> int:
        lo, hi = 0, len(self.line_starts) - 1
        while lo < hi:
            mid = (lo + hi + 1) // 2
            if self.line_starts[mid] <= offset:
                lo = mid
            else:
                hi = mid - 1
        return lo + 1

    def _handle_header(self, start: int, end: int, stack: list[_Block], ends_with_body: bool) -> Kind | None:
        raw = self.text[start:end]
        if not raw.strip():
            return None
        first = start + (len(raw) - len(raw.lstrip()))

        javadoc = None
        for jd in self.javadocs:
            if start <= jd.start and jd.end <= first:
                javadoc = parse_javadoc(jd.text)  # 頭部の直前にある最後の Javadoc

        enclosing = stack[-1].type_kind if stack else None
        # 宣言自身の注釈だけを拾う（引数や初期化子の中の注釈は除く）
        own = re.split(r"[(=]", raw, maxsplit=1)[0]
        annotations = frozenset(m.group(1).split(".")[-1] for m in _ANNOTATION_RE.finditer(own))
        header = " ".join(_ANNOTATION_RE.sub(" ", raw.replace("@interface", " interface ")).split())
        if not header:
            return None

        type_match = _TYPE_RE.search(header)
        if type_match and "(" not in header[: type_match.start()]:
            kind = Kind(type_match.group(1))
            modifiers = self._modifiers(header[: type_match.start()], enclosing)
            self._add(Declaration(kind, type_match.group(2), self._line_of(first), modifiers,
                                  javadoc=javadoc, annotations=annotations))
            return kind

        if header in MODIFIERS or header == "static":  # static { ... } などの初期化ブロック
            return None

        if "(" in header and "=" not in header.split("(")[0]:
            self._add_method(header, first, enclosing, javadoc, annotations)
        elif not ends_with_body:
            self._add_field(header, first, enclosing, javadoc, annotations)
        return None

    def _add(self, decl: Declaration) -> None:
        self.result.append(decl)

    @staticmethod
    def _modifiers(prefix: str, enclosing: Kind | None) -> frozenset[str]:
        mods = {w for w in prefix.split() if w in MODIFIERS}
        if enclosing in (Kind.INTERFACE,) and "private" not in mods:
            mods.add("public")  # インターフェースのメンバーは暗黙的に public
        return frozenset(mods)

    def _add_method(self, header: str, first: int, enclosing: Kind | None,
                    javadoc: Javadoc | None, annotations: frozenset[str]) -> None:
        open_idx = header.index("(")
        close_idx = _matching_paren(header, open_idx)
        before = header[:open_idx].strip()
        params_text = header[open_idx + 1: close_idx]
        after = header[close_idx + 1:]

        name_match = re.search(r"(\w+)$", before)
        if not name_match:
            return
        name = name_match.group(1)
        prefix = before[: name_match.start()].strip()
        prefix = _strip_type_parameters(prefix)
        words = prefix.split()
        rest = [w for w in words if w not in MODIFIERS]
        modifiers = self._modifiers(" ".join(w for w in words if w in MODIFIERS), enclosing)

        throws_match = re.search(r"\bthrows\s+([\w.,\s<>]+)", after)
        throws = tuple(t.strip().split(".")[-1] for t in throws_match.group(1).split(",")) if throws_match else ()

        kind = Kind.CONSTRUCTOR if not rest else Kind.METHOD
        self._add(Declaration(
            kind=kind,
            name=name,
            line=self._line_of(first),
            modifiers=modifiers,
            params=tuple(_param_names(params_text)),
            return_type=" ".join(rest) if rest else None,
            throws=throws,
            javadoc=javadoc,
            annotations=annotations,
        ))

    def _add_field(self, header: str, first: int, enclosing: Kind | None,
                   javadoc: Javadoc | None, annotations: frozenset[str]) -> None:
        decl_part = header.split("=")[0]
        while re.search(r"<[^<>]*>", decl_part):  # Map<String, List<Integer>> → Map
            decl_part = re.sub(r"<[^<>]*>", "", decl_part)
        words = decl_part.replace(",", " ").split()
        names = [w for w in words if re.fullmatch(r"[A-Za-z_$][\w$]*", w) and w not in MODIFIERS]
        if len(names) < 2:  # 型と名前の 2 つが必要
            return
        modifiers = {w for w in words if w in MODIFIERS}
        if enclosing == Kind.INTERFACE:
            modifiers |= {"public", "static", "final"}
        self._add(Declaration(Kind.FIELD, names[-1] if "," not in decl_part else names[1], self._line_of(first),
                              frozenset(modifiers), javadoc=javadoc, annotations=annotations))


def _strip_type_parameters(prefix: str) -> str:
    """修飾子の後ろにある型パラメータ（`<K, V extends Comparable<V>>`）を取り除く。"""
    m = re.match(r"((?:[\w-]+\s+)*?)<", prefix)
    if not m or any(w not in MODIFIERS for w in m.group(1).split()):
        return prefix  # 戻り値型のジェネリクス（List<String> など）はそのまま
    depth = 0
    for k in range(m.end() - 1, len(prefix)):
        depth += {"<": 1, ">": -1}.get(prefix[k], 0)
        if depth == 0:
            return (m.group(1) + prefix[k + 1:]).strip()
    return prefix


def _matching_paren(s: str, open_idx: int) -> int:
    depth = 0
    for k in range(open_idx, len(s)):
        if s[k] == "(":
            depth += 1
        elif s[k] == ")":
            depth -= 1
            if depth == 0:
                return k
    return len(s)


def _param_names(params_text: str) -> list[str]:
    """`final Map<String, List<Integer>> map, String... args` → ["map", "args"]"""
    params, depth, current = [], 0, ""
    for ch in params_text:
        if ch in "<(":
            depth += 1
        elif ch in ">)":
            depth -= 1
        if ch == "," and depth == 0:
            params.append(current)
            current = ""
        else:
            current += ch
    if current.strip():
        params.append(current)

    names = []
    for p in params:
        p = _ANNOTATION_RE.sub(" ", p).replace("...", " ").replace("[]", " ")
        tokens = [t for t in p.split() if t != "final"]
        if tokens:
            names.append(tokens[-1])
    return names
