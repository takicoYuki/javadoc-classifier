"""Javadoc の中身を種類ごとに分類する。

タグ名と分類の対応は CATEGORY_REGISTRY に登録する（Registry / Factory パターン）。
独自タグを分類したいときは register_tag() を呼ぶだけでよく、分類処理そのものは変更しない。
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from enum import Enum

from .model import Declaration, Javadoc


class Category(str, Enum):
    SUMMARY = "概要"
    DETAIL = "詳細説明"
    PARAMETER = "引数"
    RETURN = "戻り値"
    EXCEPTION = "例外"
    DEPRECATION = "非推奨"
    REFERENCE = "参照"
    META = "作成者・版"
    OTHER = "その他"


CATEGORY_REGISTRY: dict[str, Category] = {
    "param": Category.PARAMETER,
    "return": Category.RETURN,
    "throws": Category.EXCEPTION,
    "exception": Category.EXCEPTION,
    "deprecated": Category.DEPRECATION,
    "see": Category.REFERENCE,
    "author": Category.META,
    "version": Category.META,
    "since": Category.META,
}

_INLINE_TAG_RE = re.compile(r"\{@(\w+)\s*([^}]*)\}")
_SENTENCE_END_RE = re.compile(r"(?<=[。．.!?！？])\s*")


def register_tag(tag_name: str, category: Category) -> None:
    """独自タグ（@apiNote など）の分類を登録する。"""
    CATEGORY_REGISTRY[tag_name] = category


def category_of(tag_name: str) -> Category:
    return CATEGORY_REGISTRY.get(tag_name, Category.OTHER)


@dataclass(frozen=True)
class ClassifiedItem:
    category: Category
    text: str
    target: str = ""  # 引数名・例外名など


@dataclass
class ClassifiedJavadoc:
    items: list[ClassifiedItem] = field(default_factory=list)
    inline_tags: Counter = field(default_factory=Counter)

    def of(self, category: Category) -> list[ClassifiedItem]:
        return [i for i in self.items if i.category == category]


def split_summary(description: str) -> tuple[str, str]:
    """説明文を「最初の 1 文（概要）」と「残り（詳細）」に分ける。Javadoc の仕様と同じ考え方。"""
    text = re.sub(r"<[^>]+>", " ", description)  # <p> などの HTML タグを除く
    text = " ".join(text.split())
    if not text:
        return "", ""
    parts = _SENTENCE_END_RE.split(text, maxsplit=1)
    summary = parts[0].strip()
    detail = parts[1].strip() if len(parts) > 1 else ""
    return summary, detail


def classify(javadoc: Javadoc) -> ClassifiedJavadoc:
    result = ClassifiedJavadoc()
    summary, detail = split_summary(javadoc.description)
    if summary:
        result.items.append(ClassifiedItem(Category.SUMMARY, summary))
    if detail:
        result.items.append(ClassifiedItem(Category.DETAIL, detail))

    for tag in javadoc.tags:
        result.items.append(ClassifiedItem(category_of(tag.name), tag.text, tag.argument))

    all_text = " ".join([javadoc.description] + [t.text for t in javadoc.tags])
    for m in _INLINE_TAG_RE.finditer(all_text):
        result.inline_tags[m.group(1)] += 1
        if m.group(1) in ("link", "linkplain"):
            result.items.append(ClassifiedItem(Category.REFERENCE, m.group(2).strip()))
    return result


@dataclass
class Statistics:
    """ファイルやプロジェクト全体の集計。"""

    api_declarations: int = 0
    documented: int = 0
    categories: Counter = field(default_factory=Counter)
    inline_tags: Counter = field(default_factory=Counter)

    @property
    def coverage(self) -> float:
        return 100.0 if self.api_declarations == 0 else self.documented * 100 / self.api_declarations

    def add(self, decl: Declaration) -> None:
        if decl.is_api and "Override" not in decl.annotations:
            self.api_declarations += 1
            if decl.javadoc is not None:
                self.documented += 1
        if decl.javadoc is not None:
            classified = classify(decl.javadoc)
            self.categories.update(item.category for item in classified.items)
            self.inline_tags.update(classified.inline_tags)

    def merge(self, other: Statistics) -> None:
        self.api_declarations += other.api_declarations
        self.documented += other.documented
        self.categories.update(other.categories)
        self.inline_tags.update(other.inline_tags)
