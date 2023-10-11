from enum import Enum
import re


class Constants:
    magScienceFileNamev2Regex = re.compile(r"MAG\w+-(\w+)-\(([0-9]+),([0-9]+)\)-([0-9]+)s-\w+-\w+", re.IGNORECASE | re.MULTILINE)


class Mode(str, Enum):
    normalE8 = "NormalE8"
    normalE2 = "NormalE2"
    burst128 = "BurstE128"
    burst64 = "BurstE64"
    unknown = "?"


class ModeConfig:
    primary_rate = 0
    secondary_rate = 0
    rows_per_packet = 0
    seconds_between_packets = 0

    def __init__(self, modeOrFileName: Mode | str):
        if isinstance(modeOrFileName, Mode):

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
        else:
            # use regex to parse data_file like
            #    MAGScience-normal-(2,2)-8s-20230922-11h50.csv
            #    MAGScience-burst-(128,128)-2s-20230922-11h50.csv
            match = Constants.magScienceFileNamev2Regex.search(modeOrFileName)
            if not match:
                raise Exception("Unable to parse mode from file name")

            self.primary_rate = int(match.group(2))
            self.secondary_rate = int(match.group(3))
            self.seconds_between_packets = int(match.group(4))

        self.rows_per_packet = max(self.primary_rate, self.secondary_rate) * self.seconds_between_packets
