#!/usr/bin/env python
"""Tests for `check-gaps`."""
# pylint: disable=redefined-outer-name

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
default_command_params = []
alt_command_params = []


# or use something like @pytest.mark.usefixtures("run_around_tests")
@pytest.fixture(autouse=True)
def run_around_tests():
    global testIndex
    global report_file
    global command_start_params
    global default_command_params
    global alt_command_params

    if report_file.exists():
        os.remove(report_file.absolute())

    testIndex += 1
    report_file = Path(f"sample-data/test{testIndex}_gap-report.txt")
    command_start_params = ["check-gap", "--report", report_file.absolute()]
    default_command_params = [
        "check-gap",
        "--report",
        report_file.absolute(),
        "--mode",
        "BurstE128",
        "sample-data/example.csv",
    ]
    alt_command_params = [
        "check-gap",
        "--report",
        report_file.absolute(),
        "-f",
        "-m",
        "normalE8",
        "sample-data/example.csv",
    ]

    if report_file.exists():
        os.remove(report_file.absolute())

    yield

    if report_file.exists():
        os.remove(report_file.absolute())

    json = Path("sample-data/gap_check_summary.json")
    if json.exists():
        os.remove(json.absolute())


def test_check_gap_creates_report():
    result = runner.invoke(app, default_command_params)

    print(result.stdout)
    assert result.exit_code == 0
    assert os.path.exists(report_file.absolute())


def test_check_gap_creates_report_name_based_on_a_suffix():
    expected_report_file = Path("sample-data/example_TEST_SUFFIX.txt")
    if expected_report_file.exists():
        os.remove(expected_report_file.absolute())

    result = runner.invoke(
        app,
        [
            "check-gap",
            "--report-suffix",
            "_TEST_SUFFIX.txt",
            "--mode",
            "BurstE128",
            "sample-data/example.csv",
        ],
    )

    print(result.stdout)
    assert result.exit_code == 0
    assert os.path.exists(expected_report_file.absolute())
    os.remove(expected_report_file.absolute())


def test_check_gap_with_no_report_does_not_create_report():
    runner.invoke(
        app,
        [
            "check-gap",
            "--no-report",
            "--mode",
            "BurstE128",
            "sample-data/example.csv",
        ],
    )

    assert not os.path.exists(report_file.absolute())


def test_check_gap_creates_error_report_when_too_many_row_per_packet():
    result = runner.invoke(app, alt_command_params)

    print(result.stdout)
    assert result.exit_code != 0
    assert (
        "Packet has too many rows. Expected 32. line number 34, sequence count: 0"
        in result.stdout
    )
    assert report_file.exists


def test_check_gap_will_not_overwrite_report():
    with open(report_file.absolute(), "w"):
        pass

    result = runner.invoke(app, default_command_params)

    assert result.exit_code == 1
    assert (
        "gap-report.txt already exists - specify a different report file name with --report or use --force to overwrite"
        in result.stdout
    )


def test_check_gap_will_overwrite_report_when_forced():
    with open(report_file.absolute(), "w"):
        pass

    result = runner.invoke(
        app,
        command_start_params + ["-f", "--mode", "BurstE128", "sample-data/example.csv"],
    )

    assert result.exit_code == 0
    assert report_file.exists


def test_check_gap_will_overwrite_error_report_when_forced():
    with open(report_file.absolute(), "w"):
        pass

    result = runner.invoke(app, alt_command_params)

    assert result.exit_code != 0
    assert report_file.exists


def test_check_gap_finds_invalid_sequence_counter():
    result = runner.invoke(
        app,
        command_start_params
        + [
            "--mode",
            "normalE8",
            "sample-data/normal_data20230112-11h23-bad-sequence.csv",
        ],
    )

    print(result.stdout)
    assert (
        "Non sequential packet detected! line number 34, sequence count: 99, vector number 1"
        in result.stdout
    )
    assert result.exit_code == 2


def test_check_gap_finds_invalid_sequence_counter_within_packet():
    result = runner.invoke(
        app,
        command_start_params
        + [
            "--mode",
            "normalE8",
            "sample-data/normal_data20230112-11h23-bad-sequence-within-packet.csv",
        ],
    )

    assert (
        "Non sequential packet detected! line number 4, sequence count: 99"
        in result.stdout
    )
    assert result.exit_code == 2


def test_check_gap_has_no_errors_for_valid_burst_data():
    result = runner.invoke(
        app, command_start_params + ["sample-data/burst_data20230112-11h23.csv"]
    )

    assert result.exit_code == 0
    assert (
        "Gap checker completed successfully. Checked 2 packet(s) across 512 rows of data."
        in result.stdout
    )


def test_check_gap_finds_invalid_if_in_wrong_mode():
    result = runner.invoke(
        app,
        command_start_params
        + ["--mode", "normalE8", "sample-data/burst_data20230112-11h23.csv"],
    )

    print(result.stdout)
    assert "Error - found bad science data! Checked 2 packet" in result.stdout
    assert result.exit_code == 2


def test_check_gap_finds_invalid_if_course_time_jumps_3_seconds_not_2():
    result = runner.invoke(
        app,
        command_start_params
        + ["sample-data/burst_data20230112-11h23-bad-time-course.csv"],
    )

    assert (
        "primary timestamp is 3.00000s after the previous packets (more than 2.005s). line number 258, sequence count: 1"
        in result.stdout
    )
    assert result.exit_code == 2


def test_check_gap_finds_invalid_if_course_time_is_under_threshold_in_secondary_timestamp():
    result = runner.invoke(
        app,
        command_start_params
        + ["sample-data/burst_data20230112-11h23-bad-time-fine.csv"],
    )

    assert (
        "secondary timestamp is 1.98998s after the previous packets (less than 1.995s). line number 258, sequence count: 1"
        in result.stdout
    )
    assert result.exit_code == 2


def test_check_gap_ignores_wrapping_sequence_counter():
    result = runner.invoke(
        app,
        command_start_params
        + ["--mode", "normalE8", "sample-data/example-seq-count-wraps.csv"],
    )

    assert "Non sequential packet detected" not in result.stdout


def test_check_gap_identifies_all_zero_vectors():
    result = runner.invoke(
        app,
        command_start_params
        + [
            "--mode",
            "normalE8",
            "sample-data/example-all-vectors-are-zero.csv",
        ],
    )

    print(result.stdout)
    assert (
        "Vectors are all zero for primary on line number 2, sequence count: 1"
        in result.stdout
    )
    assert (
        "Vectors are all zero for secondary on line number 2, sequence count: 1"
        in result.stdout
    )
    assert result.exit_code == 2


def test_check_gap_has_no_errors_for_valid_normal_data_in_filename_mode():
    result = runner.invoke(
        app,
        command_start_params
        + ["sample-data/MAGScience-normal-(2,2)-8s-20230922-11h50.csv"],
    )

    print(result.stdout)
    assert result.exit_code == 0
    assert (
        "Gap checker completed successfully. Checked 1 packet(s) across 16 rows of data."
        in result.stdout
    )


def test_check_gap_has_no_errors_for_valid_normal_data_at_1s_in_filename_mode():
    result = runner.invoke(
        app,
        command_start_params
        + ["sample-data/MAGScience-normal-(2,2)-1s-20230922-11h50.csv"],
    )

    print(result.stdout)
    assert result.exit_code == 0
    assert (
        "Gap checker completed successfully. Checked 2 packet(s) across 4 rows of data."
        in result.stdout
    )


def test_check_gap_finds_one_error_for_single_zero_vector_like_ramp_mode_in_valid_normal_data_at_1s():
    result = runner.invoke(
        app,
        command_start_params
        + [
            "sample-data/MAGScience-normal-(2,2)-1s-20230922-11h50-single-zero-vector.csv"
        ],
    )

    print(result.stdout)
    assert result.exit_code != 0
    assert (
        "Checking sample-data/MAGScience-normal-(2,2)-1s-20230922-11h50-single-zero-vector.csv in mode auto (2, 2) @ 1s\n"
        + "Vectors are all zero for primary on line number 3, sequence count: 0\n"
        + "Error - found bad science data! Checked 2 packet(s) across 4 rows of data."
        in result.stdout
    )


def test_check_gap_has_no_errors_for_valid_normal_data_with_lower_secondary_rate_in_filename_mode():
    result = runner.invoke(
        app,
        command_start_params
        + ["sample-data/MAGScience-normal-(2,1)-1s-20230922-11h50.csv"],
    )

    print(result.stdout)
    assert result.exit_code == 0
    assert (
        "Gap checker completed successfully. Checked 2 packet(s) across 4 rows of data."
        in result.stdout
    )


def test_check_gap_has_no_errors_for_valid_normal_data_with_lower_primary_rate_in_filename_mode():
    result = runner.invoke(
        app,
        command_start_params
        + ["sample-data/MAGScience-normal-(1,2)-1s-20230922-11h50.csv"],
    )

    print(result.stdout)
    assert result.exit_code == 0
    assert (
        "Gap checker completed successfully. Checked 2 packet(s) across 4 rows of data."
        in result.stdout
    )


def test_check_gap_finds_course_time_jump_2s_when_should_be_1s_for_normal_data_with_lower_secondary_rate_in_filename_mode():
    result = runner.invoke(
        app,
        command_start_params
        + [
            "sample-data/MAGScience-normal-(2,1)-1s-20230922-11h50-bad-time-course.csv",
        ],
    )

    print(result.stdout)
    assert result.exit_code != 0
    assert (
        "primary timestamp is 2.00000s after the previous packets (more than 1.005s). line number 4, sequence count: 1"
        in result.stdout
    )
    assert (
        "secondary timestamp is 2.00000s after the previous packets (more than 1.005s). line number 4, sequence count: 1"
        in result.stdout
    )
    assert result.exit_code == 2


def test_check_gap_finds_finds_incomplete_packets_in_both_sensors_for_normal_data_with_lower_secondary_rate_in_filename_mode():
    result = runner.invoke(
        app,
        command_start_params
        + [
            "sample-data/MAGScience-normal-(2,1)-4s-20230922-11h50-incomplete-packet.csv",
        ],
    )

    print(result.stdout)
    assert result.exit_code != 0
    assert (
        "A packet is incomplete, found 7 primary and 3 secondary vectors, expected 8 and 4. line number 2, sequence count: 0"
        in result.stdout
    )
    assert result.exit_code == 2


def test_check_gap_finds_finds_incomplete_packets_in_one_sensor_for_normal_data_with_lower_secondary_rate_in_filename_mode():
    result = runner.invoke(
        app,
        command_start_params
        + [
            "sample-data/MAGScience-normal-(2,1)-4s-20230922-11h50-incomplete-packet-v2.csv",
        ],
    )

    print(result.stdout)
    assert result.exit_code != 0
    assert (
        "A packet is incomplete, found 7 primary and 4 secondary vectors, expected 8 and 4. line number 2, sequence count: 0"
        in result.stdout
    )
    assert result.exit_code == 2


def test_check_gap_finds_finds_incomplete_last_packet_in_both_sensors_for_normal_data_with_lower_secondary_rate_in_filename_mode():
    result = runner.invoke(
        app,
        command_start_params
        + [
            "sample-data/MAGScience-normal-(2,1)-4s-20230922-11h50-incomplete-last-packet.csv",
        ],
    )

    print(result.stdout)
    assert result.exit_code != 0
    assert (
        "The last packet is incomplete, found 7 primary and 3 secondary vectors, expected 8 and 4. line number 10, sequence count: 1"
        in result.stdout
    )
    assert result.exit_code == 2


def test_check_gap_find_additional_secondary_sensor_data_with_lower_secondary_rate_in_filename_mode():
    result = runner.invoke(
        app,
        command_start_params
        + [
            "sample-data/MAGScience-normal-(2,1)-1s-20230922-11h50-extra-secondary-data.csv",
        ],
    )

    print(result.stdout)
    assert result.exit_code != 0
    assert (
        "Vectors are non-empty for secondary on line number 5, sequence count: 1"
        in result.stdout
    )
    assert "Checked 2 packet(s) across 4 rows of data" in result.stdout
    assert (
        "Checking sample-data/MAGScience-normal-(2,1)-1s-20230922-11h50-extra-secondary-data.csv in mode auto (2, 1) @ 1s"
        in result.stdout
    )


def test_check_gap_generates_correct_summary_file():
    result = runner.invoke(
        app,
        command_start_params
        + [
            "sample-data/MAGScience-normal-(2,1)-1s-20230922-11h50-extra-secondary-data.csv",
        ],
    )
    with open("sample-data/gap_check_summary.json", "r") as json_file:
        json_object = json.load(json_file)

    print(result.stdout)
    assert result.exit_code != 0
    assert json_object["Gap check result"] == "FAILED"
    assert json_object["Corrupt science packet errors"] == 1
