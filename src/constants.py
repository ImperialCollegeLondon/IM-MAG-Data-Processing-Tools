import re
from datetime import datetime, timezone


class CONSTANTS:
    TOO_MANY_ROWS = "Packet has too many rows"
    VECTORS_ALL_ZERO = "Vectors are all zero"
    NONE_SEQUENTIAL = "Non sequential packet"
    PACKET_INCOMPLETE = "packet is incomplete"
    EXPECTED_NUMERIC_FORMAT = "Expected line {line_count} to have a numeric"
    EXPECTED_NUMERIC_MATCH_REGEX = "Expected line [0-9]+ to have a numeric"
    SEQUENCE_NUMBERS_VARY = "Sequence numbers vary within packet"
    RANGE_IS_INVALID = "Range value is out of range"
    VECTORS_NON_EMPTY = "Vectors are non-empty"
    PACKET_TOO_BIG = "packet is too big"
    TIMESTAMP = "timestamp"
    DEFAULT_TIME_TOLERANCE_BETWEEN_PACKETS = 0.00059  # 7.5% of the vector cadence (req is 10%), so (1/128) * 0.075 = 0.0005859375s
    DEFAULT_TIME_TOLERANCE_BETWEEN_PACKETS_IALIRT = 0.05
    MAG_SCIENCE_FILE_NAMES_V2_REGEX = re.compile(
        r"MAG\w+-(\w+)-\(([0-9]+),([0-9]+)\)-([0-9]+)s-\w+-\w+",
        re.IGNORECASE | re.MULTILINE,
    )
    IMAP_EPOCH = datetime(2010, 1, 1, 0, 0, 0, 0, tzinfo=timezone.utc)
    APID_MAG_START = 0x3E0
    APID_MAG_END = 0x45F
    APID_MAG_SCIENCE_NM = 0x41C
    APID_MAG_SCIENCE_BM = 0x42C

    MAX_FINE_TIME = 65536  # 2^16
