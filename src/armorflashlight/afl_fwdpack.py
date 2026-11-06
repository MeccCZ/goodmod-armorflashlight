# uncompyle6 version 3.7.4
# Python bytecode 2.7 (62211)
# Decompiled from: Python 3.10.6 (tags/v3.10.6:9c7b4bd, Aug  1 2022, 21:53:49) [MSC v.1932 64 bit (AMD64)]
# Embedded file name: scripts/client/gui/mods/armorflashlight/afl_fwdpack.py
# Compiled at: 2026-01-01 04:00:00
import struct
CONTAINERS = 'AXYZW'
PAYLOAD_BITS = 30
FIELDS = (
 ('cal', 'A', 10),
 ('fol', 'A', 1),
 ('mode', 'A', 5),
 ('qual', 'A', 2),
 ('alpha', 'A', 5),
 ('rh', 'A', 7),
 ('yaw', 'X', 17),
 ('cls', 'X', 3),
 ('rnd', 'X', 4),
 ('pitch', 'Y', 17),
 ('norm', 'Y', 4),
 ('vy', 'Y', 9),
 ('pp', 'Z', 14),
 ('muz', 'Z', 1),
 ('thr', 'Z', 1),
 ('rcos', 'Z', 5),
 ('vx', 'Z', 9),
 ('ndcx', 'W', 11),
 ('ndcy', 'W', 11),
 ('vz', 'W', 8))
V_RANGE = 32.0
RH_MAX = 0.3
YAW_BITS = 17

def _layout():
    shifts, used = {}, dict((c, 0) for c in CONTAINERS)
    for name, c, n in FIELDS:
        shifts[name] = (
         c, used[c], n)
        used[c] += n

    for c, u in used.items():
        if u > PAYLOAD_BITS:
            raise ValueError('container %s holds %d bits (max %d)' % (c, u, PAYLOAD_BITS))

    return shifts


LAYOUT = _layout()

def to_float(payload):
    """30-bit payload -> a normal float32 value (the bit pattern described at the top)"""
    bits = payload & 536870911 | 1073741824 | (payload >> 29 & 1) << 31
    return struct.unpack('<f', struct.pack('<I', bits))[0]


def from_float(f):
    b = struct.unpack('<I', struct.pack('<f', f))[0]
    return b & 536870911 | (b >> 31 & 1) << 29


def encode(values):
    """{field: integer} -> [A, X, Y, Z, W] floats; missing fields are 0, values are clamped to their width"""
    pl = dict((c, 0) for c in CONTAINERS)
    for name, (c, shift, n) in LAYOUT.items():
        v = max(0, min((1 << n) - 1, int(values.get(name, 0))))
        pl[c] |= v << shift

    return [ to_float(pl[c]) for c in CONTAINERS ]


def decode(floats):
    pl = dict((c, from_float(f)) for c, f in zip(CONTAINERS, floats))
    return dict((name, pl[c] >> shift & (1 << n) - 1) for name, (c, shift, n) in LAYOUT.items())


def q_unit(x, lo, hi, n):
    """quantise x in lo..hi to n bits (clamped)"""
    m = (1 << n) - 1
    return max(0, min(m, int(round((x - lo) / (hi - lo) * m))))


def hlsl_defines():
    """macros for the shader: PL_<container> must be the container's payload (uint) in scope; FW_<name> reads a field"""
    out = [
     '// generated from mod/afl_fwdpack.py FIELDS (tools/build_shader.py): the standard-graphics parameter layout']
    for name, (c, shift, n) in sorted(LAYOUT.items(), key=lambda kv: (CONTAINERS.index(kv[1][0]), kv[1][1])):
        out.append('#define FW_%s ((PL_%s >> %du) & %du)' % (name, c, shift, (1 << n) - 1))

    out.append('#define FW_V_RANGE %s' % repr(V_RANGE))
    out.append('#define FW_RH_MAX %s' % repr(RH_MAX))
    return ('\n').join(out) + '\n'