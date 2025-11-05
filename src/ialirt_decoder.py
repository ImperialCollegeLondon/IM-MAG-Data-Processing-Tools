import csv
import os
import threading
import time
from collections import namedtuple
from ctypes import c_int32
from datetime import datetime

import numpy as np

from constants import CONSTANTS
from science_mode import ModeName
from src import time_util
from time_util import get_met_from_shcourse, humanise_timedelta

Vector = namedtuple("Vector", ["x", "y", "z", "rng"])


class _IALIRTFileWriter:

    def __init__(
        self,
        folder: str,
        packet_type: str = "mag",
    ):

        self.time_now = datetime.now().strftime("%Y%m%d-%Hh%M")
        self.filename = None
        self.file = None
        self.isOpen = 0
        self.closePending = False
        self.writer = None
        self.idleTimer = None
        self.base_path = folder
        self.packet_type = packet_type
        self.data_start_timestamp = None

    def _first_write(self, firstPriCoarse, firstPriFine):

        if self.isOpen == 1:
            return

        first_vector_time = float(firstPriCoarse) + (
            float(firstPriFine) / CONSTANTS.MAX_FINE_TIME
        )
        self.data_start_timestamp = get_met_from_shcourse(first_vector_time)

        self.filename = self._generateFileName(
            self.packet_type,
            self.data_start_timestamp.strftime("%Y%m%d-%Hh%Mm%Ss"),
        )
        exists_already = os.path.isfile(self.filename)
        self.file = open(self.filename, "a")
        self.isOpen = 1
        self.closePending = False
        self.writer = csv.writer(self.file)
        if not exists_already:
            self.writer.writerow(
                [
                    "x_pri",
                    "y_pri",
                    "z_pri",
                    "rng_pri",
                    "x_sec",
                    "y_sec",
                    "z_sec",
                    "rng_sec",
                    "pri_coarse",
                    "pri_fine",
                    "sec_coarse",
                    "sec_fine",
                    "pri_utc",
                    "sec_utc",
                ]
            )
            print(f"Opened new alirt data file {self.filename}")
        else:
            print(f"Appending to existing alirt data file {self.filename}")

    def _generateFileName(self, packet_type, data_start_timestamp):
        return f"{self.base_path}/IALiRT-{packet_type}-{data_start_timestamp}.csv"

    def write(
        self,
        primary_vector,
        secondary_vector,
        primary_science_time_coarse,
        primary_science_time_fine,
        secondary_science_time_coarse,
        secondary_science_time_fine,
        pri_time_utc,
        sec_time_utc,
    ):
        if self.isOpen == 0:
            self._first_write(primary_science_time_coarse, primary_science_time_fine)

        assert self.writer is not None

        if self.isOpen == 1:
            self.writer.writerow(
                [
                    primary_vector.x if primary_vector else None,
                    primary_vector.y if primary_vector else None,
                    primary_vector.z if primary_vector else None,
                    primary_vector.rng if primary_vector else None,
                    secondary_vector.x if secondary_vector else None,
                    secondary_vector.y if secondary_vector else None,
                    secondary_vector.z if secondary_vector else None,
                    secondary_vector.rng if secondary_vector else None,
                    primary_science_time_coarse if primary_vector else None,
                    primary_science_time_fine if primary_vector else None,
                    secondary_science_time_coarse if secondary_vector else None,
                    secondary_science_time_fine if secondary_vector else None,
                    pri_time_utc if primary_vector else None,
                    sec_time_utc if secondary_vector else None,
                ]
            )
            # after each packet make sure everything is written to disk
            self.flush()

    def flush(self):
        if self.isOpen == 1 and self.file:
            self.file.flush()

    def close(self):
        if self.isOpen == 1:
            if self.file:
                self.file.close()
            self.isOpen = 0
            self.closePending = False


class IALIRTDecoder:

    epoch = datetime(2010, 1, 1, 0, 0, 0)

    @staticmethod
    def toSigned16(n):
        n = n & 0xFFFF
        return n | (-(n & 0x8000))

    # in SC  packet the whole packet is 183 bytes long, mag data starts at byte offset 171 and is 12 bytes long. NO data after mag data
    # in MAG packet the whole packet is 24  bytes long, mag data starts at byte offset 10  and is 12 bytes long.  2 bytes after mag data

    def __init__(self, folder, stream_type="mag"):
        self._writer = None
        self.base_path = folder
        self.last_time = None
        self.stream_type = stream_type
        self.packet_group_sci_data = []
        self.primary_science_time_coarse = None
        self.primary_science_time_fine = None
        self.secondary_science_time_coarse = None
        self.secondary_science_time_fine = None

    def extract_packet_to_csv(
        self,
        apId,
        packet_bytes,
    ):
        if apId == CONSTANTS.APID_SPACECRAFT_IALIRT:
            offset = 171
        elif apId == CONSTANTS.APID_MAG_IALIRT:
            offset = 10
        else:
            raise ValueError(f"Unsupported APID for I-ALiRT decoding: {hex(apId)}")

        if not packet_bytes or len(packet_bytes) < offset + 12:
            print("Packet too short to contain mag data")
            return

        mag_data_start = offset
        course_4bytes = packet_bytes[mag_data_start : mag_data_start + 4]
        fine_2bytes = packet_bytes[mag_data_start + 4 : mag_data_start + 6]

        course = int.from_bytes(course_4bytes, byteorder="big", signed=False)
        fine = int.from_bytes(fine_2bytes, byteorder="big", signed=False)

        status_3bytes = packet_bytes[mag_data_start + 6 : mag_data_start + 9]
        status = (
            (packet_bytes[mag_data_start + 6] << 16)
            | (packet_bytes[mag_data_start + 7] << 8)
            | (packet_bytes[mag_data_start + 8] << 0)
        ) & 0xFFFFFF
        sci_3bytes = packet_bytes[mag_data_start + 9 : mag_data_start + 12]
        # first 2 bits only of status byte 0 is pkt counter
        pkt_counter = status_3bytes[0] >> 6 & 0b11

        if pkt_counter == 0:
            # reset the groups data
            self.packet_group_sci_data = []
            self.primary_science_time_coarse = None
            self.primary_science_time_fine = None
            self.secondary_science_time_coarse = None
            self.secondary_science_time_fine = None

        # save the chunk of science for pkt 4
        self.packet_group_sci_data.extend(sci_3bytes)

        if pkt_counter == 1:
            self.primary_science_time_coarse = course
            self.primary_science_time_fine = fine
        elif pkt_counter == 2:
            self.secondary_science_time_coarse = course
            self.secondary_science_time_fine = fine

        if pkt_counter == 3 and len(self.packet_group_sci_data) == 12:
            # more hk info is over here
            # https://github.com/ImperialCollegeLondon/IM-MAG-SW/blob/main/acceptance-tests/gseos/IMAP.8.7.044/Instruments/MAG_Common/ialirt_HKdecoder.py
            FOB_RANGE = (status >> 3) & 0x3
            FIB_RANGE = (status >> 1) & 0x3

            decoded_pri_vector = [
                IALIRTDecoder.toSigned16(
                    ((self.packet_group_sci_data[0] << 8) & 0xFF00)
                    | ((self.packet_group_sci_data[1] << 0) & 0x00FF)
                ),
                IALIRTDecoder.toSigned16(
                    ((self.packet_group_sci_data[2] << 8) & 0xFF00)
                    | ((self.packet_group_sci_data[3] << 0) & 0x00FF)
                ),
                IALIRTDecoder.toSigned16(
                    ((self.packet_group_sci_data[4] << 8) & 0xFF00)
                    | ((self.packet_group_sci_data[5] << 0) & 0x00FF)
                ),
            ]
            decoded_sec_vector = [
                IALIRTDecoder.toSigned16(
                    ((self.packet_group_sci_data[6] << 8) & 0xFF00)
                    | ((self.packet_group_sci_data[7] << 0) & 0x00FF)
                ),
                IALIRTDecoder.toSigned16(
                    ((self.packet_group_sci_data[8] << 8) & 0xFF00)
                    | ((self.packet_group_sci_data[9] << 0) & 0x00FF)
                ),
                IALIRTDecoder.toSigned16(
                    ((self.packet_group_sci_data[10] << 8) & 0xFF00)
                    | ((self.packet_group_sci_data[11] << 0) & 0x00FF)
                ),
            ]

            pri = Vector(
                decoded_pri_vector[0],
                decoded_pri_vector[1],
                decoded_pri_vector[2],
                FOB_RANGE,
            )
            sec = Vector(
                decoded_sec_vector[0],
                decoded_sec_vector[1],
                decoded_sec_vector[2],
                FIB_RANGE,
            )

            if self._writer is None:
                self._writer = _IALIRTFileWriter(
                    folder=self.base_path,
                    packet_type=self.stream_type,
                )

            self._writer.write(
                pri,
                sec,
                self.primary_science_time_coarse,
                self.primary_science_time_fine,
                self.secondary_science_time_coarse,
                self.secondary_science_time_fine,
                time_util.get_met_from_sci_timestamp(
                    self.primary_science_time_coarse, self.primary_science_time_fine
                ),
                time_util.get_met_from_sci_timestamp(
                    self.secondary_science_time_coarse, self.secondary_science_time_fine
                ),
            )

    def close_all(self):
        if self._writer is not None:
            self._writer.close()
