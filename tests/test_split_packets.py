#!/usr/bin/env python
"""Tests for `check-gaps`."""
# pylint: disable=redefined-outer-name

import glob
import json
import os
from pathlib import Path

import pytest
from typer.testing import CliRunner

from src.main import app

runner = CliRunner()
testIndex = 0
report_file = Path("uninitialised.txt")
command_start_params = []
SAMPLE_DATA_FOLDER = "sample-data"


# or use something like @pytest.mark.usefixtures("run_around_tests")
@pytest.fixture(autouse=True)
def run_around_tests():
    global testIndex
    global report_file
    global command_start_params
    global alt_command_params

    if report_file.exists():
        os.remove(report_file.absolute())

    testIndex += 1
    report_file = Path(f"{SAMPLE_DATA_FOLDER}/test{testIndex}_packet-report.csv")
    command_start_params = [
        "split-packets",
        "--all",
        "--report",
        report_file.absolute(),
        f"{SAMPLE_DATA_FOLDER}/mag_l0_test_data.pkts",
    ]

    removeGeneratedFiles()

    yield

    removeGeneratedFiles()


def removeGeneratedFiles():
    if report_file.exists():
        os.remove(report_file.absolute())

    for bin in glob.glob(f"{SAMPLE_DATA_FOLDER}/1052/*.bin"):
        os.remove(bin)

    for bin in glob.glob(f"{SAMPLE_DATA_FOLDER}/1068/*.bin"):
        os.remove(bin)

    for csv in glob.glob(f"{SAMPLE_DATA_FOLDER}/*packet-report*.csv"):
        os.remove(csv)


def test_split_packets_creates_report():
    result = runner.invoke(app, command_start_params)

    print(result.stdout)
    assert result.exit_code == 0
    assert os.path.exists(report_file.absolute())
    assert "Processing sample-data/mag_l0_test_data.pkts" in result.stdout
    assert (
        "Saved 36 packets from sample-data/mag_l0_test_data.pkts to sample-data (38608 bytes)"
        in result.stdout
    )


def test_split_packets_creates_one_file_per_packet():
    runner.invoke(app, command_start_params)

    assert len(glob.glob(f"{SAMPLE_DATA_FOLDER}/1068/*.bin")) == 19
    assert len(glob.glob(f"{SAMPLE_DATA_FOLDER}/1052/*.bin")) == 17
