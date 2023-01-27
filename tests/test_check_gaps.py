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

def test_check_gap_will_overwrite_report_when_forced():

    with open(report_file.absolute(), 'w'):
        pass

    result = runner.invoke(app, alt_command_params)

    assert result.exit_code == 0

def test_check_gap_finds_invalid_seqence_counter():

    result = runner.invoke(app, ["check-gap", "--mode", "normalE8", "sample-data/normal_data20230112-11h23-bad-sequence.csv"])

    assert "Non sequential packet detected! line number 34, sequence count: 99, vector number 1" in result.stdout
    assert result.exit_code == 2

def test_check_gap_finds_invalid_seqence_counter_within_packet():

    result = runner.invoke(app, ["check-gap", "--mode", "normalE8", "sample-data/normal_data20230112-11h23-bad-sequence-within-packet.csv"])

    assert "Non sequential packet detected! line number 4, sequence count: 99" in result.stdout
    assert result.exit_code == 2

def test_check_gap_has_no_errors_for_valid_burst_data():

    result = runner.invoke(app, ["check-gap", "sample-data/burst_data20230112-11h23.csv"])

    assert result.exit_code == 0
    assert "Gap checker complete successfully. Checked 1 packet(s) across 513 lines." in result.stdout

def test_check_gap_finds_invalid_if_in_wrong_mode():

    result = runner.invoke(app, ["check-gap", "--mode", "normalE8", "sample-data/burst_data20230112-11h23.csv"])

    assert "Expected 32 vectors in packet but found 256" in result.stdout
    assert "Error - found bad science data! Checked 1 packet" in result.stdout
    assert result.exit_code == 2
