import csv
import glob
import json
import os
import re
import sys
from datetime import datetime, timedelta
from io import TextIOWrapper
from pathlib import Path
from typing import Optional

import typer
from click.exceptions import Exit

from constants import CONSTANTS
from science_mode import Mode, ModeConfig

app = typer.Typer()

report_file: TextIOWrapper
no_report_flag = False
exit_code = 0
MIN_FINE = 0
MAX_FINE = 0x0000FFFF  # max 16bit number, the largest fine time value in a packet. Fine time is 24 bits but we only telemeter the top 16


@app.callback(
    invoke_without_command=True
)  # use callback because we want this to be the default command
def main(
    ctx: typer.Context,
    data_file: Path = typer.Argument(
        ...,
        help="file path to the csv file to be scanned e.g burst_data20230112-11h23.csv or folder containing csv files",
    ),
    report_file_path: Optional[Path] = typer.Option(
        "",
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
    no_report: bool = typer.Option(
        False, "--no-report", help="Disable the report file"
    ),
    report_file_suffix: str = typer.Option(
        ".gap_report.txt",
        "--report-suffix",
        help="Suffix used to identify report file names and automatically appended to data file names when generating report names automatically",
    ),
    summarise_only: bool = typer.Option(
        False,
        "--summarise",
        help="Skip the gap checking and just generate the summary files",
    ),
    tolerance: float = typer.Option(
        -1,
        "--tolerance",
        help="The tolerance in seconds for the time between packets. Defaults to 7.5% of the vector cadence in science mode, and 0.05s for I-ALiRT mode.",
    ),
):
    """
    Check MAG science CSV files for gaps in sequence counters and time stamps
    """
    global report_file
    global no_report_flag
    global exit_code

    report_file = None
    no_report_flag = False
    exit_code = 0
    globPath = None

    if data_file.is_dir():
        globPath = os.path.join(data_file, "*.csv")
    elif "*" in str(data_file) or "?" in str(data_file):
        globPath = str(data_file)

    if globPath:
        check_gaps_multi_file(
            globPath,
            ctx,
            report_file_path,
            mode,
            force,
            no_report,
            report_file_suffix,
            summarise_only,
            tolerance,
        )
        return

    report_file_path, report_file_suffix = prepare_report_file(
        data_file, report_file_path, no_report, report_file_suffix
    )

    mode = validate_check_gap_args(
        data_file, report_file_path, mode, force, no_report, summarise_only
    )

    if not summarise_only:
        if not no_report:
            report_file = open(report_file_path, "a")
        else:
            no_report_flag = no_report

        if mode != Mode.auto:
            mode_config = ModeConfig(mode, tolerance)
        else:
            mode_config = ModeConfig(data_file, tolerance)

        check_gaps_in_one_file(
            data_file, report_file_path, mode_config, no_report, tolerance
        )

    if not no_report:
        # generate a nice summary of all the errors by scanning all gap reports in the folder
        folder = data_file.parent
        generate_summary(folder, f"*{report_file_suffix}")

    if exit_code != 0:
        raise typer.Exit(code=exit_code)


def check_gaps_in_one_file(
    data_file: Path,
    report_file_path,
    mode_config: ModeConfig,
    no_report: bool,
    tolerance: float,
):
    global exit_code

    with open(data_file) as f:
        reader = csv.DictReader(f)

        line_count = 0
        packet_start_line_count = 0
        packet_line_count = 0
        packet_counter = 0
        prev_seq = -1
        primary_vector_count = 0
        secondary_vector_count = 0

        write_line(
            f"Checking {data_file} in mode {mode_config.mode.value} ({mode_config.primary_rate}, {mode_config.secondary_rate}) @ {mode_config.seconds_between_packets}s with tolerence {mode_config.tolerance}s"
        )

        for row in reader:
            packet_line_count += 1
            line_count += 1

            sequence = get_integer(line_count, row, "sequence")

            if line_count == 1 and packet_counter == 0:
                # we have our first packet
                packet_counter += 1
                packet_start_line_count += 1

                # if the seq count has moved we assume this is the start of a new packet
            if line_count > 1 and sequence != prev_seq:
                # check the previous packet has a complete set of vectors
                verify_packet_completeness(
                    primary_vector_count,
                    secondary_vector_count,
                    mode_config,
                    prev_seq,
                    packet_start_line_count,
                    False,
                )
                packet_counter += 1
                packet_start_line_count = line_count
                primary_vector_count = 0
                secondary_vector_count = 0

            packet_line_count = verify_sequence_counter(
                mode_config, line_count, packet_line_count, prev_seq, sequence
            )

            hasPrimary = packet_line_count <= mode_config.primary_vectors_per_packet
            hasSeconday = packet_line_count <= mode_config.secondary_vectors_per_packet

            if packet_line_count > mode_config.rows_per_packet:
                if packet_line_count == mode_config.rows_per_packet + 1:
                    write_error(
                        f"{CONSTANTS.TOO_MANY_ROWS}. Expected {mode_config.rows_per_packet}. line number {line_count + 1}, sequence count: {sequence}"
                    )
            else:
                if hasPrimary:
                    pri_coarse = get_integer(line_count, row, "pri_coarse")
                    pri_fine = get_integer(line_count, row, "pri_fine")

                    verify_timestamp(
                        mode_config,
                        line_count,
                        packet_line_count,
                        sequence,
                        pri_coarse,
                        pri_fine,
                        "primary",
                    )
                    if is_non_empty_vector(row, line_count, sequence, "primary"):
                        primary_vector_count += 1
                        verify_non_zero_vectors(row, line_count, sequence, "primary")

                else:
                    verify_empty_vectors(row, line_count, sequence, "primary")

                if hasSeconday:
                    sec_coarse = get_integer(line_count, row, "sec_coarse")
                    sec_fine = get_integer(line_count, row, "sec_fine")

                    verify_timestamp(
                        mode_config,
                        line_count,
                        packet_line_count,
                        sequence,
                        sec_coarse,
                        sec_fine,
                        "secondary",
                    )

                    if is_non_empty_vector(row, line_count, sequence, "secondary"):
                        secondary_vector_count += 1
                        verify_non_zero_vectors(row, line_count, sequence, "secondary")

                else:
                    verify_empty_vectors(row, line_count, sequence, "secondary")

            prev_seq = sequence

        # check the last packet has a complete set of vectors
    complete_gap_check(
        report_file_path,
        no_report,
        mode_config,
        line_count,
        packet_start_line_count,
        packet_counter,
        prev_seq,
        primary_vector_count,
        secondary_vector_count,
    )


def prepare_report_file(data_file, report_file_path, no_report, report_file_suffix):
    if not no_report and not report_file_path.name:
        report_file_path = Path(
            f"{data_file.with_suffix('').resolve()}{report_file_suffix}"
        )
    # if the reportname has been specified and no suffix has been specified then use the report file name as the suffix
    elif report_file_suffix == ".gap_report.txt":
        report_file_suffix = report_file_path.name
    return report_file_path, report_file_suffix


def check_gaps_multi_file(
    globPath,
    ctx,
    report_file_path,
    mode,
    force,
    no_report,
    report_file_suffix,
    summarise_only,
    tolerance,
):
    multifile_exit_code = 0
    files = 0
    for filename in glob.glob(globPath):
        files += 1
        try:
            result = ctx.invoke(
                main,
                data_file=Path(filename),
                ctx=ctx,
                report_file_path=report_file_path,
                mode=mode,
                force=force,
                no_report=no_report,
                report_file_suffix=report_file_suffix,
                summarise_only=summarise_only,
                tolerance=tolerance,
            )
            if result and result.exit_code != 0:
                multifile_exit_code = result.exit_code
        except Exit as exit:
            multifile_exit_code = exit.exit_code
        except Exception as e:
            print(f"Error processing {filename}: {e}", file=sys.stderr)
            if multifile_exit_code == 0:
                multifile_exit_code = 1

        print("")  # new line between files

    if files == 0:
        multifile_exit_code = 1

    print(f"Processed {files} files matching {globPath}")
    raise typer.Exit(code=multifile_exit_code)


def complete_gap_check(
    report_file_path,
    no_report,
    mode_config,
    line_count,
    packet_start_line_count,
    packet_counter,
    prev_seq,
    primary_vector_count,
    secondary_vector_count,
):
    verify_packet_completeness(
        primary_vector_count,
        secondary_vector_count,
        mode_config,
        prev_seq,
        packet_start_line_count,
        True,
    )

    if exit_code != 0:
        write_line(
            f"Error - found bad science data! Checked {packet_counter} packet(s) across {line_count} rows of data."
        )
    else:
        write_line(
            f"Gap checker completed successfully. Checked {packet_counter} packet(s) across {line_count} rows of data."
        )

    if report_file:
        report_file.close()

    if not no_report:
        print(f"Report saved to {report_file_path}")


def get_integer(line_count, row, field):
    value = row[field]
    if not (value.strip("-").isnumeric()):
        msg = CONSTANTS.EXPECTED_NUMERIC_FORMAT + " {field}, found '{value}'"
        write_error(msg.format(line_count=line_count + 1, field=field, value=value))
        value = 0
    else:
        value = int(value)
    return value


def validate_check_gap_args(
    data_file: Path, report_file_path, mode, force, no_report, summarise_only
):
    if not data_file.exists():
        print(f"{data_file} does not exist")
        raise typer.Abort()

    if not (no_report) and report_file_path.exists() and not summarise_only:
        if force:
            os.remove(report_file_path)
        else:
            print(
                f"{report_file_path} already exists - specify a different report file name with --report or use --force to overwrite"
            )
            raise typer.Abort()

    if not data_file.name:
        print("data_file name is empty or invalid")
        raise typer.Abort()

    match = CONSTANTS.MAG_SCIENCE_FILE_NAMES_V2_REGEX.search(data_file.name)

    # files in v1 format will not match the regex so guess mode from file name
    if not match and mode == Mode.auto:
        if "burst" in data_file.name:
            mode = Mode.burst128
        elif "normal" in data_file.name:
            mode = Mode.normalE8
        elif "IALiRT" in data_file.name:
            mode = Mode.i_alirt

        if mode == Mode.auto:
            print(
                "unable to determine the mode - specify --mode NormalE8, --mode BurstE64. See --help for more info."
            )
            raise typer.Abort()

    return mode


def verify_sequence_counter(
    mode_config: ModeConfig, line_count, packet_line_count, prev_seq, sequence
):
    if line_count > 1:
        line_id = f"line number {line_count + 1}, sequence count: {sequence}, vector number {packet_line_count}"

        if sequence != prev_seq:
            # start of a new packet
            packet_line_count = 1
            line_id = f"line number {line_count + 1}, sequence count: {sequence}, vector number {packet_line_count}"

        # check that the seqence numbers are the same within the packet
        if packet_line_count > 1 and sequence != prev_seq:
            write_error(f"{CONSTANTS.SEQUENCE_NUMBERS_VARY}! {line_id}")

        # sequence count must be seqential between packets
        if packet_line_count == 1 and sequence != (
            (prev_seq + mode_config.sequence_counter_increment) % 0x4000
        ):
            write_error(f"{CONSTANTS.NONE_SEQUENTIAL} detected! {line_id}")

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
    sclk = (CONSTANTS.IMAP_EPOCH + timedelta(seconds=coarse)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )
    line_id = f"line number {line_count + 1}, sequence count: {sequence}, SCLK: {sclk}"

    if fine < MIN_FINE or fine > MAX_FINE:
        write_error(
            f"{timestamp_type} {CONSTANTS.TIMESTAMP} fine time {fine} is out of range ({MIN_FINE}-{MAX_FINE}). {line_id}"
        )
        fine = 0

    prev_time = verify_timestamp.prev_time[timestamp_type]
    time: float = float(coarse) + (float(fine) / float(MAX_FINE))
    gap_between_packets = time - prev_time

    if line_count > 1 and packet_line_count == 1:
        lower_limit = mode_config.seconds_between_packets - mode_config.tolerance
        upper_limit = mode_config.seconds_between_packets + mode_config.tolerance

        if gap_between_packets < lower_limit:
            write_error(
                "{0} {1} is {2:{3}}s after the previous packets (less than {4:{3}}s). {5}".format(
                    timestamp_type,
                    CONSTANTS.TIMESTAMP,
                    gap_between_packets,
                    mode_config.time_delta_format,
                    lower_limit,
                    line_id,
                )
            )
        if gap_between_packets > upper_limit:
            write_error(
                "{0} {1} is {2:{3}}s after the previous packets (more than {4:{3}}s). {5}".format(
                    timestamp_type,
                    CONSTANTS.TIMESTAMP,
                    gap_between_packets,
                    mode_config.time_delta_format,
                    upper_limit,
                    line_id,
                )
            )

    elif line_count > 0 and packet_line_count > 1:
        if gap_between_packets > 0:
            write_error(
                f"{timestamp_type} {CONSTANTS.TIMESTAMP} should be the same as the previous line. {line_id}"
            )

    verify_timestamp.prev_time[timestamp_type] = time


verify_timestamp.prev_time: dict = {"primary": float(0), "secondary": float(0)}


def verify_non_zero_vectors(
    row: dict[str, str], line_count: int, sequence: int, primary_or_secondary: str
) -> bool:
    line_id = f"line number {line_count + 1}, sequence count: {sequence}"

    # take the first 3 chars
    pri_or_sec = primary_or_secondary[0:3]

    x = get_integer(line_count, row, f"x_{pri_or_sec}")
    y = get_integer(line_count, row, f"y_{pri_or_sec}")
    z = get_integer(line_count, row, f"z_{pri_or_sec}")
    r = get_integer(line_count, row, f"rng_{pri_or_sec}")

    if x == 0 and y == 0 and z == 0:
        write_error(
            f"{CONSTANTS.VECTORS_ALL_ZERO} for {primary_or_secondary} on {line_id}"
        )
        return False

    if r < 0 or r > 3:
        write_error(
            f"{CONSTANTS.RANGE_IS_INVALID} for {primary_or_secondary} on {line_id}"
        )
        return False

    return True


def is_non_empty_vector(
    row: dict[str, str], line_count: int, sequence: int, primary_or_secondary: str
) -> bool:
    # take the first 3 chars
    pri_or_sec = primary_or_secondary[0:3]

    x = row[f"x_{pri_or_sec}"]
    y = row[f"y_{pri_or_sec}"]
    z = row[f"z_{pri_or_sec}"]
    r = row[f"rng_{pri_or_sec}"]

    if x and y and z and r:
        return True

    return False


def verify_empty_vectors(
    row: dict[str, str], line_count: int, sequence: int, primary_or_secondary: str
) -> bool:
    line_id = f"line number {line_count + 1}, sequence count: {sequence}"

    # take the first 3 chars
    pri_or_sec = primary_or_secondary[0:3]

    x = row[f"x_{pri_or_sec}"]
    y = row[f"y_{pri_or_sec}"]
    z = row[f"z_{pri_or_sec}"]
    r = row[f"rng_{pri_or_sec}"]

    if x or y or z or r:
        write_error(
            f"{CONSTANTS.VECTORS_NON_EMPTY} for {primary_or_secondary} on {line_id}"
        )
        return False

    return True


def verify_packet_completeness(
    primary_vector_count: int,
    secondary_vector_count: int,
    mode_config: ModeConfig,
    prev_seq: int,
    packet_start_line_count: int,
    is_last_packet: bool,
):
    packet_name = "The last" if is_last_packet else "A"
    if (
        primary_vector_count < mode_config.primary_vectors_per_packet
        or secondary_vector_count < mode_config.secondary_vectors_per_packet
    ):
        write_error(
            f"{packet_name} {CONSTANTS.PACKET_INCOMPLETE}, found {primary_vector_count} primary and {secondary_vector_count} secondary vectors, expected {mode_config.primary_vectors_per_packet} and {mode_config.secondary_vectors_per_packet}. line number {packet_start_line_count + 1}, sequence count: {prev_seq}"
        )
    if (
        primary_vector_count > mode_config.primary_vectors_per_packet
        or secondary_vector_count > mode_config.secondary_vectors_per_packet
    ):
        write_error(
            f"{packet_name} {CONSTANTS.PACKET_TOO_BIG}, found {primary_vector_count} primary and {secondary_vector_count} secondary vectors, expected {mode_config.primary_vectors_per_packet} and {mode_config.secondary_vectors_per_packet}. line number {packet_start_line_count + 1}, sequence count: {prev_seq}"
        )


def write_line(message: str):
    print(message)
    global report_file
    global no_report_flag

    if not no_report_flag:
        report_file.write(message + "\n")


def write_error(message: str):
    global exit_code
    exit_code = 2
    write_line(message)


def generate_summary(folder: Path, report_file_glob: str):
    """Scan the folder for report files that match report_file_suffic and generate a summary count of all the errors"""

    global exit_code

    # get a list of all files in folder that match the report_file_suffix
    report_files = list(folder.glob(report_file_glob))
    summaryJsonPath = Path(folder, "gap_check_summary.json")

    if not report_files:
        print(
            f"No report file(s) matching {report_file_glob} found in {folder} so unable to generate a summary"
        )
        exit_code = 3
        return

    print(
        f"{len(report_files)} file(s) matching {report_file_glob} found in {folder} - generating {summaryJsonPath}"
    )

    # iterate over each report file and generate a summary
    summary = {}
    summary["Folder"] = str(folder.absolute())
    summary["Generated"] = str(datetime.now())
    summary["Failed"] = []
    summary["Passed"] = []

    for file in report_files:
        with open(file, "r") as f:
            errorCount = 0
            for line in f:
                error = None
                if line.find(CONSTANTS.VECTORS_ALL_ZERO) != -1:
                    error = "Vectors are all zero errors"
                elif line.find(CONSTANTS.NONE_SEQUENTIAL) != -1 or line.startswith(
                    f"A {CONSTANTS.PACKET_INCOMPLETE}"
                ):  # ignore last line error
                    error = "Missing science data errors"
                elif (
                    re.search(CONSTANTS.EXPECTED_NUMERIC_MATCH_REGEX, line)
                    or line.find(CONSTANTS.SEQUENCE_NUMBERS_VARY) != -1
                    or line.find(CONSTANTS.RANGE_IS_INVALID) != -1
                    or line.find(CONSTANTS.VECTORS_NON_EMPTY) != -1
                    or line.find(CONSTANTS.TOO_MANY_ROWS) != -1
                    or line.find(CONSTANTS.PACKET_TOO_BIG) != -1
                ):
                    error = "Corrupt science packet errors"

                elif line.find(CONSTANTS.TIMESTAMP) != -1:
                    error = "incorrect timestamp errors"

                if error:
                    errorCount += 1
                    if error in summary:
                        summary[error] += 1
                    else:
                        summary[error] = 1

                    if file.name not in summary["Failed"]:
                        summary["Failed"].append(file.name)

            if errorCount == 0 and file.name not in summary["Passed"]:
                summary["Passed"].append(file.name)

            f.close()

    if len(summary["Failed"]) == 0:
        summary["Gap check result"] = "PASSED"
        print("Gap check passed")
    else:
        summary["Gap check result"] = "FAILED"
        print("Gap check failed")

    if summaryJsonPath.exists():
        os.remove(summaryJsonPath)

    with open(summaryJsonPath, "w") as fp:
        json.dump(summary, fp, indent=2)  # encode dict into JSON


# only needed when this file is run as its own app
if __name__ == "__main__":
    app()

    if report_file:
        report_file.close()
