import csv
import os
from io import TextIOWrapper
from pathlib import Path
from typing import Optional

import typer

from science_mode import Mode, ModeConfig

app = typer.Typer()

report_file: TextIOWrapper
exit_code = 0
MAX_FINE = 0x00FFFFFF  # max 24bit number, the largest fine time value
TIME_TOLERANCE_BETWEEN_PACKETS = 0.001


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
        Mode.unknown,
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
    mode_config = ModeConfig(mode)
    exit_code = 0
    line_count = 0
    packet_line_count = 0
    packet_counter = 0
    prev_seq = -1

    write_line(f"Checking {data_file.name} in mode {mode.value}")

    for row in reader:
        sequence = int(row["sequence"])
        pri_coarse = int(row["pri_coarse"])
        pri_fine = int(row["pri_fine"])
        sec_coarse = int(row["sec_coarse"])
        sec_fine = int(row["sec_fine"])

        packet_line_count += 1

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

        line_count += 1
        prev_seq = sequence

    if exit_code != 0:
        write_line(
            f"Error - found bad science data! Checked {packet_counter} packet(s) across {line_count+1} lines."
        )
    else:
        write_line(
            f"Gap checker complete successfully. Checked {packet_counter} packet(s) across {line_count+1} lines."
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

    if "burst" in data_file.name and mode == Mode.unknown:
        mode = Mode.burst128
    elif "normal" in data_file.name and mode == Mode.unknown:
        mode = Mode.normal

    if mode == Mode.unknown:
        print(
            "unable to determine the mode - specify --mode NormalE8, --mode BurstE64. See --help for more info."
        )
        raise typer.Abort()
    return mode


def verify_sequence_counter(
    mode_config, line_count, packet_line_count, prev_seq, sequence
):
    if line_count > 0:
        line_id = f"line number { line_count+2 }, sequence count: { sequence }, vector number {packet_line_count}"

        if sequence != prev_seq:
            # are we changing between packets after an unexpected number of vectors?
            if packet_line_count != mode_config.vectors_per_packet + 1:
                write_error(
                    f"Expected {mode_config.vectors_per_packet} vectors in packet but found {packet_line_count-1}. {line_id}"
                )

            # start of a new packet
            packet_line_count = 1
            line_id = f"line number { line_count+2 }, sequence count: { sequence }, vector number {packet_line_count}"

        # check that the seqence numbers are the same within the packet
        if packet_line_count > 1 and sequence != prev_seq:
            write_error(f"Sequence numbers vary within packet! {line_id}")

        # sequence count must be seqential between packets
        if packet_line_count == 1 and sequence != (prev_seq + 1):
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
    line_id = f"line number { line_count+2 }, sequence count: { sequence }"

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
