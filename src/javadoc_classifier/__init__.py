"""Java ソースの Javadoc を分類・集計し、書き漏れを見つけるツール。"""

__version__ = "1.0.0"

from .analyzer import Analyzer, ProjectReport  # noqa: E402
from .classifier import Category, classify, register_tag  # noqa: E402
from .parser import parse_java, parse_javadoc  # noqa: E402

__all__ = ["Analyzer", "ProjectReport", "Category", "classify", "register_tag", "parse_java", "parse_javadoc"]
