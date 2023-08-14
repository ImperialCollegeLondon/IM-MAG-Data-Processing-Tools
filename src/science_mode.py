from enum import Enum


class Mode(str, Enum):
    normal = "NormalE8"
    burst128 = "BurstE128"
    burst64 = "BurstE64"
    unknown = "?"


class ModeConfig:
    vectors_per_packet = 0
    seconds_between_packets = 0

    def __init__(self, mode: Mode):
        if mode == Mode.normal:
            self.vectors_per_packet = 32
            self.seconds_between_packets = 4
        elif mode == Mode.burst128:
            self.vectors_per_packet = 256
            self.seconds_between_packets = 2
        elif mode == Mode.burst64:
            self.vectors_per_packet = 256
            self.seconds_between_packets = 2
