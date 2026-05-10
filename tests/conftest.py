import os


def pytest_configure():
    os.environ.setdefault("SHELL_ENABLED", "true")
    os.environ.setdefault("GIT_ENABLED", "true")
