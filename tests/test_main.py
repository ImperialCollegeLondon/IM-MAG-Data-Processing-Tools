#!/usr/bin/env python
"""Tests for `app` package."""
# pylint: disable=redefined-outer-name


import pytest
from typer.testing import CliRunner

from src.main import app

runner = CliRunner()

@pytest.fixture
def response():
    """Sample pytest fixture.

    See more at: http://doc.pytest.org/en/latest/fixture.html
    """

def test_app_says_hello():
    result = runner.invoke(app, ["hello", "Camila"])
    assert result.exit_code == 0
    assert "Hello Camila" in result.stdout

def test_app_says_goodbye():
    name = "Camila"
    result = runner.invoke(app, ["goodbye", name, "--formal"])
    assert result.exit_code == 0
    assert f"Goodbye Ms. {name}. Have a good day." in result.stdout
