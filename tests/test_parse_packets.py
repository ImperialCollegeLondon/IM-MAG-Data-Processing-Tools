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
output_file_glob = Path("uninitialised.txt")
command_start_params = []
SAMPLE_DATA_FOLDER = "sample-data/l0_to_l1"


# or use something like @pytest.mark.usefixtures("run_around_tests")
@pytest.fixture(autouse=True)
def run_around_tests():
    global testIndex
    global output_file_glob
    global command_start_params

    testIndex += 1

    output_file_glob = (
        f"{SAMPLE_DATA_FOLDER}/test-output-{testIndex}/MAGScience-normal-(2,2)-8s-*.csv"
    )

    output_folder = f"{SAMPLE_DATA_FOLDER}/test-output-{testIndex}"

    command_start_params = [
        "parse-packets",
        "-o",
        output_folder,
        f"{SAMPLE_DATA_FOLDER}/mag-l0-l1a-t003-in.bin",
    ]

    if os.path.exists(output_folder):
        for f in os.listdir(output_folder):
            os.remove(os.path.join(output_folder, f))
        os.removedirs(output_folder)

    os.makedirs(output_folder, exist_ok=True)

    yield

    if os.path.exists(output_folder):
        for f in os.listdir(output_folder):
            os.remove(os.path.join(output_folder, f))
        os.removedirs(output_folder)


def test_parse_packets_creates_report():
    global output_file_glob
    result = runner.invoke(app, command_start_params)

    print(result.output)
    assert result.exit_code == 0
    assert f"Processing {SAMPLE_DATA_FOLDER}/mag-l0-l1a-t003-in.bin" in result.stdout
    assert (
        "Extracted data from 1 packets in sample-data/l0_to_l1/mag-l0-l1a-t003-in.bin to test-output-1 (150 bytes processed in 0s). Ignored 0 packets."
        in result.stdout
    )

    files = []
    for output_file in glob.glob(output_file_glob):
        files.append(output_file)

    assert len(files) == 1
    assert files[0].endswith("MAGScience-normal-(2,2)-8s-20250204-14h56m08s.csv")


def test_parse_packets_results_matched_expected_for_one_packet():
    global output_file_glob

    result = runner.invoke(app, command_start_params)

    print(result.output)
    assert result.exit_code == 0

    expected_csv_data = f"{SAMPLE_DATA_FOLDER}/mag-l0-l1a-t003-out.csv"
    print(output_file_glob)
    actual_csv_data = glob.glob(output_file_glob).pop()

    with open(actual_csv_data, "r") as actual, open(expected_csv_data, "r") as expected:
        actual_lines = actual.readlines()
        expected_lines = expected.readlines()

        assert len(actual_lines) == len(expected_lines)

        for line1, line2 in zip(actual_lines, expected_lines):
            assert line1 == line2


def test_parse_packets_errors_when_zero_packets():
    global output_file_glob

    should_fail_command_start_params = (
        command_start_params[0:3] + ["--apid", "0x999"] + command_start_params[3:]
    )
    result = runner.invoke(app, should_fail_command_start_params)

    print(result.output)
    assert result.exit_code != 0
    assert "Zero packets parsed" in result.output
