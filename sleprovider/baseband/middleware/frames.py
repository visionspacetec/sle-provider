import logging; logging.basicConfig(level=logging.DEBUG); logger = logging.getLogger(__name__)
import array
import struct
import traceback
from collections import OrderedDict
from datetime import datetime
from enum import Enum
from bitstring import BitArray

class SpacePacket(dict):

    def __init__(self, data=None):
        super().__init__()
        self._data = None
        if data:
            self._data = data

    def decode(self, data):
        raise NotImplementedError

    def encode(self):
        if self._data:
            return self._data
        space_packet = BitArray()
        space_packet.append(format(self['version'], '#05b'))
        space_packet.append(format(self['type'], '#03b'))
        space_packet.append(format(self['sec_header_flag'], '#03b'))
        space_packet.append(self['apid'])
        space_packet.append(format(self['sequence_flags'], '#04b'))
        space_packet.append(format(self['seq_ctr_or_pkt_name'], '#016b'))
        space_packet.append(format(int(self['data'].length / 8) - 1, '#018b'))
        # ToDo: Implement secondary header with timestamp
        if self['sec_header_flag']:
            raise NotImplementedError
        space_packet.append(self['data'])
        return space_packet


def calculate_fecf(byte_array):
    shift_register = 0x0000FFFF
    polynomial = 0x00001021
    array_size = len(byte_array)
    index = 0
    while index < array_size:
        next_byte = byte_array[index]
        bit_number = 7
        while bit_number >= 0:
            mask = (1 << bit_number)
            if (next_byte & mask) > 0:
                h = 0x00010000
            else:
                h = 0
            shift_register <<= 1
            if (h ^ (shift_register & 0x00010000)) > 0:
                shift_register ^= polynomial
            bit_number -= 1
        index += 1
    return shift_register & 0x0000FFFF


class TelemetryTransferFrame(dict):

    def __init__(self, data=None, frame_error_control_field=False, space_packet=None):
        super().__init__()
        self._data = []
        self.has_fecf = frame_error_control_field
        self.is_idle = False
        self.has_no_pkts = False
        self.space_packet = space_packet
        if data:
            self.decode(data)
            self._data = data
            self.length = int(len(data[2:])/2)

    def decode(self, data):
        """Decode data as a TM Transfer Frame"""
        hdr = BitArray(data[:14])
        self['version'] = hdr[0:2].uint
        self['spacecraft_id'] = hdr[2:12].uint
        self['virtual_channel_id'] = hdr[12:15].uint
        self['ocf_flag'] = hdr[15]
        self['master_chan_frame_count'] = hdr[16:24].uint
        self['virtual_chan_frame_count'] = hdr[24:32].uint
        self['sec_header_flag'] = hdr[32]
        self['sync_flag'] = hdr[33]
        self['pkt_order_flag'] = hdr[34]
        self['seg_len_id'] = hdr[35:37].uint
        self['first_hdr_ptr'] = hdr[37:48].uint

        if self['ocf_flag']:
            if self.has_fecf:
                self['ocf'] = BitArray('0x' + data[-12:-4])
            else:
                self['ocf'] = BitArray('0x' + data[-8:])

        if self.has_fecf:
            self['fecf'] = BitArray('0x' + data[-4:])

        # idle frame received
        if self['first_hdr_ptr'] == int('11111111110', 2):
            self.is_idle = True
            return

        if self['first_hdr_ptr'] == int('11111111111', 2):
            self.has_no_pkts = True
            return

        if self['sec_header_flag']:
            raise NotImplementedError

    def encode(self):
        tm_frame = BitArray()
        tm_frame.append(format(self['version'], '#04b'))
        tm_frame.append(format(self['spacecraft_id'], '#012b'))
        tm_frame.append(format(self['virtual_channel_id'], '#05b'))
        tm_frame.append(format(self['ocf_flag'], '#03b'))
        tm_frame.append(format(self['master_chan_frame_count'], '#010b'))
        tm_frame.append(format(self['virtual_chan_frame_count'], '#010b'))
        tm_frame.append(format(self['sec_header_flag'], '#03b'))
        tm_frame.append(format(self['sync_flag'], '#03b'))
        tm_frame.append(format(self['pkt_order_flag'], '#03b'))
        tm_frame.append(format(self['seg_len_id'], '#04b'))
        tm_frame.append(format(self['first_hdr_ptr'], '#013b'))

        if self['sec_header_flag']:
            raise NotImplementedError
        offset = tm_frame.length
        if self['ocf_flag']:
            offset += 32
        if self.has_fecf:
            offset += 16
        if self.has_no_pkts is True:
            tm_frame.append(format(0, '#0{}b'.format((self.length * 8 - offset) + 2)))
        elif self.is_idle is True:
            idle_space_packet = SpacePacket()
            idle_space_packet['version'] = 0
            idle_space_packet['type'] = 0
            idle_space_packet['sec_header_flag'] = False
            idle_space_packet['apid'] = BitArray('0b11111111111')
            idle_space_packet['sequence_flags'] = 3
            idle_space_packet['seq_ctr_or_pkt_name'] = 0
            idle_space_packet['data'] = BitArray(format(0, '#0{}b'.format((self.length * 8 - offset) + 2)))
            idle_space_packet = idle_space_packet.encode()
            tm_frame.append(idle_space_packet)
        else:
            space_packet = self.space_packet.encode()
            tm_frame.append(space_packet)
            offset += space_packet.length
            idle_space_packet = SpacePacket()
            idle_space_packet['version'] = 0
            idle_space_packet['type'] = 0
            idle_space_packet['sec_header_flag'] = False
            idle_space_packet['apid'] = BitArray('0b11111111111')
            idle_space_packet['sequence_flags'] = 3
            idle_space_packet['seq_ctr_or_pkt_name'] = 0
            offset += 6 * 8
            idle_space_packet['data'] = BitArray(format(0, '#0{}b'.format((self.length * 8 - offset) + 2)))
            idle_space_packet = idle_space_packet.encode()
            tm_frame.append(idle_space_packet)
        if self['ocf_flag']:
            tm_frame.append(self['ocf'])
        if self.has_fecf:
            self['fecf'] = format(calculate_fecf(bytearray.fromhex(tm_frame.hex)), '#018b')
            tm_frame.append(self['fecf'])
        return tm_frame.hex


# All code below this line is based upon sources provided by Dominik Marszk

# Used for some heuristics to detect already descrambled frames
GOOD_SOURCE_NODES = [1, 2, 3, 4, 5, 6, 7]
GOOD_DST_NODES = [10, 11, 12, 13, 14, 15]
GOOD_SOURCE_PORTS = [0, 1, 7]
MAL_DST_PORT = 10
GOOD_DST_PORTS = [MAL_DST_PORT]

AX25_HEADER_LEN = 16

RPARAM_CSP_PORT = 7
PING_CSP_PORT = 1
MAL_CSP_PORT = 10

INIT_NODES_LIST = [1, 2, 3, 4, 5, 6, 7]
MAX_PARAM_NAME_LEN = 14
PARAM_DEF_FORMAT = "<H 4B {}s".format(MAX_PARAM_NAME_LEN)
PARAM_DEF_SIZE = struct.calcsize(PARAM_DEF_FORMAT)

# RPARAM_ACTION
RPARAM_GET = 0x00
RPARAM_REPLY = 0x55
RPARAM_SET = 0xFF
RPARAM_SET_TO_FILE = 0xEE
RPARAM_TABLE = 0x44
RPARAM_COPY = 0x77
RPARAM_LOAD = 0x88
RPARAM_SAVE = 0x99
RPARAM_CLEAR = 0xAA

# RPARAM_REPLY
RPARAM_SET_OK = 1
RPARAM_LOAD_OK = 2
RPARAM_SAVE_OK = 3
RPARAM_COPY_OK = 4
RPARAM_CLEAR_OK = 5
RPARAM_ERROR = 0xFF

TYPES_MAP = {
    0: {"size": 1, "format": "B"},  # PARAM_UINT8,
    1: {"size": 2, "format": "H"},  # PARAM_UINT16,
    2: {"size": 4, "format": "L"},  # PARAM_UINT32,
    3: {"size": 8, "format": "Q"},  # PARAM_UINT64,
    4: {"size": 1, "format": "b"},  # PARAM_INT8,
    5: {"size": 2, "format": "h"},  # PARAM_INT16,
    6: {"size": 4, "format": "l"},  # PARAM_INT32,
    7: {"size": 8, "format": "q"},  # PARAM_INT64,
    8: {"size": 1, "format": "B"},  # PARAM_X8,
    9: {"size": 2, "format": "H"},  # PARAM_X16,
    10: {"size": 4, "format": "L"},  # PARAM_X32,
    11: {"size": 8, "format": "Q"},  # PARAM_X64,
    12: {"size": 8, "format": "d"},  # PARAM_DOUBLE,
    13: {"size": 4, "format": "f"},  # PARAM_FLOAT,
    14: {"size": 1, "format": "s"},  # PARAM_STRING,
    15: {"size": 1, "format": "B"},  # PARAM_DATA,
}


class CSP(object):
    """
    Reused from:
    https://github.com/daniestevez/gr-satellites/blob/master/python/csp_header.py
    """

    def __init__(self, csp_bytes, timestamp=datetime(1234, 1, 1), metadata={}):
        if len(csp_bytes) < 4:
            raise ValueError("Malformed CSP packet (too short)")
        self.csp_bytes = csp_bytes
        csp = struct.unpack(">I", csp_bytes[0:4])[0]
        self.priority = (csp >> 30) & 0x3
        self.source = (csp >> 25) & 0x1f
        self.destination = (csp >> 20) & 0x1f
        self.dest_port = (csp >> 14) & 0x3f
        self.source_port = (csp >> 8) & 0x3f
        self.reserved = (csp >> 4) & 0xf
        self.hmac = (csp >> 3) & 1
        self.xtea = (csp >> 2) & 1
        self.rdp = (csp >> 1) & 1
        self.crc = csp & 1
        self.flags=int('{HMAC}{XTEA}{RDP}{CRC}'.format(HMAC=self.hmac, XTEA=self.xtea, RDP=self.rdp, CRC=self.crc))
        self.payload = self.csp_bytes[4:]
        self.timestamp = timestamp
        self.metadata = metadata

    def __str__(self):
        return ("""CSP header:
        Priority:\t\t{}
        Source:\t\t\t{}
        Destination:\t\t{}
        Destination port:\t{}
        Source port:\t\t{}
        Reserved field:\t\t{}
        HMAC:\t\t\t{}
        XTEA:\t\t\t{}
        RDP:\t\t\t{}
        CRC:\t\t\t{}
        length (with hdr):\t{}
        timestamp:\t\t{}
        payload:\t\t{}
-----------------------------------------""".format(
            self.priority, self.source, self.destination, self.dest_port,
            self.source_port, self.reserved, self.hmac, self.xtea, self.rdp,
            self.crc, self.get_length(), self.timestamp.strftime("%Y/%m/%d %H:%M:%S"), self.payload.hex()))

    def to_dict(self):
        return OrderedDict(
            [
                ("timestamp", self.timestamp.strftime("%Y/%m/%d %H:%M:%S")),
                ("csp_priority", self.priority),
                ("csp_source", self.source),
                ("csp_destination", self.destination),
                ("csp_dest_port", self.dest_port),
                ("csp_source_port", self.source_port),
                ("csp_reserved", self.reserved),
                ("csp_hmac", self.hmac),
                ("csp_xtea", self.xtea),
                ("csp_rdp", self.rdp),
                ("csp_crc", self.crc),
                ("csp_total_len", self.get_length()),
                ("csp_payload_len", len(self.payload)),
                ("csp_payload", self.payload.hex())
            ]
        )

    def get_length(self):
        return len(self.csp_bytes)

    def get_hex(self):
        return self.csp_bytes.hex()


def get_printable_ascii_str(s, unprintable_chars='show'):
    filtered_parts = []
    # remove null padding and replace non-printable characters
    for c in s:
        if 128 > c >= 32:
            filtered_parts.append(chr(c))
        elif c != 0:
            if unprintable_chars == 'show':
                filtered_parts.append("{{x{:02x}}}".format(c))
            elif unprintable_chars == 'ignore':
                pass
            else:
                filtered_parts.append(unprintable_chars)
    return "".join(filtered_parts)


class ProcessingError(Exception):
    pass


class FrameLevel(Enum):
    BAD_FRAME = 1
    SCRAMBLED = 2
    DESCRAMBLED_GOOD = 3
    DESCRAMBLED_ENDIAN_SWAP = 4


def pop_count(x):
    r = x - ((x >> 1) & 0o33333333333) - ((x >> 2) & 0o11111111111)
    return ((r + (r >> 3)) & 0o30707070707) % 63


class LFSR:
    def __init__(self, mask, seed, shift_len):
        self.mask = mask
        self.reg = seed
        self.shift_len = shift_len

    def next_bit(self):
        output = self.reg & 1
        newbit = pop_count(self.reg & self.mask) & 1
        self.reg = ((self.reg >> 1) | (newbit << self.shift_len))
        return output

    def next_byte(self):
        output = self.reg & 0xFF
        for _ in range(8):
            self.next_bit()
        return output


def parse_ax25_address(buf):
    return array.array("B", map(lambda c: c >> 1, buf)).tobytes().decode("ascii").rstrip(" ")


def parse_ax25_header(buf):
    if len(buf) != AX25_HEADER_LEN:
        raise ProcessingError("Malformed AX25 header (")
    header = OrderedDict()
    header["to"] = parse_ax25_address(buf[:6])
    header["to_ssid"] = (buf[6] & 0x0f)
    header["from"] = parse_ax25_address(buf[7:13])
    header["from_ssid"] = (buf[13] & 0x0f)
    header["ctrl"] = buf[14]
    header["pid"] = buf[15]
    return header


def reverse_byte(byte):
    return int('{:08b}'.format(byte)[::-1], 2) & 0xFF


def descramble(buf):
    L = LFSR(0xA9, 0xFF, 7)
    out = bytearray()
    for b in buf:
        # Start from MSB
        descrambled = reverse_byte(reverse_byte(b) ^ L.next_byte())
        out.append(descrambled)
    return out


def frame_looks_good(csp):
    if (csp.source in GOOD_SOURCE_NODES
            and (csp.dest_port in GOOD_DST_PORTS or csp.source_port in GOOD_SOURCE_PORTS)
            and csp.destination in GOOD_DST_NODES):
        return True
    return False


# Apply some heuristics to check whether the frame looks sane w/o descramble and whether it needs endian swap
def detect_frame_level(buf):
    if frame_looks_good(CSP(buf[:4])):
        return FrameLevel.DESCRAMBLED_GOOD
    elif frame_looks_good(CSP(buf[:4][::-1])):
        return FrameLevel.DESCRAMBLED_ENDIAN_SWAP
    elif frame_looks_good(CSP(descramble(buf[:4]))):
        return FrameLevel.SCRAMBLED
    return FrameLevel.BAD_FRAME


def process_ax25_frame(frame, callsign):
    ax25_buf = frame["data"]
    if len(ax25_buf) < AX25_HEADER_LEN:
        raise ProcessingError("AX.25 Frame shorter than minimum of {} bytes".format(AX25_HEADER_LEN))
    header = parse_ax25_header(ax25_buf[:AX25_HEADER_LEN])
    if header["from"] != callsign:
        raise ProcessingError("AX.25 Header has an unexpected callsign: {}".format(header))
    payload = ax25_buf[AX25_HEADER_LEN:]
    try:
        frame_level = detect_frame_level(payload)
        if frame_level == FrameLevel.SCRAMBLED:
            descrambled = descramble(payload)
            # Remove R-S block and CRC - ToDo: perform actual decoding?
            descrambled = descrambled[:-36]
        elif frame_level == FrameLevel.DESCRAMBLED_GOOD:
            # Assume frame is already ready descrambled and FEC+CRC processed
            descrambled = payload
        elif frame_level == FrameLevel.DESCRAMBLED_ENDIAN_SWAP:
            descrambled = bytearray(payload)
            descrambled[:4] = payload[:4][::-1]
            descrambled = bytes(descrambled)
        elif frame_level == FrameLevel.BAD_FRAME:
            raise ProcessingError(
                "Unrecognized CSP frame detected.\nScrambled:\n\n{}\n\nDescrambled:\n\n{}".format(CSP(payload),
                                                                                                  CSP(descramble(payload)))
            )

        csp = CSP(descrambled, frame["timestamp"], frame)
    except ValueError as err:
        raise ProcessingError("Error '{}' when extracting CSP from AX25 frame: {}".format(err, header))
    return csp


def sort_frame(tm_frame, ordered_fields):
    out = OrderedDict()
    for field in ordered_fields:
        if field in tm_frame:
            out[field] = tm_frame[field]
    return out


class param_def(object):
    def __init__(self, buf, node, mem):
        self.node = node
        self.mem = mem
        self.addr, self.type, self.size, \
            self.count, self.flags, self.name \
            = struct.unpack(PARAM_DEF_FORMAT, buf)
        self.name = str(self.name, "ascii").strip('\x00') # Strip any zeroes
        if self.type not in TYPES_MAP:
            self.type %= 16

    def __str__(self):
        return ", ".join("%s: %s" % item for item in vars(self).items())

    def printable_str(self):
        if self.count == 0:
            return ["{}-{}[0x{:03x}] {}".format(self.node, self.mem, self.addr, self.name)]
        else:
            ret = []
            for i in range(0, self.count):
                ret.append("{}-{}[0x{:03x}] {}[{}]".format(self.node, self.mem, self.addr, self.name, i))
            return ret


def is_csp_beacon(csp):
    if (
            csp.priority == 3
            and csp.source == 5
            and csp.destination == 10
            and csp.dest_port == 31
            and csp.source_port == 0
            and csp.get_length() == 58
    ):
        return True
    else:
        return False


class csp_tm_parser(object):

    def __init__(self):
        pass

    def get_tm(self, csp):
        tm = OrderedDict()
        tm["type"] = "unknown"
        try:
            if is_csp_beacon(csp):
                tm["type"] = "beacon"
            elif csp.source_port == RPARAM_CSP_PORT:
                tm["type"] = "rparam_unknown"
            elif csp.source_port == PING_CSP_PORT:
                tm["type"] = "ping"
            elif csp.dest_port == MAL_CSP_PORT:
                tm["type"] = "malspp"
            else:
                logger.info("Could not retrieve TM from CSP frame. Storing unparsed CSP: {}".format(csp))
        except (struct.error, ProcessingError) as err:
            logger.info("Error when extracting the telemetry: {}\n{}".format(err, traceback.format_exc()))
            tm["type"] = "error"
        return tm


def ax25_csp_to_spp(ax25_frame):

    try:
        csp_frame = process_ax25_frame(ax25_frame, callsign="DP0OPS")
    except ProcessingError as err:
        logger.info("Error '{}' when processing the frame {}".format(str(err), str(ax25_frame)))

    csp_parser = csp_tm_parser()
    tm_frame = OrderedDict()
    tm_frame.update([
        ("timestamp", csp_frame.timestamp.strftime("%Y/%m/%d %H:%M:%S"))
    ])
    tm_frame.update(csp_parser.get_tm(csp_frame))
    if not tm_frame:
        logger.info("Frame dropped: Could not retrieve TM from CSP")
    elif tm_frame["type"] == "malspp":
        logger.info("Frame sent: Retrieved TM from CSP with SPP inside")
        return csp_frame.payload
    else:
        logger.info("Frame dropped: Retrieved TM from CSP but no SPP inside")
    return None
