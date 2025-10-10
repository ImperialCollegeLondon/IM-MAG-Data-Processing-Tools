#!/usr/bin/env python
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
output_file = Path("output.bin")
command_start_params = []
SAMPLE_DATA_FOLDER = "sample-data"


# or use something like @pytest.mark.usefixtures("run_around_tests")
@pytest.fixture(autouse=True)
def run_around_tests():
    global testIndex
    global output_file
    global command_start_params
    global alt_command_params

    if output_file.exists():
        os.remove(output_file.absolute())

    testIndex += 1
    output_file = Path(f"{SAMPLE_DATA_FOLDER}/test{testIndex}_output.bin")
    command_start_params = [
        "filter-packets",
        "--all",
        "--output-file",
        output_file.absolute(),
        f"{SAMPLE_DATA_FOLDER}/mag_l0_test_data.pkts",
    ]

    removeGeneratedFiles()

    yield

    removeGeneratedFiles()


def removeGeneratedFiles():
    if output_file.exists():
        os.remove(output_file.absolute())


def test_filter_packets_creates_output():
    result = runner.invoke(app, command_start_params)

    print(result.stdout)
    assert result.exit_code == 0
    assert os.path.exists(output_file.absolute())
    assert "Processing sample-data/mag_l0_test_data.pkts" in result.stdout
    assert (
        "Saved 36 packets from sample-data/mag_l0_test_data.pkts to test1_output.bin (38608 bytes processed, 38608 bytes written)"
        in result.stdout
    )
