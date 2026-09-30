from pathlib import Path

from cavat.main import app
from cavat.modules.content.lesson_package import load_lesson_package, validate_package
from fastapi.testclient import TestClient

REPO = Path(__file__).resolve().parents[3]
LESSON = REPO / "docs/pedagogy/math-g5/so-sanh-so-thap-phan/lesson.yaml"


def test_health():
    assert TestClient(app).get("/health").json()["status"] == "ok"


def test_lesson_package_is_valid():
    pkg = load_lesson_package(LESSON)
    assert validate_package(pkg) == []
