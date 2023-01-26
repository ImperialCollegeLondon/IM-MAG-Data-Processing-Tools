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

def test_check_gap_creates_report():
    if(report_file.exists()):
        os.remove(report_file.absolute())

    result = runner.invoke(app, ["check-gap", "sample-data/example.csv"])
    assert result.exit_code == 0
    assert report_file.exists

def test_check_gap_will_not_overwrite_report():
    if(report_file.exists()):
        os.remove(report_file.absolute())

    # run twice to create file
    result = runner.invoke(app, ["check-gap", "sample-data/example.csv"])
    result = runner.invoke(app, ["check-gap", "sample-data/example.csv"])

    assert result.exit_code == 1
    assert "gap-report.txt already exists - delete file or use --force" in result.stdout
