import glob
import io
import os
import re
import sys
from datetime import datetime, timedelta
from io import TextIOWrapper
from pathlib import Path
from typing import List, Optional

import typer
from ccsdspy.utils import iter_packet_bytes
from click.exceptions import Exit
from rich.progress import Progress, track

from constants import CONSTANTS
from packet_util import (
    get_imap_basic_packet_def,
    get_imap_science_packet_headers_only_def,
    parse_apids,
)
from time_util import get_met_from_shcourse

app = typer.Typer()

report_file: TextIOWrapper
sci_report_file: TextIOWrapper
exit_code = 0
packet_counter = 0
is_multi_file = False


@app.callback(
    invoke_without_command=True
)  # use callback because we want this to be the default command
def split_packets(
    ctx: typer.Context,
    packets_files: Path = typer.Argument(
        ...,
        help="file path(s) to the binary ccsds files to be to be processed or folder containing .bin files",
    ),
    report_file_path: Optional[Path] = typer.Option(
        "",
        "--report",
        help="Path to a file to save a summary of the packets. Appends if it already exists.",
    ),
    no_report: bool = typer.Option(
        False, "--no-report", help="Disable the report file"
    ),
    summarise_only: bool = typer.Option(
        False,
        "--summarise",
        help="Skip the packet splitting and just generate the summary files",
    ),
    limit: int = typer.Option(
        0,
        "--limit",
        help="Limit the number of packets to process",
    ),
    apids: Optional[List[str]] = typer.Option(
        (),
        "--apid",
        help="Restrict the results to packets with one or more specificied ApIDs. Defaults to all ApIDs.",
    ),
    mag_only: bool = typer.Option(
        True,
        "--mag-only/--all",
        help="mag-only = only process MAG packets and ignore ApIDs outside of the MAG range, all = process all packets inc spacecraft and other instruments",
    ),
):
    """
    Check MAG science CSV files for gaps in sequence counters and time stamps
    """
    global report_file
    global sci_report_file
    global exit_code
    global is_multi_file

    report_file = None
    exit_code = 0
    globPath = None

    if packets_files.is_dir():
        globPath = os.path.join(packets_files, "*.bin")
    elif "*" in str(packets_files) or "?" in str(packets_files):
        globPath = str(packets_files)

    report_file_path = (
        (report_file_path / "packets.csv")
        if report_file_path.is_dir()
        else report_file_path
    )

    if globPath:
        _split_packets_in_multiple_files_from_glob(
            globPath,
            ctx,
            report_file_path,
            no_report,
            summarise_only,
            limit,
            apids,
            mag_only,
        )
        return

    _validate_split_packets_args(
        packets_files, report_file_path, no_report, summarise_only, limit, apids
    )

    if not no_report:
        headers = False
        if not report_file_path.exists():
            headers = True
        report_file = open(report_file_path, "a")
        if headers:
            report_file.write("APID,Sequence Count,Length,SHCOURSE,MET_UTC\n")

        sci_file = (
            report_file_path.parent
            / f"{report_file_path.with_suffix('').name}_scionly.csv"
        )
        headers = False
        if not sci_file.exists():
            headers = True
        sci_report_file = open(sci_file, "a")
        if headers:
            sci_report_file.write(
                "APID,PHSEQCNT,PHDLEN,SHCOURSE,PUS_SSUBTYPE,COMPRESSION,FOB_ACT,FIB_ACT,PRI_SENS,PRI_VECSEC,SEC_VECSEC,PRI_COARSETM,PRI_FNTM,SEC_COARSETM,SEC_FNTM,MET_UTC\n"
            )

    filter_to_apids = parse_apids(apids)

    _split_packets_in_one_file(
        packets_files, no_report, limit, mag_only, filter_to_apids, summarise_only
    )

    if not no_report and not is_multi_file:
        report_file.close()
        print(f"Packet summary saved to {report_file_path}")

    if exit_code != 0:
        raise typer.Exit(code=exit_code)


def _split_packets_in_one_file(
    packet_file: Path,
    no_report: bool,
    limit: int,
    mag_only: bool,
    apid_filter: List[int],
    summarise_only: bool = False,
):
    global exit_code
    global packet_counter
    global report_file
    global sci_report_file

    pktDefinition = get_imap_basic_packet_def()
    sciPktDefinition = get_imap_science_packet_headers_only_def()

    if limit != 0 and packet_counter >= limit:
        return

    size = os.path.getsize(packet_file)
    processed_bytes = 0
    with Progress(refresh_per_second=1) as progress:
        task1 = progress.add_task(f"Processing {packet_file}", total=size)
        for packet_bytes in iter_packet_bytes(packet_file, include_primary_header=True):
            progress.update(task1, advance=len(packet_bytes))
            processed_bytes += len(packet_bytes)

            fileLikeObject = io.BytesIO(packet_bytes)
            pkt = pktDefinition.load(fileLikeObject, include_primary_header=True)
            apid = pkt["CCSDS_APID"][0]

            # check the packet shopuld not be filtered out
            if mag_only:
                if apid < CONSTANTS.APID_MAG_START or apid > CONSTANTS.APID_MAG_END:
                    continue

            if apid_filter:
                if apid not in apid_filter:
                    continue

            is_science = False
            if (
                apid == CONSTANTS.APID_MAG_SCIENCE_NM
                or apid == CONSTANTS.APID_MAG_SCIENCE_BM
            ):
                is_science = True

                fileLikeObject.seek(0)
                pkt = sciPktDefinition.load(fileLikeObject, include_primary_header=True)

            # Save the single packet to it's own .bin file?
            if not summarise_only:
                newFileName = (
                    packet_file.parent
                    / str(apid)
                    / f"{pkt['SHCOARSE'][0]}-{pkt['CCSDS_SEQUENCE_COUNT'][0]}.bin"
                )

                if newFileName.exists():
                    print(f"Existing packet found: {newFileName} - skipped it")
                    exit_code = 1
                else:
                    if not newFileName.parent.exists():
                        newFileName.parent.mkdir(parents=True)

                    with open(newFileName, "wb") as f:
                        f.write(packet_bytes)

            packet_counter += 1

            if not no_report:
                met_utc = get_met_from_shcourse(int(pkt["SHCOARSE"][0])).strftime(
                    "%Y-%m-%d %H:%M:%S.%f"
                )[:-3]
                report_file.write(
                    f"{apid},{pkt['CCSDS_SEQUENCE_COUNT'][0]},{pkt['CCSDS_PACKET_LENGTH'][0]},{pkt['SHCOARSE'][0]},{met_utc}\n"
                )
                if is_science:
                    sci_report_file.write(
                        f"{apid},{pkt['CCSDS_SEQUENCE_COUNT'][0]},{pkt['CCSDS_PACKET_LENGTH'][0]},{pkt['SHCOARSE'][0]},"
                        + f"{pkt['PUS_SSUBTYPE'][0]},"
                        + f"{pkt['COMPRESSION'][0]},"
                        + f"{pkt['FOB_ACT'][0]},"
                        + f"{pkt['FIB_ACT'][0]},"
                        + f"{pkt['PRI_SENS'][0]},"
                        + f"{pkt['PRI_VECSEC'][0]},"
                        + f"{pkt['SEC_VECSEC'][0]},"
                        + f"{pkt['PRI_COARSETM'][0]},"
                        + f"{pkt['PRI_FNTM'][0]},"
                        + f"{pkt['SEC_COARSETM'][0]},"
                        + f"{pkt['SEC_FNTM'][0]}"
                        + f",{met_utc}"
                        + "\n"
                    )

            if limit > 0 and packet_counter >= limit:
                print(f"Limit of {limit} packets reached")
                break

    if not summarise_only:
        print(
            f"Saved {packet_counter} packets from {packet_file} to {packet_file.parent} ({processed_bytes} bytes processed)"
        )


def _split_packets_in_multiple_files_from_glob(
    globPath, ctx, report_file_path, no_report, summarise_only, limit, apids, mag_only
):
    multifile_exit_code = 0
    files = 0
    global is_multi_file
    is_multi_file = True
    for filename in glob.glob(globPath):
        files += 1
        try:
            result = ctx.invoke(
                split_packets,
                packets_files=Path(filename),
                ctx=ctx,
                report_file_path=report_file_path,
                no_report=no_report,
                summarise_only=summarise_only,
                limit=limit,
                apids=apids,
                mag_only=mag_only,
            )
            if result and result.exit_code != 0:
                multifile_exit_code = result.exit_code
        except Exit as exit:
            multifile_exit_code = exit.exit_code
        except Exception as e:
            print(f"Error processing {filename}: {e}", file=sys.stderr)
            if multifile_exit_code == 0:
                multifile_exit_code = 1

    if files == 0:
        multifile_exit_code = 1

    print(f"Processed {files} files matching {globPath}")

    if not no_report:
        print(f"Packet summary saved to {report_file_path}")

    if multifile_exit_code != 0:
        raise typer.Exit(code=multifile_exit_code)


def _validate_split_packets_args(
    data_file: Path,
    report_file_path,
    no_report: bool,
    summarise_only: bool,
    limit: int,
    apids: List[str] | None,
):
    if not data_file.exists():
        print(f"{data_file} does not exist")
        raise typer.Abort()

    if not (no_report) and report_file_path.exists() and not summarise_only:
        print(f"{report_file_path} already exists - will append to this file")

    if not data_file.name:
        print("data_file name is empty or invalid")
        raise typer.Abort()

    if limit < 0:
        print("limit must be a positive integer")
        raise typer.Abort()

    if apids:
        for apid in apids:
            # ensure it is an int or an int in hex format
            if not re.match(r"^(0(x|X))?[0-9a-fA-F]+$", apid):
                print(f"Invalid APID: {apid}")
                raise typer.Abort()


# only needed when this file is run as its own app
if __name__ == "__main__":
    app()

    if report_file:
        report_file.close()
