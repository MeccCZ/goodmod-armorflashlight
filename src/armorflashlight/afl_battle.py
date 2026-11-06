# uncompyle6 version 3.7.4
# Python bytecode 2.7 (62211)
# Decompiled from: Python 3.10.6 (tags/v3.10.6:9c7b4bd, Aug  1 2022, 21:53:49) [MSC v.1932 64 bit (AMD64)]
# Embedded file name: scripts/client/gui/mods/armorflashlight/afl_battle.py
# Compiled at: 2026-01-01 04:00:00
import json, math, os, struct, time, BigWorld, CGF, GenericComponents, Math, ResMgr, afl_data as A, afl_fwdpack as FP, afl_havok as HK, afl_settings as SET, lai_models as M, log as LG, runtime
try:
    import afl_accel as X
except Exception:
    X = None
    LG.exception('afl', 'afl_accel import (the data is built in Python)')

CACHE_VFS = 'afl_cache'
PROXY_BBOX_PAD = 1500.0
CACHE_VER = 'v40'
FX = 'shaders/custom/afl_flashlight46.fx'
FOL_OFF_DELAY = 0.6
CACHE_TAG = '%s_%s' % (CACHE_VER, FX.split('/')[(-1)].split('.')[0].replace('afl_flashlight', 'fx'))
CACHE_KEEP = '_%s(_proxy)?$' % CACHE_TAG
GEN_BUDGET = 0.004
PRE_MARGIN = 3.0
PRE_BUDGET = (0.002, 0.008)
BATTLE_BUDGET = 0.002
URGENT_SHARE = 0.5
PRE_SHARE = (0.06, 0.3)
BATTLE_SHARE = 0.06
STEP_EST = 0.001
CREDIT_FRAMES = 4
JOB_COST = {'data': 0.1, 'warm': 0.01}
NATIVE_COST = 0.005
SLOW_STEP = 0.008
RETRY_FAILED = 30.0
APPEAR = 0.0
CIRCLE_ADJUST = 1.15
RADIUS_MIN = 1.5
HOLD = 3.0
CIRCLE_BLEND = 0.25
EU_RADIUS_BY_DIST = ((100.0, 0.5), (300.0, 0.8))
EU_SMOOTH_ADJ = 1.4
EU_T2 = 0.439453125
EU_SIZE_MUL, EU_MIN_PX = (1.72333, 32.0)
EU_CAP, OURS_CAP = (0.14, 0.28)
CUT_SPAN = 0.3
DDS_DATA = 148
FADEOFF_NOT_AIMED = 0.0
SCHEMES = ('redYellowGreen', 'redShades', 'greenShades')
PATTERNS = ('none', 'pattern_1 solid', 'pattern_2 sparse', 'pattern_3 dense')
QUALITY = ('normal (circle up to 28 % of the screen, like EU)', 'economy (circle up to 14 %: fewer pixels traced)',
           'full (no circle: the whole visible target, most pixels traced)')
RASTER = -1
MODE_WEAKPC = 3
_S = {'on': False, 'enabled': True, 'muzzle': True, 'through': True, 'allies': False, 'debug': 0, 'quality': 0, 'scheme': 0, 'pattern': 1, 'opacity': 0.7, 'marker': None, 
   'target': None, 'proxy': None, 'jobs': [], 'specs': {}, 'err': None, 'seen': 0.0, 'tp': {}, 'warm': {}, 'dt': 1.0 / 60, 'last_tick': 0.0, 'failed': {}, 'cache_dir': None, 'nocache': False, 'est': STEP_EST, 
   'credit': 0.0, 'foliage': True, 'destr': True, 'via': False, 'circle_key': None, 
   'typing': None, 'circle_k': 0.0, 'circle_s': 0.0, 'circle_t': 0.0, 'mode': 0, 'weakpc': False}

def _log(*a):
    LG.note('afl', *a)


def _dbg(*a):
    LG.debug('afl', *a)


def _cache_dir():
    """the cache folder (res_mods/<ver>/afl_cache) if the VFS sees files written there now, else None"""
    c = runtime.cache(CACHE_VFS)
    if c['ok']:
        return c['path']
    else:
        return


def load_native():
    """the C++ accelerator of the data build (optional, see afl_accel): loaded once at mod start, not in battle -- the
    shim's first load per Tanki.exe scans the exe for ~5 s"""
    pyd = runtime.native_pyd()
    if pyd is None:
        _log('native accelerator: not in this build, the data is built in Python')
        return
    else:
        if X is None:
            return
        return X.load(pyd, runtime.temp_dir())


_KEYS = {}

def _wheel_havoks(td):
    """the collision files of the wheels (see _wheel_nodes / _wheel_files), the cheap way: names only, no model is loaded"""
    ch = td.chassis
    try:
        if not ch.wheelsArmor:
            return []
        else:
            if ch.wheels is not None:
                return [ w.hitTester.bspModelName.replace('.model', '.havok') for w in ch.wheels.wheels if w.hitTester.bspModelName ]
            return sorted(_wheel_files(td).values())

    except Exception:
        return []

    return


def _key(td):
    """cache key of a vehicle configuration: short name + hash of everything the data is built from (collision models,
    their materials, the part mounts), so chassis / hull variants with other armour get their own data and the same
    armour under another name shares it"""
    names = (td.name, td.chassis.name, getattr(td.hull, 'variantName', ''), td.turret.name, td.gun.name)
    k = _KEYS.get(names)
    if k is None:
        import hashlib
        h = hashlib.md5()
        for pi, name in enumerate(A.PARTS):
            comp = getattr(td, name)
            h.update(comp.hitTester.bspModelName)
            h.update(runtime.fingerprint(comp.hitTester.bspModelName.replace('.model', '.havok')))
            for kind, mi in sorted(dict(comp.materials).items()):
                h.update(repr((kind, A.mat_record(mi, pi) if mi is not None else None)))

        for path in _wheel_havoks(td):
            h.update(runtime.fingerprint(path))

        v3 = lambda v: (
         v[0], v[1], v[2])
        h.update(repr((v3(td.chassis.hullPosition), v3(td.hull.turretPositions[0]), v3(td.turret.gunPosition))))
        k = _KEYS[names] = '%s__%s_%s' % (td.name.split(':')[(-1)], h.hexdigest()[:10], CACHE_TAG)
    return k


def _cached_spec(key):
    """-> spec from memory or the disk cache, None if the data was never built"""
    sp = _S['specs'].get(key)
    if sp is not None:
        return sp
    else:
        sec = ResMgr.openSection(CACHE_VFS + '/' + key + '.json')
        if sec is None:
            return
        try:
            sp = json.loads(sec.asBinary)
            (sp['dds'], sp['proxy'])
        except (ValueError, KeyError, TypeError) as ex:
            _log('cache', key, 'unreadable, rebuilding:', repr(ex))
            return

        _S['specs'][key] = sp
        runtime.touch(CACHE_VFS, key)
        return sp


def _spec(td):
    """-> {'dds', 'proxy'} if the data exists (memory or disk), else None (and queues the generation, urgent)"""
    sp = _cached_spec(_key(td))
    if sp is None:
        _enqueue(td, urgent=True)
    return sp


def _enqueue(td, urgent=False, kind='data'):
    """kind 'data': build the data texture + proxy; 'warm': load the built resources into the engine ahead of time"""
    key = _key(td)
    if kind == 'data':
        if key in _S['specs'] or _S['nocache']:
            return
        failed = _S['failed'].get(key)
        if failed is not None and time.time() - failed < RETRY_FAILED:
            return
    jid = kind + ':' + key
    jobs = _S['jobs']
    for j in jobs:
        if j['id'] == jid:
            if urgent:
                j['urgent'] = True
                if jobs[0] is not j:
                    jobs.remove(j)
                    jobs.insert(0, j)
            break
    else:
        j = {'id': jid, 'key': key, 'td': td, 'it': None, 'kind': kind, 'urgent': urgent}
        if urgent:
            jobs.insert(0, j)
        else:
            jobs.append(j)
    if urgent and kind == 'data':
        for w in jobs[1:]:
            if w['id'] == 'warm:' + key:
                w['urgent'] = True
                jobs.remove(w)
                jobs.insert(1, w)
                break

    return


def _wheel_nodes(td):
    """-> [(nodeName, (x, y, z) in chassis space, collision .model path or None)] of the wheels that have their own
    collision. In the game each wheel is a separate collision part placed at its chassis node (model_assembler.attachModels),
    with the material chassis.wheelsArmor[node] (Vehicle.getMatinfo) -- none of this is in chassis.havok.
    Two descriptor kinds: chassis.wheels (own hitTester + position per wheel) and generalWheelsAnimatorConfig (node names;
    the collision files wheel_l_*.havok / wheel_r_*.havok lie next to the chassis one, the nodes are in the chassis model)"""
    ch = td.chassis
    if not ch.wheelsArmor:
        return []
    else:
        if ch.wheels is not None:
            return [ (w.nodeName, tuple(w.position), w.hitTester.bspModelName) for w in ch.wheels.wheels if w.hitTester.bspModelName ]
        cfg = ch.generalWheelsAnimatorConfig
        if cfg is None:
            return []
        model = BigWorld.Model(ch.models.undamaged)
        out = []
        for n in cfg.getNonTrackWheelNodeNames():
            t = Math.Matrix(model.node(n)).translation
            out.append((n, (t.x, t.y, t.z), None))

        return out


def _wheel_files(td):
    """{'l': path, 'r': path} or {'': path}: the wheel collision files lying next to the chassis one (general wheels)"""
    d = td.chassis.hitTester.bspModelName.rsplit('/', 1)[0]
    sec = ResMgr.openSection(d)
    names = sorted(k for k in (sec.keys() if sec is not None else ()) if k.lower().startswith('wheel') and k.endswith('.havok'))
    res = {}
    for k in names:
        low = k.lower()
        side = 'l' if '_l_' in low or low.startswith('wheel_l') else 'r' if '_r_' in low or low.startswith('wheel_r') else ''
        res.setdefault(side, d + '/' + k)

    return res


def _wheel_bodies(td):
    """-> ([(bodyName, matKind, [(p0, p1, p2)])] in chassis space, {kind: MaterialInfo}) for the wheels, or ([], {}).
    The vehicle's wheel material (wheelsArmor, e.g. 5 mm / no damage / collide once) replaces the common one of the same
    kind (the common 254 has no armour at all): the game takes the wheel's own first"""
    bodies, mats, cache = [], {}, {}
    nodes = _wheel_nodes(td)
    if not nodes:
        return (bodies, mats)
    else:
        files = _wheel_files(td) if td.chassis.wheels is None else {}
        for wi, (name, pos, path) in enumerate(nodes):
            if path is None:
                path = files.get('l' if pos[0] < 0.0 else 'r') or files.get('')
            if not path:
                continue
            tris = cache.get(path)
            if tris is None:
                sec = ResMgr.openSection(path.replace('.model', '.havok'))
                raw = []
                if sec is not None:
                    for _ in HK.read_havok_iter(sec.asBinary, raw, []):
                        pass

                tris = cache[path] = raw
            mi = td.chassis.wheelsArmor.get(name)
            for bname, kind, ts in tris:
                moved = [ tuple((p[0] + pos[0], p[1] + pos[1], p[2] + pos[2]) for p in tri) for tri in ts ]
                k = WHEEL_KIND0 + wi
                bodies.append(('%s:%s' % (name, bname), k, moved))
                if mi is not None:
                    mats[k] = _MatAs(mi, k)

        return (
         bodies, mats)


WHEEL_KIND0 = 1000

class _MatAs(object):
    """a MaterialInfo under another kind number"""
    __slots__ = ('armor', 'vehicleDamageFactor', 'useHitAngle', 'mayRicochet', 'collideOnceOnly',
                 'checkCaliberForRichet', 'checkCaliberForHitAngleNorm', 'extra',
                 'kind')

    def __init__(self, mi, kind):
        for a in self.__slots__:
            setattr(self, a, getattr(mi, a, False))

        self.kind = kind


def _job_iter(j):
    """havok of the four parts (+ the wheels) -> data texture + proxy cube model, written to afl_cache"""
    from items import vehicles
    td = j['td']
    d = _S['cache_dir'] or _cache_dir()
    if d is None or not os.path.isdir(d):
        raise RuntimeError('cache folder %s not available (created in this session: restart the client)' % CACHE_VFS)
    key = j['key']
    havok, own = [], []
    for name in A.PARTS:
        comp = getattr(td, name)
        sec = ResMgr.openSection(comp.hitTester.bspModelName.replace('.model', '.havok'))
        havok.append(sec.asBinary if sec is not None else '')
        own.append(dict(comp.materials))

    rig, common = A.rig_from_descriptor(td), vehicles.g_cache.commonConfig['materials']
    wheels, wmats = _wheel_bodies(td)
    yield
    own[0].update(wmats)
    r = None if wheels or X is None else X.build(havok, own, common, rig)
    if r is not None:
        dds, info, sphere = r
        with open(os.path.join(d, key + '.dds'), 'wb') as (f):
            f.write(dds)
    else:
        parts = {}
        for pi, name in enumerate(A.PARTS):
            bodies, trees = [], []
            if havok[pi]:
                for _ in HK.read_havok_iter(havok[pi], bodies, trees):
                    yield

            if pi == 0 and wheels:
                bodies = list(bodies) + wheels
                trees = list(trees) + [None] * len(wheels)
            parts[name] = (
             bodies, own[pi], trees)

        res = []
        for _ in A.build_texture_iter(parts, rig, common, res):
            yield

        texels, info = res
        out = []
        for _ in A.dds_iter(texels, out):
            yield

        with open(os.path.join(d, key + '.dds'), 'wb') as (f):
            f.write(out[0])
        sphere = texels[A.H_SPHERE]
    yield
    cx, cy, cz, R = sphere
    corner = lambda sx, sy, sz: (cx + sx * R, cy + sy * R, cz + sz * R)
    faces = [((-1, -1, -1), (1, -1, -1), (1, 1, -1), (-1, 1, -1)), ((-1, -1, 1), (-1, 1, 1), (1, 1, 1), (1, -1, 1)),
     (
      (-1, -1, -1), (-1, 1, -1), (-1, 1, 1), (-1, -1, 1)), ((1, -1, -1), (1, -1, 1), (1, 1, 1), (1, 1, -1)),
     (
      (-1, -1, -1), (-1, -1, 1), (1, -1, 1), (1, -1, -1)), ((-1, 1, -1), (1, 1, -1), (1, 1, 1), (-1, 1, 1))]
    tris = []
    for a, b, c, e in faces:
        tris += [(corner(*a), corner(*b), corner(*c)), (corner(*a), corner(*c), corner(*e))]

    old = M.FX_PATH
    M.FX_PATH = FX
    try:
        r = M.build([('proxy', 1, tris)], {1: {'armor': 1.0, 'vdf': 1.0}}, CACHE_VFS, key + '_proxy', inflate=0.0, blend='alpha', bbox_pad=PROXY_BBOX_PAD)
    finally:
        M.FX_PATH = old

    yield
    for ext, data in zip(('.model', '.visual_processed', '.primitives_processed'), r[:3]):
        with open(os.path.join(d, key + '_proxy' + ext), 'wb') as (f):
            f.write(data)

    yield
    sp = {'dds': CACHE_VFS + '/' + key + '.dds', 'proxy': CACHE_VFS + '/' + key + '_proxy.model', 'raster': {}, 'info': info}
    final = os.path.join(d, key + '.json')
    with open(final + '.tmp', 'wb') as (f):
        f.write(json.dumps(sp))
    if os.path.exists(final):
        os.remove(final)
    os.rename(final + '.tmp', final)
    _S['specs'][key] = sp
    return


def _countdown_left():
    """s until the battle starts: > 0 while the pre-battle countdown runs, None while waiting for players
    (no end time yet), 0 once the battle runs"""
    try:
        import constants
        arena = BigWorld.player().arena
        if arena.period == constants.ARENA_PERIOD.PREBATTLE:
            return max(0.0, arena.periodEndTime - BigWorld.serverTime())
        if arena.period in (constants.ARENA_PERIOD.IDLE, constants.ARENA_PERIOD.WAITING):
            return
    except Exception:
        pass

    return 0.0


def _budget():
    """s of generation this frame: the aimed-at target at once; the roster paced to be ready before the countdown
    ends (PRE_MARGIN s early), then a trickle"""
    jobs = _S['jobs']
    if not jobs:
        return 0.0
    else:
        frame = max(_S['dt'], 1.0 / 240)
        if jobs[0].get('urgent'):
            return min(GEN_BUDGET, URGENT_SHARE * frame)
        left = _countdown_left()
        lo, hi = min(PRE_BUDGET[0], PRE_SHARE[0] * frame), min(PRE_BUDGET[1], PRE_SHARE[1] * frame)
        if left is None:
            return lo
        if left <= 0.0:
            return min(BATTLE_BUDGET, BATTLE_SHARE * frame)
        left -= PRE_MARGIN
        if left <= 0.0:
            return hi
        native = X is not None and X._S['mod'] is not None
        work = sum((NATIVE_COST if native and j['kind'] == 'data' else JOB_COST[j['kind']]) for j in jobs)
        return min(hi, max(lo, 1.3 * work / (left / frame)))


def _gen_step():
    """generator steps while the budget lasts: unused budget carries over (CREDIT_FRAMES), a step runs once the credit
    covers the expected step time, and a step longer than expected is paid back by the next frames"""
    jobs = _S['jobs']
    if not jobs:
        _S['credit'] = 0.0
        return
    else:
        allow = _budget()
        credit = min(_S.get('credit', 0.0) + allow, CREDIT_FRAMES * allow + _S['est'])
        while _S['jobs'] and credit >= _S['est']:
            j = _S['jobs'][0]
            if j['it'] is None:
                j['it'] = (_warm_iter if j['kind'] == 'warm' else _job_iter)(j)
                j['n'], j['t'], j['slow'] = (0, 0.0, 0.0)
            t0 = time.clock()
            try:
                next(j['it'])
            except StopIteration:
                _S['jobs'].pop(0)
                if j['slow'] > SLOW_STEP:
                    _dbg('%s %s: %d steps, %.0f ms, slowest %.0f ms' % (j['kind'], j['key'], j['n'], j['t'] * 1000.0,
                     j['slow'] * 1000.0))
            except Exception:
                _S['jobs'].pop(0)
                if j['kind'] == 'data':
                    first = j['key'] not in _S['failed']
                    _S['failed'][j['key']] = time.time()
                    if first:
                        import traceback
                        _log('data for', j['key'], 'failed:', traceback.format_exc())
                else:
                    import traceback
                    _log(j['kind'], 'for', j['key'], 'failed:', traceback.format_exc())

            dt = time.clock() - t0
            j['n'] += 1
            j['t'] += dt
            j['slow'] = max(j['slow'], dt)
            credit -= dt
            _S['est'] = 0.9 * _S['est'] + 0.1 * dt

        _S['credit'] = credit
        return


def _texture(sp):
    tp = _S['tp'].get(sp['dds'])
    if tp is None:
        tp = _S['tp'][sp['dds']] = BigWorld.PyTextureProvider(sp['dds'])
    return tp


def _warm_iter(j):
    """engine resources of a built vehicle, loaded ahead of the first aim: spec, data texture, proxy model (background
    loader, the refs keep it cached), our copy of its collision models (engine offsets, _raw_collider)"""
    sp = _cached_spec(j['key'])
    if sp is None:
        return
    else:
        yield
        _texture(sp)
        yield
        if sp['proxy'] not in _S['warm']:
            _S['warm'][sp['proxy']] = None

            def loaded(refs, path=sp['proxy'], warm=_S['warm']):
                if _S['on'] and _S['warm'] is warm:
                    warm[path] = refs

            BigWorld.loadResourceListBG((sp['proxy'],), loaded)
        yield
        _raw_collider(j['td'], j['key'])
        return


def _enemy_td(player, info):
    td = info.get('vehicleType')
    if td is None or info.get('team') == player.team or 'observer' in td.type.tags:
        return
    return td


def _preload(tds):
    """warm-ups of the types already built first (cheap, most of the roster), then data + warm-up of each new type"""
    cached, fresh = [], []
    for td in tds:
        try:
            (fresh if _cached_spec(_key(td)) is None else cached).append(td)
        except Exception as ex:
            _log('roster entry', td.name, 'skipped:', repr(ex))

    for td in cached:
        _enqueue(td, kind='warm')

    for td in fresh:
        _enqueue(td)
        _enqueue(td, kind='warm')

    return


def _preload_roster():
    """every enemy vehicle type: data (if not cached yet), then the warm-up; paced by _budget() over the countdown"""
    player = BigWorld.player()
    tds = [ td for td in (_enemy_td(player, info) for info in player.arena.vehicles.itervalues()) if td is not None ]
    _preload(tds)
    _prune_jobs(set(_key(td) for td in tds))
    _dbg('roster: %d jobs, countdown %s s' % (len(_S['jobs']), _countdown_left()))
    return


def _prune_jobs(keys):
    """drop queued roster jobs of types no enemy fields any more (vehicle chosen again, respawn modes)"""
    _S['jobs'][:] = [ j for j in _S['jobs'] if j['urgent'] or j['key'] in keys or j['it'] is not None ]
    return


def _on_vehicle(vid):
    """arena.onVehicleAdded / onVehicleUpdated: a type that joined or changed during the battle"""
    if not _S['on']:
        return
    else:
        try:
            player = BigWorld.player()
            info = player.arena.vehicles.get(vid)
            td = info and _enemy_td(player, info)
            if td is None:
                return
            key = _key(td)
            if key in _RAW or key in _S['failed'] or any(j['key'] == key for j in _S['jobs']):
                return
            _preload([td])
            keys = set()
            for i in player.arena.vehicles.itervalues():
                t = _enemy_td(player, i)
                if t is not None:
                    keys.add(_key(t))

            _prune_jobs(keys)
        except Exception as ex:
            _log('roster update:', repr(ex))

        return


def _on_vehicle_list():
    if _S['on']:
        try:
            _preload_roster()
        except Exception as ex:
            _log('roster:', repr(ex))


def _arena_events(subscribe):
    """subscribe to the current arena / unsubscribe from the one subscribed to (player.arena is None by then)"""
    if subscribe:
        arena = _S['arena'] = getattr(BigWorld.player(), 'arena', None)
    else:
        arena, _S['arena'] = _S.get('arena'), None
    if arena is None:
        return
    else:
        try:
            for ev, fn in (('onVehicleAdded', _on_vehicle), ('onVehicleUpdated', _on_vehicle),
             (
              'onNewVehicleListReceived', _on_vehicle_list)):
                e = getattr(arena, ev)
                if subscribe:
                    e += fn
                else:
                    e -= fn

        except Exception as ex:
            _log('arena events:', repr(ex))

        return


class _Flags(object):
    from AvatarInputHandler import aih_global_binding as _b
    flags = _b.bindRO(_b.BINDING_ID.GUN_MARKERS_FLAGS)
    client = _b.bindRO(_b.BINDING_ID.CLIENT_GUN_MARKER_STATE)
    server = _b.bindRO(_b.BINDING_ID.SERVER_GUN_MARKER_STATE)
    clientDP = _b.bindRO(_b.BINDING_ID.CLIENT_GUN_MARKER_DATA_PROVIDER)
    serverDP = _b.bindRO(_b.BINDING_ID.SERVER_GUN_MARKER_DATA_PROVIDER)


_FLAGS = _Flags()

def _on_marker(markerType, position, direction, collData, *a, **k):
    from aih_constants import GUN_MARKER_TYPE, GUN_MARKER_FLAG
    try:
        flags = _FLAGS.flags
    except Exception:
        flags = None

    if flags is not None:
        server = bool(flags & GUN_MARKER_FLAG.SERVER_MODE_ENABLED)
        if server and markerType != GUN_MARKER_TYPE.SERVER:
            return
        if not server and markerType != GUN_MARKER_TYPE.CLIENT:
            return
    _S['marker'] = (
     Math.Vector3(position), Math.Vector3(direction), collData)
    return


def _poll_marker():
    """current gun-marker state (position, direction, collData) read every frame from the input-handler bindings
    (the crosshair event only fires when the state changes -> a still aim would never deliver it)"""
    from aih_constants import GUN_MARKER_FLAG
    try:
        server = bool(_FLAGS.flags & GUN_MARKER_FLAG.SERVER_MODE_ENABLED)
        st = _FLAGS.server if server else _FLAGS.client
    except Exception:
        st = None

    if st and not isinstance(st[1], (int, float)):
        H = Math.Vector3(st[0])
        _S['marker_pt'] = Math.Vector3(H)
        try:
            dp = _FLAGS.serverDP if server else _FLAGS.clientDP
            H = Math.Matrix(dp.positionMatrixProvider).translation
        except Exception:
            pass

        _S['marker'] = (Math.Vector3(H), Math.Vector3(st[1]), st[2])
    elif st:
        _S['marker'] = None
    return


def _target_ok(e, player):
    from Vehicle import Vehicle
    try:
        if e is None or not isinstance(e, Vehicle) or not e.isAlive() or getattr(e, 'health', 0) <= 0:
            return False
        if not getattr(e, 'isStarted', True) or getattr(e, 'appearance', None) is None:
            return False
        return e.publicInfo['team'] != player.team or _S['allies']
    except AttributeError:
        return False

    return


def _sphere(sp):
    """hull-space bounding sphere (centre xyz, radius) of a configuration: texel H_SPHERE of its data texture"""
    s = sp.get('sphere')
    if s is None:
        try:
            raw = ResMgr.openSection(sp['dds']).asBinary
            o = DDS_DATA + A.H_SPHERE * 16
            s = struct.unpack('<4f', raw[o:o + 16])
        except Exception as ex:
            _log('bounding sphere of', sp['dds'], 'unreadable:', repr(ex))
            s = (0.0, 1.5, 0.0, 6.0)

        sp['sphere'] = s
    return s


def _reaches(e, H):
    """the aiming circle still overlaps the target's bounding sphere on screen (angles seen from the camera, like the
    shader's circle): a shot that grazes the turret lands hundreds of metres behind it, yet the circle stays on it"""
    sp = _cached_spec(_key(e.typeDescriptor))
    if sp is None:
        return False
    else:
        cx, cy, cz, R = _sphere(sp)
        try:
            C = Math.Matrix(e.appearance.compoundModel.node('hull')).applyPoint(Math.Vector3(cx, cy, cz))
            cam = Math.Vector3(BigWorld.camera().position)
        except Exception:
            return False

        a, b = C - cam, H - cam
        la, lb = a.length, b.length
        if la <= R or lb < 0.001:
            return True
        cos = max(-1.0, min(1.0, a.dot(b) / (la * lb)))
        try:
            dist = (Math.Vector3(e.position) - BigWorld.player().getOwnVehiclePosition()).length
        except Exception:
            dist = la

        rc, _, tanh = _circle(dist)
        return math.acos(cos) <= math.asin(R / la) + math.atan(2.0 * rc * tanh)


try:
    from constants import DESTRUCTIBLE_MATKIND as _DK
    DESTR_KINDS = (_DK.MIN, _DK.MAX)
except Exception:
    DESTR_KINDS = (71, 100)

DESTR_REACH = 700.0

def _is_destr(r):
    """a BigWorld.collideSegment result is a breakable object (fence, wall, car...): shells fly through those"""
    try:
        return r is not None and DESTR_KINDS[0] <= r.matKind <= DESTR_KINDS[1]
    except Exception:
        return False

    return


GROUND_KIND_MIN = 101

def _is_ground(r):
    """the collide result is the ground: terrain, or a static model with a ground material (a kerb, a road edge)"""
    try:
        return bool(r.isTerrain()) or r.matKind >= GROUND_KIND_MIN
    except Exception:
        return False


def _first_solid(sp, a, b, skip=True, thin=0.0):
    """first static hit on a -> b that stops a shell: the segment is walked on past the breakable objects when skip is set
    (measured in a replay: AP, APCR and HE all fly on through fences and walls, each one a pair of hits ~0.7 m apart).
    thin > 0: a non-terrain solid that the segment leaves again within this many metres (a post, a trunk, a lamp) is walked
    past as well. -> the collide result or None"""
    d = b - a
    L = d.length
    if L < 0.001:
        return
    else:
        d = d * (1.0 / L)
        pos = a
        for _ in range(24):
            r = BigWorld.collideSegment(sp, pos, b, 128)
            if r is None:
                return
            cp = r.closestPoint
            if skip and _is_destr(r):
                pos = cp + d * 0.05
                continue
            if thin > 0.0 and not _is_ground(r):
                far = cp + d * min(thin, max((b - cp).length, 0.0))
                r2 = BigWorld.collideSegment(sp, cp + d * 0.05, far, 128) if (far - cp).length > 0.1 else None
                if r2 is not None:
                    pos = r2.closestPoint + d * 0.05
                    continue
            return r

        return


DESTR_LOSS = 25.0

def _destr_info(H):
    """the breakable objects on the line camera -> H: (metres from the first one to H, how many objects). An object is a pair
    of hits (the way in, the way out); the walk stops at anything solid. (0.0, 0) when there is none"""
    try:
        sp = BigWorld.player().spaceID
        cam = Math.Vector3(BigWorld.camera().position)
        v = H - cam
        L = v.length
        if L < 0.001:
            return (0.0, 0)
        v = v * (1.0 / L)
        pos, hits, first = cam, 0, None
        for _ in range(40):
            r = BigWorld.collideSegment(sp, pos, H, 128)
            if r is None or not _is_destr(r):
                break
            d = (r.closestPoint - cam).length
            if first is None:
                first = d
            hits += 1
            pos = r.closestPoint + v * 0.05

        if first is None:
            return (0.0, 0)
        return (
         max(L - first, 0.0), (hits + 1) // 2)
    except Exception:
        return (0.0, 0)

    return


def _marker_on_destr(H):
    """the game's marker point lies on a breakable object (fence, wall, car)"""
    try:
        cam = Math.Vector3(BigWorld.camera().position)
        v = H - cam
        L = v.length
        if L < 1.0:
            return False
        v = v * (1.0 / L)
        return _is_destr(BigWorld.collideSegment(BigWorld.player().spaceID, H - v * 0.5, H + v * 0.5, 128))
    except Exception:
        return False


def _through_destr(player, H, cam=None):
    """the game's gun marker rests on a breakable object, but the shot goes through it: the vehicle behind it on the same
    line of sight (a shell passes the object, so the marker's own point says nothing about what it hits) or None.
    Candidates must lie past the marker and before the first solid obstacle behind it"""
    try:
        sp = player.spaceID
        cam_arg = cam
        if cam is None:
            cam = Math.Vector3(BigWorld.camera().position)
        v = H - cam
        L = v.length
        if L < 1.0:
            return
        v = v * (1.0 / L)
        if not _is_destr(BigWorld.collideSegment(sp, H - v * 0.5, H + v * 0.5, 128)):
            return
        far = cam + v * DESTR_REACH
        solid = _first_solid(sp, H, far)
        tmax = (solid.closestPoint - cam).dot(v) if solid is not None else DESTR_REACH
        best, bt = (None, None)
        for e in BigWorld.entities.values():
            if e.id == player.playerVehicleID or not _target_ok(e, player):
                continue
            s = _cached_spec(_key(e.typeDescriptor))
            if s is None:
                continue
            cx, cy, cz, R = _sphere(s)
            C = Math.Matrix(e.appearance.compoundModel.node('hull')).applyPoint(Math.Vector3(cx, cy, cz))
            t = (C - cam).dot(v)
            if t < L - 0.5 or t > tmax + R:
                continue
            if (_reaches(e, H) if cam_arg is None else (C - (cam + v * t)).length <= R) is False:
                continue
            if bt is None or t < bt:
                best, bt = e, t

        return best
    except Exception as ex:
        _dbg('through destructibles:', repr(ex))
        return

    return


def _target_from_marker():
    player = BigWorld.player()
    _poll_marker()
    _S['via'] = False
    m = _S['marker']
    try:
        sniper = player.inputHandler.ctrlModeName in ('sniper', 'dualgun')
    except Exception:
        sniper = False

    _S['held'] = False
    if m is None or not sniper:
        _S['target'] = None
        return
    else:
        e = getattr(m[2], 'entity', None) if m[2] is not None else None
        if e is not None:
            if _target_ok(e, player):
                _S['target'] = e.id
                return e
            _S['target'] = None
            return
        tid = _S['target']
        e = BigWorld.entities.get(tid) if tid is not None else None
        if e is not None and _target_ok(e, player) and _reaches(e, m[0]):
            _S['held'] = True
            _S['via'] = _S['destr'] and _marker_on_destr(m[0])
            return e
        if _S['destr']:
            e = _through_destr(player, m[0])
            if e is not None:
                _S['target'], _S['held'], _S['via'] = e.id, True, True
                return e
        _S['target'] = None
        return


COVER_PERIOD = 0.05
COVER_CLEAR_DELAY = 0.15
COVER_MIN = 1
COVER_THIN = 1.2
COVER_SHORT = 0.3

def _cover_points(e, sp):
    """sample points of the target in the hull node's space: the middle, top, front, back, both sides of the hull box.
    The hull collision box (typeDescriptor.hull.hitTester.bbox) when the game filled it, else the bounding sphere's centre
    with a fraction of its radius"""
    try:
        bb = e.typeDescriptor.hull.hitTester.bbox
        lo, hi = Math.Vector3(bb[0]), Math.Vector3(bb[1])
        c, h = (lo + hi) * 0.5, (hi - lo) * 0.5
    except Exception:
        cx, cy, cz, R = _sphere(sp)
        c, h = Math.Vector3(cx, cy, cz), Math.Vector3(R, R, R) * 0.25

    k = 0.7
    return [c, c + Math.Vector3(0, h.y * k, 0), c + Math.Vector3(0, 0, h.z * k), c - Math.Vector3(0, 0, h.z * k),
     c + Math.Vector3(h.x * k, 0, 0), c - Math.Vector3(h.x * k, 0, 0)]


def _circle_ends(e, sp, H, cam):
    """world end points of the cover probes along the lines of sight through the aiming circle (the colour is drawn only
    inside it): the centre, 4 at half the radius, 8 on the rim, each stopped at the target's depth. None when the circle
    is not drawn (the "full" mode paints the whole visible target) or cannot be measured"""
    if _S['quality'] == 2:
        return
    else:
        try:
            cx, cy, cz, R = _sphere(sp)
            C = Math.Matrix(e.appearance.compoundModel.node('hull')).applyPoint(Math.Vector3(cx, cy, cz))
            v = H - cam
            if v.length < 0.001:
                return
            v.normalise()
            t = max((C - cam).dot(v) - 0.5 * R, 1.0)
            dist = (Math.Vector3(e.position) - BigWorld.player().getOwnVehiclePosition()).length
            rc, _, tanh = _circle(dist)
            th = math.atan(2.0 * rc * tanh)
            right = Math.Vector3(v.z, 0.0, -v.x)
            if right.length < 0.001:
                right = Math.Vector3(1.0, 0.0, 0.0)
            right.normalise()
            up = Math.Vector3(right.y * v.z - right.z * v.y, right.z * v.x - right.x * v.z, right.x * v.y - right.y * v.x)
            ends = [cam + v * t]
            for a, n in ((0.5 * th, 4), (th, 8)):
                for k in range(n):
                    b = 2.0 * math.pi * k / n
                    d = v * math.cos(a) + (right * math.cos(b) + up * math.sin(b)) * math.sin(a)
                    ends.append(cam + d * t)

            return ends
        except Exception:
            return

        return


def _solid_cover(e, sp, H=None):
    """STANDARD graphics only. True when static geometry (terrain, buildings, rocks, trunks: what shells collide with, the
    flag 128; bushes are not in it) hides part of what the colour is drawn over: the lines of sight through the aiming circle
    (_circle_ends), or in the "full" mode at least one sample point of the target (_cover_points). Breakable objects and
    thin posts do not count.
    Forward has no G-buffer, so the shader cannot tell a bush from the ground under a pixel; the through-foliage colour (lifted
    over the depth buffer for the whole target) must therefore be off whenever something solid covers a part of the target,
    or the covered part would show through the ground. Off at once; the caller keeps it off COVER_CLEAR_DELAY after"""
    now = time.time()
    c = _S.get('cover')
    if c is not None and c['id'] == e.id and now - c['t'] < COVER_PERIOD:
        return now - c['seen'] < COVER_CLEAR_DELAY
    else:
        blocked = destr = False
        try:
            cam = Math.Vector3(BigWorld.camera().position)
            thin = COVER_THIN if _S['destr'] else 0.0
            ends = _circle_ends(e, sp, H, cam) if H is not None else None
            rim = 5 if ends is not None else len(_cover_points(e, sp)) + 1
            if ends is None:
                hull = Math.Matrix(e.appearance.compoundModel.node('hull'))
                ends = []
                for lp in _cover_points(e, sp):
                    pt = hull.applyPoint(lp)
                    v = pt - cam
                    L = v.length
                    if L >= 1.0:
                        ends.append(pt - v * (COVER_SHORT / L))

            hidden = ground = 0
            for k, end in enumerate(ends):
                if _S['destr'] and not destr and _is_destr(BigWorld.collideSegment(e.spaceID, cam, end, 128)):
                    destr = True
                r = _first_solid(e.spaceID, cam, end, _S['destr'], thin)
                if r is None:
                    continue
                if not _is_ground(r):
                    hidden += 1
                    continue
                if k == 0:
                    hidden += 1
                elif k < rim:
                    ground += 1

            blocked = hidden >= COVER_MIN or ground >= 2
        except Exception:
            blocked = False

        seen = now if blocked else c['seen'] if c is not None and c['id'] == e.id else 0.0
        _S['cover'] = {'id': e.id, 't': now, 'seen': seen, 'destr': destr}
        return now - seen < COVER_CLEAR_DELAY


def _beyond(e, H):
    """the marker point lies farther from the camera than the target: the shot went past it, nothing stopped it in front"""
    try:
        cam = Math.Vector3(BigWorld.camera().position)
    except Exception:
        return False

    return (H - cam).length > (Math.Vector3(e.position) - cam).length


def _held_point(e, H):
    """the marker point moved along the view ray to the held target's distance (same place on screen; the circle is in
    screen units), so the penetration is for the target, not for where a grazing shot would land hundreds of metres
    behind it"""
    try:
        cam = Math.Vector3(BigWorld.camera().position)
    except Exception:
        return H

    v = H - cam
    lh, lt = v.length, (e.position - cam).length
    if lh < 0.001 or lt < 0.001:
        return H
    return cam + v * (lt / lh)


SHOT_REFRESH = 0.5
_SHOT = {}

def _shot_params(H):
    """per frame only what depends on the distance; the shell's own data is cached per shot (shell switch) and re-read
    every SHOT_REFRESH s (the vehicle's gunPiercing attribute) -- same values as reading everything every frame"""
    f = _SHOT.get('fn')
    if f is None:
        from AvatarInputHandler.gun_marker_ctrl import _computePiercingPowerAtDistImpl
        from helpers_common import computeDistanceFactor
        f = _SHOT['fn'] = (
         _computePiercingPowerAtDistImpl, computeDistanceFactor)
    player = BigWorld.player()
    shot = player.getVehicleDescriptor().shot
    now = time.time()
    st = _SHOT.get('static')
    if st is None or st[0] is not shot or now - st[1] > SHOT_REFRESH:
        st = _SHOT['static'] = (
         shot, now, _shot_static(player, shot))
    p100, p500, cal, norm, rcos, jet, rnd, flags = st[2]
    dist = (H - player.getOwnVehiclePosition()).length
    pp = f[0](dist, shot.maxDistance, p100, p500) * f[1](shot.shell, dist, 'pierceFactor')
    flags |= _S['quality'] << 4 | (64 if _S['muzzle'] else 0) | (128 if _S['through'] else 0)
    return (dist, pp, Math.Vector4(cal, norm, rcos, jet), (rnd, float(flags)))


def _shot_static(player, shot):
    """the shell's part of the shot parameters (no distance)"""
    import constants
    from AvatarInputHandler.gun_marker_ctrl import _CrosshairShotResults
    shell = shot.shell
    mult = 1.0
    try:
        mult = player.guiSessionProvider.shared.feedback.getVehicleAttrs().get('gunPiercing', 1)
    except Exception:
        pass

    p100, p500 = shot.piercingPower
    extra = _CrosshairShotResults._SHELL_EXTRA_DATA.get(shell.kind)
    has_norm, may_ric, check_cal, jet = extra if extra is not None else (False, False, False, 0.0)
    mods = player.guiSessionProvider.arenaVisitor.modifiers
    norm = rcos = 0.0
    try:
        if has_norm:
            norm = mods.getShellNormalization(shell.kind)
        if may_ric:
            rcos = mods.getShellRicochetCos(shell.kind)
    except KeyError:
        pass

    modern = shell.kind == constants.SHELL_TYPES.HIGH_EXPLOSIVE and shell.type.mechanics == constants.SHELL_MECHANICS_TYPE.MODERN
    shield = bool(getattr(shell.type, 'shieldPenetration', False))
    flags = (1 if may_ric else 0) | (2 if check_cal else 0) | (4 if modern else 0) | (8 if shield else 0)
    return (p100 * mult, p500 * mult, float(shell.caliber), norm, rcos if may_ric else -2.0, jet,
     float(shell.piercingPowerRandomization), flags)


def _alpha(dist, since):
    player = BigWorld.player()
    a = _S['opacity']
    try:
        cur, ideal = player.gunRotator.getCurShotDispersionAngles()[:2]
        if cur > 0.0 and FADEOFF_NOT_AIMED > 0.0:
            a *= min((ideal / cur) ** FADEOFF_NOT_AIMED, 1.0)
    except Exception:
        pass

    if APPEAR > 0.0:
        a *= min(1.0, max(0.0, (time.time() - since) / APPEAR))
    return a


def _interp(tbl, x):
    """piecewise-linear over ((x, y), ...), clamped at both ends (EU's distance tables)"""
    if x <= tbl[0][0]:
        return tbl[0][1]
    for (x0, y0), (x1, y1) in zip(tbl, tbl[1:]):
        if x <= x1:
            return y0 + (y1 - y0) * (x - x0) / (x1 - x0)

    return tbl[(-1)][1]


def _circle(dist):
    """-> (R, cut, tanh): circle radius as a fraction of the screen height -- ours, blended to WoT EU's while the circle
    key is held (_circle_blend) --, the hard cut as a fraction of R, tan(fovY / 2).
    Ours: the aiming circle x 1.15 at the marker, at least RADIUS_MIN m, cap 28 % (economy 14 %).
    EU (WorldOfTanks.exe 2.4.0.1 ArmorFlashlightFeature 0x141427610, docs/EU_FLASHLIGHT_SPEC.md section 19): min(t1, k t2,
    14 %); t1 = a world disc of radiusByDist(dist) m at the target, t2 = the stock marker x 1.15 with EU's pixel constants,
    k = 1.4 for the drawn circle and 1 for its hard cut (only nearer than ~80 m does t2 win)"""
    s = _S['circle_s']
    try:
        tanh = math.tan(0.5 * BigWorld.projection().fov)
        cam = Math.Vector3(BigWorld.camera().position)
        zM = max((_S['marker'][0] - cam).length, 1.0)
        Dm = float(BigWorld.player().gunRotator.markerInfo[2])
    except Exception:
        return (0.0, 1.0, 0.5)

    if _S.get('held') and _S.get('target') is not None:
        try:
            t = BigWorld.entities.get(_S['target'])
            zT = max((Math.Vector3(t.position) - cam).length, 1.0)
            Dm, zM = Dm * zT / zM, zT
        except Exception:
            pass

    cap = OURS_CAP * (0.5 if _S['quality'] == 1 else 1.0)
    ours = min(max(0.5 * Dm * CIRCLE_ADJUST, RADIUS_MIN) / (2.0 * zM * tanh), cap)
    if s <= 0.0:
        return (ours, 1.0, tanh)
    else:
        import GUI
        hpx = float(GUI.screenResolution()[1])
        d = max(dist, 1.0)
        t1 = 0.5 * _interp(EU_RADIUS_BY_DIST, d) / (d * tanh)
        t2 = EU_T2 * CIRCLE_ADJUST * max(EU_SIZE_MUL * Dm / (2.0 * zM * tanh) * hpx, EU_MIN_PX) / hpx
        r2, r1 = min(t1, EU_SMOOTH_ADJ * t2, EU_CAP), min(t1, t2, EU_CAP)
        return (ours + (r2 - ours) * s, 1.0 + (r1 / max(r2, 1e-09) - 1.0) * s, tanh)


def _circle_word(R, cut):
    """g_albedoConversions.w: the soft-edge blend and the hard cut as a code (integer part) + R (below 0.5)"""
    qs = int(round(_S['circle_s'] * 31.0))
    qc = int(round(min(max((1.0 - cut) / CUT_SPAN, 0.0), 1.0) * 31.0))
    return float(qs + 32 * qc) + min(max(R, 0.0), 0.4999)


def _circle_blend():
    """0 -> 1 over CIRCLE_BLEND s while the circle key is held, back when released; eased (smoothstep). Polled every
    frame (no key events: a key released outside the window or while the chat had the focus cannot stick)"""
    key, held = _S['circle_key'], _S['weakpc']
    if not held and key is not None:
        try:
            typing = _S['typing']
            held = bool(BigWorld.isKeyDown(key)) and not (typing is not None and typing())
        except Exception:
            held = False

    now = time.time()
    dt = min(max(now - (_S['circle_t'] or now), 0.0), 0.1)
    _S['circle_t'] = now
    k = _S['circle_k']
    k = min(k + dt / CIRCLE_BLEND, 1.0) if held else max(k - dt / CIRCLE_BLEND, 0.0)
    _S['circle_k'] = k
    _S['circle_s'] = k * k * (3.0 - 2.0 * k)
    return


def _colour_blind():
    """the game's colour-blind setting, cached: read once per battle and again when the settings change"""
    cb = _S.get('cb')
    if cb is None:
        cb = 0
        try:
            from helpers import dependency
            from skeletons.account_helpers.settings_core import ISettingsCore
            from account_helpers.settings_core.settings_constants import GRAPHICS
            cb = 1 if dependency.instance(ISettingsCore).getSetting(GRAPHICS.COLOR_BLIND) else 0
        except Exception:
            pass

        _S['cb'] = cb
    return cb


def _on_game_settings(diff):
    from account_helpers.settings_core.settings_constants import GRAPHICS
    if GRAPHICS.COLOR_BLIND in diff:
        _S['cb'] = None
    return


def _settings_events(subscribe):
    try:
        from helpers import dependency
        from skeletons.account_helpers.settings_core import ISettingsCore
        ev = dependency.instance(ISettingsCore).onSettingsChanged
        if subscribe:
            ev += _on_game_settings
        else:
            ev -= _on_game_settings
    except Exception as ex:
        _log('settings events:', repr(ex))


def _mode_code():
    return float(_S['scheme'] + 3 * _colour_blind() + 6 * _S['pattern'] + 24 * _S['debug'])


def _mk_follower(e, path, node):
    parent = e.appearance.gameObject
    go = CGF.GameObject(e.spaceID)
    try:
        go.createComponent(GenericComponents.HierarchyComponent, parent)
        go.createComponent(GenericComponents.TransformComponent, Math.Vector3(0, 0, 0))
        go.createComponent(GenericComponents.NodeFollower, node, True, parent)
        dm = go.createComponent(GenericComponents.DynamicModelComponent, path)
        go.activate()
    except Exception:
        CGF.removeGameObject(go)
        raise

    return (
     go, dm)


def _attach(e, sp):
    """quality 0-2: one proxy cube on the hull node (camera ray + shot ray per pixel);
    quality RASTER: the armour models of the four parts on their nodes (rasterised point + shot ray per pixel)"""
    _detach()
    raster = _S['quality'] == RASTER and sp.get('raster')
    objs = []
    if raster:
        for pi, name in enumerate(A.PARTS):
            path = sp['raster'].get(name)
            if path:
                go, dm = _mk_follower(e, path, name)
                objs.append({'go': go, 'dm': dm, 'part': pi, 'valid': 0})

    else:
        go, dm = _mk_follower(e, sp['proxy'], 'hull')
        objs.append({'go': go, 'dm': dm, 'part': -1, 'valid': 0})
    since = _S.get('since_id') == e.id and _S.get('since') or time.time()
    _S['since_id'], _S['since'] = e.id, since
    _S['proxy'] = {'objs': objs, 'raster': bool(raster), 'id': e.id, 'entity': e, 'app': e.appearance, 'dds': sp['dds'], 
       'tp': _texture(sp), 'since': since}


def _detach():
    p = _S['proxy']
    _S['proxy'] = None
    if p is not None:
        for o in p['objs']:
            try:
                CGF.removeGameObject(o['go'])
            except Exception:
                pass

    return


_X, _Y = Math.Vector3(1, 0, 0), Math.Vector3(0, 1, 0)

def _node_rot(e):
    """turret yaw / gun pitch since calibration, from the compound model nodes (rotation part only): turret * hull^-1
    and gun * turret^-1 with the engine's matrices (row-vector convention, like afl_data.mul; 5x faster than in Python)"""
    cm = e.appearance.compoundModel
    hull = Math.Matrix(cm.node('hull'))
    tur = Math.Matrix(cm.node('turret'))
    Mg = Math.Matrix(cm.node('Gun'))
    hull.invert()
    Mt = Math.Matrix(tur)
    Mt.postMultiply(hull)
    tur.invert()
    Mg.postMultiply(tur)
    x, y = Mt.applyVector(_X), Mg.applyVector(_Y)
    return Math.Vector4(x.x, x.z, y.y, y.z)


def _shot_origin(H, d):
    """muzzle mode: a virtual muzzle on the line of the shell's flight direction at H (end of the arc), as far from H as
    the real muzzle, so rays O -> P follow the arc near H. Computed every frame from the gun's current position and
    direction (getCurShotPosition) and the shell gravity -- the marker direction d only updates ~10 times a second and
    made the zones jerk while the gun traversed. Rockets (gravity 0) fly straight: O is the muzzle itself."""
    try:
        m, v = BigWorld.player().gunRotator.getCurShotPosition()[:2]
        m, v = Math.Vector3(m), Math.Vector3(v)
    except Exception:
        return Math.Vector3(BigWorld.camera().position)

    shot = BigWorld.player().getVehicleDescriptor().shot
    g = float(getattr(shot, 'gravity', 0.0) or 0.0)
    if g <= 0.0 or v.length < 1e-06:
        return m
    v.normalise()
    v *= float(shot.speed)
    hx, hz = H.x - m.x, H.z - m.z
    vh = (v.x * v.x + v.z * v.z) ** 0.5
    if vh < 0.001:
        return m
    t = (hx * hx + hz * hz) ** 0.5 / vh
    dn = Math.Vector3(v.x, v.y - g * t, v.z)
    dn.normalise()
    return H - dn * (H - m).length


OFFSET_EVERY = 0.5
OFFSET_PARTS = (0, 1)
_RAW = {}

def _offset_rays():
    import random
    rnd = random.Random(5)
    out = []
    for _ in range(24):
        d = Math.Vector3(rnd.gauss(0, 1), rnd.gauss(0, 1), rnd.gauss(0, 1))
        d.normalise()
        out.append(((rnd.random(), rnd.random(), rnd.random()), d))

    return out


_OFFSET_RAYS = _offset_rays()

def _raw_collider(td, key):
    r = _RAW.get(key)
    if r is None:
        from vehicle_systems.tankStructure import TankPartNames
        r = _RAW[key] = {'go': None, 'comp': None, 'since': 0.0, 'task': None}
        space = BigWorld.player().spaceID
        models = tuple((TankPartNames.getIdx(n), getattr(td, n).hitTester.bspModelName) for n in A.PARTS)

        def loaded(refs, r=r, space=space):
            if _RAW.get(key) is not r:
                return
            else:
                r['task'] = None
                if refs.failedIDs:
                    _log('collision copy for', key, 'failed to load:', refs.failedIDs)
                    return
                try:
                    from vehicle_systems.tankStructure import ColliderTypes
                    go = CGF.GameObject(space)
                    comp = go.createComponent(BigWorld.CollisionComponent, refs['collisionAssembler'])
                    go.activate()
                    m = Math.Matrix()
                    m.setTranslate(Math.Vector3(0.0, -300.0, 0.0))
                    comp.connect(0, ColliderTypes.DYNAMIC_COLLIDER, tuple((i, m) for i in range(4)))
                    r['go'], r['comp'], r['since'] = go, comp, time.time()
                except Exception as ex:
                    _log('collision copy for', key, 'failed:', repr(ex))

                return

        r['task'] = BigWorld.loadResourceListBG((BigWorld.CollisionAssembler(models, space),), loaded)
    if r['comp'] is None or time.time() - r['since'] < 0.2:
        return
    return r['comp']


def _free_raw():
    for r in _RAW.values():
        if r.get('task') is not None:
            try:
                BigWorld.stopLoadResourceListBGTask(r['task'])
            except Exception:
                pass

        if r['go'] is not None:
            try:
                CGF.removeGameObject(r['go'])
            except Exception:
                pass

    _RAW.clear()
    return


def _solve3(M, b):
    m = [ list(M[i]) + [b[i]] for i in range(3) ]
    for i in range(3):
        p = max(range(i, 3), key=lambda r: abs(m[r][i]))
        m[i], m[p] = m[p], m[i]
        if abs(m[i][i]) < 1e-09:
            return None
        for r in range(3):
            if r != i:
                f = m[r][i] / m[i][i]
                for k in range(4):
                    m[r][k] -= f * m[i][k]

    return [ m[i][3] / m[i][i] for i in range(3) ]


OFFSET_RAYS_PER_STEP = 4

def _measure_offsets(e, raw):
    """-> {part: (x, y, z)} metres, engine surface = our surface + offset (part space); None if not measurable"""
    res = []
    for _ in _measure_offsets_iter(e, raw, res):
        pass

    return res[0]


def _measure_offsets_iter(e, raw, res):
    """generator version of _measure_offsets (yields every OFFSET_RAYS_PER_STEP rays); res[0] = the result"""
    res[:] = [
     None]
    col = e.appearance.collisions
    EPS = 0.002
    axes = (Math.Vector3(EPS, 0, 0), Math.Vector3(0, EPS, 0), Math.Vector3(0, 0, EPS))
    out = {}
    for pi in OFFSET_PARTS:
        lo, hi, _ = raw.getBoundingBox(pi)
        lo, hi = Math.Vector3(lo), Math.Vector3(hi)
        ext = hi - lo
        L = ext.length
        rows, rhs = [], []
        for k, (u, d) in enumerate(_OFFSET_RAYS):
            if k and k % OFFSET_RAYS_PER_STEP == 0:
                yield
            tgt = Math.Vector3(lo.x + ext.x * u[0], lo.y + ext.y * u[1], lo.z + ext.z * u[2])
            s, en = tgt - d * L, tgt + d * L
            te, tr = col.collideLocal(pi, s, en), raw.collideLocal(pi, s, en)
            if te < 0.0 or tr < 0.0 or abs(te - tr) > 0.005:
                continue
            g = []
            for ax in axes:
                t1 = raw.collideLocal(pi, s + ax, en + ax)
                if t1 < 0.0 or abs(t1 - tr) > 0.05:
                    break
                g.append((t1 - tr) / EPS)

            if len(g) == 3:
                rows.append(g)
                rhs.append(tr - te)

        x = None
        for _ in range(2):
            if len(rows) < 8:
                return
            x = _solve3([ [ sum(r[i] * r[j] for r in rows) for j in range(3) ] for i in range(3) ], [ sum(r[i] * v for r, v in zip(rows, rhs)) for i in range(3) ])
            if x is None:
                return
            keep = [ k for k, (r, v) in enumerate(zip(rows, rhs)) if abs(v - sum(r[i] * x[i] for i in range(3))) < 0.0002 ]
            rows, rhs = [ rows[k] for k in keep ], [ rhs[k] for k in keep ]

        out[pi] = tuple(x)
        yield

    res[0] = out
    return


def _update_offsets(p):
    """one step per frame of the current measurement; a new one every OFFSET_EVERY s"""
    g = p.get('off_gen')
    if g is None:
        now = time.time()
        if now - p.get('off_t', 0.0) < OFFSET_EVERY:
            return
        p['off_t'] = now
        e = p['entity']
        raw = _raw_collider(e.typeDescriptor, _key(e.typeDescriptor))
        if raw is None:
            return
        p['off_res'] = []
        g = p['off_gen'] = _measure_offsets_iter(e, raw, p['off_res'])
    try:
        next(g)
        return
    except StopIteration:
        off = p['off_res'][0] if p['off_res'] else None
    except Exception as ex:
        off = None
        _log('collision offsets:', repr(ex))

    p['off_gen'] = None
    if off is not None:
        p['off'] = off
    return


def _pack_offsets(off):
    """-> three floats with two 12-bit fields each (0.01 mm, bias 2048), see shader/afl_flashlight.hlsl"""
    h = off.get(1, (0.0, 0.0, 0.0)) if off else (0.0, 0.0, 0.0)
    c = off.get(0, (0.0, 0.0, 0.0)) if off else (0.0, 0.0, 0.0)
    q = [ max(0, min(4095, int(round(v * 100000.0)) + 2048)) for v in (h[0], h[1], h[2], c[0], c[1], c[2]) ]
    return (float(q[0] * 4096 + q[1]), float(q[2] * 4096 + q[3]), float(q[4] * 4096 + q[5]))


TM_FILTERS = {'RexpTM': 0, 'FilmicTM': 1, 'LinearExpTM': 2}
TM_DEFAULT = (0, 1.0, 1.0)

def _tonemap():
    tm = _S.get('tm')
    if tm is not None:
        return tm
    else:
        tm = TM_DEFAULT
        try:
            geom = BigWorld.player().arena.arenaType.geometryName
            envs = ResMgr.openSection('spaces/%s/environments/environments.xml' % geom)
            guid = envs['activeEnvironment'].asString.strip().lower().replace('.', '-')
            env = ResMgr.openSection('spaces/%s/environments/%s/environment.xml' % (geom, guid))
            tms = env['HDR']['tonemappings']
            entries = [ v for k, v in tms.items() if k == 'tonemapping' ]
            e = entries[tms['active'].asInt]
            name = e['name'].asString.strip()
            if name in TM_FILTERS:
                tm = (
                 TM_FILTERS[name], e['whitePoint'].asFloat, e['blackPoint'].asFloat)
            _dbg('tone mapping of', geom, guid, name, tm)
        except Exception as ex:
            _log('tone mapping: default', TM_DEFAULT, repr(ex))

        _S['tm'] = tm
        return tm


def _pack_params(shellv, R, flags, alpha, mode, off):
    """-> (g_color, g_animationParams) with the offsets in the three spare words and the map's tone curve packed with
    the calibre (see shader/afl_flashlight.hlsl sceneColour)"""
    w1, w2, w3 = _pack_offsets(off)
    filt, wp, bp = _tonemap()
    fl = int(flags) | (256 if shellv.w > 0.0 else 0) | (512 if filt == 1 else 0) | (1024 if filt == 2 else 0)
    cal = max(0, min(1023, int(round(shellv.x * 2.0))))
    wpq = max(0, min(255, int(round((wp + 32.0) * 4.0))))
    bpq = max(1, min(63, int(round(bp * 10.0))))
    return (Math.Vector4(float(cal + 1024 * (wpq + 256 * bpq)), shellv.y, shellv.z, w1),
     Math.Vector4(w2, fl + min(max(R, 0.0), 0.999), w3, float(mode) + min(max(alpha, 0.0), 1.0) * 0.999))


def _push(p, H, d, foliage=False, lift=False, gap=0.0, objs=0):
    ready = []
    for o in p['objs']:
        if o['valid'] < 2:
            if o['dm'].isValid():
                o['valid'] += 1
            if o['valid'] < 2:
                continue
            o['dm'].setMaterialParameterTexture('diffuseMap', p['tp'])
        ready.append(o)

    if not ready:
        return
    dist, pp, shellv, (R, flags) = _shot_params(H)
    if gap > 0.0 and shellv.w > 0.0:
        pp *= max(0.0, 1.0 - gap * shellv.w)
    if objs > 0 and shellv.w <= 0.0:
        pp = max(0.0, pp - objs * DESTR_LOSS)
    if _S.get('forward'):
        _push_forward(ready, p, H, d, dist, pp, foliage)
        return
    if foliage:
        flags = int(flags) | 2048
    if lift:
        flags = int(flags) | 4096
    a = _alpha(dist, p['since'])
    rc, cut, _ = _circle(dist)
    v1 = Math.Vector4(H.x, H.y, H.z, _circle_word(rc, cut))
    if _S['muzzle']:
        m = _shot_origin(H, d)
        v2 = Math.Vector4(m.x, m.y, m.z, pp)
    else:
        v2 = Math.Vector4(d.x, d.y, d.z, pp)
    v3 = _node_rot(p['entity'])
    mode = _mode_code()
    _update_offsets(p)
    for o in ready:
        dm = o['dm']
        w = mode + (1000.0 * (o['part'] + 1) if o['part'] >= 0 else 0.0)
        v4, v5 = _pack_params(shellv, R, flags, a, w, p.get('off'))
        dm.setMaterialParameterVector4('g_albedoConversions', v1)
        dm.setMaterialParameterVector4('g_glossConversions', v2)
        dm.setMaterialParameterVector4('g_metallicConversions', v3)
        dm.setMaterialParameterVector4('g_color', v4)
        dm.setMaterialParameterVector4('g_animationParams', v5)


def _screen_ndc(H):
    """NDC (x, y) of the world point H for the current camera -- where the shader's circle centre goes. Clamped to the
    screen; (0, 0) when the point is behind the camera or the camera is not usable"""
    try:
        from AvatarInputHandler import cameras
        c = cameras.getViewProjectionMatrix().applyV4Point(Math.Vector4(H.x, H.y, H.z, 1.0))
        if c.w <= 0.0001:
            return (0.0, 0.0)
        return (
         max(-1.0, min(1.0, c.x / c.w)), max(-1.0, min(1.0, c.y / c.w)))
    except Exception:
        return (0.0, 0.0)


def _q(v, hi):
    return max(0, min(hi, int(round(v))))


def _shell_class(shot, st):
    """0 AP, 1 APCR, 2 FSDS, 3 HEAT, 4 APHE, 5 HE (legacy), 6 HE modern, 7 HE modern with shield penetration: what the
    forward shader needs to rebuild the shell's normalisation / ricochet / jet rules (table FWD_* in afl_flashlight.hlsl).
    st = _shot_static(...): (p100, p500, calibre, norm, rcos, jet, rnd, flags)"""
    import constants
    kind, flags = shot.shell.kind, int(st[7])
    if flags & 4:
        if flags & 8:
            return 7
        return 6
    if kind == constants.SHELL_TYPES.HOLLOW_CHARGE:
        return 3
    if kind == constants.SHELL_TYPES.ARMOR_PIERCING_FSDS:
        return 2
    if kind == constants.SHELL_TYPES.ARMOR_PIERCING_CR:
        return 1
    if kind == constants.SHELL_TYPES.ARMOR_PIERCING_HE:
        return 4
    if kind == constants.SHELL_TYPES.HIGH_EXPLOSIVE:
        return 5
    return 0


def _push_forward(ready, p, H, d, dist, pp, foliage=False):
    """standard graphics: the .11 effect takes only g_color (4 floats) and alphaReference (1 float) -- measured in the
    forward client (shader/afl_dbg_multi.hlsl). Everything is packed into the bits of those five floats (30 free bits
    each, layout table in afl_fwdpack.py: calibre, flags, mode, quality, opacity, circle radius, turret yaw, gun pitch,
    shell class and its normalisation / ricochet / randomisation, the full piercing power at the marker, the marker on the
    screen, and the shot's origin).
    The shot origin is the same as on the deferred path: the virtual muzzle (_shot_origin: a point on the shell's flight
    direction at the marker, as far from it as the real muzzle) relative to the camera, or the shot direction d when the
    'shot rays' option is parallel. What is still not sent: the tone-mapping inputs (no HDR resolve on forward); and there
    is no G-buffer, so the through-foliage flag (set only while the marker is on the target, and only if no static
    geometry covers the target, _solid_cover) lifts the whole colour over the depth buffer, not only over vegetation"""
    st = _SHOT['static'][2]
    rot = _node_rot(p['entity'])
    nx, ny = _screen_ndc(H)
    rc, _, _ = _circle(dist)
    ang = lambda y, x: FP.q_unit(math.atan2(y, x), -math.pi, math.pi, FP.YAW_BITS)
    muzzle = bool(_S['muzzle'])
    if muzzle:
        v = _shot_origin(H, d) - Math.Vector3(BigWorld.camera().position)
        lo, hi = -FP.V_RANGE, FP.V_RANGE
    else:
        v = Math.Vector3(d)
        v.normalise()
        lo, hi = (-1.0, 1.0)
    rcos = st[4]
    vals = {'cal': max(1, _q(st[2], 1023)), 
       'fol': 1 if foliage else 0, 'mode': int(_mode_code()) & 31, 'qual': _S['mode'] & 3, 
       'alpha': max(1, FP.q_unit(_alpha(dist, p['since']), 0.0, 1.0, 5)), 'rh': FP.q_unit(rc, 0.0, FP.RH_MAX, 7), 
       'yaw': ang(rot.y, rot.x), 
       'cls': _shell_class(_SHOT['static'][0], st), 'rnd': _q(st[6] * 32.0, 15), 'pitch': ang(rot.w, rot.z), 
       'norm': _q(math.degrees(st[3]) / 0.5, 15), 'pp': _q(pp * 4.0, 16383), 
       'muz': 1 if muzzle else 0, 'thr': 1 if _S['through'] else 0, 'rcos': 31 if rcos < -1.5 else _q(rcos / (0.5 / 30.0), 30), 
       'vx': FP.q_unit(v.x, lo, hi, 9), 
       'vy': FP.q_unit(v.y, lo, hi, 9), 'vz': FP.q_unit(v.z, lo, hi, 8), 'ndcx': FP.q_unit(nx, -1.0, 1.0, 11), 
       'ndcy': FP.q_unit(ny, -1.0, 1.0, 11)}
    a, x, y, z, w = FP.encode(vals)
    col = Math.Vector4(x, y, z, w)
    for o in ready:
        dm = o['dm']
        dm.setMaterialParameterVector4('g_color', col)
        dm.setMaterialParameterFloat('alphaReference', a)


def _hide(p):
    for o in p['objs']:
        try:
            if o['valid'] >= 2:
                if _S.get('forward'):
                    o['dm'].setMaterialParameterFloat('alphaReference', 0.0)
                else:
                    o['dm'].setMaterialParameterVector4('g_animationParams', Math.Vector4(0, 0, 0, 0))
        except Exception:
            pass


def _tick():
    if not _S['on']:
        return
    else:
        now = time.clock()
        if _S['last_tick']:
            _S['dt'] = 0.9 * _S['dt'] + 0.1 * min(max(now - _S['last_tick'], 1.0 / 240), 0.1)
        _S['last_tick'] = now
        try:
            _frame()
            _S['err'] = None
        except Exception as ex:
            if _S['err'] != repr(ex):
                _S['err'] = repr(ex)
                import traceback
                traceback.print_exc()
                try:
                    _detach()
                except Exception:
                    _S['proxy'] = None

        BigWorld.callback(0.0, _tick)
        return


def _frame():
    _gen_step()
    _circle_blend()
    e = _target_from_marker() if _S['enabled'] else None
    p = _S['proxy']
    if p is not None and p['app'] is not getattr(p['entity'], 'appearance', None):
        _detach()
        p = None
    if e is None:
        if p is not None and time.time() - _S['seen'] > HOLD:
            _detach()
            _S['since_id'] = None
        elif p is not None:
            _hide(p)
        return
    _S['seen'] = time.time()
    sp = _spec(e.typeDescriptor)
    if sp is None:
        if p is not None:
            _hide(p)
        return
    if p is not None and p['id'] != e.id:
        _S['since_id'] = None
    if p is not None and p['raster'] != (_S['quality'] == RASTER and bool(sp.get('raster'))):
        _detach()
        p = None
    if p is None or p['id'] != e.id or p['entity'] is not e or p['dds'] != sp['dds']:
        _attach(e, sp)
        p = _S['proxy']
    H, d, _ = _S['marker']
    fol = _S['foliage']
    raw = fol
    if _S.get('held'):
        raw = fol and _beyond(e, _S.get('marker_pt') or H)
        H = _held_point(e, H)
    now = time.time()
    if raw:
        _S['fol_t'], _S['fol_id'] = now, e.id
    fol = fol and (raw or _S.get('fol_id') == e.id and now - _S.get('fol_t', 0.0) < FOL_OFF_DELAY)
    if _S['via'] and _S['destr']:
        fol = True
    lift = False
    if _S['destr']:
        covered = _solid_cover(e, sp, H)
        if not covered:
            if _S.get('forward'):
                fol = True
            else:
                lift = True
        elif _S.get('forward'):
            fol = False
    else:
        if _S.get('forward') and fol and _solid_cover(e, sp, H):
            fol = False
    _S['lift'] = lift
    gap, objs = _destr_info(H) if _S['destr'] else (0.0, 0)
    _S['objs'] = objs
    _push(p, H, d, fol, lift, gap, objs)
    return


def start():
    if _S['on']:
        return
    else:
        if type(BigWorld.player()).__name__ != 'PlayerAvatar':
            return
        _S['forward'] = BigWorld.getGraphicsSetting('RENDER_PIPELINE') != 0
        if _S['forward'] and not _S.get('pipeline_noted'):
            _S['pipeline_noted'] = True
            _log('standard graphics (RENDER_PIPELINE != 0): reduced flashlight, forward variant of the effect')
        _S['tm'] = None
        _S['enabled'] = bool(SET.values[SET.ENABLED])
        try:
            ch = BigWorld.player().guiSessionProvider.shared.crosshair
            ch.onGunMarkerStateChanged += _on_marker
        except Exception as ex:
            _log('crosshair not ready:', repr(ex))
            BigWorld.callback(1.0, start)
            return

        _S.update({'on': True, 'marker': None, 'target': None, 'proxy': None, 'jobs': [], 'last_tick': 0.0, 'since_id': None, 
           'failed': {}, 'tp': {}, 'warm': {}, 'credit': 0.0})
        d = _cache_dir()
        _S['cache_dir'], _S['nocache'] = d, d is None
        if _S['nocache']:
            _log('cache folder %s not available until the client restarts: no new data in this session' % CACHE_VFS)
        _arena_events(True)
        _S['cb'] = None
        _SHOT.clear()
        _settings_events(True)
        try:
            _preload_roster()
        except Exception as ex:
            _log('roster:', repr(ex))

        _tick()
        _dbg('started')
        return


def stop():
    if not _S['on']:
        return
    else:
        _S['on'] = False
        try:
            BigWorld.player().guiSessionProvider.shared.crosshair.onGunMarkerStateChanged -= _on_marker
        except Exception:
            pass

        _arena_events(False)
        _settings_events(False)
        _detach()
        _free_raw()
        _S.update({'jobs': [], 'tp': {}, 'warm': {}, 'marker': None, 'target': None, 'since_id': None, 'since': None})
        return


def _on_setting(name, value):
    """afl_settings -> state; the menu previews/applies through here, the hotkeys go through SET.set_value too"""
    if name == SET.SCHEMA:
        _S['scheme'] = int(value) % len(SCHEMES)
    elif name == SET.FILL:
        _S['pattern'] = int(value) + 1
    elif name == SET.OPACITY:
        _S['opacity'] = float(value)
    elif name == SET.MODE:
        m = int(value) % len(SET.MODE_OPTIONS)
        _S['mode'] = m
        _S['weakpc'] = m == MODE_WEAKPC
        _S['quality'] = 1 if _S['weakpc'] else m
    elif name == SET.FOLIAGE:
        _S['foliage'] = bool(value)
    elif name == SET.DESTR:
        _S['destr'] = bool(value)


def _init_settings():
    SET.load()
    SET.listen(_on_setting)
    for n in (SET.SCHEMA, SET.FILL, SET.OPACITY, SET.MODE, SET.FOLIAGE, SET.DESTR):
        _on_setting(n, SET.values[n])


def toggle():
    _S['enabled'] = not _S['enabled']
    _log('enabled' if _S['enabled'] else 'disabled')


def next_scheme():
    SET.set_value(SET.SCHEMA, (_S['scheme'] + 1) % len(SCHEMES))
    _log('scheme', SCHEMES[_S['scheme']])


def toggle_allies():
    _S['allies'] = not _S['allies']
    _log('allies as targets:', _S['allies'])


def toggle_through():
    _S['through'] = not _S['through']
    _log('colour', 'over the target details (boxes, fenders, spare tracks)' if _S['through'] else 'only where the armour is visible')


def toggle_muzzle():
    _S['muzzle'] = not _S['muzzle']
    _log('shot rays', 'from the muzzle to every point' if _S['muzzle'] else 'parallel to the aim direction')


def next_quality():
    SET.set_value(SET.MODE, (_S['mode'] + 1) % len(SET.MODE_OPTIONS))
    _log('mode', SET.MODE_OPTIONS[_S['mode']]['label'])


OPACITY_STEPS = (1.0, 0.85, 0.7, 0.55, 0.4)

def next_opacity():
    steps = OPACITY_STEPS
    cur = _S['opacity']
    i = min(range(len(steps)), key=lambda k: abs(steps[k] - cur))
    SET.set_value(SET.OPACITY, steps[((i + 1) % len(steps))])
    _log('opacity', '%d %%' % int(round(_S['opacity'] * 100)))


def next_pattern():
    SET.set_value(SET.FILL, _S['pattern'] % 3)
    _log('pattern', PATTERNS[_S['pattern']])


_init_settings()