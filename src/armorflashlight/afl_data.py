# uncompyle6 version 3.7.4
# Python bytecode 2.7 (62211)
# Decompiled from: Python 3.10.6 (tags/v3.10.6:9c7b4bd, Aug  1 2022, 21:53:49) [MSC v.1932 64 bit (AMD64)]
# Embedded file name: scripts/client/gui/mods/armorflashlight/afl_data.py
# Compiled at: 2026-01-01 04:00:00
import math, struct
MAGIC = 7.0
VERSION = 2.0
TEX_W = 1024
PARTS = ('chassis', 'hull', 'turret', 'gun')
LEAF = 4
H_PARTS, H_CHASSIS, H_TURRET, H_GUN, H_SPHERE, H_MAT = (1, 5, 9, 13, 17, 18)
HEADER = 19
F_USE_HIT_ANGLE, F_MAY_RICOCHET, F_ONCE, F_CAL_RIC, F_CAL_NORM, F_EXTRA = (1, 2, 4,
                                                                           8, 16,
                                                                           32)

def mat_from_bw(m):
    """BigWorld Math.Matrix -> 4x3 rows: row k = image of axis k (p * M convention), row 3 = translation"""
    import Math
    rows = []
    for ax in ((1, 0, 0), (0, 1, 0), (0, 0, 1)):
        v = m.applyVector(Math.Vector3(*ax))
        rows.append([v.x, v.y, v.z])

    t = m.translation
    rows.append([t.x, t.y, t.z])
    return rows


def xform(p, M):
    return (
     p[0] * M[0][0] + p[1] * M[1][0] + p[2] * M[2][0] + M[3][0],
     p[0] * M[0][1] + p[1] * M[1][1] + p[2] * M[2][1] + M[3][1],
     p[0] * M[0][2] + p[1] * M[1][2] + p[2] * M[2][2] + M[3][2])


def xdir(v, M):
    return (
     v[0] * M[0][0] + v[1] * M[1][0] + v[2] * M[2][0],
     v[0] * M[0][1] + v[1] * M[1][1] + v[2] * M[2][1],
     v[0] * M[0][2] + v[1] * M[1][2] + v[2] * M[2][2])


def mul(A, B):
    """row-vector composition: p * A * B"""
    R = [ [ sum(A[r][k] * B[k][c] for k in range(3)) for c in range(3) ] for r in range(3) ]
    R.append(list(xform(A[3], B)))
    return R


def inverse(M):
    a, b, c = M[0], M[1], M[2]
    det = a[0] * (b[1] * c[2] - b[2] * c[1]) - a[1] * (b[0] * c[2] - b[2] * c[0]) + a[2] * (b[0] * c[1] - b[1] * c[0])
    inv = [[(b[1] * c[2] - b[2] * c[1]) / det, -(a[1] * c[2] - a[2] * c[1]) / det, (a[1] * b[2] - a[2] * b[1]) / det],
     [
      -(b[0] * c[2] - b[2] * c[0]) / det, (a[0] * c[2] - a[2] * c[0]) / det, -(a[0] * b[2] - a[2] * b[0]) / det],
     [
      (b[0] * c[1] - b[1] * c[0]) / det, -(a[0] * c[1] - a[1] * c[0]) / det, (a[0] * b[1] - a[1] * b[0]) / det]]
    t = M[3]
    inv.append([ -(t[0] * inv[0][k] + t[1] * inv[1][k] + t[2] * inv[2][k]) for k in range(3) ])
    return inv


def rig_from_nodes(chassisW, hullW, turretW, gunW):
    """world matrices of the part nodes (4x3 lists) -> (hull->chassis, hull->turret, turret->gun, M_t, M_g)
    M_t = turret local -> hull, M_g = gun local -> turret local (kept to compute D_t / D_g later)."""
    iHull = inverse(hullW)
    M_c = mul(chassisW, iHull)
    M_t = mul(turretW, iHull)
    M_g = mul(gunW, inverse(turretW))
    return (inverse(M_c), inverse(M_t), inverse(M_g), M_t, M_g)


def translate(t):
    return [
     [
      1.0, 0.0, 0.0], [0.0, 1.0, 0.0], [0.0, 0.0, 1.0], [float(t[0]), float(t[1]), float(t[2])]]


def rig_from_descriptor(td):
    """Calibration from the vehicle descriptor (verified equal to the node matrices, XM57, 0.1 mm):
    chassis local -> hull = translate(-hullPosition), turret local -> hull = translate(turretPositions[0]) at yaw 0,
    gun local -> turret local = translate(gunPosition) at pitch 0."""
    hp = td.chassis.hullPosition
    M_c = translate((-hp[0], -hp[1], -hp[2]))
    M_t = translate(td.hull.turretPositions[0])
    M_g = translate(td.turret.gunPosition)
    return (inverse(M_c), inverse(M_t), inverse(M_g), M_t, M_g)


def rotation_since(M_now, M_cal):
    """D = M_now * inv(M_cal): the rotation applied in the part's local frame since calibration."""
    return mul(M_now, inverse(M_cal))


def mat_record(mi, part_index):
    flags = (F_USE_HIT_ANGLE if mi.useHitAngle else 0) | (F_MAY_RICOCHET if mi.mayRicochet else 0) | (F_ONCE if mi.collideOnceOnly else 0) | (F_CAL_RIC if getattr(mi, 'checkCaliberForRichet', False) else 0) | (F_CAL_NORM if getattr(mi, 'checkCaliberForHitAngleNorm', False) else 0) | (F_EXTRA if mi.extra else 0)
    return (float(mi.armor or 0.0), float(mi.vehicleDamageFactor or 0.0), float(flags), float(part_index * 256 + mi.kind))


def _bounds(tris, ids):
    lo = [
     1e+30] * 3
    hi = [-1e+30] * 3
    for i in ids:
        for p in tris[i][:3]:
            for k in range(3):
                if p[k] < lo[k]:
                    lo[k] = p[k]
                if p[k] > hi[k]:
                    hi[k] = p[k]

    return (
     lo, hi)


def build_bvh(tris):
    """tris: [(p0, p1, p2, mat)] -> (nodes [(lo, hi, left, right)], order [tri ids in leaf order]).
    Median split on the centroid along the widest axis; leaves hold <= LEAF triangles; node 0 is the root."""
    res = []
    for _ in build_bvh_iter(tris, res):
        pass

    return (
     res[0], res[1])


BVH_NODES_PER_STEP = 12

def build_bvh_iter(tris, res):
    """generator version of build_bvh (yields every BVH_NODES_PER_STEP nodes), result in res = [nodes, order]"""
    cent = [ tuple((t[0][k] + t[1][k] + t[2][k]) / 3.0 for k in range(3)) for t in tris ]
    yield
    nodes = []
    order = []
    res[:] = [
     nodes, order]
    stack = [(list(range(len(tris))), None, None)]
    while stack:
        if len(nodes) % BVH_NODES_PER_STEP == BVH_NODES_PER_STEP - 1:
            yield
        ids, parent, is_left = stack.pop()
        lo, hi = _bounds(tris, ids)
        me = len(nodes)
        nodes.append([lo, hi, 0, 0])
        if parent is not None:
            nodes[parent][2 if is_left else 3] = me
        if len(ids) <= LEAF:
            nodes[me][2] = (
             'leaf', len(order))
            nodes[me][3] = len(ids)
            order.extend(ids)
            continue
        ext = [ hi[k] - lo[k] for k in range(3) ]
        ax = ext.index(max(ext))
        ids.sort(key=lambda i: cent[i][ax])
        mid = len(ids) // 2
        stack.append((ids[mid:], me, False))
        stack.append((ids[:mid], me, True))

    return


def bvh_entries(tris):
    """our own median-split BVH as entries (a body without a usable Havok tree)"""
    nodes, order = build_bvh(tris)
    size = [1] * len(nodes)
    for k in range(len(nodes) - 1, -1, -1):
        left = nodes[k][2]
        if not isinstance(left, tuple):
            size[k] = 1 + size[left] + size[nodes[k][3]]

    out = []
    for k, (lo, hi, left, right) in enumerate(nodes):
        if isinstance(left, tuple):
            out.append([lo, hi, 'L', [ tris[i] for i in order[left[1]:left[1] + right] ]])
        else:
            if not (left == k + 1):
                raise AssertionError('BVH not in pre-order')
            out.append([lo, hi, 'I', k + size[k]])

    return out


def top_tree(lists):
    """per-body entry lists (each starts with its root) -> one list: a median-split binary tree over the body roots with
    the bodies grafted at its leaves (without it every ray tests every body root: +90 % visits on 50TP)"""
    out = []

    def rec(its):
        if len(its) == 1:
            base = len(out)
            out.extend(([e[0], e[1], 'I', e[3] + base] if e[2] == 'I' else e) for e in its[0][2])
            return
        else:
            lo = [ min(i[0][k] for i in its) for k in range(3) ]
            hi = [ max(i[1][k] for i in its) for k in range(3) ]
            me = len(out)
            out.append([lo, hi, 'I', None])
            ext = [ hi[k] - lo[k] for k in range(3) ]
            ax = ext.index(max(ext))
            its = sorted(its, key=lambda i: i[0][ax] + i[1][ax])
            mid = len(its) // 2
            rec(its[:mid])
            rec(its[mid:])
            out[me][3] = len(out)
            return

    items = [ (l[0][0], l[0][1], l) for l in lists if l ]
    if items:
        rec(items)
    return out


class Texels(object):

    def __init__(self):
        self.t = []

    def add(self, v):
        self.t.append(tuple(float(x) for x in v))
        return len(self.t) - 1

    def set(self, i, v):
        while len(self.t) <= i:
            self.t.append((0.0, 0.0, 0.0, 0.0))

        self.t[i] = tuple(float(x) for x in v)


def build_texture(parts, rig, common_materials=None):
    """parts: {name: (bodies [(bodyName, matKind, [(p0,p1,p2)])], materials {kind: MaterialInfo}[, trees])}
    trees (optional, afl_havok.read_havok_iter): per body its Havok tree, or None -> our own BVH for that body.
    rig: (hull->chassis, hull->turret, turret->gun, M_t, M_g) from rig_from_nodes / rig_from_descriptor.
    Returns (texels list, info dict). Materials with armor 0 (vision blocks, triplexes, devices: vehicleDamageFactor 0) are kept: for HEAT the
    jet starts at the first layer it meets, so the gap behind a triplex costs 50 % per metre like in the game."""
    res = []
    for _ in build_texture_iter(parts, rig, common_materials, res):
        pass

    return (
     res[0], res[1])


def build_texture_iter(parts, rig, common_materials, res):
    """generator version of build_texture (yields between steps, result in res = [texels, info])"""
    T = Texels()
    for i in range(HEADER):
        T.set(i, (0, 0, 0, 0))

    mat_index = {}
    mats = []
    part_lists = []
    info = {'tris': [], 'mats': 0, 'nodes': [], 'own_bvh': 0}
    for pi, name in enumerate(PARTS):
        p = parts.get(name, ([], {}))
        bodies, materials = p[0], p[1]
        trees = p[2] if len(p) > 2 else None
        lists = []
        n = 0
        for bi, (bname, kind, ts) in enumerate(bodies):
            mi = materials.get(kind)
            if mi is None and common_materials is not None:
                mi = common_materials.get(kind)
            if mi is None or mi.armor is None or not ts:
                continue
            key = (
             pi, kind)
            if key not in mat_index:
                mat_index[key] = len(mats)
                mats.append(mat_record(mi, pi))
            m = mat_index[key]
            bt = [ (p0, p1, p2, m) for p0, p1, p2 in ts ]
            n += len(bt)
            e = None
            if trees is not None and trees[bi] is not None:
                import afl_havok
                try:
                    e = afl_havok.simd_entries(trees[bi], bt)
                except ValueError:
                    e = None

            if e is None:
                info['own_bvh'] += 1
                e = bvh_entries(bt)
            lists.append(e)
            yield

        part_lists.append(lists)
        info['tris'].append(n)

    mat_base = len(T.t)
    for rec in mats:
        T.add(rec)

    T.set(H_MAT, (mat_base, len(mats), 0, 0))
    info['mats'] = len(mats)
    for pi, lists in enumerate(part_lists):
        entries = top_tree(lists)
        yield
        node_base = len(T.t)
        tri_base = node_base + 2 * len(entries)
        nxt = tri_base
        for k, (lo, hi, kind, pl) in enumerate(entries):
            if kind == 'L':
                T.add((lo[0], lo[1], lo[2], -1.0 - nxt))
                T.add((hi[0], hi[1], hi[2], len(pl)))
                nxt += 3 * len(pl)
            else:
                if not (k < pl <= len(entries)):
                    raise AssertionError('tree not in pre-order')
                T.add((lo[0], lo[1], lo[2], node_base + 2 * pl))
                T.add((hi[0], hi[1], hi[2], 0.0))
            if k % 250 == 249:
                yield

        yield
        n_done = 0
        for lo, hi, kind, pl in entries:
            if kind != 'L':
                continue
            for p0, p1, p2, m in pl:
                T.add((p0[0], p0[1], p0[2], mat_base + m))
                T.add((p1[0] - p0[0], p1[1] - p0[1], p1[2] - p0[2], 0))
                T.add((p2[0] - p0[0], p2[1] - p0[1], p2[2] - p0[2], 0))
                n_done += 1
                if n_done % 200 == 0:
                    yield

        info['nodes'].append(len(entries))
        T.set(H_PARTS + pi, (node_base, tri_base, len(entries), n_done))

    iC, iT, iG, M_t, M_g = rig
    for base, M in ((H_CHASSIS, iC), (H_TURRET, iT), (H_GUN, iG)):
        for r in range(4):
            T.set(base + r, (M[r][0], M[r][1], M[r][2], 0))

    sph = []
    for _ in bounding_sphere_iter(parts, rig, sph):
        yield

    T.set(H_SPHERE, sph[0])
    T.set(0, (MAGIC, VERSION, TEX_W, len(PARTS)))
    info['texels'] = len(T.t)
    res[:] = [T.t, info]
    return


def bounding_sphere(parts, rig):
    """hull-space sphere that contains chassis + hull at their pose and turret + gun at any yaw/pitch."""
    res = []
    for _ in bounding_sphere_iter(parts, rig, res):
        pass

    return res[0]


SPHERE_STEP = 700

def _vertex_chunks(bodies):
    """distinct vertices of the bodies, SPHERE_STEP at a time (a triangle list repeats each vertex ~6 times)"""
    for body in bodies:
        vs = list(set(p for t in body[2] for p in t))
        for i in xrange(0, len(vs), SPHERE_STEP):
            yield vs[i:i + SPHERE_STEP]


def bounding_sphere_iter(parts, rig, res):
    """generator version of bounding_sphere (steps of SPHERE_STEP vertices), result in res[0]"""
    iC, iT, iG, M_t, M_g = rig
    M_c = inverse(iC)
    pts = []
    for name, M in (('chassis', M_c), ('hull', None)):
        for vs in _vertex_chunks(parts.get(name, ([], {}))[0]):
            pts.extend([ xform(p, M) for p in vs ] if M is not None else vs)
            yield

    if not pts:
        res[:] = [
         (0, 0, 0, 10)]
        return
    else:
        lo, hi = [
         1e+30] * 3, [-1e+30] * 3
        for i in xrange(0, len(pts), SPHERE_STEP):
            ch = pts[i:i + SPHERE_STEP]
            for k in range(3):
                lo[k] = min(lo[k], min(p[k] for p in ch))
                hi[k] = max(hi[k], max(p[k] for p in ch))

            yield

        c = [ (lo[k] + hi[k]) * 0.5 for k in range(3) ]
        R = 0.0
        for i in xrange(0, len(pts), SPHERE_STEP):
            R = max(R, max(math.sqrt(sum((p[k] - c[k]) ** 2 for k in range(3))) for p in pts[i:i + SPHERE_STEP]))
            yield

        pivot = M_t[3]
        reach = 0.0
        M_gh = mul(M_g, M_t)
        for name, M in (('turret', M_t), ('gun', M_gh)):
            for vs in _vertex_chunks(parts.get(name, ([], {}))[0]):
                for p in vs:
                    q = xform(p, M)
                    reach = max(reach, math.sqrt(sum((q[k] - pivot[k]) ** 2 for k in range(3))))

                yield

        R = max(R, math.sqrt(sum((pivot[k] - c[k]) ** 2 for k in range(3))) + reach)
        res[:] = [(c[0], c[1], c[2], R + 0.05)]
        return


DDS_STEP = 4096

def dds_iter(texels, out):
    """generator: the DDS file (RGBA32F, DX10 header) of the texels, DDS_STEP texels per step, result in out[0]"""
    h = (len(texels) + TEX_W - 1) // TEX_W
    flags = 4111
    pf = struct.pack('<II4sIIIII', 32, 4, 'DX10', 0, 0, 0, 0, 0)
    hdr = struct.pack('<IIIIIII', 124, flags, h, TEX_W, TEX_W * 16, 0, 1) + '\x00' * 44 + pf + struct.pack('<IIIII', 4096, 0, 0, 0, 0)
    chunks = ['DDS ' + hdr + struct.pack('<IIIII', 2, 3, 0, 1, 0)]
    for i in xrange(0, len(texels), DDS_STEP):
        ch = texels[i:i + DDS_STEP]
        chunks.append(struct.pack(('<%df' % (4 * len(ch))), *[ x for t in ch for x in t ]))
        yield

    chunks.append('\x00' * (TEX_W * h * 16 - 16 * len(texels)))
    out[:] = [('').join(chunks)]


def write_dds(path, texels):
    out = []
    for _ in dds_iter(texels, out):
        pass

    with open(path, 'wb') as (f):
        f.write(out[0])
    return (len(texels) + TEX_W - 1) // TEX_W


class Ref(object):

    def __init__(self, texels):
        self.t = texels

    def part_rays(self, o, d, Dt=None, Dg=None):
        """hull-space ray -> [(part index, local origin, local dir)] using the calibration + run-time rotations."""
        t = self.t
        M = lambda b: [ list(t[(b + r)][:3]) for r in range(4) ]
        iC, iT, iG = M(H_CHASSIS), M(H_TURRET), M(H_GUN)
        oc, oh = xform(o, iC), o
        off = self.offsets
        if off:
            oc = tuple(oc[k] - off[0][k] for k in range(3))
            oh = tuple(o[k] - off[1][k] for k in range(3))
        out = [
         (
          0, oc, xdir(d, iC)), (1, oh, d)]
        ot, dt = xform(o, iT), xdir(d, iT)
        if Dt is not None:
            ot, dt = _rot_t(ot, Dt), _rot_t(dt, Dt)
        out.append((2, ot, dt))
        og, dg = xform(ot, iG), xdir(dt, iG)
        if Dg is not None:
            og, dg = _rot_t(og, Dg), _rot_t(dg, Dg)
        out.append((3, og, dg))
        return out

    def hits_part(self, pi, o, d, tmax=1000000000.0):
        t = self.t
        nb, tb, nn, nt = [ int(x) for x in t[(H_PARTS + pi)] ]
        res = []
        if nn == 0:
            return res
        else:
            inv = tuple((1.0 / c if abs(c) > 1e-12 else 1000000000000.0) for c in d)
            n, end = nb, nb + 2 * nn
            it, cap = 0, self.max_iter or 1073741824
            while n < end:
                it += 1
                if it > cap:
                    self.capped += 1
                    break
                lo, hi = t[n], t[(n + 1)]
                leaf = lo[3] < 0
                if _slab(o, inv, lo, hi, tmax):
                    if leaf:
                        first = int(-1 - lo[3])
                        for k in range(int(hi[3])):
                            b = first + 3 * k
                            h = _tri(o, d, t[b], t[(b + 1)], t[(b + 2)])
                            if h is not None and h[0] <= tmax:
                                res.append((h[0], int(t[b][3]), h[1], pi))

                    n += 2
                else:
                    n = n + 2 if leaf else int(lo[3])

            return res

    def all_hits(self, o, d, Dt=None, Dg=None):
        hits = []
        for pi, lo, ld in self.part_rays(o, d, Dt, Dg):
            hits.extend(self.hits_part(pi, lo, ld))

        hits.sort(key=lambda h: (h[0] + (self.TIE if self.t[h[1]][1] > 0.0 else 0.0), h[3]))
        return hits

    TIE = 5e-05
    offsets = None
    max_iter = None
    capped = 0

    def material(self, m):
        return self.t[m]


def _rot_t(v, D):
    """v * transpose(D[0..2])"""
    return (
     v[0] * D[0][0] + v[1] * D[0][1] + v[2] * D[0][2],
     v[0] * D[1][0] + v[1] * D[1][1] + v[2] * D[1][2],
     v[0] * D[2][0] + v[1] * D[2][1] + v[2] * D[2][2])


def _slab(o, inv, lo, hi, tmax):
    t0, t1 = 0.0, tmax
    for k in range(3):
        a = (lo[k] - o[k]) * inv[k]
        b = (hi[k] - o[k]) * inv[k]
        if a > b:
            a, b = b, a
        t0 = max(t0, a)
        t1 = min(t1, b)

    return t0 <= t1 + 1e-06


def _tri(o, d, a, e1, e2):
    """Moller-Trumbore, double sided -> (t, |cos|) or None"""
    px = d[1] * e2[2] - d[2] * e2[1]
    py = d[2] * e2[0] - d[0] * e2[2]
    pz = d[0] * e2[1] - d[1] * e2[0]
    det = e1[0] * px + e1[1] * py + e1[2] * pz
    if abs(det) < 1e-12:
        return None
    else:
        inv = 1.0 / det
        sx, sy, sz = o[0] - a[0], o[1] - a[1], o[2] - a[2]
        u = (sx * px + sy * py + sz * pz) * inv
        if u < 0.0 or u > 1.0:
            return None
        qx = sy * e1[2] - sz * e1[1]
        qy = sz * e1[0] - sx * e1[2]
        qz = sx * e1[1] - sy * e1[0]
        v = (d[0] * qx + d[1] * qy + d[2] * qz) * inv
        if v < 0.0 or u + v > 1.0:
            return None
        t = (e2[0] * qx + e2[1] * qy + e2[2] * qz) * inv
        if t <= 1e-05:
            return None
        nx = e1[1] * e2[2] - e1[2] * e2[1]
        ny = e1[2] * e2[0] - e1[0] * e2[2]
        nz = e1[0] * e2[1] - e1[1] * e2[0]
        ln = math.sqrt(nx * nx + ny * ny + nz * nz) * math.sqrt(d[0] ** 2 + d[1] ** 2 + d[2] ** 2)
        return (t, abs(nx * d[0] + ny * d[1] + nz * d[2]) / ln if ln > 0 else 1.0)


def classify_lesta(hits, ref, shot):
    """Lesta 1.45 gun_marker_ctrl.__shotResultDefault on ordered hits [(dist, mat, |cos|, part)].
    shot: dict pp (full, at distance), cal, norm (0 if no normalisation), rcos (< -1: shell never ricochets),
    checkCal (kind checks the 3-calibre rule), jet (loss per metre), R (randomisation), modernHE.
    Returns 1 NOT, 2 LITTLE, 3 GREAT (SHOT_RESULT values)."""
    pp = shot['pp']
    full = pp
    minPP = 100.0 * (1.0 - shot['R'] * 0.5)
    maxPP = 100.0 * (1.0 + shot['R'] * 0.5)
    result = 1
    ignored = set()
    is_jet = False
    jet_start = 0.0
    for dist, m, c_abs, part in hits:
        armor, vdf, flags, key = ref.material(m)
        flags = int(flags)
        if key in ignored:
            continue
        if is_jet:
            jd = dist - jet_start
            if jd > 0.0:
                pp *= 1.0 - jd * shot['jet']
        c = c_abs if flags & F_USE_HIT_ANGLE else 1.0
        if not is_jet and shot['rcos'] > -1.5 and flags & F_MAY_RICOCHET and armor != 0 and c <= shot['rcos'] and (not flags & F_CAL_RIC or not shot['checkCal'] or armor * 3.0 >= shot['cal']):
            return 1
        pa = armor
        if flags & F_USE_HIT_ANGLE:
            n = shot['norm']
            if n > 0.0 and c < 1.0:
                if flags & F_CAL_NORM and shot['cal'] > armor * 2.0 > 0.0:
                    n *= 1.4 * shot['cal'] / (armor * 2.0)
                a = math.acos(c) - n
                c = 1.0 if a < 0.0 else math.cos(min(a, math.pi * 0.5 - 1e-05))
            pa = armor / max(c, 1e-05)
        pct = 100.0 + (pa - pp) / full * 100.0
        pp -= pa
        if vdf > 0.0:
            if minPP < pct < maxPP:
                return 2
            if pct <= minPP:
                return 3
            return 1
        if flags & F_ONCE:
            ignored.add(key)
        if pp <= 0.0:
            break
        if shot['jet'] > 0.0:
            is_jet = True
            jet_start = dist + armor * 0.001

    return result