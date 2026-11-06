# uncompyle6 version 3.7.4
# -*- coding: utf-8 -*-
# Python bytecode 2.7 (62211)
# Decompiled from: Python 3.10.6 (tags/v3.10.6:9c7b4bd, Aug  1 2022, 21:53:49) [MSC v.1932 64 bit (AMD64)]
# Embedded file name: scripts/client/gui/mods/armorflashlight/lai_inspector.py
# Compiled at: 2026-01-01 04:00:00
import json, math, os, time, BigWorld, CGF, GenericComponents, Math, ResMgr, lai_models as M, log as LG, runtime
CACHE_VFS = 'lai_cache'
CACHE_VER = 'v3'
CACHE_KEEP = '_%s($|_sp_)' % CACHE_VER
PARTS = ('chassis', 'hull', 'turret', 'gun')
ALPHA = 0.5
GEN_BUDGET = 0.01
TRACE_BUDGET = 0.004
SAMPLES = 4
MODES = (None, 'nominal', 'penetration')
TIERS = {1: (5, 30, 5, 30), 2: (5, 45, 5, 45), 3: (5, 55, 5, 55), 4: (10, 65, 10, 65), 5: (10, 85, 10, 85), 6: (15, 110, 15, 110), 
   7: (15, 140, 15, 140), 8: (20, 170, 20, 170), 9: (25, 190, 25, 190), 10: (30, 210, 30, 210), 
   11: (30, 225, 30, 225)}
ATTACKERS = {1: 'germany:G12_Ltraktor', 2: 'germany:G06_PzII', 3: 'germany:G102_Pz_III', 4: 'germany:G10_PzIII_AusfJ', 
   5: 'france:F112_M10_RBFM', 6: 'ussr:R108_T34_85M', 7: 'usa:A130_Super_Hellcat', 
   8: 'italy:It13_Progetto_M35_mod_46', 9: 'ussr:R151_Object_257_2', 10: 'france:F18_Bat_Chatillon25t', 
   11: 'usa:A183_XM69_Hacker'}
_S = {'mode': 0, 'shell': 0, 'veh': None, 'parts': [], 'groups': [], 'jobs': [], 'pending': [], 'shot': None, 
   'cam': None, 'trace_queue': [], 'tick': False, 'label': ''}
_SPECS = {}

def _log(*a):
    LG.note('lai', *a)


def _hangar():
    from helpers import dependency
    from skeletons.gui.shared.utils import IHangarSpace
    return dependency.instance(IHangarSpace)


def _vehicle():
    hs = _hangar()
    if not hs.spaceInited or not hs.isModelLoaded:
        return
    v = hs.getVehicleEntity()
    if v is None or getattr(v, 'typeDescriptor', None) is None or not v.appearance or not v.appearance.isLoaded:
        return
    return v


def _cache_dir():
    """the cache folder (res_mods/<ver>/lai_cache) if the VFS sees files written there now, else None"""
    c = runtime.cache(CACHE_VFS)
    if c['ok']:
        return c['path']
    else:
        return


def _key(td, part):
    c = getattr(td, part)
    hv = c.hitTester.bspModelName
    base = hv.split('/')[(-1)].replace('.model', '')
    extra = '_' + c.name.replace(':', '_') if part in ('gun', 'turret') else ''
    fp = runtime.fingerprint(hv.replace('.model', '.havok'))
    fp = '_' + fp if fp else ''
    return ('%s__%s%s%s_%s' % (td.name.split(':')[(-1)], base, extra, fp, CACHE_VER), hv)


def _cached(name):
    if name in _SPECS:
        return _SPECS[name]
    else:
        sec = ResMgr.openSection(CACHE_VFS + '/' + name + '.json')
        if sec is not None:
            try:
                _SPECS[name] = json.loads(sec.asBinary)
                runtime.touch(CACHE_VFS, name)
                return _SPECS[name]
            except ValueError as ex:
                _log('cache', name, 'unreadable, rebuilding:', repr(ex))

        return


def _queue_part(td, part):
    name, hv = _key(td, part)
    if _cached(name) is not None or any(j['name'] == name for j in _S['jobs']):
        return
    _S['jobs'].append({'name': name, 'hv': hv, 'mats': M.materials_of(getattr(td, part)), 'it': None, 'res': []})
    return


def _gen_step():
    t_end = time.clock() + GEN_BUDGET
    while _S['jobs'] and time.clock() < t_end:
        j = _S['jobs'][0]
        if j['it'] is None:
            d = _cache_dir()
            if d is None:
                if not _S.get('nocache_logged'):
                    _S['nocache_logged'] = True
                    _log('cache folder', CACHE_VFS, 'not available until the client restarts: no new models now')
                del _S['jobs'][:]
                return
            data = ResMgr.openSection(j['hv'].replace('.model', '.havok'))
            if data is None:
                _SPECS[j['name']] = {'primary': None, 'spaced': []}
                _S['jobs'].pop(0)
                continue
            j['d'] = d
            j['it'] = M.build_part_iter(data.asBinary, j['mats'], CACHE_VFS, j['name'], j['res'], 'alpha')
        try:
            next(j['it'])
            continue
        except StopIteration:
            pass

        _S['jobs'].pop(0)
        files, primary, spaced = j['res']
        for fn, b in files.iteritems():
            with open(os.path.join(j['d'], fn), 'wb') as (f):
                f.write(b)

        spec = {'primary': primary, 'spaced': spaced}
        final = os.path.join(j['d'], j['name'] + '.json')
        with open(final + '.tmp', 'wb') as (f):
            f.write(json.dumps(spec))
        if os.path.exists(final):
            os.remove(final)
        os.rename(final + '.tmp', final)
        ResMgr.purge(CACHE_VFS + '/' + j['name'] + '.json')
        _SPECS[j['name']] = spec

    return


def _mk_go(v, path, node):
    go = CGF.GameObject(v.spaceID)
    t = go.createComponent(GenericComponents.TransformComponent, Math.Vector3(0, 0, 0))
    t.transform = Math.Matrix(node)
    dm = go.createComponent(GenericComponents.DynamicModelComponent, path)
    go.activate()
    return (go, t, dm)


def _follow():
    cache = {}
    for p in _S['parts']:
        key = id(p['node'])
        if key not in cache:
            m = Math.Matrix(p['node'])
            tr = m.translation
            cache[key] = (m, (round(tr.x, 4), round(tr.y, 4), round(tr.z, 4), round(m.yaw, 5), round(m.pitch, 5), round(m.roll, 5)))
        m, sig = cache[key]
        if p['sig'] != sig:
            p['t'].transform = m
            p['sig'] = sig


def _attach(v):
    td = v.typeDescriptor
    specs = []
    for part in PARTS:
        name, _ = _key(td, part)
        sp = _cached(name)
        if sp is None:
            return False
        specs.append((part, sp))

    for part, sp in specs:
        node = v.model.node(part)
        if sp['primary']:
            _S['pending'].append((sp['primary'], part, node, None))
        for g in sp['spaced']:
            _S['pending'].append((g['model'], part, node, g))

    _S['veh'] = v
    return True


def _build_step(v, budget=16):
    while _S['pending'] and budget > 0:
        path, part, node, g = _S['pending'].pop(0)
        go, t, dm = _mk_go(v, path, node)
        p = {'go': go, 't': t, 'dm': dm, 'node': node, 'sig': None, 'ok': False, 'seen': False, 'cpu': g is not None, 
           'pushed': None}
        _S['parts'].append(p)
        if g is not None:
            c = g['centroids']
            step = max(1, len(c) // SAMPLES)
            _S['groups'].append({'part': p, 'node': node, 'samples': [ Math.Vector3(*q) for q in c[::step] ][:SAMPLES], 'res': None})
        budget -= 1

    return


def _detach():
    for p in _S['parts']:
        try:
            CGF.removeGameObject(p['go'])
        except Exception:
            pass

    _S.update({'veh': None, 'parts': [], 'groups': [], 'pending': [], 'trace_queue': [], 'cam': None})
    return


def _extra_data(kind):
    try:
        from AvatarInputHandler.gun_marker_ctrl import _CrosshairShotResults
        return _CrosshairShotResults._SHELL_EXTRA_DATA[kind]
    except Exception:
        import constants
        T = constants.SHELL_TYPES
        return {T.ARMOR_PIERCING: (True, True, True, 0.0), T.ARMOR_PIERCING_CR: (True, True, True, 0.0), T.ARMOR_PIERCING_HE: (
                               True, False, False, 0.0), 
           T.HOLLOW_CHARGE: (False, True, False, 0.5)}.get(kind, (False, False, False, 0.0))


def _impact(kind):
    from gui.battle_control.arena_visitor import _ArenaModifiersVisitor
    mv = _ArenaModifiersVisitor()
    try:
        return (
         mv.getShellNormalization(kind), mv.getShellRicochetCos(kind))
    except KeyError:
        return (0.0, -2.0)


def _attacker_shots(target_td):
    from items import vehicles
    name = ATTACKERS.get(target_td.level)
    td = None
    if name and vehicles.g_list.isVehicleExisting(name):
        td = vehicles.VehicleDescr(typeName=name)
    if td is None:
        td = target_td
    return (
     td, list(td.gun.shots))


def _update_shot(v):
    atd, shots = _attacker_shots(v.typeDescriptor)
    shot = shots[(_S['shell'] % len(shots))]
    shell = shot.shell
    has_norm, may_ric, check_cal, jet = _extra_data(shell.kind)
    norm, rcos = _impact(shell.kind)
    _S['shot'] = {'pp': float(shot.piercingPower[0]), 'cal': float(shell.caliber), 'R': float(shell.piercingPowerRandomization), 'norm': norm if has_norm else 0.0, 
       'rcos': rcos if may_ric else -2.0, 'mayRic': may_ric, 
       'checkCal': check_cal, 'jet': jet, 'kind': shell.kind}
    _S['label'] = '%s, %s %d mm' % (atd.type.userString, shell.kind, int(shot.piercingPower[0]))


def _params(p):
    mode = MODES[_S['mode']]
    R = _S['shot']['R'] if _S['shot'] else 0.15
    if mode == 'nominal':
        t = TIERS.get(_S['veh'].typeDescriptor.level, TIERS[10])
        return (
         Math.Vector4(*t), Math.Vector4(1.0, ALPHA, R, 0.0))
    else:
        s = _S['shot']
        if not p['cpu']:
            return (Math.Vector4(s['pp'], s['cal'] if s['checkCal'] else -s['cal'], s['norm'], s['rcos']),
             Math.Vector4(2.0, ALPHA, R, 0.0))
        return (None, None)


def _push_all():
    for p in _S['parts']:
        if not p['ok']:
            continue
        col, anim = _params(p)
        key = (_S['mode'], _S['shell'], p['cpu'])
        if col is None:
            if p['pushed'] != key:
                p['dm'].setMaterialParameterVector4('g_animationParams', Math.Vector4(0.0, 0.0, 0.0, 0.0))
                p['pushed'] = key
            continue
        if p['pushed'] != key:
            p['dm'].setMaterialParameterVector4('g_color', col)
            p['dm'].setMaterialParameterVector4('g_animationParams', anim)
            p['pushed'] = key

    return


def _mat_info(v, part_index, mat_kind):
    """Vehicle.getMatinfo for the hangar vehicle (1.45 Vehicle.py:1006)"""
    from items import vehicles
    from vehicle_systems.tankStructure import TankPartIndexes
    from vehicle_systems.model_assembler import collisionIdxToTrackPairIdx
    td = v.typeDescriptor
    mi = None
    if part_index == TankPartIndexes.CHASSIS:
        mi = td.chassis.materials.get(mat_kind)
    elif part_index == TankPartIndexes.HULL:
        mi = td.hull.materials.get(mat_kind)
    elif part_index == TankPartIndexes.TURRET:
        mi = td.turret.materials.get(mat_kind)
    elif part_index == TankPartIndexes.GUN:
        mi = td.gun.materials.get(mat_kind)
    elif part_index > len(TankPartIndexes.ALL):
        pair = collisionIdxToTrackPairIdx(part_index, td)
        if pair is not None:
            mi = td.chassis.tracks[pair].materials.get(mat_kind)
    if mi is None:
        mi = vehicles.g_cache.commonConfig['materials'].get(mat_kind)
    return mi


def _penetration(v, hits):
    """EU penetration_utils.calculatePenetrationInfo -> (result 0/1/2, fraction)"""
    s = _S['shot']
    if not hits:
        return
    else:
        first = hits[0][0]
        remaining = s['pp']
        ignored = set()
        is_jet = False
        jet_start = 0.0
        for dist, cos_, kind, part in hits:
            mi = _mat_info(v, part, kind)
            if mi is None or mi.armor is None:
                continue
            key = (
             part, mi.kind)
            if key in ignored:
                continue
            c = min(1.0, max(0.0, abs(cos_))) if mi.useHitAngle else 1.0
            armor = float(mi.armor or 0.0)
            if not is_jet and s['mayRic'] and mi.mayRicochet and armor > 1e-05 and c <= s['rcos'] and (not mi.checkCaliberForRichet or not s['checkCal'] or armor * 3.0 >= s['cal']):
                return (1, 0.0)
            cd = dist - first + 0.1
            if is_jet:
                jd = cd - jet_start
                if jd > 0.0:
                    remaining *= max(1.0 - jd * s['jet'], 0.0)
            if mi.useHitAngle:
                na = s['norm']
                if na > 0.0 and c < 1.0:
                    if mi.checkCaliberForHitAngleNorm and s['cal'] > armor * 2.0 > 0.0:
                        na *= 1.4 * s['cal'] / (armor * 2.0)
                    ang = min(math.acos(c) - na, math.pi * 0.5)
                    c = 1.0 if ang <= 1e-05 else max(math.cos(ang), 1e-05)
                eff = armor / max(c, 1e-05)
            else:
                eff = armor
            if mi.vehicleDamageFactor and mi.vehicleDamageFactor > 1e-05:
                ratio = (remaining - eff) / s['pp'] + 1.0
                R = s['R']
                return (
                 0, min(1.0, max(0.0, (ratio + R - 1.0) / R / 2.0)))
            remaining -= eff
            if mi.collideOnceOnly:
                ignored.add(key)
            if s['jet'] > 0.0:
                is_jet = True
                jet_start = cd + armor * 0.001
            if remaining <= 0.0:
                break

        return (2, 0.0)


def _trace_step(v):
    if MODES[_S['mode']] != 'penetration' or _S['shot'] is None:
        return
    cam = Math.Vector3(BigWorld.camera().position)
    if _S['cam'] is None or (cam - _S['cam']).length > 0.01:
        _S['cam'] = cam
        _S['trace_queue'] = [ g for g in _S['groups'] if g['part']['ok'] ]
    coll = v.appearance.collisions
    t_end = time.clock() + TRACE_BUDGET
    while _S['trace_queue'] and time.clock() < t_end:
        g = _S['trace_queue'].pop(0)
        m = Math.Matrix(g['node'])
        votes = {0: [], 1: 0, 2: 0}
        for q in g['samples']:
            pt = m.applyPoint(q)
            d = pt - cam
            if d.length < 0.05:
                continue
            d.normalise()
            hits = coll.collideAllWorld(cam, pt + d * 15.0)
            r = _penetration(v, hits) if hits else None
            if r is None:
                continue
            if r[0] == 0:
                votes[0].append(r[1])
            else:
                votes[r[0]] += 1

        n0 = len(votes[0])
        if n0 == 0 and votes[1] == 0 and votes[2] == 0:
            continue
        if n0 >= max(votes[1], votes[2]):
            res = (
             0.0, sum(votes[0]) / n0)
        elif votes[1] >= votes[2]:
            res = (1.0, 0.0)
        else:
            res = (2.0, 0.0)
        if res != g['res']:
            g['res'] = res
            dm = g['part']['dm']
            dm.setMaterialParameterVector4('g_color', Math.Vector4(res[0], res[1], 0.0, 0.0))
            dm.setMaterialParameterVector4('g_animationParams', Math.Vector4(3.0, ALPHA, _S['shot']['R'], 0.0))

    return


def _tick():
    if not _S['tick']:
        return
    try:
        _frame()
    except Exception:
        import traceback
        traceback.print_exc()
        disable()
        return

    BigWorld.callback(0.0, _tick)


def _frame():
    if MODES[_S['mode']] is None:
        return
    else:
        v = _vehicle()
        if v is None:
            if _S['veh'] is not None:
                _detach()
            return
        if _S['veh'] is not None and (_S['veh'] is not v or _S['veh'].typeDescriptor.name != v.typeDescriptor.name):
            _detach()
        if _S['veh'] is None:
            for part in PARTS:
                _queue_part(v.typeDescriptor, part)

            _gen_step()
            if not _S['jobs']:
                if _attach(v):
                    _update_shot(v)
            return
        _build_step(v)
        _follow()
        for p in _S['parts']:
            if not p['ok']:
                if p['seen']:
                    p['ok'] = True
                elif p['dm'].isValid():
                    p['seen'] = True

        _push_all()
        _trace_step(v)
        return


def _message(text):
    try:
        from gui import SystemMessages
        SystemMessages.pushMessage(text, type=SystemMessages.SM_TYPE.Information)
    except Exception:
        _log(text)


def set_mode(i):
    _S['mode'] = i % len(MODES)
    for p in _S['parts']:
        p['pushed'] = None

    for g in _S['groups']:
        g['res'] = None

    _S['cam'] = None
    if MODES[_S['mode']] is None:
        _detach()
        _message('Броня: выкл')
        return
    else:
        if not _S['tick']:
            _S['tick'] = True
            _tick()
        v = _vehicle()
        if v is not None and _S['veh'] is not None:
            _update_shot(v)
        _message('Броня: %s%s' % ('номинальная' if MODES[_S['mode']] == 'nominal' else 'шанс пробития',
         ' (%s)' % _S['label'] if MODES[_S['mode']] == 'penetration' and _S['label'] else ''))
        return


def next_shell():
    _S['shell'] += 1
    v = _vehicle()
    if v is not None:
        _update_shot(v)
    for p in _S['parts']:
        p['pushed'] = None

    for g in _S['groups']:
        g['res'] = None

    _S['cam'] = None
    _message('Снаряд: %s' % _S['label'])
    return


def disable():
    _S['tick'] = False
    _detach()