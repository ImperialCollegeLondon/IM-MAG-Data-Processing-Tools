import glob
import io
import os
import re
import sys
from datetime import datetime, timedelta
from io import TextIOWrapper
from pathlib import Path
from typing import List, Optional

import ccsdspy
import typer
from ccsdspy import PacketField
from ccsdspy.utils import iter_packet_bytes
from click.exceptions import Exit
from rich.progress import Progress, track

from constants import CONSTANTS
from packet_util import get_imap_basic_packet_def, parse_apids

app = typer.Typer()

packet_counter = 0
is_multi_file = False
unique_packets = set()
needs_sort = False


@app.callback(
    invoke_without_command=True
)  # use callback because we want this to be the default command
def filter_packets(
    ctx: typer.Context,
    packet_files: Path = typer.Argument(
        ...,
        help="file path(s) to the binary ccsds files to be to be processed or folder containing .bin files",
    ),
    output_file: Optional[Path] = typer.Option(
        None,
        "--output-file",
        "-o",
        help="Output file path for the deduped packets. Defaults to <input_file>_[timestamp].bin",
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
    sort_packets: bool = typer.Option(
        False,
        "--sort-packets/--no-sort-packets",
        "-s",
        help="Sort packets by SHCOARSE, APID, SEQ COUNT in the outputted file",
    ),
):
    """
    Extract and dedupe raw packets based on apid. Removes and flags duplicates based on apid and seq count. Can filter out other instruments or apids.
    """

    global is_multi_file
    global unique_packets
    global needs_sort

    globPath = None

    if packet_files.is_dir():
        globPath = os.path.join(packet_files, "*.bin")
    elif "*" in str(packet_files) or "?" in str(packet_files):
        globPath = str(packet_files)

    if output_file and output_file.exists() and not is_multi_file:
        print(
            f"{output_file} already exists and will be appended to. Packets in this file already will not be duplicated against (to do that, use this file as an input file to filter-packets and create a new file rather than append to it)."
        )

    if globPath:
        _filter_packets_in_multiple_files_from_glob(
            globPath, output_file, ctx, limit, apids, mag_only, sort_packets
        )
        return

    _validate_filter_packets_args(packet_files, output_file, limit, apids)

    filter_to_apids = parse_apids(apids)

    packet_file_name = packet_files
    if not output_file:
        output_file = (
            packet_file_name.parent
            / f"{packet_file_name.stem}_{datetime.now().strftime('%Y%m%d%H%M%S')}.bin"
        )

    _filter_packets_in_one_file(
        packet_file_name, output_file, limit, mag_only, filter_to_apids
    )

    if not is_multi_file:
        if needs_sort:
            if sort_packets:
                _sort_packets_in_one_file(output_file)
            else:
                print(
                    f"Packet sorting needed in {output_file} - rerun with --sort-packets"
                )
            needs_sort = False
        else:
            print(f"Packets in {output_file} are sorted correctly")

    print(f"Filtered packets saved to {output_file.absolute()}")


def _filter_packets_in_one_file(
    packet_file: Path,
    output_file: Path,
    limit: int,
    mag_only: bool,
    apid_filter: List[int],
):
    global exit_code
    global packet_counter
    global unique_packets
    global needs_sort

    pktDefinition = get_imap_basic_packet_def()

    if limit != 0 and packet_counter >= limit:
        return

    size = os.path.getsize(packet_file)
    processed_bytes = 0
    ignored_packets = 0
    previous_packet_timestamp = 0
    previous_packet_seq_count: dict[int, int] = {}  # apid -> seq_count
    with open(output_file, "ab") as output_file_handle:
        with Progress(refresh_per_second=1) as progress:
            task1 = progress.add_task(f"Processing {packet_file}", total=size)
            for packet_bytes in iter_packet_bytes(
                packet_file, include_primary_header=True
            ):
                progress.update(task1, advance=len(packet_bytes))
                processed_bytes += len(packet_bytes)

                fileLikeObject = io.BytesIO(packet_bytes)
                pkt = pktDefinition.load(fileLikeObject, include_primary_header=True)
                apid = int(pkt["CCSDS_APID"][0])
                sequence_count = int(pkt["CCSDS_SEQUENCE_COUNT"][0])
                shcourse = int(pkt["SHCOARSE"][0])

                # check the packet shopuld not be filtered out
                if mag_only:
                    if apid < CONSTANTS.APID_MAG_START or apid > CONSTANTS.APID_MAG_END:
                        ignored_packets += 1
                        continue

                if apid_filter:
                    if apid not in apid_filter:
                        ignored_packets += 1
                        continue

                if not output_file.parent.exists():
                    output_file.parent.mkdir(parents=True)

                unique_id = (apid, pkt["SHCOARSE"][0], sequence_count)
                if unique_id in unique_packets:
                    print(
                        f"Duplicate packet found - ApID: {hex(apid)} Seq Count: {sequence_count} SHCOARSE: {shcourse}. Skipping it.",
                        file=sys.stderr,
                    )
                    ignored_packets += 1
                    continue

                if shcourse < previous_packet_timestamp:
                    print(
                        f"WARNING: {CONSTANTS.NON_SEQUENTIAL} time detected at SHCOURSE {shcourse} (previous was {previous_packet_timestamp})",
                        file=sys.stderr,
                    )
                    needs_sort = True
                previous_packet_timestamp = shcourse

                if (
                    apid in previous_packet_seq_count
                    and sequence_count
                    != (
                        (previous_packet_seq_count[apid] + 1)
                        % CONSTANTS.MAX_SEQUENCE_COUNT
                    )
                    and sequence_count != 0
                ):
                    print(
                        f"WARNING: {CONSTANTS.NON_SEQUENTIAL} sequence count detected for ApID {hex(apid)} at Seq Count {sequence_count} (previous was {previous_packet_seq_count[apid]})",
                        file=sys.stderr,
                    )
                    needs_sort = True
                previous_packet_seq_count[apid] = sequence_count

                unique_packets.add(unique_id)
                output_file_handle.write(packet_bytes)
                packet_counter += 1

                if limit > 0 and packet_counter >= limit:
                    print(f"Limit of {limit} packets reached")
                    break

    print(
        f"Saved {packet_counter} packets from {packet_file} to {output_file.name} ({processed_bytes} bytes processed, {os.path.getsize(output_file)} bytes written). Ignored {ignored_packets} packets."
    )


def _filter_packets_in_multiple_files_from_glob(
    globPath, output_file, ctx, limit, apids, mag_only, sort_packets
):
    multifile_exit_code = 0
    files = 0
    global is_multi_file
    global needs_sort
    is_multi_file = True
    needs_sort = False
    for filename in glob.glob(globPath):
        files += 1
        try:
            result = ctx.invoke(
                filter_packets,
                packet_files=Path(filename),
                output_file=output_file,
                ctx=ctx,
                limit=limit,
                apids=apids,
                mag_only=mag_only,
                sort_packets=False,
            )
            if result and result.exit_code != 0:
                multifile_exit_code = result.exit_code
        except Exit as exit:
            multifile_exit_code = exit.exit_code
        except Exception as e:
            print(f"Error processing {filename}: {e}", file=sys.stderr)
            if multifile_exit_code == 0:
                multifile_exit_code = 1

    is_multi_file = False

    if files == 0:
        multifile_exit_code = 1

    if needs_sort:
        if sort_packets:
            _sort_packets_in_one_file(output_file)
        else:
            print(f"Packet sorting needed in {output_file} - rerun with --sort-packets")
        needs_sort = False
    else:
        print(f"Packets in {output_file} are sorted correctly")

    print(f"Processed {files} files matching {globPath}")

    print(f"Packets saved to {output_file}")

    if multifile_exit_code != 0:
        raise typer.Exit(code=multifile_exit_code)


def _validate_filter_packets_args(
    data_file: Path,
    output_file: Path | None,
    limit: int,
    apids: List[str] | None,
):
    if not data_file.exists():
        print(f"{data_file} does not exist")
        raise typer.Abort()

    if not data_file.name:
        print("data_file name is empty or invalid")
        raise typer.Abort()

    if output_file and output_file.is_dir():
        print(f"output_file {output_file} is a directory, please provide a file path")
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


def _sort_packets_in_one_file(
    packet_file: Path,
):
    pktDefinition = get_imap_basic_packet_def()

    output_file = packet_file.with_name(
        f"{packet_file.stem}_sorted{packet_file.suffix}"
    )
    size = os.path.getsize(packet_file)
    in_mem_ordered_packets: list[tuple[(tuple[int, int, int], bytes)]] = []
    packet_counter = 0

    print("Sorting packets - read all packets into memory")

    with open(output_file, "ab") as output_file_handle:
        with Progress(refresh_per_second=1) as progress:
            task1 = progress.add_task(f"Reading {packet_file}", total=size)
            task2 = progress.add_task(f"Writing {output_file}", total=size)
            for packet_bytes in iter_packet_bytes(
                packet_file, include_primary_header=True
            ):
                progress.update(task1, advance=len(packet_bytes))

                fileLikeObject = io.BytesIO(packet_bytes)
                pkt = pktDefinition.load(fileLikeObject, include_primary_header=True)
                apid = int(pkt["CCSDS_APID"][0])
                sequence_count = int(pkt["CCSDS_SEQUENCE_COUNT"][0])
                shcourse = int(pkt["SHCOARSE"][0])
                in_mem_ordered_packets.append(
                    ((shcourse, apid, sequence_count), packet_bytes)
                )
                packet_counter += 1

            for keys, packet_bytes in sorted(in_mem_ordered_packets):
                output_file_handle.write(packet_bytes)
                progress.update(task2, advance=len(packet_bytes))

    del in_mem_ordered_packets
    os.remove(packet_file)
    os.rename(output_file, packet_file)

    print(
        f"Sorted {packet_counter} packets in {packet_file} ({os.path.getsize(packet_file)} bytes written)."
    )


# only needed when this file is run as its own app
if __name__ == "__main__":
    app()
