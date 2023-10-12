import csv
import os
import re
from io import TextIOWrapper
from pathlib import Path
from typing import Optional

import typer

from science_mode import Constants, Mode, ModeConfig

app = typer.Typer()

report_file: TextIOWrapper
exit_code = 0
MAX_FINE = 0x00FFFFFF  # max 24bit number, the largest fine time value
TIME_TOLERANCE_BETWEEN_PACKETS = 0.005


@app.callback(
    invoke_without_command=True
)  # use callback because we want this to be the default command
def main(
    data_file: typer.FileText = typer.Argument(
        ...,
        help="file path to the csv file to be scanned e.g burst_data20230112-11h23.csv",
    ),
    report_file_path: Optional[Path] = typer.Option(
        "gap-report.txt",
        "--report",
        help="Path to a file to save a summary of the analysis performed",
    ),
    mode: Mode = typer.Option(
        Mode.auto,
        "--mode",
        "-m",
        case_sensitive=False,
        help="Which science mode MAG was in. Will try and guess from the file name if not specified",
    ),
    force: bool = typer.Option(
        False, "--force", "-f", help="Allow the overwrite of the report file"
    ),
):
    """
    Check MAG science CSV files for gaps in sequence counters and time stamps
    """
    global report_file
    global exit_code

    mode = validate_check_gap_args(data_file, report_file_path, mode, force)

    report_file = open(report_file_path, "a")
    reader = csv.DictReader(data_file)

    if mode != Mode.auto:
        mode_config = ModeConfig(mode)
    else:
        mode_config = ModeConfig(data_file.name)

    exit_code = 0
    line_count = 0
    packet_line_count = 0
    packet_counter = 0
    prev_seq = -1

    write_line(
        f"Checking {data_file.name} in mode {mode.value} ({mode_config.primary_rate}, {mode_config.secondary_rate}) @ {mode_config.seconds_between_packets}s)"
    )

    for row in reader:
        sequence = int(row["sequence"])
        pri_coarse = int(row["pri_coarse"])
        pri_fine = int(row["pri_fine"])
        sec_coarse = int(row["sec_coarse"])
        sec_fine = int(row["sec_fine"])

        packet_line_count += 1

        if line_count == 0 and packet_counter == 0:
            # we have our first packet
            packet_counter += 1

        # if the seq count has moved we assume this is the start of a new packet
        if line_count > 0 and sequence != prev_seq:
            packet_counter += 1

        packet_line_count = verify_sequence_counter(
            mode_config, line_count, packet_line_count, prev_seq, sequence
        )

        verify_timestamp(
            mode_config,
            line_count,
            packet_line_count,
            sequence,
            pri_coarse,
            pri_fine,
            "primary",
        )

        verify_timestamp(
            mode_config,
            line_count,
            packet_line_count,
            sequence,
            sec_coarse,
            sec_fine,
            "secondary",
        )

        verify_non_zero_vectors(row, line_count, sequence)

        line_count += 1
        prev_seq = sequence

    if exit_code != 0:
        write_line(
            f"Error - found bad science data! Checked {packet_counter} packet(s) across {line_count} rows of data."
        )
    else:
        write_line(
            f"Gap checker completed successfully. Checked {packet_counter} packet(s) across {line_count} rows of data."
        )

    report_file.close()
    if exit_code != 0:
        raise typer.Exit(code=exit_code)


def validate_check_gap_args(data_file, report_file_path, mode, force):
    if report_file_path.exists():
        if force:
            os.remove(report_file_path)
        else:
            print(f"{report_file_path} already exists - delete file or use --force")
            raise typer.Abort()

    if not data_file.name:
        print("data_file name is empty or invalid")
        raise typer.Abort()

    match = Constants.magScienceFileNamev2Regex.search(data_file.name)

    # files in v1 format will not match the regex so gues mode from file name
    if not match and mode == Mode.auto:
        if "burst" in data_file.name:
            mode = Mode.burst128
        elif "normal" in data_file.name:
            mode = Mode.normalE8

        if mode == Mode.auto:
            print(
                "unable to determine the mode - specify --mode NormalE8, --mode BurstE64. See --help for more info."
            )
            raise typer.Abort()

    return mode


def verify_sequence_counter(
    mode_config, line_count, packet_line_count, prev_seq, sequence
):
    if line_count > 0:
        line_id = f"line number {line_count+2}, sequence count: {sequence}, vector number {packet_line_count}"

        if sequence != prev_seq:
            # are we changing between packets after an unexpected number of vectors?
            if packet_line_count != mode_config.rows_per_packet + 1:
                write_error(
                    f"Expected {mode_config.rows_per_packet} vectors in packet but found {packet_line_count - 1}. {line_id}"
                )

            # start of a new packet
            packet_line_count = 1
            line_id = f"line number {line_count + 2}, sequence count: {sequence}, vector number {packet_line_count}"

        # check that the seqence numbers are the same within the packet
        if packet_line_count > 1 and sequence != prev_seq:
            write_error(f"Sequence numbers vary within packet! {line_id}")

        # sequence count must be seqential between packets
        if packet_line_count == 1 and sequence != ((prev_seq + 1) % 0x4000):
            write_error(f"Non sequential packet detected! {line_id}")

    return packet_line_count


def verify_timestamp(
    mode_config: ModeConfig,
    line_count: int,
    packet_line_count: int,
    sequence: int,
    coarse: int,
    fine: int,
    timestamp_type: str,
):
    line_id = f"line number {line_count + 2}, sequence count: {sequence}"

    prev_time = verify_timestamp.prev_time[timestamp_type]
    time: float = float(coarse) + (float(fine) / float(MAX_FINE))
    gap_between_packets = time - prev_time

    if line_count > 0 and packet_line_count == 1:
        lower_limit = (
            mode_config.seconds_between_packets - TIME_TOLERANCE_BETWEEN_PACKETS
        )
        upper_limit = (
            mode_config.seconds_between_packets + TIME_TOLERANCE_BETWEEN_PACKETS
        )

        if gap_between_packets < lower_limit:
            write_error(
                f"{timestamp_type} timestamp is {gap_between_packets:.5f}s after the previous packets (less than {lower_limit}s). {line_id}"
            )
        if gap_between_packets > upper_limit:
            write_error(
                f"{timestamp_type} timestamp is {gap_between_packets:.5f}s after the previous packets (more than {upper_limit}s). {line_id}"
            )

    elif line_count > 0 and packet_line_count > 1:
        if gap_between_packets > 0:
            write_error(
                f"{timestamp_type} timestamp should be the same as the previous line. {line_id}"
            )

    verify_timestamp.prev_time[timestamp_type] = time


verify_timestamp.prev_time: dict = {"primary": float(0), "secondary": float(0)}


def verify_non_zero_vectors(row: dict[str, str], line_count: int, sequence: int):
    line_id = f"line number {line_count + 2}, sequence count: {sequence}"
    x_pri = int(row["x_pri"])
    y_pri = int(row["y_pri"])
    z_pri = int(row["z_pri"])
    x_sec = int(row["x_sec"])
    y_sec = int(row["y_sec"])
    z_sec = int(row["z_sec"])

    if (
        x_pri == 0
        and y_pri == 0
        and z_pri == 0
        and x_sec == 0
        and y_sec == 0
        and z_sec == 0
    ):
        write_error(f"Vectors are all zero. {line_id}")


def write_line(message: str):
    print(message)
    global report_file
    report_file.write(message + "\n")


def write_error(message: str):
    global exit_code
    exit_code = 2
    write_line(message)


# only needed when this file is run as its own app
if __name__ == "__main__":
    app()
