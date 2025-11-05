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
    get_imap_science_packet_def,
    parse_apids,
)
from science_decoder import MAGScienceDecoder
from src.ialirt_decoder import IALIRTDecoder
from time_util import humanise_timedelta

app = typer.Typer()

packet_counter = 0
is_multi_file = False
unique_packets = set()


@app.callback(
    invoke_without_command=True
)  # use callback because we want this to be the default command
def parse_packets(
    ctx: typer.Context,
    packet_files: Path = typer.Argument(
        ...,
        help="file path(s) to the binary ccsds files to be to be processed or folder containing .bin files. Can be a glob pattern like 'data/*.bin'",
    ),
    output_folder: Optional[Path] = typer.Option(
        Path.cwd(),
        "--output-folder",
        "-o",
        help="Output folder path for the parsed packet data. Defaults to the working directory",
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
):
    """
    Parse MAG (science only!) packets based on apid and puts vectors in a CSV file.
    """

    global is_multi_file
    global unique_packets
    global packet_counter

    globPath = None

    if packet_files.is_dir():
        globPath = os.path.join(packet_files, "*.bin")
    elif "*" in str(packet_files) or "?" in str(packet_files):
        globPath = str(packet_files)

    if globPath:
        _parse_packets_in_mulitple_files_from_glob_path(
            globPath, output_folder, ctx, limit, apids
        )
        return

    _validate_parse_packets_args(packet_files, output_folder, limit, apids)

    if not output_folder:
        output_folder = Path.cwd()

    if output_folder and output_folder.is_dir() and not output_folder.exists():
        output_folder.mkdir(parents=True)

    filter_to_apids = parse_apids(apids)

    if apids:
        print(
            f"WARN: Currently only able to decode MAG BM/NM science. Filtering to ApIDs: {', '.join([str(apid) for apid in filter_to_apids])}"
        )

    # just a single file at this point
    packet_file_name = packet_files

    _parse_packets_in_one_file(packet_file_name, output_folder, limit, filter_to_apids)

    print(f"Data extracted to {output_folder.absolute()}")


def _parse_packets_in_one_file(
    packet_file: Path,
    output_folder: Path,
    limit: int,
    apid_filter: List[int],
):
    global exit_code
    global packet_counter
    global unique_packets

    if not is_multi_file:
        unique_packets = set()
        packet_counter = 0

    pktDefinition = get_imap_basic_packet_def()
    sciFullPktDefinition = get_imap_science_packet_def()

    if limit != 0 and packet_counter >= limit:
        return

    size = os.path.getsize(packet_file)
    processed_bytes = 0
    ignored_packets = 0
    started_at = datetime.now()
    sci_decoder = MAGScienceDecoder(output_folder)
    ialirt_mag_decoder = IALIRTDecoder(output_folder, "mag")
    ialirt_scpacket_decoder = IALIRTDecoder(output_folder, "sc")

    with Progress(refresh_per_second=1) as progress:
        task1 = progress.add_task(f"Processing {packet_file}", total=size)
        for packet_bytes in iter_packet_bytes(packet_file, include_primary_header=True):
            progress.update(task1, advance=len(packet_bytes))
            processed_bytes += len(packet_bytes)

            fileLikeObject = io.BytesIO(packet_bytes)
            pkt = pktDefinition.load(fileLikeObject, include_primary_header=True)
            apid = pkt["CCSDS_APID"][0].astype(int)

            if apid == CONSTANTS.APID_MAG_IALIRT:
                ialirt_mag_decoder.extract_packet_to_csv(apid, packet_bytes)
                packet_counter += 1
                if limit > 0 and packet_counter >= limit:
                    print(f"Limit of {limit} packets reached")
                    break

                continue
            elif apid == CONSTANTS.APID_SPACECRAFT_IALIRT:
                ialirt_scpacket_decoder.extract_packet_to_csv(apid, packet_bytes)
                packet_counter += 1
                if limit > 0 and packet_counter >= limit:
                    print(f"Limit of {limit} packets reached")
                    break

                continue

            # check the packet should not be filtered out
            if apid < CONSTANTS.APID_MAG_START or apid > CONSTANTS.APID_MAG_END:
                ignored_packets += 1
                continue

            if apid_filter:
                if apid not in apid_filter:
                    ignored_packets += 1
                    continue

            if not (
                apid == CONSTANTS.APID_MAG_SCIENCE_NM
                or apid == CONSTANTS.APID_MAG_SCIENCE_BM
            ):
                ignored_packets += 1
                continue

            # So this must be a science packet, reparse it with the full science definition
            fileLikeObject.seek(0)
            pkt = sciFullPktDefinition.load(fileLikeObject, include_primary_header=True)

            unique_id = (apid, pkt["SHCOARSE"][0], pkt["CCSDS_SEQUENCE_COUNT"][0])
            if unique_id in unique_packets:
                print(
                    f"Duplicate packet found - ApID: {hex(apid)} Seq Count: {pkt['CCSDS_SEQUENCE_COUNT'][0]} SHCOARSE: {pkt['SHCOARSE'][0]}. Skipping it.",
                    file=sys.stderr,
                )
                ignored_packets += 1
                continue

            unique_packets.add(unique_id)
            packet_counter += 1

            # decode vectors!
            sci_decoder.extract_packet_to_csv(
                apid,
                pkt["CCSDS_SEQUENCE_COUNT"][0].astype(int),
                pkt["CCSDS_PACKET_LENGTH"][0].astype(int),
                pkt["PUS_STYPE"][0].astype(int),
                pkt["PUS_SSUBTYPE"][0].astype(int),
                pkt["PRI_COARSETM"][0].astype(int),
                pkt["PRI_FNTM"][0].astype(int),
                pkt["SEC_COARSETM"][0].astype(int),
                pkt["SEC_FNTM"][0].astype(int),
                pkt["PRI_VECSEC"][0].astype(int),
                pkt["SEC_VECSEC"][0].astype(int),
                pkt["COMPRESSION"][0].astype(int),
                pkt["FOB_ACT"][0].astype(int),
                pkt["FIB_ACT"][0].astype(int),
                pkt["PRI_SENS"][0].astype(int),
                pkt["VECTOR_DATA"][0].tobytes(),
            )

            if limit > 0 and packet_counter >= limit:
                print(f"Limit of {limit} packets reached")
                break

    ended_at = datetime.now()
    duration = ended_at - started_at
    sci_decoder.close_all()
    ialirt_mag_decoder.close_all()
    ialirt_scpacket_decoder.close_all()

    print(
        f"Extracted data from {packet_counter} packets in {packet_file} to {output_folder.name} ({processed_bytes} bytes processed in {humanise_timedelta(duration)}). Ignored {ignored_packets} packets."
    )

    if packet_counter == 0:
        exit_code = 1
        print("Zero packets parsed", file=sys.stderr)
        raise typer.Exit(code=exit_code)


def _parse_packets_in_mulitple_files_from_glob_path(
    globPath, output_folder, ctx, limit, apids
):
    multifile_exit_code = 0
    files = 0
    global is_multi_file
    global packet_counter
    is_multi_file = True
    for filename in glob.glob(globPath):
        files += 1
        try:
            result = ctx.invoke(
                parse_packets,
                packet_files=Path(filename),
                output_folder=output_folder,
                ctx=ctx,
                limit=limit,
                apids=apids,
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

    print(f"Extracted data saved to {output_folder}")

    is_multi_file = False
    packet_counter = 0

    if multifile_exit_code != 0:
        raise typer.Exit(code=multifile_exit_code)


def _validate_parse_packets_args(
    data_file: Path,
    output_folder: Path | None,
    limit: int,
    apids: List[str] | None,
):
    if not data_file.exists():
        print(f"{data_file} does not exist")
        raise typer.Abort()

    if not data_file.name:
        print("data_file name is empty or invalid")
        raise typer.Abort()

    if output_folder and not output_folder.is_dir():
        print(
            f"output_folder {output_folder} is not a directory, please provide a directory path"
        )
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
