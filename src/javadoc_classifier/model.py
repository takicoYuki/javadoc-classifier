"""解析結果を表すデータクラス。"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Kind(str, Enum):
    """Javadoc が付く宣言の種類。"""

    CLASS = "class"
    INTERFACE = "interface"
    ENUM = "enum"
    RECORD = "record"
    CONSTRUCTOR = "constructor"
    METHOD = "method"
    FIELD = "field"


class Severity(str, Enum):
    ERROR = "error"
    WARNING = "warning"


@dataclass(frozen=True)
class Tag:
    """ブロックタグ（@param x 説明 など）1つ分。"""

    name: str  # "param", "return" など（@ は含まない）
    argument: str  # @param / @throws の対象名。それ以外は空文字
    text: str


@dataclass(frozen=True)
class Javadoc:
    description: str
    tags: tuple[Tag, ...] = ()

    def tags_named(self, *names: str) -> list[Tag]:
        return [t for t in self.tags if t.name in names]


@dataclass(frozen=True)
class Declaration:
    """Javadoc の対象になるクラス・メソッドなどの宣言。"""

    kind: Kind
    name: str
    line: int
    modifiers: frozenset[str] = frozenset()
    params: tuple[str, ...] = ()
    return_type: str | None = None  # メソッド以外は None
    throws: tuple[str, ...] = ()
    javadoc: Javadoc | None = None
    annotations: frozenset[str] = frozenset()

    @property
    def is_api(self) -> bool:
        """外部から使われる宣言か（public / protected）"""
        return bool({"public", "protected"} & self.modifiers)


@dataclass(frozen=True)
class Issue:
    """チェックで見つかった問題。"""

    file: str
    line: int
    declaration: str
    rule: str
    severity: Severity
    message: str


@dataclass
class FileReport:
    file: str
    declarations: list[Declaration] = field(default_factory=list)
    issues: list[Issue] = field(default_factory=list)
