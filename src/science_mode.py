from __future__ import annotations

import re
from enum import Enum
from pathlib import Path

from constants import CONSTANTS


# ModeName enum:
class ModeName(str, Enum):
    normal = "normal"
    burst = "burst"


class Mode(str, Enum):
    normalE8 = "NormalE8"
    normalE2 = "NormalE2"
    burst128 = "BurstE128"
    burst64 = "BurstE64"
    i_alirt = "I-ALiRT"
    auto = "auto"


class ModeConfig:
    primary_rate = 0
    secondary_rate = 0
    rows_per_packet = 0
    seconds_between_packets = 0
    primary_vectors_per_packet = 0
    secondary_vectors_per_packet = 0
    sequence_counter_increment = 1
    time_delta_format = ".5f"

    def __init__(self, modeOrFileName: Mode | Path, tolerance: float):

        self.tolerance = tolerance

        if isinstance(modeOrFileName, Mode):
            self.mode = modeOrFileName
            if modeOrFileName == Mode.normalE8:
                self.primary_rate = 8
                self.secondary_rate = 8
                self.seconds_between_packets = 4
            if modeOrFileName == Mode.normalE2:
                self.primary_rate = 2
                self.secondary_rate = 2
                self.seconds_between_packets = 8
            elif modeOrFileName == Mode.burst128:
                self.primary_rate = 128
                self.secondary_rate = 128
                self.seconds_between_packets = 2
            elif modeOrFileName == Mode.burst64:
                self.primary_rate = 64
                self.secondary_rate = 64
                self.seconds_between_packets = 2
            elif modeOrFileName == Mode.i_alirt:
                self.primary_rate = 1 / 4
                self.secondary_rate = 1 / 4
                self.seconds_between_packets = 4
                self.sequence_counter_increment = 4
                self.time_delta_format = ".3f"

            if self.tolerance == -1:
                if modeOrFileName == Mode.i_alirt:
                    self.tolerance = (
                        CONSTANTS.DEFAULT_TIME_TOLERANCE_BETWEEN_PACKETS_IALIRT
                    )
                else:
                    self.tolerance = CONSTANTS.DEFAULT_TIME_TOLERANCE_BETWEEN_PACKETS
        else:
            # use regex to parse data_file like
            #    MAGScience-normal-(2,2)-8s-20230922-11h50.csv
            #    MAGScience-burst-(128,128)-2s-20230922-11h50.csv
            match = CONSTANTS.MAG_SCIENCE_FILE_NAMES_V2_REGEX.search(
                str(modeOrFileName)
            )
            if not match:
                raise Exception("Unable to parse mode from file name")

            self.primary_rate = int(match.group(2))
            self.secondary_rate = int(match.group(3))
            self.seconds_between_packets = int(match.group(4))
            self.mode = Mode.auto

        if self.tolerance == -1:
            self.tolerance = CONSTANTS.DEFAULT_TIME_TOLERANCE_BETWEEN_PACKETS

        if self.tolerance < 0:
            raise Exception(
                "Tolerance must be greater than or equal to 0, or -1 for default tolerance."
            )

        self.primary_vectors_per_packet = (
            self.primary_rate * self.seconds_between_packets
        )
        self.secondary_vectors_per_packet = (
            self.secondary_rate * self.seconds_between_packets
        )
        self.rows_per_packet = (
            max(self.primary_rate, self.secondary_rate) * self.seconds_between_packets
        )
