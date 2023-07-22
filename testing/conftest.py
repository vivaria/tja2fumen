import pytest


def pytest_addoption(parser):
    parser.addoption("--entry-point", action="store", default="python-api")


@pytest.fixture
def entry_point(request):
    return request.config.getoption("--entry-point")
