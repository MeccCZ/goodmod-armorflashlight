# uncompyle6 version 3.7.4
# -*- coding: utf-8 -*-
# Python bytecode 2.7 (62211)
# Decompiled from: Python 3.10.6 (tags/v3.10.6:9c7b4bd, Aug  1 2022, 21:53:49) [MSC v.1932 64 bit (AMD64)]
# Embedded file name: runtime
import hashlib, os, re, shutil, time, zlib, ResMgr, log as L
MOD_ID = 'goodmod.armorflashlight'
PKG_DIR = 'armorflashlight'
NATIVE_VFS = PKG_DIR + '/native/afl_native.pyd'
TAG = 'armorflashlight'
_P = {}
NOTES = []
RESTART = []

def notify(text):
    """Queue a one-shot note (skipped if already queued)."""
    if text not in NOTES:
        NOTES.append(text)
def game_root():
    d = _P.get('game')
    if d is None:
        d = os.getcwd()
        try:
            m = os.path.normpath(ResMgr.mainAppDirectory())
            if os.path.isfile(os.path.join(m, 'paths.xml')):
                d = m
        except Exception:
            pass

        _P['game'] = d
    return d


def _paths():
    """(res_mods/<ver>, mods/<ver>) as absolute paths, from the client's paths.xml"""
    if 'res_mods' not in _P:
        res = mods = None
        try:
            for name, p in ResMgr.openSection('../paths.xml')['Paths'].items():
                if name != 'Path':
                    continue
                s = p.asString.strip()
                if 'mask' in p.keys() and p['mask'].asString.strip().lower().endswith('.mtmod'):
                    mods = mods or os.path.normpath(os.path.join(game_root(), s))
                elif 'res_mods' in s:
                    res = res or os.path.normpath(os.path.join(game_root(), s))

        except Exception:
            L.exception(TAG, 'paths.xml')

        _P['res_mods'], _P['mods'] = res, mods
    return (
     _P['res_mods'], _P['mods'])


def res_mods_dir():
    """res_mods/<version> as an absolute path."""
    return _paths()[0]
def mods_dir():
    """mods/<version> as an absolute path."""
    return _paths()[1]
def temp_dir(*sub):
    d = os.path.join(game_root(), 'mods', 'temp', MOD_ID, *sub)
    if not os.path.isdir(d):
        os.makedirs(d)
    return d


_CACHES = {}
FEATURES = {'afl_cache': 'а подсветка брони в бою', 'lai_cache': ' инспектор брони в ангаре'}

def cache(name):
    """-> {'path': real folder or None, 'ok': the VFS sees files written there now, 'created': made in this session}"""
    c = _CACHES.get(name)
    if c is not None:
        return c
    else:
        c = _CACHES[name] = {'path': None, 'ok': False, 'created': False}
        res = res_mods_dir()
        if res is None or not os.path.isdir(res):
            L.note(TAG, 'no res_mods folder in paths.xml: generated data is off')
            return c
        d = c['path'] = os.path.join(res, name)
        try:
            if not os.path.isdir(d):
                os.makedirs(d)
                c['created'] = True
            probe = '.probe_%d_%d' % (os.getpid(), int(time.time() * 1000))
            with open(os.path.join(d, probe), 'wb') as (f):
                f.write('x')
            c['ok'] = ResMgr.openSection(name + '/' + probe) is not None
            os.remove(os.path.join(d, probe))
        except Exception:
            L.exception(TAG, 'cache folder ' + d)

        if not c['ok']:
            where = 'res_mods\\%s\\%s' % (os.path.basename(res), name)
            if c['created']:
                L.note(TAG, 'cache folder %s: created now -- the client sees it after a restart' % d)
                notify('Armor Flashlight: создана папка данных %s. Перезапустите клиент, чтобы заработал%s.' % (
                 where, FEATURES.get(name, 'и функции мода')))
                if where not in RESTART:
                    RESTART.append(where)
            else:
                L.note(TAG, 'cache folder %s: cannot write there or the client does not see it' % d)
                notify('Armor Flashlight: папка данных %s недоступна (нет прав на запись?): без неё не работает%s.' % (
                 where, FEATURES.get(name, 'и функции мода')))
        return c


_FP = {}

def fingerprint(path):
    """size + crc32 of a game file as a file-name-safe string ('' if the VFS has none), remembered per path (the parts are
    shared by many vehicles). Lets a cache key follow the CONTENT, so the cache can be carried over to a new client version
    and a file the patch changed gets its data built again"""
    r = _FP.get(path)
    if r is None:
        r = ''
        try:
            sec = ResMgr.openSection(path)
            if sec is not None:
                b = sec.asBinary
                r = '%x_%08x' % (len(b), zlib.crc32(b) & 4294967295)
        except Exception:
            pass

        _FP[path] = r
    return r


def _version_key(name):
    return tuple(int(x) for x in name.split('.'))


def _store(name):
    """the version-independent copy of a cache: mods/temp/<mod id>/store/<name> (not in the client's VFS, it survives patches
    and a deleted res_mods/<ver>); None if it cannot be made"""
    try:
        return temp_dir('store', name)
    except OSError:
        return

    return


MAX_AGE = 7776000.0
_DAY = 86400.0
_TEMP_EXT = ('.tmp', '.part')

def _is_data(f, rx):
    low = f.lower()
    return low.endswith(CACHE_EXT) and not low.endswith(_TEMP_EXT) and rx.search(stem(f)) is not None


def _copy_iter(src, dst, rx, only_missing, stat):
    """copy the cache files (the age limit applies), one file per step; stat = {'n', 'size'}. Each file goes through <name>.part
    and a rename, so a killed copy leaves no half file under a real name; the .json (what the mod looks for first) is copied
    last and only if every other file went well: a .json in the folder means the whole set is there"""
    now = time.time()
    names = sorted((f for f in os.listdir(src) if _is_data(f, rx)), key=lambda f: f.lower().endswith('.json'))
    failed = False
    for f in names:
        p, t = os.path.join(src, f), os.path.join(dst, f)
        try:
            m = os.path.getmtime(p)
            if now - m > MAX_AGE:
                continue
            if os.path.isfile(t):
                if only_missing and m - os.path.getmtime(t) > _DAY:
                    os.utime(t, (m, m))
                if only_missing:
                    continue
            if failed and f.lower().endswith('.json'):
                continue
            part = t + '.part'
            shutil.copy2(p, part)
            if os.path.isfile(t):
                os.remove(t)
            os.rename(part, t)
            stat['n'] += 1
            stat['size'] += os.path.getsize(t)
        except (IOError, OSError):
            failed = True
            try:
                if os.path.isfile(t + '.part'):
                    os.remove(t + '.part')
            except OSError:
                pass

        yield


def _copy(src, dst, rx, only_missing):
    stat = {'n': 0, 'size': 0}
    for _ in _copy_iter(src, dst, rx, only_missing, stat):
        pass

    return (
     stat['n'], stat['size'])


def _drop_old(d, rx):
    """store housekeeping: files of another cache format, in-flight leftovers and entries not used for MAX_AGE"""
    now = time.time()
    for f in os.listdir(d):
        p = os.path.join(d, f)
        try:
            if os.path.isfile(p) and (f.lower().endswith(_TEMP_EXT) or f.lower().endswith(CACHE_EXT)) and (not rx.search(stem(f)) or now - os.path.getmtime(p) > MAX_AGE):
                os.remove(p)
        except OSError:
            pass


_TOUCHED = set()

def touch(name, prefix):
    """the entry `prefix` (a cache key) was used in this session: refresh its files' mtime (once a day at most) so the age limit
    drops only what nobody asks for"""
    if (
     name, prefix) in _TOUCHED:
        return
    else:
        _TOUCHED.add((name, prefix))
        d = cache(name)['path']
        if not d or not os.path.isdir(d):
            return
        now = time.time()
        try:
            for f in os.listdir(d):
                if f.startswith(prefix) and f.lower().endswith(CACHE_EXT):
                    p = os.path.join(d, f)
                    if now - os.path.getmtime(p) > _DAY:
                        os.utime(p, None)

        except OSError:
            pass

        return


def _mirror_iter(name, keep):
    """copy the cache files res_mods/<ver>/<name> has and the store has not into the store (cheap when nothing is new)"""
    c = cache(name)
    s = _store(name)
    if not c['path'] or not s or not os.path.isdir(c['path']):
        return
    rx = re.compile(keep)
    _drop_old(s, rx)
    stat = {'n': 0, 'size': 0}
    for _ in _copy_iter(c['path'], s, rx, True, stat):
        yield

    if stat['n']:
        L.note(TAG, 'cache %s: %d new files (%.1f MB) saved in the store, they survive a client update' % (
         name, stat['n'], stat['size'] / 1048576.0))


def _inherit_iter(name, keep):
    """a new client version starts with an empty res_mods/<ver>: copy the cache files (stem matching `keep`) from the
    version-independent store, else from the newest older version's folder, when this one has no finished set yet. The keys
    hash the content of what the data is built from, so a file that does not fit the new patch is simply not found and is
    built again. Files already there (generated meanwhile) are left alone"""
    c = cache(name)
    d = c['path']
    res = res_mods_dir()
    if not d or not res or not os.path.isdir(d):
        return
    rx = re.compile(keep)
    if any(f.lower().endswith('.json') and _is_data(f, rx) for f in os.listdir(d)):
        return
    parent, cur = os.path.dirname(res), os.path.basename(res)
    try:
        olds = sorted((x for x in os.listdir(parent) if x != cur and re.match('^\\d+(\\.\\d+)+$', x) and os.path.isdir(os.path.join(parent, x, name))), key=_version_key, reverse=True)
    except OSError:
        return

    s = _store(name)
    sources = ([('the store', s)] if s else []) + [ (ver, os.path.join(parent, ver, name)) for ver in olds ]
    for label, src in sources:
        if not os.path.isdir(src):
            continue
        stat = {'n': 0, 'size': 0}
        for _ in _copy_iter(src, d, rx, True, stat):
            yield

        if stat['n']:
            L.note(TAG, 'cache %s: %d files (%.1f MB) taken over from %s, not built again' % (name, stat['n'], stat['size'] / 1048576.0, label))
            return


def _count(it):
    n = 0
    for _ in it:
        n += 1

    return n


def inherit(name, keep):
    """-> number of steps run; the whole take-over at once (tests, tools)"""
    return _count(_inherit_iter(name, keep))


def mirror(name, keep):
    return _count(_mirror_iter(name, keep))


SYNC_SLICE = 0.004

def sync_cache(name, keep):
    """take over the cache of an older version, then save what the store lacks -- spread over frames (a first start after a
    patch copies hundreds of files, which must not stall the client's start-up)"""
    import itertools
    it = itertools.chain(_inherit_iter(name, keep), _mirror_iter(name, keep))

    def tick():
        t = time.clock()
        try:
            next(it)
            while time.clock() - t < SYNC_SLICE:
                next(it)

        except StopIteration:
            return
        except Exception:
            L.exception(TAG, 'cache sync ' + name)
            return

        import BigWorld
        BigWorld.callback(0.0, tick)

    tick()


def _restart_flag():
    try:
        return os.path.join(temp_dir(), 'restart_pending.flag')
    except Exception:
        return

    return


def restart_pending():
    f = _restart_flag()
    return bool(f) and os.path.isfile(f)


def mark_restart_pending():
    """write the flag before restarting -> True on success; False means don't auto-restart (can't guard the loop)"""
    f = _restart_flag()
    if not f:
        return False
    try:
        with open(f, 'wb') as (fh):
            fh.write('1')
        return True
    except Exception:
        L.exception(TAG, 'restart flag write')
        return False


def clear_restart_pending():
    f = _restart_flag()
    if f and os.path.isfile(f):
        try:
            os.remove(f)
        except OSError:
            pass


def stem(filename):
    """cache file name without its extension (and a .tmp after it): names may hold dots (Havok body names)"""
    if filename.endswith('.tmp'):
        filename = filename[:-4]
    return os.path.splitext(filename)[0]


CACHE_EXT = ('.dds', '.json', '.model', '.visual_processed', '.primitives_processed',
             '.tmp')

def prune(name, keep):
    """delete the cache files (CACHE_EXT) of cache `name` whose stem does not match the regex `keep` (re.search) or that were
    not used for MAX_AGE (see touch);
    anything else in the folder (the archive's _keep.txt, a player's file) stays"""
    c = cache(name)
    d = c['path']
    if not d or not os.path.isdir(d):
        return 0
    rx = re.compile(keep)
    n = size = 0
    for f in os.listdir(d):
        p = os.path.join(d, f)
        if not os.path.isfile(p) or not f.lower().endswith(CACHE_EXT):
            continue
        try:
            if rx.search(stem(f)) and time.time() - os.path.getmtime(p) <= MAX_AGE:
                continue
            size += os.path.getsize(p)
            os.remove(p)
            n += 1
        except OSError:
            pass

    if n:
        L.note(TAG, 'cache %s: %d old files removed (%.1f MB)' % (name, n, size / 1048576.0))
    return n


def native_pyd():
    """copy the packaged afl_native.pyd to a real file -> its path, or None (not in the package / cannot write)"""
    try:
        sec = ResMgr.openSection(NATIVE_VFS)
        if sec is None:
            return
        data = sec.asBinary
        if not data:
            return
        h = hashlib.md5(data).hexdigest()[:12]
        d = temp_dir('native_lesta')
        path = os.path.join(d, 'afl_native_%s.pyd' % h)
        if not (os.path.isfile(path) and os.path.getsize(path) == len(data)):
            tmp = path + '.tmp'
            with open(tmp, 'wb') as (f):
                f.write(data)
            if os.path.exists(path):
                os.remove(path)
            os.rename(tmp, path)
        for f in os.listdir(d):
            if f.startswith('afl_native_') and f != os.path.basename(path):
                try:
                    os.remove(os.path.join(d, f))
                except OSError:
                    pass

        return path
    except Exception:
        L.exception(TAG, 'native accelerator copy')
        return

    return


LEGACY = ('mod_afl.pyc', 'mod_lai_armor.pyc', 'afl_battle.pyc', 'lai_inspector.pyc')
_NEIGHBOURS = ('openwg', 'xfw', 'xvm', 'modssettingsapi', 'vxsettingsapi', 'modslistapi',
               'settings', 'gameface', 'unbound', 'mods_gui', 'hook', 'wot.common',
               'poliroid', 'izeberg', 'polarfox')

def startup_report(version, build_client=None):
    """one block in python.log at the mod start: the client, how the mod is installed, the other mods that can interfere
    (settings window, shared libraries), the native bridge. A player's log then says what is going on without questions"""
    try:
        import helpers
        client = helpers.getFullClientVersion()
    except Exception:
        client = '?'

    L.note(TAG, '== v%s start | client %s | built for %s' % (version, client, build_client or 'dev copy (no check)'))
    res, mods = _paths()
    L.note(TAG, 'folders: res_mods=%s mods=%s' % (res, mods))
    packages = []
    names = []
    if mods and os.path.isdir(mods):
        for base, _, files in os.walk(mods):
            for f in files:
                if f.lower().endswith('.mtmod'):
                    names.append(f)
                    if 'armorflashlight' in f.lower():
                        packages.append(f)

    L.note(TAG, 'our packages: %s%s' % ((', ').join(packages) or 'none',
     '  <-- SEVERAL, the client disables conflicting ones' if len(packages) > 1 else ''))
    neighbours = sorted(n for n in names if 'armorflashlight' not in n.lower() and any(k in n.lower() for k in _NEIGHBOURS))
    L.note(TAG, 'mods in %s: %d; settings / library related: %s' % (os.path.basename(mods or '') or '?', len(names),
     (', ').join(neighbours) or 'none'))
    shim = os.path.join(game_root(), 'mods', 'temp', 'net.openwg.native', 'native_lesta', 'python27.dll')
    import sys
    L.note(TAG, 'native bridge: wot.common shim %s, python27 module %s' % (
     'present' if os.path.isfile(shim) else 'absent',
     'loaded (%s)' % getattr(sys.modules['python27'], '__file__', '?') if 'python27' in sys.modules else 'not loaded'))
    L.note(TAG, 'settings tab SWF: %s' % ('present' if ResMgr.isFile('gui/flash/aflArmorFlashlightSettings.swf') else 'MISSING'))


def check_install():
    """a loose copy in res_mods (old flat layout, or ours next to the package) and several package versions"""
    res, mods = _paths()
    loose = []
    if res:
        g = os.path.join(res, 'scripts', 'client', 'gui', 'mods')
        loose = [ f for f in LEGACY if os.path.isfile(os.path.join(g, f)) ]
        if loose:
            L.note(TAG, 'old loose install in %s: %s' % (g, (', ').join(loose)))
            notify('Подсветка брони: в res_mods найдена старая установка мода (%s). Удалите её: она мешает новой версии.' % (', ').join(loose))
    packages = []
    if mods and os.path.isdir(mods):
        for base, _, files in os.walk(mods):
            packages += [ os.path.join(base, f) for f in files if 'armorflashlight' in f.lower() and f.lower().endswith('.mtmod')
                        ]

    if len(packages) > 1:
        L.note(TAG, 'several packages: %s' % (', ').join(packages))
        notify('Подсветка брони: в mods несколько версий мода (%s). Оставьте одну: игра отключает конфликтующие пакеты.' % (', ').join(os.path.basename(p) for p in packages))
    if res and packages and os.path.isfile(os.path.join(res, 'scripts', 'client', 'gui', 'mods', 'mod_armorflashlight.pyc')):
        L.note(TAG, 'a loose copy in res_mods overrides the package %s' % os.path.basename(packages[0]))
        notify('Armor Flashlight: в res_mods лежит копия мода файлами (scripts/client/gui/mods/mod_armorflashlight.pyc и папка armorflashlight) -- она перекрывает установленный пакет %s. Удалите её.' % os.path.basename(packages[0]))
    return (
     loose, packages)