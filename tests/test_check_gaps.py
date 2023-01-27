#!/usr/bin/env python
"""Tests for `check-gaps`."""
# pylint: disable=redefined-outer-name

import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.main import app

runner = CliRunner()
report_file = Path('gap-report.txt')
default_command_params = ["check-gap", "--mode", "BurstE128", "sample-data/example.csv"]
alt_command_params = ["check-gap", "-f", "-m", "normalE8", "sample-data/example.csv"]

@pytest.fixture(autouse=True)
def run_around_tests():
    if(report_file.exists()):
        os.remove(report_file.absolute())

    yield

    if(report_file.exists()):
        os.remove(report_file.absolute())

#@pytest.mark.usefixtures("run_around_tests")
def test_check_gap_creates_report():

    result = runner.invoke(app, default_command_params)
    assert result.exit_code == 0
    assert report_file.exists

def test_check_gap_creates_report_with_alternative_arguments():

    result = runner.invoke(app, alt_command_params)
    assert result.exit_code == 0
    assert report_file.exists

def test_check_gap_will_not_overwrite_report():

    with open(report_file.absolute(), 'w'):
        pass

    result = runner.invoke(app, default_command_params)

    assert result.exit_code == 1
    assert "gap-report.txt already exists - delete file or use --force" in result.stdout
