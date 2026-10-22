import os

def pytest_configure() -> None:
    os.environ.setdefault("MODEL_MODE", "fixture")
