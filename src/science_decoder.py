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


class _ScienceFileWriter:

    def __init__(
        self,
        folder: str,
        modeName: ModeName,
        primaryRate: float,
        secondaryRate: float,
        secsPerPacket: float,
    ):

        self.time_now = datetime.now().strftime("%Y%m%d-%Hh%M")
        self.currentRate = (primaryRate, secondaryRate, secsPerPacket)
        self.filename = None
        self.file = None
        self.isOpen = 0
        self.modeName = modeName
        self.closePending = False
        self.secsPerPacket = secsPerPacket
        self.writer = None
        self.idleTimer = None
        self.base_path = folder

    def _first_write(self, firstPriCoarse, firstPriFine):

        if self.isOpen == 1:
            return

        first_vector_time = float(firstPriCoarse) + (
            float(firstPriFine) / CONSTANTS.MAX_FINE_TIME
        )
        self.data_start_timestamp = get_met_from_shcourse(first_vector_time)

        self.filename = self._generateFileName(
            self.modeName.value,
            self.currentRate[0],
            self.currentRate[1],
            self.currentRate[2],
            self.data_start_timestamp.strftime("%Y%m%d-%Hh%Mm%Ss"),
        )
        exists_already = os.path.isfile(self.filename)
        self.file = open(self.filename, "a")
        self.isOpen = 1
        self.closePending = False
        self.secsPerPacket = self.secsPerPacket
        self.writer = csv.writer(self.file)
        if not exists_already:
            self.writer.writerow(
                [
                    "sequence",
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
                    "compression",
                    "compression_width_bits",
                    "pri_active",
                    "sec_active",
                ]
            )
            print(f"Opened new {self.modeName.value} data file {self.filename}")
        else:
            print(
                f"Appending to existing {self.modeName.value} data file {self.filename}"
            )

    def _generateFileName(
        self, modeName, primaryRate, secondaryRate, secsPerPacket, data_start_timestamp
    ):
        return f"{self.base_path}/MAGScience-{modeName}-({primaryRate},{secondaryRate})-{secsPerPacket}s-{data_start_timestamp}.csv"

    def write(
        self,
        sequence_count,
        primary_vector,
        secondary_vector,
        primary_science_time_coarse,
        primary_science_time_fine,
        secondary_science_time_course,
        secondary_science_time_fine,
        compression,
        compression_width_bits,
        primary_is_active,
        secondary_is_active,
    ):
        if self.isOpen == 0:
            self._first_write(primary_science_time_coarse, primary_science_time_fine)

        assert self.writer is not None

        if self.isOpen == 1:
            self.writer.writerow(
                [
                    sequence_count,
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
                    secondary_science_time_course if secondary_vector else None,
                    secondary_science_time_fine if secondary_vector else None,
                    compression,
                    compression_width_bits,
                    int(primary_is_active),
                    int(secondary_is_active),
                ]
            )

    def flush(self):
        if self.isOpen == 1 and self.file:
            self.file.flush()

    def close(self):
        if self.isOpen == 1:
            if self.file:
                self.file.close()
            self.isOpen = 0
            self.closePending = False
            print(f"Closed {self.modeName.value} data file {self.filename}")

    def rateHasChanged(self, primaryRate, secondaryRate, secsPerPacket):
        return (
            self.isOpen == 1
            and (primaryRate, secondaryRate, secsPerPacket) != self.currentRate
        )


class MAGScienceDecoder:

    class Rates:
        RATE_ONE_VEC_PER_SEC = 0
        RATE_TWO_VEC_PER_SEC = 1
        RATE_FOUR_VEC_PER_SEC = 2
        RATE_EIGHT_VEC_PER_SEC = 3
        RATE_SIXTEEN_VEC_PER_SEC = 4
        RATE_THIRTYTWO_VEC_PER_SEC = 5
        RATE_SIXTYFOUR_VEC_PER_SEC = 6
        RATE_ONETWENTYEIGHT_VEC_PER_SEC = 7

    PRIMARY_SENSOR_IS_FOB = 0
    PRIMARY_SENSOR_IS_FIB = 1

    MAX_COMPRESSION_WIDTH = 20
    SCIENCE_COMPRESSION_REFERENCE_WIDTH_DEFAULT = 16
    AXIS_COUNT = 3
    HDR_VECTOR_WIDTH_THRESHOLD = AXIS_COUNT * MAX_COMPRESSION_WIDTH

    FIBONACCI_SEQUENCE = [
        1,
        2,
        3,
        5,
        8,
        13,
        21,
        34,
        55,
        89,
        144,
        233,
        377,
        610,
        987,
        1597,
        2584,
        4181,
        6765,
        10946,
        17711,
        28657,
        46368,
        75025,
        121393,
        196418,
        317811,
        514229,
        832040,
        1346269,
        2178309,
        3524578,
        5702887,
        9227465,
        14930352,
        24157817,
        39088169,
        63245986,
        102334155,
        165580141,
    ]

    @staticmethod
    def _to_int32(val):
        # TODO: insane to include NP just for this - replace me!
        return np.int32(val)

    @staticmethod
    def _toSigned16(n):
        n = n & 0xFFFF
        return n | (-(n & 0x8000))

    @staticmethod
    def _twos_complement(value: int, bits: int) -> int:
        """Compute the two's complement of an integer

        This function will return the two's complement of a given integer value.
        If the integer with respect to the number of bits does not have a sign bit
        set, then the input value is returned without modification.

        Parameters
        ----------
        value : int
            Non-negative integer
        bits : int
            Number of bits to use for the 2's complement

        Returns
        -------
        int
            two's complement of the input value
        """
        if (value & (1 << (bits - 1))) != 0:
            value = value - (1 << bits)
        return value

    @staticmethod
    def _unpack_value(buffer, bit_cursor, bit_count):
        value = 0
        while bit_count:
            buffer_index = bit_cursor // 8
            bits_unread = 8 - (bit_cursor % 8)
            bit_shift = bit_count - bits_unread
            if bit_shift >= 0:
                read_mask = (1 << bits_unread) - 1
                value += (buffer[buffer_index] & read_mask) << bit_shift
                bit_cursor += bits_unread
                bit_count = bit_shift
            else:
                read_mask = ((1 << bits_unread) - 1) & (0xFF << -bit_shift)
                value += (buffer[buffer_index] & read_mask) >> -bit_shift
                bit_cursor += bit_count
                bit_count = 0
        return (value, bit_cursor)

    @staticmethod
    def _fibonacci_encode(value):
        value += 1
        code_buffer = 1
        code_bits = 0
        for i, fib in zip(
            range(39, -1, -1), MAGScienceDecoder.FIBONACCI_SEQUENCE[::-1]
        ):
            if value < fib:
                continue
            if code_buffer == 1:
                code_bits = i + 2
            code_buffer |= 1 << (code_bits - i - 1)
            value -= fib
        code = f"{code_buffer:0{code_bits}b}"
        return code

    @staticmethod
    def _fibonacci_decode(code):
        code = code[:-1]
        fibonacci_decomposition = [
            MAGScienceDecoder.FIBONACCI_SEQUENCE[i]
            for i, bit in enumerate(code)
            if bit == "1"
        ]
        return sum(fibonacci_decomposition) - 1

    @staticmethod
    def _get_next_fibonacci_code(bit_buffer: str, bit_cursor: int):
        code_start = bit_cursor
        code_length = bit_buffer[bit_cursor:].find("11") + 2
        code = bit_buffer[code_start : code_start + code_length]
        return code, code_start + code_length

    @staticmethod
    def _zigzag_encode(value):
        return (value >> 31) ^ (value << 1)

    @staticmethod
    def _zigzag_decode(code):
        return (code >> 1) ^ -(code & 1)

    @staticmethod
    def _getVectorsPerSecond(outRateId: int):
        if outRateId == MAGScienceDecoder.Rates.RATE_ONE_VEC_PER_SEC:
            return 1
        elif outRateId == MAGScienceDecoder.Rates.RATE_TWO_VEC_PER_SEC:
            return 2
        elif outRateId == MAGScienceDecoder.Rates.RATE_FOUR_VEC_PER_SEC:
            return 4
        elif outRateId == MAGScienceDecoder.Rates.RATE_EIGHT_VEC_PER_SEC:
            return 8
        elif outRateId == MAGScienceDecoder.Rates.RATE_SIXTEEN_VEC_PER_SEC:
            return 16
        elif outRateId == MAGScienceDecoder.Rates.RATE_THIRTYTWO_VEC_PER_SEC:
            return 32
        elif outRateId == MAGScienceDecoder.Rates.RATE_SIXTYFOUR_VEC_PER_SEC:
            return 64
        elif outRateId == MAGScienceDecoder.Rates.RATE_ONETWENTYEIGHT_VEC_PER_SEC:
            return 128
        else:
            raise ValueError(f"Invalid outRateId {outRateId}")

    def __init__(self, folder):
        self._burstWriter = None
        self._normalWriter = None
        self.currentModeName = None | ModeName
        self.base_path = folder
        self.last_burst_time = None
        self.last_normal_time = None

    def extract_packet_to_csv(
        self,
        apId,
        sequence,
        packet_length,
        pus_stype,
        pus_ssubtype,
        pri_coarse,
        pri_fine,
        sec_coarse,
        sec_fine,
        PRI_VECSEC,
        SEC_VECSEC,
        compression,
        fob_is_active,
        fib_is_active,
        pri_sensor,
        vector_data,
    ):
        secs_per_packet = pus_ssubtype + 1
        pri_vecs_per_sec = self._getVectorsPerSecond(PRI_VECSEC)
        sec_vecs_per_sec = self._getVectorsPerSecond(SEC_VECSEC)
        compression_width_bits = 16
        has_range_data_section = False
        self.currentModeName = (
            ModeName.burst if apId == CONSTANTS.APID_MAG_SCIENCE_BM else ModeName.normal
        )
        pri_time_utc = time_util.get_met_from_sci_timestamp(pri_coarse, pri_fine)

        # calc how much data is in this packet
        total_pri_vecs = secs_per_packet * pri_vecs_per_sec
        total_sec_vecs = secs_per_packet * sec_vecs_per_sec
        start_of_VECTORS = 0

        primary_is_active = (
            pri_sensor == MAGScienceDecoder.PRIMARY_SENSOR_IS_FOB and fob_is_active == 1
        ) or (
            pri_sensor == MAGScienceDecoder.PRIMARY_SENSOR_IS_FIB and fib_is_active == 1
        )
        secondary_is_active = (
            pri_sensor == MAGScienceDecoder.PRIMARY_SENSOR_IS_FOB and fib_is_active == 1
        ) or (
            pri_sensor == MAGScienceDecoder.PRIMARY_SENSOR_IS_FIB and fob_is_active == 1
        )

        # check for compression
        if compression:
            compression_width_bits = (vector_data[start_of_VECTORS] >> 2) & 0b111111
            has_range_data_section = (vector_data[start_of_VECTORS] >> 1) & 0b1
            start_of_VECTORS += 1

        vector_data = vector_data[start_of_VECTORS:]

        # build 2 lists of vectors, primary and secondary
        # parse in 50bit chunks, 16+16+16+2 so use repeating parse pattern every 4 vectors based on 8bit aligned bytes
        if compression:
            primaryVectors, secondaryVectors = (
                MAGScienceDecoder._unpackCompressedVectors(
                    total_pri_vecs,
                    total_sec_vecs,
                    vector_data,
                    compression_width_bits,
                    has_range_data_section,
                    pri_coarse,
                    pri_time_utc,
                )
            )
        else:
            primaryVectors, secondaryVectors = (
                MAGScienceDecoder._unpackUncompressedVectors(
                    total_pri_vecs, total_sec_vecs, vector_data
                )
            )

        # close the file if the rate has changed
        if (
            self.currentModeName == ModeName.burst
            and self._burstWriter is not None
            and self._burstWriter.rateHasChanged(
                pri_vecs_per_sec, sec_vecs_per_sec, secs_per_packet
            )
        ):
            print(f"Rate has changed, close {self._burstWriter.filename}")
            self._burstWriter.close()

        if (
            self.currentModeName == ModeName.normal
            and self._normalWriter is not None
            and self._normalWriter.rateHasChanged(
                pri_vecs_per_sec, sec_vecs_per_sec, secs_per_packet
            )
        ):
            print(f"Rate has changed, close {self._normalWriter.filename}")
            self._normalWriter.close()

        new_packet_time = max(pri_coarse, sec_coarse)
        last_packet_time = (
            self.last_burst_time
            if self.currentModeName == ModeName.burst
            else self.last_normal_time
        )
        gap_between_packets = humanise_timedelta(
            (new_packet_time - last_packet_time) if last_packet_time else 0,
            inputtype="s",
        )
        long_gap_between_packets = (
            last_packet_time is not None
            and new_packet_time > last_packet_time + (secs_per_packet * 5)
        )

        if self.currentModeName == ModeName.burst:
            if long_gap_between_packets and self._burstWriter is not None:
                print(
                    f"{gap_between_packets} gap detected in burst data - mode has changed, close {self._burstWriter.filename}"
                )
                self._burstWriter.close()
            self.last_burst_time = new_packet_time
        elif self.currentModeName == ModeName.normal:
            if long_gap_between_packets and self._normalWriter is not None:
                print(
                    f"{gap_between_packets} gap detected in normal data - mode has changed, close {self._normalWriter.filename}"
                )
                self._normalWriter.close()
            self.last_normal_time = new_packet_time

        if self.currentModeName == ModeName.burst and (
            self._burstWriter is None or self._burstWriter.isOpen == 0
        ):
            self._burstWriter = _ScienceFileWriter(
                self.base_path,
                self.currentModeName,
                pri_vecs_per_sec,
                sec_vecs_per_sec,
                secs_per_packet,
            )

        if self.currentModeName == ModeName.normal and (
            self._normalWriter is None or self._normalWriter.isOpen == 0
        ):
            self._normalWriter = _ScienceFileWriter(
                self.base_path,
                self.currentModeName,
                pri_vecs_per_sec,
                sec_vecs_per_sec,
                secs_per_packet,
            )

        # which writer shall we use? based on packet ApId
        writer = (
            self._burstWriter
            if self.currentModeName == ModeName.burst
            else self._normalWriter
        )

        if writer is None:
            raise ValueError(f"No writer found for mode {self.currentModeName}")

        # if mixed rates (like (64,8) we need the bigger of the 2 lengths so wecan put that many rows into the CSV
        maxVectors = max(len(primaryVectors), len(secondaryVectors))
        for i in range(maxVectors):
            primary = primaryVectors[i] if i < len(primaryVectors) else None
            secondary = secondaryVectors[i] if i < len(secondaryVectors) else None
            writer.write(
                sequence,
                primary,
                secondary,
                pri_coarse,
                pri_fine,
                sec_coarse,
                sec_fine,
                compression,
                compression_width_bits,
                primary_is_active,
                secondary_is_active,
            )

        # after each packet make sure everything is written to disk
        writer.flush()

        # close the file if we are now in config mode or have transitioned
        if self._burstWriter is not None and self._burstWriter.closePending:
            self._burstWriter.close()

        if self._normalWriter is not None and self._normalWriter.closePending:
            self._normalWriter.close()

    def close_all(self):
        if self._burstWriter is not None:
            self._burstWriter.close()
        if self._normalWriter is not None:
            self._normalWriter.close()

    @staticmethod
    def _unpackOneVector(vector_data, sci_cursor, width, hasRange):
        x, sci_cursor = MAGScienceDecoder._unpack_value(vector_data, sci_cursor, width)
        y, sci_cursor = MAGScienceDecoder._unpack_value(vector_data, sci_cursor, width)
        z, sci_cursor = MAGScienceDecoder._unpack_value(vector_data, sci_cursor, width)
        rng, sci_cursor = (
            (0, sci_cursor)
            if not (hasRange)
            else MAGScienceDecoder._unpack_value(vector_data, sci_cursor, 2)
        )
        # print(f"Unpacked vector: {x},{y},{z},{rng}")
        return (
            Vector(
                MAGScienceDecoder._twos_complement(x, width),
                MAGScienceDecoder._twos_complement(y, width),
                MAGScienceDecoder._twos_complement(z, width),
                int(rng),
            ),
            sci_cursor,
        )

    @staticmethod
    def _unpackCompressedVectors(
        total_pri_vecs,
        total_sec_vecs,
        vector_data,
        compression_width_bits,
        has_range_data_section,
        pri_coarse,
        pri_time_utc,
    ):
        sci_cursor = 0
        primaryVectors = []
        secondaryVectors = []
        # Extract reference samples  first vectors which are packed full width
        primaryFirstVector, sci_cursor = MAGScienceDecoder._unpackOneVector(
            vector_data, sci_cursor, compression_width_bits, True
        )
        primaryVectors.append(primaryFirstVector)

        # Prepare bit buffer from compressed data to support getting fibonacci codes
        sci_bits = "".join(f"{byte:08b}" for byte in vector_data)

        # Decode PRIMARY samples
        PRI_HDR_FLAG = False
        for i in range(1, total_pri_vecs):
            if PRI_HDR_FLAG:
                vector, sci_cursor = MAGScienceDecoder._unpackOneVector(
                    vector_data, sci_cursor, compression_width_bits, False
                )
            else:
                sci_cursor_start = sci_cursor
                code, sci_cursor = MAGScienceDecoder._get_next_fibonacci_code(
                    sci_bits, sci_cursor
                )
                x = MAGScienceDecoder._zigzag_decode(
                    MAGScienceDecoder._fibonacci_decode(code)
                )
                code, sci_cursor = MAGScienceDecoder._get_next_fibonacci_code(
                    sci_bits, sci_cursor
                )
                y = MAGScienceDecoder._zigzag_decode(
                    MAGScienceDecoder._fibonacci_decode(code)
                )
                code, sci_cursor = MAGScienceDecoder._get_next_fibonacci_code(
                    sci_bits, sci_cursor
                )
                z = MAGScienceDecoder._zigzag_decode(
                    MAGScienceDecoder._fibonacci_decode(code)
                )
                bits_read = sci_cursor - sci_cursor_start
                diffVector = Vector(x, y, z, 0)
                vector = Vector(
                    MAGScienceDecoder._to_int32(primaryVectors[i - 1].x) + diffVector.x,
                    MAGScienceDecoder._to_int32(primaryVectors[i - 1].y) + diffVector.y,
                    MAGScienceDecoder._to_int32(primaryVectors[i - 1].z) + diffVector.z,
                    0,
                )

                if bits_read > MAGScienceDecoder.HDR_VECTOR_WIDTH_THRESHOLD:
                    print(
                        f"NOTE: HDR detected in primary sensor after {i} vectors. Switching to full width. (Primary vector time {pri_coarse} ~ {pri_time_utc.strftime('%Y-%m-%d %H:%M:%S')})"
                    )
                    PRI_HDR_FLAG = True

            primaryVectors.append(vector)

        secondaryFirstVector, sci_cursor = MAGScienceDecoder._unpackOneVector(
            vector_data, sci_cursor, compression_width_bits, True
        )
        secondaryVectors.append(secondaryFirstVector)

        SEC_HDR_FLAG = False
        for i in range(1, total_sec_vecs):
            if SEC_HDR_FLAG:
                vector, sci_cursor = MAGScienceDecoder._unpackOneVector(
                    vector_data, sci_cursor, compression_width_bits, False
                )
            else:
                sci_cursor_start = sci_cursor
                code, sci_cursor = MAGScienceDecoder._get_next_fibonacci_code(
                    sci_bits, sci_cursor
                )
                x = MAGScienceDecoder._zigzag_decode(
                    MAGScienceDecoder._fibonacci_decode(code)
                )
                code, sci_cursor = MAGScienceDecoder._get_next_fibonacci_code(
                    sci_bits, sci_cursor
                )
                y = MAGScienceDecoder._zigzag_decode(
                    MAGScienceDecoder._fibonacci_decode(code)
                )
                code, sci_cursor = MAGScienceDecoder._get_next_fibonacci_code(
                    sci_bits, sci_cursor
                )
                z = MAGScienceDecoder._zigzag_decode(
                    MAGScienceDecoder._fibonacci_decode(code)
                )
                bits_read = sci_cursor - sci_cursor_start
                diffVector = Vector(x, y, z, 0)
                vector = Vector(
                    MAGScienceDecoder._to_int32(secondaryVectors[i - 1].x)
                    + diffVector.x,
                    MAGScienceDecoder._to_int32(secondaryVectors[i - 1].y)
                    + diffVector.y,
                    MAGScienceDecoder._to_int32(secondaryVectors[i - 1].z)
                    + diffVector.z,
                    0,
                )

                if bits_read > MAGScienceDecoder.HDR_VECTOR_WIDTH_THRESHOLD:
                    print(
                        f"NOTE: HDR detected in secondary sensor after {i} vectors. Switching to full width. (Primary vector time {pri_coarse} ~ {pri_time_utc.strftime('%Y-%m-%d %H:%M:%S')})"
                    )
                    SEC_HDR_FLAG = True

            secondaryVectors.append(vector)

        # Add range to the samples
        if has_range_data_section:
            # unpack the range data and fill in the vectors with the range
            sci_cursor = (sci_cursor + 7) & 0xFFFFFFF8
            for i in range(1, total_pri_vecs):
                rng, sci_cursor = MAGScienceDecoder._unpack_value(
                    vector_data, sci_cursor, 2
                )
                primaryVectors[i] = primaryVectors[i]._replace(rng=int(rng))
            for i in range(1, total_sec_vecs):
                rng, sci_cursor = MAGScienceDecoder._unpack_value(
                    vector_data, sci_cursor, 2
                )
                secondaryVectors[i] = secondaryVectors[i]._replace(rng=int(rng))
        else:
            # copy the range from the first vector as range has been static for the entire packet
            for i in range(1, total_pri_vecs):
                primaryVectors[i] = primaryVectors[i]._replace(
                    rng=primaryVectors[0].rng
                )
            for i in range(1, total_sec_vecs):
                secondaryVectors[i] = secondaryVectors[i]._replace(
                    rng=secondaryVectors[0].rng
                )

        return primaryVectors, secondaryVectors

    @staticmethod
    def _unpackUncompressedVectors(total_pri_vecs, total_sec_vecs, vector_data):
        pos = 0
        primaryVectors = []
        secondaryVectors = []
        for i in range(total_pri_vecs + total_sec_vecs):  # 0..63 say
            x, y, z, rng = 0, 0, 0, 0
            if i % 4 == 0:  # start at bit 0, take 8 bits + 8bits
                # pos = 0, 25, 50...
                x = (
                    ((vector_data[pos + 0] & 0xFF) << 8)
                    | ((vector_data[pos + 1] & 0xFF) << 0)
                ) & 0xFFFF
                y = (
                    ((vector_data[pos + 2] & 0xFF) << 8)
                    | ((vector_data[pos + 3] & 0xFF) << 0)
                ) & 0xFFFF
                z = (
                    ((vector_data[pos + 4] & 0xFF) << 8)
                    | ((vector_data[pos + 5] & 0xFF) << 0)
                ) & 0xFFFF
                rng = (vector_data[pos + 6] >> 6) & 0x3
                pos += 6
            elif i % 4 == 1:  # start at bit 2, take 6 bits, 8 bit, 2 bits per vector
                # pos = 6, 31...
                x = (
                    ((vector_data[pos + 0] & 0x3F) << 10)
                    | ((vector_data[pos + 1] & 0xFF) << 2)
                    | ((vector_data[pos + 2] >> 6) & 0x03)
                ) & 0xFFFF
                y = (
                    ((vector_data[pos + 2] & 0x3F) << 10)
                    | ((vector_data[pos + 3] & 0xFF) << 2)
                    | ((vector_data[pos + 4] >> 6) & 0x03)
                ) & 0xFFFF
                z = (
                    ((vector_data[pos + 4] & 0x3F) << 10)
                    | ((vector_data[pos + 5] & 0xFF) << 2)
                    | ((vector_data[pos + 6] >> 6) & 0x03)
                ) & 0xFFFF
                rng = (vector_data[pos + 6] >> 4) & 0x3
                pos += 6
            elif i % 4 == 2:  # start at bit 4, take 4 bits, 8 bits, 4 bits per vector
                # pos = 12, 37...
                x = (
                    ((vector_data[pos + 0] & 0x0F) << 12)
                    | ((vector_data[pos + 1] & 0xFF) << 4)
                    | ((vector_data[pos + 2] >> 4) & 0x0F)
                ) & 0xFFFF
                y = (
                    ((vector_data[pos + 2] & 0x0F) << 12)
                    | ((vector_data[pos + 3] & 0xFF) << 4)
                    | ((vector_data[pos + 4] >> 4) & 0x0F)
                ) & 0xFFFF
                z = (
                    ((vector_data[pos + 4] & 0x0F) << 12)
                    | ((vector_data[pos + 5] & 0xFF) << 4)
                    | ((vector_data[pos + 6] >> 4) & 0x0F)
                ) & 0xFFFF
                rng = (vector_data[pos + 6] >> 2) & 0x3
                pos += 6
            elif i % 4 == 3:  # start at bit 6, take 2 bits, 8 bits, 6 bits per vector
                # pos = 18, 43...
                x = (
                    ((vector_data[pos + 0] & 0x03) << 14)
                    | ((vector_data[pos + 1] & 0xFF) << 6)
                    | ((vector_data[pos + 2] >> 2) & 0x3F)
                ) & 0xFFFF
                y = (
                    ((vector_data[pos + 2] & 0x03) << 14)
                    | ((vector_data[pos + 3] & 0xFF) << 6)
                    | ((vector_data[pos + 4] >> 2) & 0x3F)
                ) & 0xFFFF
                z = (
                    ((vector_data[pos + 4] & 0x03) << 14)
                    | ((vector_data[pos + 5] & 0xFF) << 6)
                    | ((vector_data[pos + 6] >> 2) & 0x3F)
                ) & 0xFFFF
                rng = (vector_data[pos + 6] >> 0) & 0x3
                pos += 7

            vector = Vector(
                MAGScienceDecoder._toSigned16(x),
                MAGScienceDecoder._toSigned16(y),
                MAGScienceDecoder._toSigned16(z),
                rng,
            )

            if i < total_pri_vecs:
                primaryVectors.append(vector)
            else:
                secondaryVectors.append(vector)
        return primaryVectors, secondaryVectors
