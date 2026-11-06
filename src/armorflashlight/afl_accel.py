# uncompyle6 version 3.7.4
# Python bytecode 2.7 (62211)
# Decompiled from: Python 3.10.6 (tags/v3.10.6:9c7b4bd, Aug  1 2022, 21:53:49) [MSC v.1932 64 bit (AMD64)]
# Embedded file name: scripts/client/gui/mods/armorflashlight/afl_accel.py
# Compiled at: 2026-01-01 04:00:00
import imp, os, struct, sys, time, afl_data as A, log as LG, runtime
SHIM = os.path.join('mods', 'temp', 'net.openwg.native', 'native_lesta', 'python27.dll')
GUARD = 'native.loading'
_S = {'mod': None, 'state': 'not loaded', 'common': {}, 'errors': 0}

def _log(*a):
    LG.note('afl', *a)


def _exe_stamp():
    try:
        st = os.stat(sys.executable)
        return '%s %d %d' % (os.path.basename(sys.executable), st.st_size, int(st.st_mtime))
    except Exception:
        return '?'


def _pe(path):
    """(machine, is64, sections [(vsize, rva, rawsize, rawptr)], offset of the data directories, data) of a PE file"""
    with open(path, 'rb') as (f):
        d = f.read()
    if d[:2] != 'MZ':
        raise ValueError('not a PE file')
    pe = struct.unpack_from('<I', d, 60)[0]
    if d[pe:pe + 4] != 'PE\x00\x00':
        raise ValueError('no PE signature')
    machine, nsec = struct.unpack_from('<HH', d, pe + 4)
    opt_size = struct.unpack_from('<H', d, pe + 20)[0]
    opt = pe + 24
    is64 = struct.unpack_from('<H', d, opt)[0] == 523
    dd = opt + (112 if is64 else 96)
    sec = opt + opt_size
    sections = [ struct.unpack_from('<IIII', d, sec + 40 * i + 8) for i in range(nsec) ]
    return (machine, is64, sections, dd, d)


def _file_off(sections, rva):
    for vsize, va, rawsize, rawptr in sections:
        if va <= rva < va + max(vsize, rawsize):
            return rva - va + rawptr

    raise ValueError('rva %#x outside the sections' % rva)


def _cstr(d, off):
    return d[off:d.index('\x00', off)]


def pe_exports(path):
    """(machine, the names a DLL exports)"""
    machine, is64, sections, dd, d = _pe(path)
    rva = struct.unpack_from('<I', d, dd)[0]
    if not rva:
        return (machine, set())
    o = _file_off(sections, rva)
    n_names = struct.unpack_from('<I', d, o + 24)[0]
    names_rva = struct.unpack_from('<I', d, o + 32)[0]
    no = _file_off(sections, names_rva)
    return (machine, set(_cstr(d, _file_off(sections, struct.unpack_from('<I', d, no + 4 * i)[0])) for i in range(n_names)))


def pe_imports(path, dll):
    """(machine, the names a module imports from `dll`, case-insensitive)"""
    machine, is64, sections, dd, d = _pe(path)
    rva = struct.unpack_from('<I', d, dd + 8)[0]
    out = []
    if not rva:
        return (machine, out)
    step, fmt = (8, '<Q') if is64 else (4, '<I')
    flag = 1 << (63 if is64 else 31)
    o = _file_off(sections, rva)
    while True:
        orig_first, _, _, name_rva, first = struct.unpack_from('<IIIII', d, o)
        if not name_rva:
            break
        if _cstr(d, _file_off(sections, name_rva)).lower() == dll.lower():
            t = _file_off(sections, orig_first or first)
            while True:
                v = struct.unpack_from(fmt, d, t)[0]
                if not v:
                    break
                if not v & flag:
                    out.append(_cstr(d, _file_off(sections, v & 2147483647) + 2))
                t += step

        o += 20

    return (
     machine, out)


def compatible(pyd, shim_path):
    """(ok, why): the shim exports everything the accelerator imports from python27.dll and is the same architecture.
    Nothing is loaded: a mismatching (old / other) shim is found out here and not by a crash in the loader"""
    try:
        m_pyd, need = pe_imports(pyd, 'python27.dll')
        m_shim, have = pe_exports(shim_path)
    except Exception as e:
        return (
         False, 'cannot read the PE tables: %s' % e)

    if not need:
        return (False, 'the module imports nothing from python27.dll')
    if m_pyd != m_shim:
        return (False, 'architecture differs (module %#x, shim %#x)' % (m_pyd, m_shim))
    missing = sorted(n for n in need if n not in have)
    if missing:
        return (False, 'the shim lacks %d functions: %s' % (len(missing), (', ').join(missing[:6])))
    return (
     True, '%d functions' % len(need))


def load(pyd, guard_dir):
    """pyd: the accelerator as a real file; guard_dir: where GUARD is kept. -> the module or None"""
    if _S['mod'] is not None:
        return _S['mod']
    else:
        shim = os.path.join(runtime.game_root(), SHIM)
        if not os.path.isfile(pyd):
            _S['state'] = 'off: %s missing' % pyd
            _log('native accelerator', _S['state'])
            return
        if 'python27' not in sys.modules and not os.path.isfile(shim):
            _S['state'] = 'off: no wot.common (its %s is missing): the data is built in Python' % SHIM
            _log('native accelerator', _S['state'])
            return
        shim_file = getattr(sys.modules.get('python27'), '__file__', None) or shim
        if os.path.isfile(shim_file):
            ok, why = compatible(pyd, shim_file)
            if not ok:
                _S['state'] = 'off: the shim %s is not compatible: %s (the data is built in Python)' % (os.path.basename(shim_file), why)
                _log('native accelerator', _S['state'])
                return
            _log('native accelerator: shim is compatible,', why)
        guard = os.path.join(guard_dir, GUARD)
        stamp = _exe_stamp()
        if os.path.isfile(guard):
            with open(guard, 'rb') as (f):
                was = f.read()
            if was == stamp:
                _S['state'] = 'off: loading it took the client down before (%s); delete %s to retry' % (stamp, guard)
                _log('native accelerator', _S['state'])
                return
        with open(guard, 'wb') as (f):
            f.write(stamp)
        t0 = time.clock()
        try:
            if 'python27' not in sys.modules:
                imp.load_dynamic('python27', shim)
            mod = imp.load_dynamic('afl_native', pyd)
            r = mod.build(('', '', '', ''), ('', '', '', ''), '\x00' * 576)
            if not (isinstance(r, tuple) and len(r) == 3 and r[0][:4] == 'DDS '):
                raise RuntimeError('self-test: unexpected result %r' % (r[:2] if isinstance(r, tuple) else r,))
        except Exception as e:
            _S['state'] = 'off: load failed: %s' % e
            _log('native accelerator', _S['state'])
            os.remove(guard)
            return

        os.remove(guard)
        _S['mod'] = mod
        _S['state'] = 'on (%.0f ms to load)' % ((time.clock() - t0) * 1000.0)
        _log('native accelerator', _S['state'])
        return mod


def _mats(own, common, pi):
    """'<4d' records (kind, armor, vehicleDamageFactor, flags): the part's own materials first (no armour -> flags -1:
    skipped, not taken from the common table; None -> falls through), then the common ones (the first record of a kind
    wins in the C++ build, as materials.get(kind) or common.get(kind) in afl_data)"""
    out = []
    for kind in sorted(own):
        mi = own[kind]
        if mi is None:
            continue
        if mi.armor is None:
            out.append(struct.pack('<4d', kind, 0, 0, -1))
            continue
        rec = A.mat_record(mi, pi)
        out.append(struct.pack('<4d', kind, rec[0], rec[1], rec[2]))

    key = (
     id(common), pi)
    tail = _S['common'].get(key)
    if tail is None:
        tail = []
        for kind in sorted(common or {}):
            mi = common[kind]
            if mi is None or mi.armor is None:
                continue
            rec = A.mat_record(mi, pi)
            tail.append(struct.pack('<4d', kind, rec[0], rec[1], rec[2]))

        tail = _S['common'][key] = ('').join(tail)
    return ('').join(out) + tail


def _rig(rig):
    iC, iT, iG, M_t, M_g = rig
    mats = (iC, iT, iG, A.inverse(iC), M_t, A.mul(M_g, M_t))
    return struct.pack('<72d', *[ x for M in mats for row in M for x in row[:3] ])


def build(havok4, own4, common, rig):
    """havok4: the four .havok contents ('' = none); own4: the parts' own material dicts -> (dds bytes, info dict,
    bounding sphere) or None (accelerator off, a body without a Havok tree, or an error: build it in Python)"""
    mod = _S['mod']
    if mod is None:
        return
    else:
        try:
            r = mod.build(tuple(havok4), tuple(_mats(own4[pi], common, pi) for pi in range(4)), _rig(rig))
        except Exception as e:
            r = (
             'error', repr(e))

        if len(r) != 3:
            if r[0] != 'fallback':
                _S['errors'] += 1
                if _S['errors'] <= 3:
                    _log('native build error (the Python build takes over):', r[1])
            return
        dds, ci, sphere = r
        info = {'tris': list(ci[0:4]), 'nodes': list(ci[4:8]), 'mats': ci[8], 'texels': ci[9], 'own_bvh': 0, 'native': 1}
        return (dds, info, sphere)