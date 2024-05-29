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


def test_app_counts_down():
    result = runner.invoke(app, ["countdown"])
    assert result.exit_code == 0
    assert "IMAP launch is " in result.stdout


def test_app_reports_version():
    result = runner.invoke(app, ["--version"])
    assert result.exit_code == 0
    assert "MAG CLI Version " in result.stdout
