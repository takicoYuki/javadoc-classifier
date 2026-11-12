from pathlib import Path

import pytest

FIXTURES = Path(__file__).parent / "fixtures"


@pytest.fixture
def order_service_path() -> Path:
    return FIXTURES / "OrderService.java"


@pytest.fixture
def order_service(order_service_path) -> str:
    return order_service_path.read_text(encoding="utf-8")
