import re

import ccsdspy
from ccsdspy import PacketField
from ccsdspy.packet_fields import PacketArray


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


def get_imap_basic_packet_def():
    return ccsdspy.FixedLength(
        [
            PacketField(name="SHCOARSE", data_type="uint", bit_length=32),
        ]
    )


def get_imap_science_packet_def():
    return ccsdspy.VariableLength(
        [
            PacketField(name="SHCOARSE", data_type="uint", bit_length=32),
            PacketField(name="PUS_SPARE1", data_type="fill", bit_length=1),
            PacketField(name="PUS_VERSION", data_type="uint", bit_length=3),
            PacketField(name="PUS_SPARE2", data_type="fill", bit_length=4),
            PacketField(name="PUS_STYPE", data_type="uint", bit_length=8),
            PacketField(
                name="PUS_SSUBTYPE",
                data_type="uint",
                bit_length=8,
            ),
            PacketField(
                name="COMPRESSION",
                data_type="uint",
                bit_length=1,
            ),
            PacketField(
                name="FOB_ACT",
                data_type="uint",
                bit_length=1,
            ),
            PacketField(
                name="FIB_ACT",
                data_type="uint",
                bit_length=1,
            ),
            PacketField(
                name="PRI_SENS",
                data_type="uint",
                bit_length=1,
            ),
            PacketField(name="SPARE1", data_type="fill", bit_length=4),
            PacketField(
                name="PRI_VECSEC",
                data_type="uint",
                bit_length=3,
            ),
            PacketField(
                name="SEC_VECSEC",
                data_type="uint",
                bit_length=3,
            ),
            PacketField(name="SPARE2", data_type="fill", bit_length=2),
            PacketField(name="PRI_COARSETM", data_type="uint", bit_length=32),
            PacketField(
                name="PRI_FNTM",
                data_type="uint",
                bit_length=16,
            ),
            PacketField(
                name="SEC_COARSETM",
                data_type="uint",
                bit_length=32,
            ),
            PacketField(
                name="SEC_FNTM",
                data_type="uint",
                bit_length=16,
            ),
            PacketArray(
                name="VECTOR_DATA",
                data_type="uint",
                bit_length=8,
                array_shape="expand",  # makes the data field expand to fill the remaining bytes
            ),
        ]
    )


def get_imap_science_packet_headers_only_def():
    return ccsdspy.FixedLength(
        [
            PacketField(name="SHCOARSE", data_type="uint", bit_length=32),
            PacketField(
                name="PUS_SSUBTYPE", data_type="uint", bit_length=8, bit_offset=96
            ),
            PacketField(
                name="COMPRESSION", data_type="uint", bit_length=1, bit_offset=104
            ),
            PacketField(name="FOB_ACT", data_type="uint", bit_length=1, bit_offset=105),
            PacketField(name="FIB_ACT", data_type="uint", bit_length=1, bit_offset=106),
            PacketField(
                name="PRI_SENS", data_type="uint", bit_length=1, bit_offset=107
            ),
            PacketField(
                name="PRI_VECSEC", data_type="uint", bit_length=3, bit_offset=112
            ),
            PacketField(
                name="SEC_VECSEC", data_type="uint", bit_length=3, bit_offset=115
            ),
            PacketField(
                name="PRI_COARSETM", data_type="uint", bit_length=32, bit_offset=120
            ),
            PacketField(
                name="PRI_FNTM", data_type="uint", bit_length=16, bit_offset=152
            ),
            PacketField(
                name="SEC_COARSETM", data_type="uint", bit_length=32, bit_offset=168
            ),
            PacketField(
                name="SEC_FNTM", data_type="uint", bit_length=16, bit_offset=200
            ),
        ]
    )
