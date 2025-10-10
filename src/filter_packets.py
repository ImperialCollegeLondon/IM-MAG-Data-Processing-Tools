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

app = typer.Typer()

report_file: TextIOWrapper
sci_report_file: TextIOWrapper
exit_code = 0
packet_counter = 0
APID_MAG_START = 0x3E0
APID_MAG_END = 0x45F
is_multi_file = False


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
):
    """
    Extract and dedupe raw packets based on apid. Removes and flags duplicates based on apid and seq count. Can filter out other instruments or apids.
    """

    global exit_code
    global is_multi_file
    global unique_packets

    exit_code = 0
    globPath = None
    unique_packets = set()

    if packet_files.is_dir():
        globPath = os.path.join(packet_files, "*.bin")
    elif "*" in str(packet_files) or "?" in str(packet_files):
        globPath = str(packet_files)

    if output_file and output_file.exists() and not is_multi_file:
        print(
            f"{output_file} already exists and will be appended to. Packets in this file already will not be duplicated against (to do that, use this file as an input file to filter-packets and create a new file rather than append to it)."
        )

    if globPath:
        process_multi_file(globPath, output_file, ctx, limit, apids, mag_only)
        return

    validate_parse_packets_args(packet_files, output_file, limit, apids)

    filter_to_apids = parse_apids(apids)

    packet_file_name = packet_files
    if not output_file:
        output_file = (
            packet_file_name.parent
            / f"{packet_file_name.stem}_{datetime.now().strftime('%Y%m%d%H%M%S')}.bin"
        )

    parse_packets_in_one_file(
        packet_file_name, output_file, limit, mag_only, filter_to_apids
    )

    print(f"Filtered packets saved to {output_file.absolute()}")

    if exit_code != 0:
        raise typer.Exit(code=exit_code)


def parse_apids(apids):
    filter_to_apids = []
    if apids:
        for apid in apids:
            # if it is an integer, convert it to an int
            if re.match(r"^[0-9]+$", apid):
                filter_to_apids.append(int(apid, 10))
            else:
                filter_to_apids.append(int(apid, 16))
    return filter_to_apids


def parse_packets_in_one_file(
    packet_file: Path,
    output_file: Path,
    limit: int,
    mag_only: bool,
    apid_filter: List[int],
):
    global exit_code
    global packet_counter
    global unique_packets

    pktDefinition = ccsdspy.FixedLength(
        [
            PacketField(name="SHCOARSE", data_type="uint", bit_length=32),
        ]
    )

    if limit != 0 and packet_counter >= limit:
        return

    size = os.path.getsize(packet_file)
    processed_bytes = 0
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
                apid = pkt["CCSDS_APID"][0]

                # check the packet shopuld not be filtered out
                if mag_only:
                    if apid < APID_MAG_START or apid > APID_MAG_END:
                        continue

                if apid_filter:
                    if apid not in apid_filter:
                        continue

                if not output_file.parent.exists():
                    output_file.parent.mkdir(parents=True)

                unique_id = (apid, pkt["SHCOARSE"][0], pkt["CCSDS_SEQUENCE_COUNT"][0])
                if unique_id in unique_packets:
                    print(
                        f"Duplicate packet found - ApID: 0x{hex(apid)} Seq Count: {pkt['CCSDS_SEQUENCE_COUNT'][0]} SHCOARSE: {pkt['SHCOARSE'][0]}. Skipping it.",
                        file=sys.stderr,
                    )
                    continue

                unique_packets.add(unique_id)
                output_file_handle.write(packet_bytes)
                packet_counter += 1

                if limit > 0 and packet_counter >= limit:
                    print(f"Limit of {limit} packets reached")
                    break

    print(
        f"Saved {packet_counter} packets from {packet_file} to {output_file.name} ({processed_bytes} bytes processed, {os.path.getsize(output_file)} bytes written)"
    )


def process_multi_file(globPath, output_file, ctx, limit, apids, mag_only):
    multifile_exit_code = 0
    files = 0
    global is_multi_file
    is_multi_file = True
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

    print(f"Packets saved to {output_file}")

    if multifile_exit_code != 0:
        raise typer.Exit(code=multifile_exit_code)


def validate_parse_packets_args(
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


# only needed when this file is run as its own app
if __name__ == "__main__":
    app()
