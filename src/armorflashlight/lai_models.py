# uncompyle6 version 3.7.4
# Python bytecode 2.7 (62211)
# Decompiled from: Python 3.10.6 (tags/v3.10.6:9c7b4bd, Aug  1 2022, 21:53:49) [MSC v.1932 64 bit (AMD64)]
# Embedded file name: scripts/client/gui/mods/armorflashlight/lai_models.py
# Compiled at: 2026-01-01 04:00:00
import math, struct

def _be(b, p, n):
    v = 0
    for k in range(n):
        v = v << 8 | b[(p + k)]

    return v


def _le(b, p, n, signed=False):
    v = 0
    for k in range(n - 1, -1, -1):
        v = v << 8 | b[(p + k)]

    if signed and v >= 1 << 8 * n - 1:
        v -= 1 << 8 * n
    return v


def _rd_vint(b, p):
    c = b[p]
    if c < 128:
        return (c, p + 1)
    t = c >> 3
    if 16 <= t <= 23:
        return ((c << 8 | b[(p + 1)]) & 16383, p + 2)
    if 24 <= t <= 27:
        return ((c << 16 | b[(p + 1)] << 8 | b[(p + 2)]) & 2097151, p + 3)
    if t == 28:
        return (_be(b, p, 4) & 134217727, p + 4)
    if t == 29:
        return (_be(b, p, 5) & 34359738367, p + 5)
    if t == 30:
        return (_be(b, p, 8) & 576460752303423487, p + 8)
    if c == 248:
        return (_be(b, p + 1, 6), p + 7)
    if c == 249:
        return (_be(b, p + 1, 8), p + 9)
    raise ValueError('bad varint 0x%02x at %d' % (c, p))


def _half(h):
    s = -1.0 if h & 32768 else 1.0
    e = h >> 10 & 31
    m = h & 1023
    if e == 0:
        return s * m * 5.960464477539063e-08
    if e == 31:
        return s * float('inf')
    return s * (1.0 + m / 1024.0) * 2.0 ** (e - 15)


class _T(object):
    __slots__ = ('name', 'params', 'parent', 'flags', 'sub', 'ptr', 'size', 'members')

    def __init__(self):
        self.name, self.params, self.parent, self.flags = (
         None, [], 0, 0)
        self.sub = self.ptr = self.size = None
        self.members = []
        return


class TagFile(object):

    def __init__(self, data):
        self.s = data
        self.b = bytearray(data)
        self.sections = {}
        self._walk(0, len(data))
        self._read_types()
        o, n = self.sections['ITEM']
        self.items = []
        for i in range(n // 12):
            a, off, cnt = struct.unpack_from('<III', self.s, o + i * 12)
            self.items.append((a & 16777215, a >> 24, off, cnt))

        self.data_off = self.sections['DATA'][0]
        self._mcache = {}

    def _walk(self, off, end):
        while off < end:
            hdr, = struct.unpack_from('>I', self.s, off)
            size = hdr & 1073741823
            tag = self.s[off + 4:off + 8]
            self.sections.setdefault(tag, (off + 8, size - 8))
            if not hdr & 1073741824:
                self._walk(off + 8, off + size)
            off += size

    def _strs(self, tag):
        o, n = self.sections[tag]
        return self.s[o:o + n].split('\x00')

    def _read_types(self):
        tstr, fstr = self._strs('TST1'), self._strs('FST1')
        b = self.b
        o, n = self.sections['TNA1']
        cnt, p = _rd_vint(b, o)
        self.types = [None] + [ _T() for _ in range(1, cnt) ]
        for i in range(1, cnt):
            t = self.types[i]
            ni, p = _rd_vint(b, p)
            t.name = tstr[ni]
            np_, p = _rd_vint(b, p)
            for _ in range(np_):
                pn, p = _rd_vint(b, p)
                pv, p = _rd_vint(b, p)
                t.params.append((tstr[pn], pv))

        o, n = self.sections['TBDY']
        p, end = o, o + n
        while p < end:
            ti, p = _rd_vint(b, p)
            if ti == 0:
                continue
            t = self.types[ti]
            t.parent, p = _rd_vint(b, p)
            t.flags, p = _rd_vint(b, p)
            f = t.flags
            if f & 1:
                t.sub, p = _rd_vint(b, p)
            if f & 2 and t.sub is not None and t.sub & 15 >= 6:
                t.ptr, p = _rd_vint(b, p)
            if f & 4:
                _, p = _rd_vint(b, p)
            if f & 8:
                t.size, p = _rd_vint(b, p)
                _, p = _rd_vint(b, p)
            if f & 16:
                _, p = _rd_vint(b, p)
            if f & 32:
                nm, p = _rd_vint(b, p)
                for _ in range(nm & 65535):
                    mn, p = _rd_vint(b, p)
                    mf, p = _rd_vint(b, p)
                    mo, p = _rd_vint(b, p)
                    mt, p = _rd_vint(b, p)
                    t.members.append((fstr[mn], mo, mt))

            if f & 64:
                ni, p = _rd_vint(b, p)
                for _ in range(ni):
                    _, p = _rd_vint(b, p)
                    _, p = _rd_vint(b, p)

            if f & 128:
                _, p = _rd_vint(b, p)

        return

    def _inh(self, t, attr):
        while t is not None:
            v = getattr(t, attr)
            if v is not None:
                return v
            t = self.types[t.parent] if t.parent else None

        return

    def _members(self, t):
        key = id(t)
        m = self._mcache.get(key)
        if m is None:
            chain = []
            while t is not None:
                chain.append(t)
                t = self.types[t.parent] if t.parent else None

            m = []
            for c in reversed(chain):
                m.extend(c.members)

            self._mcache[key] = m
        return m

    def read_item(self, idx):
        if idx == 0 or idx >= len(self.items):
            return None
        ti, fl, off, cnt = self.items[idx]
        t = self.types[ti]
        sz = self._inh(t, 'size') or 0
        base = self.data_off + off
        if fl & 16 and cnt == 1:
            return self.read_value(t, base)
        else:
            sub = self._inh(t, 'sub') or 0
            kind = sub & 15
            if kind == 4 and sz in (1, 2, 4, 8):
                fmt = {1: 'B', 2: 'H', 4: 'I', 8: 'Q'}[sz]
                if sub & 512:
                    fmt = fmt.lower()
                return list(struct.unpack_from('<%d%s' % (cnt, fmt), self.s, base))
            if kind == 5 and sz == 4:
                return list(struct.unpack_from('<%df' % cnt, self.s, base))
            return [ self.read_value(t, base + k * sz) for k in range(cnt) ]

    def read_value(self, t, at):
        b = self.b
        sub = self._inh(t, 'sub') or 0
        kind = sub & 15
        sz = self._inh(t, 'size') or 0
        if kind == 2:
            return b[at] != 0
        else:
            if kind == 3:
                ref, = struct.unpack_from('<I', self.s, at)
                if ref == 0:
                    return
                ti, fl, off, cnt = self.items[ref]
                return self.s[self.data_off + off:self.data_off + off + cnt].split('\x00')[0]
            if kind == 4:
                return _le(b, at, sz, bool(sub & 512))
            if kind == 5:
                if sz == 4:
                    return struct.unpack_from('<f', self.s, at)[0]
                if sz == 2:
                    return _half(_le(b, at, 2))
                if sz == 8:
                    return struct.unpack_from('<d', self.s, at)[0]
                return
            if kind == 6:
                ref, = struct.unpack_from('<I', self.s, at)
                if ref:
                    return {'@ref': ref}
                return
            if kind == 8 and not sub & 32:
                ref, = struct.unpack_from('<I', self.s, at)
                if ref:
                    return self.read_item(ref)
                return []
            if kind in (8, 9):
                n = sub >> 8
                et = self.types[self._inh(t, 'ptr')]
                esz = self._inh(et, 'size') or 0
                return [ self.read_value(et, at + k * esz) for k in range(n) ]
            if kind == 7:
                out = {}
                for mn, mo, mt in self._members(t):
                    out[mn] = self.read_value(self.types[mt], at + mo)

                return out
            return


def _deref(tf, v):
    if isinstance(v, dict) and '@ref' in v:
        return tf.read_item(v['@ref'])
    return v


def _decode_tree(tree):
    dmin, dmax = tree['domain']['min'][:3], tree['domain']['max'][:3]
    packed = tree['packedVertices'] or []
    shared = tree['sharedVertices'] or []
    sidx = tree['sharedVerticesIndex'] or []
    prims = tree['primitives'] or []
    runs = tree['primitiveDataRuns'] or []
    tris = []
    for sec in tree['sections']:
        parms = sec['codecParms']
        npv, fpv, fsv = sec['numPackedVertices'], sec['firstPackedVertexIndex'], sec['firstSharedVertexIndex']

        def vert(i):
            if i < npv:
                v = packed[(fpv + i)]
                return (
                 parms[0] + parms[3] * (v & 2047), parms[1] + parms[4] * (v >> 11 & 2047),
                 parms[2] + parms[5] * (v >> 22 & 1023))
            v = shared[sidx[(fsv + i - npv)]]
            return (dmin[0] + (dmax[0] - dmin[0]) * (v & 2097151) / 2097151.0,
             dmin[1] + (dmax[1] - dmin[1]) * (v >> 21 & 2097151) / 2097151.0,
             dmin[2] + (dmax[2] - dmin[2]) * (v >> 42 & 4194303) / 4194303.0)

        for j in range(sec['numPrimitives']):
            a, b, c, d = prims[(sec['firstPrimitiveIndex'] + j)]['indices']
            if a == b or a == c and b == d:
                continue
            tris.append((vert(a), vert(b), vert(c)))
            if c != d:
                tris.append((vert(a), vert(c), vert(d)))

    return tris


def read_havok(data):
    """-> [(bodyName, normalMatKind, [(p0, p1, p2), ...])]"""
    out = []
    for _ in read_havok_iter(data, out):
        pass

    return out


def read_havok_iter(data, out):
    """generator version: yields between steps so the work can be spread over frames; fills out"""
    tf = TagFile(data)
    yield
    root = tf.read_item(1)
    cont = _deref(tf, root['namedVariants'][0]['variant'])
    hs = {}
    for h in cont['resourceHandles']:
        h = _deref(tf, h)
        hs[h['name']] = _deref(tf, h['variant'])

    flags = dict((i['name'], i) for i in hs['HKBodyFlagsData']['flags_'])
    yield
    for body in hs['Collision Physics Data']['bodyCinfos']:
        bname = body['name'][2:] if body['name'].startswith('s_') else body['name']
        shape = _deref(tf, body['shape'])
        data_ = _deref(tf, shape['data']) if shape and 'data' in shape else None
        if not data_ or 'meshTree' not in data_:
            continue
        out.append((bname, flags[bname]['normalMatKind'], _decode_tree(data_['meshTree'])))
        yield

    return


MAGIC = 1654738501
T_ELEMENT, T_STRING, T_INT, T_FLOAT, T_BOOL, T_BLOB = range(6)

class E(object):

    def __init__(self, name, value=None, children=()):
        self.name, self.value, self.children = name, value, list(children)
        if value is None:
            self.type = T_ELEMENT
        elif isinstance(value, bool):
            self.type = T_BOOL
        elif isinstance(value, (int, long)):
            self.type = T_INT
        elif isinstance(value, (float, tuple, list)):
            self.type = T_FLOAT
        else:
            self.type = T_STRING
        return


def _enc_value(v, t):
    if t == T_ELEMENT or v is None:
        return ''
    if t == T_STRING:
        if isinstance(v, unicode):
            return v.encode('utf-8')
        return v
    if t == T_INT:
        if v == 0:
            return ''
        for fmt, lim in (('<b', 128), ('<h', 32768), ('<i', 2147483648)):
            if -lim <= v < lim:
                return struct.pack(fmt, v)

        return struct.pack('<q', v)
    else:
        if t == T_FLOAT:
            if isinstance(v, (tuple, list)):
                return struct.pack(('<%df' % len(v)), *v)
            return struct.pack('<f', v)
        if t == T_BOOL:
            if v:
                return '\x01'
            return ''
        raise ValueError(t)
        return


def _names(node, acc):
    for c in node.children:
        acc.add(c.name)
        _names(c, acc)


def _enc_section(node, index):
    self_data = _enc_value(node.value, node.type)
    self_type = node.type if node.value is not None else T_ELEMENT
    blocks, descs, end = [self_data], [], len(self_data)
    for c in node.children:
        if c.children or c.type == T_ELEMENT:
            blob, t = _enc_section(c, index), T_ELEMENT
        else:
            blob, t = _enc_value(c.value, c.type), c.type
        end += len(blob)
        descs.append(struct.pack('<HI', index[c.name], t << 28 | end))
        blocks.append(blob)

    return struct.pack('<H', len(node.children)) + struct.pack('<I', self_type << 28 | len(self_data)) + ('').join(descs) + ('').join(blocks)


def encode(root):
    acc = set()
    _names(root, acc)
    names = sorted(acc)
    index = dict((n, i) for i, n in enumerate(names))
    if root.value is None:
        root.value, root.type = '', T_STRING
    return struct.pack('<IB', MAGIC, 0) + ('').join(n + '\x00' for n in names) + '\x00' + _enc_section(root, index)


FX_PATH = 'shaders/custom/lai_armor.fx'
PRIM_MAGIC = 1117867621
BPVT = 1414942786
IDENT = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0)

def _pack_dir(v):
    return struct.pack('4B', *([ max(0, min(255, int(round((c + 1.0) * 127.5)))) for c in v ] + [0]))


def _norm(v):
    ln = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / ln, v[1] / ln, v[2] / ln)


def _cross(a, b):
    return (
     a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _sub(a, b):
    return (
     a[0] - b[0], a[1] - b[1], a[2] - b[2])


def is_spaced(mat):
    """screens, tracks, gun: vehicleDamageFactor 0 -> the shell continues -> resolved on the CPU"""
    return float(mat['vdf']) == 0.0 and mat['armor'] > 0


def build(bodies, mats, vpath, name, include=None, tri_filter=None, inflate=0.015, blend='opaque', bbox_pad=0.0):
    """bodies from read_havok; mats: {matKind: {'armor': mm, 'vdf': vehicleDamageFactor}}.
    -> (model bytes, visual bytes, primitives bytes, [per-triangle (centroid, normal)])"""
    verts, idx, gtab, tri_out = ([], [], [], [])
    bb_min, bb_max = [
     1000000000.0] * 3, [-1000000000.0] * 3
    nv = 0
    for bname, mk, tris in bodies:
        a = mats.get(mk, {'armor': 0.0, 'vdf': 1.0})
        if include is not None and not include(bname, mk, a):
            continue
        gs_i, gs_v, ntri = len(idx), nv, 0
        u = (-1.0 if float(a['vdf']) == 0.0 else 1.0) * a['armor'] / 1000.0
        uv = struct.pack('<2f', u, mk / 255.0)
        for ti, (p0, p1, p2) in enumerate(tris):
            if tri_filter is not None and not tri_filter(bname, ti):
                continue
            e1 = _sub(p1, p0)
            n = _norm(_cross(e1, _sub(p2, p0)))
            p0, p1, p2 = [ (q[0] + n[0] * inflate, q[1] + n[1] * inflate, q[2] + n[2] * inflate) for q in (p0, p1, p2) ]
            t = _norm(e1)
            bn = _cross(n, t)
            tail = _pack_dir(n) + uv + _pack_dir(t) + _pack_dir(bn)
            for p in (p0, p1, p2):
                verts.append(struct.pack('<3f', *p) + tail)
                for k in range(3):
                    if p[k] < bb_min[k]:
                        bb_min[k] = p[k]
                    if p[k] > bb_max[k]:
                        bb_max[k] = p[k]

            idx.extend((nv, nv + 1, nv + 2))
            nv += 3
            ntri += 1
            tri_out.append(([ (p0[k] + p1[k] + p2[k]) / 3.0 for k in range(3) ], n))

        if ntri:
            gtab.append((gs_i, ntri, gs_v, nv - gs_v, bname, mk))

    if not gtab:
        return
    else:
        fmt32 = nv > 65535
        ib = struct.pack(('<%d%s' % (len(idx), 'I' if fmt32 else 'H')), *idx)
        ind_sec = ('list32' if fmt32 else 'list').ljust(64, '\x00') + struct.pack('<II', len(idx), len(gtab)) + ib + ('').join(struct.pack('<4I', g[0], g[1], g[2], g[3]) for g in gtab)
        vtx_sec = struct.pack('<I', BPVT) + ('xyznuvtb').ljust(64, '\x00') + ('set3/xyznuvtbpc').ljust(64, '\x00') + struct.pack('<I', nv) + ('').join(verts)
        body, dirent = struct.pack('<I', PRIM_MAGIC), ''
        for sname, sdata in (('indices', ind_sec), ('vertices', vtx_sec)):
            body += sdata
            body += '\x00' * ((4 - len(body) % 4) % 4)
            dirent += struct.pack('<I', len(sdata)) + '\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00' + struct.pack('<I', len(sname)) + sname.ljust(len(sname) + 3 & -4, '\x00')

        prim = body + dirent + struct.pack('<I', len(dirent))
        sb, db = (2, 1) if blend == 'opaque' else (5, 6)
        pgs = []
        for i, g in enumerate(gtab):
            mat = E('material', children=[
             E('identifier', g[4]), E('collisionFlags', 0), E('materialKind', g[5]),
             E('fx', FX_PATH),
             E('property', 'g_color', [E('Vector4', (0.0, 0.0, 0.0, 0.0))]),
             E('property', 'g_animationParams', [E('Vector4', (0.0, 0.0, 0.0, 0.0))]),
             E('property', 'srcBlend', [E('Int', sb)]),
             E('property', 'destBlend', [E('Int', db)]),
             E('property', 'doubleSided', [E('Bool', True)])])
            pgs.append(E('primitiveGroup', i, [mat]))

        vis = E('root', children=[
         E('node', children=[E('identifier', 'Scene Root'), E('transform', IDENT)]),
         E('renderSet', children=[E('treatAsWorldSpaceObject', False), E('node', 'Scene Root'),
          E('geometry', children=[E('vertices', 'vertices'), E('primitive', 'indices')] + pgs)]),
         E('boundingBox', children=[E('min', tuple(c - bbox_pad for c in bb_min)),
          E('max', tuple(c + bbox_pad for c in bb_max))]),
         E('geometrySize', len(prim))])
        model = E('root', children=[E('nodelessVisual', '%s/%s' % (vpath, name))])
        return (encode(model), encode(vis), prim, tri_out)


def kmeans(points, k, iters=10):
    res = []
    for _ in kmeans_iter(points, k, res, iters):
        pass

    return (
     res[0], res[1])


def kmeans_iter(points, k, res, iters=10):
    k = max(1, min(k, len(points)))
    seeds = [ list(points[int(i * len(points) / k)]) for i in range(k) ]
    lab = [0] * len(points)
    for _ in range(iters):
        yield
        lab = [ min(range(k), key=lambda j: (c[0] - seeds[j][0]) ** 2 + (c[1] - seeds[j][1]) ** 2 + (c[2] - seeds[j][2]) ** 2) for c in points ]
        for j in range(k):
            mem = [ points[i] for i in range(len(points)) if lab[i] == j ]
            if mem:
                seeds[j] = [ sum(m[q] for m in mem) / len(mem) for q in range(3) ]

    res[:] = [
     lab, k]


PIECE_AREA = 0.12
MAX_PIECES = 40

def _area(t):
    c = _cross(_sub(t[1], t[0]), _sub(t[2], t[0]))
    return 0.5 * math.sqrt(c[0] * c[0] + c[1] * c[1] + c[2] * c[2])


def build_part(havok_bytes, mats, vpath, name, blend='opaque'):
    res = []
    for _ in build_part_iter(havok_bytes, mats, vpath, name, res, blend):
        pass

    return (
     res[0], res[1], res[2])


def build_part_iter(havok_bytes, mats, vpath, name, res, blend='opaque'):
    """one collision part -> files {filename: bytes} + spaced spec list (in res), yielding between small steps.
    primary armour -> <name>.*; every spaced/zero-damage group split into ~PIECE_AREA pieces -> <name>_sp_*."""
    bodies = []
    for _ in read_havok_iter(havok_bytes, bodies):
        yield

    files = {}
    r = build(bodies, mats, vpath, name, include=lambda b, mk, a: a['armor'] > 0 and not is_spaced(a), blend=blend)
    primary = None
    if r:
        files[name + '.model'], files[name + '.visual_processed'], files[name + '.primitives_processed'] = r[:3]
        primary = '%s/%s.model' % (vpath, name)
    yield
    spaced = []
    for bname, mk, tris in bodies:
        a = mats.get(mk)
        if a is None or not is_spaced(a) or not tris:
            continue
        cents = [ [ (t[0][q] + t[1][q] + t[2][q]) / 3.0 for q in range(3) ] for t in tris ]
        area = sum(_area(t) for t in tris)
        km = []
        for _ in kmeans_iter(cents, max(1, min(MAX_PIECES, len(cents), int(math.ceil(area / PIECE_AREA)))), km):
            yield

        lab, k = km
        for j in range(k):
            ids = set(i for i in range(len(cents)) if lab[i] == j)
            if not ids:
                continue
            sub_name = '%s_sp_%s_%02d' % (name, bname, j)
            rr = build([(bname, mk, tris)], mats, vpath, sub_name, tri_filter=lambda b, ti, ids=ids: ti in ids, inflate=0.03, blend=blend)
            if not rr:
                continue
            files[sub_name + '.model'], files[sub_name + '.visual_processed'], files[sub_name + '.primitives_processed'] = rr[:3]
            samp = [ cents[i] for i in sorted(ids) ]
            spaced.append({'group': '%s_%02d' % (bname, j), 'armor': a['armor'], 'model': '%s/%s.model' % (vpath, sub_name), 
               'centroids': samp})
            yield

    res[:] = [
     files, primary, spaced]
    return


def materials_of(component):
    """typeDescriptor.<part>.materials -> {matKind: {'armor', 'vdf'}}"""
    return dict((mk, {'armor': float(m.armor), 'vdf': float(m.vehicleDamageFactor)}) for mk, m in component.materials.iteritems())