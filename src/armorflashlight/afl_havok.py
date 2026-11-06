# uncompyle6 version 3.7.4
# Python bytecode 2.7 (62211)
# Decompiled from: Python 3.10.6 (tags/v3.10.6:9c7b4bd, Aug  1 2022, 21:53:49) [MSC v.1932 64 bit (AMD64)]
# Embedded file name: scripts/client/gui/mods/armorflashlight/afl_havok.py
# Compiled at: 2026-01-01 04:00:00
import re, struct
from itertools import izip
_U32 = struct.Struct('<I')
_HI = re.compile(b'[\x80-\xff]')

def _rd_vint(b, p):
    c = b[p]
    if c < 128:
        return (c, p + 1)
    t = c >> 3
    if 16 <= t <= 23:
        return ((c << 8 | b[(p + 1)]) & 16383, p + 2)
    if 24 <= t <= 27:
        return ((c << 16 | b[(p + 1)] << 8 | b[(p + 2)]) & 2097151, p + 3)
    v = 0
    if t == 28:
        n, m, q = 4, 134217727, p
    else:
        if t == 29:
            n, m, q = 5, 34359738367, p
        elif t == 30:
            n, m, q = 8, 576460752303423487, p
        elif c == 248:
            n, m, q = 6, 281474976710655, p + 1
        elif c == 249:
            n, m, q = 8, 18446744073709551615, p + 1
        else:
            raise ValueError('bad varint 0x%02x at %d' % (c, p))
    for k in range(n):
        v = v << 8 | b[(q + k)]

    return (
     v & m, q + n)


def _vints(s, b, start, end):
    """whole vint stream [start, end) -> list of ints. Single-byte vints are copied in bulk (bytearray slices)."""
    out = []
    p = start
    for m in _HI.finditer(s, start, end):
        q = m.start()
        if q < p:
            continue
        if q > p:
            out.extend(b[p:q])
        v, p = _rd_vint(b, q)
        out.append(v)

    if p < end:
        out.extend(b[p:end])
    return out


class Types(object):
    """parsed type table: per type index own (name, parent, sub, ptr, size, members) + inherited sub/size/ptr"""

    def __init__(self, s, b, sec):
        o, n = sec['TST1']
        tstr = s[o:o + n].split('\x00')
        o, n = sec['FST1']
        fstr = s[o:o + n].split('\x00')
        o, n = sec['TNA1']
        L = _vints(s, b, o, o + n)
        cnt = L[0]
        k = 1
        name = [None] * cnt
        for i in xrange(1, cnt):
            name[i] = tstr[L[k]]
            k += 2 + 2 * L[(k + 1)]

        parent = [
         0] * cnt
        sub = [None] * cnt
        ptr = [None] * cnt
        size = [None] * cnt
        members = [()] * cnt
        o, n = sec['TBDY']
        L = _vints(s, b, o, o + n)
        k, end = 0, len(L)
        while k < end:
            ti = L[k]
            k += 1
            if ti == 0:
                continue
            parent[ti] = L[k]
            f = L[(k + 1)]
            k += 2
            if f & 1:
                sub[ti] = L[k]
                k += 1
            if f & 2 and sub[ti] is not None and sub[ti] & 15 >= 6:
                ptr[ti] = L[k]
                k += 1
            if f & 4:
                k += 1
            if f & 8:
                size[ti] = L[k]
                k += 2
            if f & 16:
                k += 1
            if f & 32:
                nm = L[k] & 65535
                k += 1
                members[ti] = [ (fstr[L[j]], L[(j + 2)], L[(j + 3)]) for j in xrange(k, k + 4 * nm, 4) ]
                k += 4 * nm
            if f & 64:
                k += 1 + 2 * L[k]
            if f & 128:
                k += 1

        self.name, self.parent, self.members = name, parent, members
        self.sub = [ self._inh(sub, i) or 0 for i in xrange(cnt) ]
        self.size = [ self._inh(size, i) or 0 for i in xrange(cnt) ]
        self.ptr = [ self._inh(ptr, i) for i in xrange(cnt) ]
        self._mm = {}
        return

    def _inh(self, arr, i):
        while i:
            v = arr[i]
            if v is not None:
                return v
            i = self.parent[i]

        return

    def mm(self, ti):
        """all members incl. inherited: {name: (offset, type index)}"""
        m = self._mm.get(ti)
        if m is None:
            chain = []
            i = ti
            while i:
                chain.append(i)
                i = self.parent[i]

            m = {}
            for c in reversed(chain):
                for mn, mo, mt in self.members[c]:
                    m[mn] = (
                     mo, mt)

            self._mm[ti] = m
        return m

    def scalar_fmt(self, ti):
        """struct char of a scalar (kind 2 bool, 4 int, 5 float32/64) or None"""
        sub, sz = self.sub[ti], self.size[ti]
        kind = sub & 15
        if kind == 2:
            if sz == 1:
                return '?'
            return
        if kind == 4:
            c = {1: 'B', 2: 'H', 4: 'I', 8: 'Q'}.get(sz)
            if c and sub & 512:
                return c.lower()
            return c
        if kind == 5:
            return {4: 'f', 8: 'd'}.get(sz)
        else:
            return

    def fixed_fmt(self, ti):
        """struct format of a scalar or a fixed array T[N] of scalars ('6f'), or None"""
        c = self.scalar_fmt(ti)
        if c:
            return c
        else:
            sub = self.sub[ti]
            if sub & 15 in (8, 9) and sub & 32:
                e = self.ptr[ti]
                c = self.scalar_fmt(e) if e else None
                if c:
                    return '%d%s' % (sub >> 8, c)
            return


_TYPES_CACHE = {}

def _sections(s):
    sec = {}

    def walk(off, end):
        while off < end:
            hdr, = struct.unpack_from('>I', s, off)
            size = hdr & 1073741823
            sec.setdefault(s[off + 4:off + 8], (off + 8, size - 8))
            if not hdr & 1073741824:
                walk(off + 8, off + size)
            off += size

    walk(0, len(s))
    return sec


class FastTag(object):

    def __init__(self, s):
        self.s = s
        sec = self.sec = _sections(s)
        key = ('').join(s[sec[t][0]:sec[t][0] + sec[t][1]] for t in ('TST1', 'FST1',
                                                                     'TNA1', 'TBDY'))
        T = _TYPES_CACHE.get(key)
        if T is None:
            T = _TYPES_CACHE[key] = Types(s, bytearray(s), sec)
        self.T = T
        o, n = sec['ITEM']
        self.it = struct.unpack_from('<%dI' % (n // 4), s, o)
        self.nitems = n // 12
        self.d0 = sec['DATA'][0]
        self._lay = {}
        return

    def item(self, ref):
        """-> (type index, flags, absolute data offset, count)"""
        it = self.it
        a = it[(3 * ref)]
        return (a & 16777215, a >> 24, self.d0 + it[(3 * ref + 1)], it[(3 * ref + 2)])

    def u32(self, at):
        return _U32.unpack_from(self.s, at)[0]

    def string(self, ref):
        if ref == 0:
            return None
        else:
            ti, fl, at, cnt = self.item(ref)
            return self.s[at:at + cnt].split('\x00')[0]

    def layout(self, ti, names):
        """one struct.Struct reading the named members (scalars / fixed scalar arrays) of type ti in one call.
        -> (Struct, first offset, {name: (slot, width)})"""
        key = (
         ti, names)
        r = self._lay.get(key)
        if r is None:
            T = self.T
            mm = T.mm(ti)
            fields = sorted((mm[n][0], n, T.fixed_fmt(mm[n][1])) for n in names)
            fmt, pos, slots, slot = ('<', fields[0][0], {}, 0)
            for off, n, f in fields:
                if f is None:
                    raise ValueError('member %s of %s is not a scalar' % (n, T.name[ti]))
                if off > pos:
                    fmt += '%dx' % (off - pos)
                st = struct.Struct('<' + f)
                fmt += f
                w = len(st.unpack_from('\x00' * st.size))
                slots[n] = (slot, w)
                slot += w
                pos = off + st.size

            r = self._lay[key] = (
             struct.Struct(fmt), fields[0][0], slots)
        return r

    def array(self, ref):
        """dynamic array (item ref) -> (element type, base offset, count); None/[] ref -> (None, 0, 0)"""
        if ref == 0:
            return (None, 0, 0)
        else:
            ti, fl, at, cnt = self.item(ref)
            return (ti, at, cnt)

    def num_array(self, ref):
        ti, at, cnt = self.array(ref)
        if not cnt:
            return ()
        c = self.T.scalar_fmt(ti)
        return struct.unpack_from('<%d%s' % (cnt, c), self.s, at)

    def member_ref(self, ti, at, name):
        """u32 stored at member `name` (pointer / array / string ref)"""
        return _U32.unpack_from(self.s, at + self.T.mm(ti)[name][0])[0]


DECODE_STEP = 500

def decode_tree(tf, tti, tat, keys=None):
    """hkcdStaticMeshTree (type tti at absolute offset tat) -> [(p0, p1, p2)], same values/order as lai_models._decode_tree.
    keys (dict): filled with primitive key (section << 8 | primitive << 1) -> (first triangle, count)"""
    tris = []
    for _ in decode_tree_iter(tf, tti, tat, keys, tris):
        pass

    return tris


def decode_tree_iter(tf, tti, tat, keys, tris):
    """generator version of decode_tree: fills tris, yields between sections every DECODE_STEP triangles"""
    T, s = tf.T, tf.s
    mm = T.mm(tti)
    ref = lambda n: _U32.unpack_from(s, tat + mm[n][0])[0]
    do, dt = mm['domain']
    dmm = T.mm(dt)
    x0, y0, z0 = struct.unpack_from('<3f', s, tat + do + dmm['min'][0])
    x1, y1, z1 = struct.unpack_from('<3f', s, tat + do + dmm['max'][0])
    ex, ey, ez = x1 - x0, y1 - y0, z1 - z0
    packed = tf.num_array(ref('packedVertices'))
    sidx = tf.num_array(ref('sharedVerticesIndex'))
    shared = [ (x0 + ex * (v & 2097151) / 2097151.0, y0 + ey * (v >> 21 & 2097151) / 2097151.0, z0 + ez * (v >> 42 & 4194303) / 4194303.0) for v in tf.num_array(ref('sharedVertices'))
             ]
    pti, pat, pcnt = tf.array(ref('primitives'))
    if pcnt:
        pmm = T.mm(pti)
        io, it_ = pmm['indices']
        if T.size[pti] != 4 or io != 0 or T.fixed_fmt(it_) != '4B':
            raise ValueError('unexpected Primitive layout')
    pb = bytearray(s[pat:pat + 4 * pcnt])
    sti, sat, scnt = tf.array(ref('sections'))
    if not scnt:
        return
    else:
        st, s0, sl = tf.layout(sti, ('codecParms', 'firstPackedVertexIndex', 'firstSharedVertexIndex',
                                     'firstPrimitiveIndex', 'numPackedVertices',
                                     'numPrimitives'))
        cp = sl['codecParms'][0]
        i_fpv, i_fsv, i_fpi = sl['firstPackedVertexIndex'][0], sl['firstSharedVertexIndex'][0], sl['firstPrimitiveIndex'][0]
        i_npv, i_np = sl['numPackedVertices'][0], sl['numPrimitives'][0]
        ssz = T.size[sti]
        unpack = st.unpack_from
        add = tris.append
        next_yield = DECODE_STEP
        for k in xrange(scnt):
            f = unpack(s, sat + k * ssz + s0)
            ox, oy, oz, sx, sy, sz = f[cp:cp + 6]
            npv, fpv, fsv, fpi, npr = (f[i_npv], f[i_fpv], f[i_fsv], f[i_fpi], f[i_np])
            if not npr:
                continue
            a0, a1 = 4 * fpi, 4 * (fpi + npr)
            if a1 > len(pb):
                raise IndexError('primitive index out of range')
            mx = max(pb[a0:a1])
            vs = [ (ox + sx * (v & 2047), oy + sy * (v >> 11 & 2047), oz + sz * (v >> 22 & 1023)) for v in packed[fpv:fpv + min(npv, mx + 1)]
                 ]
            if len(vs) < min(npv, mx + 1):
                raise IndexError('packed vertex index out of range')
            if mx >= npv:
                vs.extend([ shared[j] for j in sidx[fsv:fsv + mx + 1 - npv] ])
            key = k << 8
            for a, b, c, d in izip(pb[a0:a1:4], pb[a0 + 1:a1:4], pb[a0 + 2:a1:4], pb[a0 + 3:a1:4]):
                if a == b or a == c and b == d:
                    key += 2
                    continue
                first = len(tris)
                va = vs[a]
                add((va, vs[b], vs[c]))
                if c != d:
                    add((va, vs[c], vs[d]))
                if keys is not None:
                    keys[key] = (
                     first, len(tris) - first)
                key += 2

            if len(tris) >= next_yield:
                next_yield = len(tris) + DECODE_STEP
                yield

        return


_NODE_MEMBERS = ('lx', 'hx', 'ly', 'hy', 'lz', 'hz', 'data', 'isLeaf')

def read_simd(tf, dti, dat):
    """hkcdSimdTree of a hknpCompressedMeshShapeData -> [(lx, hx, ly, hy, lz, hz, data, isLeaf)] per node (4-tuples),
    or None if the shape has none"""
    T, s = tf.T, tf.s
    dmm = T.mm(dti)
    if 'simdTree' not in dmm or 'hasSimdTree' not in dmm:
        return None
    if not struct.unpack_from('<?', s, dat + dmm['hasSimdTree'][0])[0]:
        return None
    else:
        so, st = dmm['simdTree']
        nti, nat, ncnt = tf.array(_U32.unpack_from(s, dat + so + T.mm(st)['nodes'][0])[0])
        if ncnt < 2:
            return None
        lay, off, slots = tf.layout(nti, _NODE_MEMBERS)
        unpack, size = lay.unpack_from, T.size[nti]
        idx = [ slots[n] for n in _NODE_MEMBERS ]
        out = []
        for i in xrange(ncnt):
            f = unpack(s, nat + i * size + off)
            out.append(tuple((f[j:j + w] if w > 1 else f[j]) for j, w in idx))

        return out


def read_havok_iter(data, out, trees=None):
    """drop-in for lai_models.read_havok_iter: fills out with (bodyName, normalMatKind, tris), yields between steps.
    trees (list): gets one (simd nodes, primitive key map) per body of out, None if the body has no simd tree"""
    tf = FastTag(data)
    T = tf.T
    yield
    rti, rfl, rat, rcnt = tf.item(1)
    nti, nat, ncnt = tf.array(tf.member_ref(rti, rat, 'namedVariants'))
    cti, cfl, cat, ccnt = tf.item(tf.member_ref(nti, nat, 'variant'))
    hti, hat, hcnt = tf.array(tf.member_ref(cti, cat, 'resourceHandles'))
    hs = {}
    for k in xrange(hcnt):
        h = tf.item(tf.u32(hat + k * T.size[hti]))
        hs[tf.string(tf.member_ref(h[0], h[2], 'name'))] = tf.member_ref(h[0], h[2], 'variant')

    fti, ffl, fat, fcnt = tf.item(hs['HKBodyFlagsData'])
    iti, iat, icnt = tf.array(tf.member_ref(fti, fat, 'flags_'))
    imm = T.mm(iti)
    no, nk = imm['name'][0], imm['normalMatKind']
    nkf = struct.Struct('<' + T.scalar_fmt(nk[1]))
    isz = T.size[iti]
    flags = {}
    for k in xrange(icnt):
        b = iat + k * isz
        flags[tf.string(tf.u32(b + no))] = nkf.unpack_from(tf.s, b + nk[0])[0]

    yield
    pti, pfl, pat, pcnt = tf.item(hs['Collision Physics Data'])
    bti, bat, bcnt = tf.array(tf.member_ref(pti, pat, 'bodyCinfos'))
    bmm = T.mm(bti)
    so, no = bmm['shape'][0], bmm['name'][0]
    bsz = T.size[bti]
    for k in xrange(bcnt):
        b = bat + k * bsz
        name = tf.string(tf.u32(b + no))
        bname = name[2:] if name.startswith('s_') else name
        sref = tf.u32(b + so)
        if not sref:
            continue
        sti, sfl, sat, scnt = tf.item(sref)
        smm = T.mm(sti)
        if 'data' not in smm or T.sub[smm['data'][1]] & 15 != 6:
            continue
        dref = tf.u32(sat + smm['data'][0])
        if not dref:
            continue
        dti, dfl, dat, dcnt = tf.item(dref)
        dmm = T.mm(dti)
        if 'meshTree' not in dmm:
            continue
        mo, mt = dmm['meshTree']
        keys = {} if trees is not None else None
        tris = []
        for _ in decode_tree_iter(tf, mt, dat + mo, keys, tris):
            yield

        out.append((bname, flags[bname], tris))
        if trees is not None:
            nodes = read_simd(tf, dti, dat)
            trees.append((nodes, keys) if nodes else None)
        yield

    return


def read_havok(data):
    out = []
    for _ in read_havok_iter(data, out):
        pass

    return out


PAD = 2e-05

def simd_entries(tree, tris):
    """one body's simd tree -> pre-order entry list (see afl_data.emit_entries), first entry = the body root.
    tris: the body's triangles as the texture wants them ((p0, p1, p2, m)), in decode order.
    Raises ValueError if the tree does not cover exactly the decoded primitives (the caller builds its own BVH)."""
    nodes, keys = tree
    out = [[None, None, 'I', None]]
    seen = set()
    n_nodes = len(nodes)

    def emit(ni):
        lx, hx, ly, hy, lz, hz, data, leaf = nodes[ni]
        for c in (0, 1, 2, 3):
            if lx[c] > hx[c]:
                continue
            lo = (
             lx[c] - PAD, ly[c] - PAD, lz[c] - PAD)
            hi = (hx[c] + PAD, hy[c] + PAD, hz[c] + PAD)
            if leaf:
                r = keys.get(data[c])
                if r is None:
                    raise ValueError('primitive key %x not decoded' % data[c])
                seen.add(data[c])
                out.append([lo, hi, 'L', tris[r[0]:r[0] + r[1]]])
            else:
                child = data[c]
                if not ni < child < n_nodes:
                    raise ValueError('bad child %d of node %d' % (child, ni))
                me = len(out)
                out.append([lo, hi, 'I', None])
                emit(child)
                if len(out) == me + 1:
                    out.pop()
                else:
                    out[me][3] = len(out)

        return

    emit(1)
    if len(seen) != len(keys):
        raise ValueError('tree covers %d of %d primitives' % (len(seen), len(keys)))
    if len(out) == 1:
        return []
    else:
        lx, hx, ly, hy, lz, hz = nodes[1][:6]
        live = [ c for c in (0, 1, 2, 3) if lx[c] <= hx[c] ]
        out[0][0] = (min(lx[c] for c in live) - PAD, min(ly[c] for c in live) - PAD, min(lz[c] for c in live) - PAD)
        out[0][1] = (max(hx[c] for c in live) + PAD, max(hy[c] for c in live) + PAD, max(hz[c] for c in live) + PAD)
        out[0][3] = len(out)
        return out