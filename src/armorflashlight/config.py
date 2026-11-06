# uncompyle6 version 3.7.4
# -*- coding: utf-8 -*-
# Python bytecode 2.7 (62211)
# Decompiled from: Python 3.10.6 (tags/v3.10.6:9c7b4bd, Aug  1 2022, 21:53:49) [MSC v.1932 64 bit (AMD64)]
# Embedded file name: config
import io, json, os, log as L, runtime
FILE_NAME = 'ArmorFlashlight.json'
TAG = 'armorflashlight'
CONFIG_VERSION = 1
DEFAULTS = {'configVersion': CONFIG_VERSION, 
   'enabled': True, 
   'debugLog': False, 
   'firstRunRestart': 'auto', 
   'flashlight': {'enabled': True, 
                  'nativeAccelerator': True, 
                  'shotFromMuzzle': True, 
                  'overTargetDetails': True, 
                  'hotkeys': {'toggle': 'Y', 'scheme': 'ALT+Y', 'pattern': 'CTRL+Y', 'opacity': 'CTRL+SHIFT+Y', 'mode': 'U', 'shotRays': 'SHIFT+U', 
                              'overDetails': 'CTRL+U', 'allies': '', 'circle': 'X'}}, 
   'inspector': {'enabled': True, 
                 'hotkeys': {'mode': 'ALT+I', 'shell': 'ALT+K'}}}
DEFAULT_TEXT = '// Armor Flashlight (goodmod.armorflashlight): настройки, которых нет в окне игры.\n// Вид подсветки (цветовая схема, заливка, непрозрачность, режим) -- в «Настройки -> Прицел -> Подсветка брони».\n// Мод файл не перезаписывает; чтобы вернуть значения по умолчанию, удалите его -- он создастся заново.\n// Клавиши, настройки подсветки и её включение действуют со следующего боя; ускоритель, инспектор и весь мод -- после\n// перезапуска клиента. Клавиши: "Y", "ALT+Y", "CTRL+SHIFT+Y", "U" и т. п., пустая строка "" -- без клавиши.\n// Не назначайте клавиши игры: клиент выполняет свою команду при любых модификаторах (F4 -- «Назад на базу!»).\n{\n    // служебная версия файла настроек: мод сам поднимает её при обновлении (сохраняя ваши значения). Не редактируйте.\n    "configVersion": 1,\n    // false -- мод не загружается совсем (ни подсветка в бою, ни инспектор в ангаре)\n    "enabled": true,\n    // подробный журнал в python.log (сборка данных по машинам, состав боя и т. п.)\n    "debugLog": false,\n    // при первом запуске мод сам создаёт папки данных в res_mods; клиент видит их только после перезапуска.\n    // "auto" -- перезапустить клиент сам один раз (с защитой от зацикливания); "ask" -- спросить в ангаре\n    // диалогом; "off" -- ничего, только сообщение «перезапустите клиент». Перезапуск делается ровно один раз.\n    "firstRunRestart": "auto",\n\n    // подсветка брони в бою\n    "flashlight": {\n        "enabled": true,\n        // C++-ускоритель сборки данных (работает, если установлен wot.common); без него та же сборка на Python\n        "nativeAccelerator": true,\n        // лучи выстрела из дула к каждой точке, как в EU; false -- параллельно направлению прицела\n        "shotFromMuzzle": true,\n        // цвет поверх навесных деталей цели (ящики, крылья, запасные траки); false -- только где видна броня\n        "overTargetDetails": true,\n        "hotkeys": {\n            "toggle": "Y",              // включить / выключить\n            "scheme": "ALT+Y",          // цветовая схема\n            "pattern": "CTRL+Y",        // заливка\n            "opacity": "CTRL+SHIFT+Y",  // непрозрачность\n            "mode": "U",                // режим: обычный / экономичный / полный / для слабых ПК (эконом + малый круг EU)\n            "shotRays": "SHIFT+U",      // лучи из дула / параллельно прицелу\n            "overDetails": "CTRL+U",    // поверх деталей / только броня\n            "allies": "",               // союзники тоже цели (для проверки в тренировочной комнате)\n            "circle": "X"               // удерживать: круг размера EU (плавно), отпустить -- обычный размер\n        }\n    },\n\n    // инспектор брони в ангаре\n    "inspector": {\n        "enabled": true,\n        "hotkeys": {\n            "mode": "ALT+I",            // выкл -> номинальная броня -> шанс пробития\n            "shell": "ALT+K"            // следующий снаряд атакующего орудия\n        }\n    }\n}\n'

def path():
    """Absolute path of the mod config under mods/configs/<MOD_ID>/."""
    return os.path.join(runtime.game_root(), 'mods', 'configs', runtime.MOD_ID, FILE_NAME)


def strip_comments(text):
    """Drop // line comments, keep // inside "..." strings.

    Reconstructed from the __owg_vm program (config.pyc::strip_comments).
    """
    out = []
    i = 0
    n = len(text)
    in_str = False
    while i < n:
        c = text[i]
        if in_str:
            out.append(c)
            if c == '\\' and i + 1 < n:
                out.append(text[i + 1])
                i += 2
                continue
            if c == '"':
                in_str = False
        elif c == '"':
            in_str = True
            out.append(c)
        elif c == '/' and text.startswith('//', i):
            j = text.find('\n', i)
            i = n if j < 0 else j
            continue
        else:
            out.append(c)
        i += 1
    return ''.join(out)
def write_default():
    p = path()
    if os.path.exists(p):
        return
    try:
        d = os.path.dirname(p)
        if not os.path.isdir(d):
            os.makedirs(d)
        with io.open(p, 'w', encoding='utf-8', newline='\n') as (f):
            f.write(DEFAULT_TEXT)
        L.note(TAG, 'config written with the defaults:', p)
    except (IOError, OSError):
        L.exception(TAG, 'config write ' + p)


def _byteify(x):
    if isinstance(x, dict):
        return dict((_byteify(k), _byteify(v)) for k, v in x.items())
    if isinstance(x, list):
        return [ _byteify(v) for v in x ]
    if isinstance(x, unicode):
        return x.encode('utf-8')
    return x


def parse_hotkey(text):
    """'CTRL+SHIFT+Y' -> (key code, alt, ctrl, shift); '' -> None; raises ValueError"""
    text = text.strip().upper()
    if not text:
        return
    else:
        parts = [ p.strip() for p in text.split('+') ]
        mods, name = set(parts[:-1]), parts[(-1)]
        bad = mods - {'ALT', 'CTRL', 'SHIFT'}
        if bad or not name:
            raise ValueError('modifiers ALT / CTRL / SHIFT and one key expected')
        try:
            import Keys
            code = getattr(Keys, 'KEY_' + name)
        except ImportError:
            code = name
        except AttributeError:
            raise ValueError('no key %s' % name)

        return (
         code, 'ALT' in mods, 'CTRL' in mods, 'SHIFT' in mods)


def matches(hotkey, event):
    return hotkey is not None and event.key == hotkey[0] and bool(event.isAltDown()) == hotkey[1] and bool(event.isCtrlDown()) == hotkey[2] and bool(event.isShiftDown()) == hotkey[3]


def _merge(defaults, raw, where):
    """Merge a parsed config dict over defaults, validating shape and types.

    Reconstructed from the __owg_vm program (config.pyc::_merge).
    """
    res = {}
    if not isinstance(raw, dict):
        raw = {}
    for k, dv in defaults.items():
        v = raw.get(k, dv)
        name = where + k
        if isinstance(dv, dict):
            if k in raw and not isinstance(raw[k], dict):
                L.note(TAG, 'config: %s must be an object, default used' % name)
            if k == 'hotkeys':
                res[k] = _hotkeys(dv, raw.get(k), name + '.')
            else:
                res[k] = _merge(dv, raw.get(k), name + '.')
        elif isinstance(dv, bool):
            if not isinstance(v, bool):
                L.note(TAG, 'config: %s must be true or false, got %r: default %r used' % (name, v, dv))
                v = dv
            res[k] = v
        else:
            res[k] = v
    return res


def _hotkeys(defaults, raw, where):
    """-> {name: (code, alt, ctrl, shift) or None}; the text of each key under '_text' (for labels)"""
    res, text = {}, {}
    raw = raw if isinstance(raw, dict) else {}
    for k, dv in defaults.items():
        v = raw.get(k, dv)
        try:
            if not isinstance(v, str):
                raise ValueError('a string expected')
            res[k] = parse_hotkey(v)
        except ValueError as ex:
            L.note(TAG, 'config: %s%s = %r: %s; default %r used' % (where, k, v, ex, dv))
            res[k], v = parse_hotkey(dv), dv

        text[k] = v.strip().upper()

    res['_text'] = text
    return res


_ABSENT = object()

def _tokenize(text):
    """[(kind, text)] covering the whole string; kind is 'triv' (whitespace / // comment), 'str', 'punct', 'lit'"""
    toks, i, n = [], 0, len(text)
    while i < n:
        c = text[i]
        if c in ' \t\r\n':
            j = i + 1
            while j < n and text[j] in ' \t\r\n':
                j += 1

            toks.append(('triv', text[i:j]))
        elif c == '/' and text[i:i + 2] == '//':
            j = text.find('\n', i)
            j = n if j < 0 else j
            toks.append(('triv', text[i:j]))
        elif c == '"':
            j = i + 1
            while j < n:
                if text[j] == '\\':
                    j += 2
                    continue
                if text[j] == '"':
                    j += 1
                    break
                j += 1

            toks.append(('str', text[i:j]))
        elif c in '{}[]:,':
            toks.append(('punct', text[i:i + 1]))
        else:
            j = i
            while j < n and text[j] not in ' \t\r\n{}[]:,"/':
                j += 1

            toks.append(('lit', text[i:j]))
        i += len(toks[(-1)][1])

    return toks


def _inject(template, values):
    """return `template` with each scalar whose key-path exists in `values` replaced by the player's value, every
    comment and all formatting kept. `values` is the parsed player config (unicode keys). configVersion is never
    taken from the player, so the template's current version is written. Raises on malformed input (caller aborts)."""
    toks = _tokenize(template)
    sig = [ (idx, k, t) for idx, (k, t) in enumerate(toks) if k != 'triv' ]
    repl = {}

    def scalar(idx, node):
        if node is not _ABSENT and not isinstance(node, (dict, list)):
            txt = json.dumps(node, ensure_ascii=False)
            repl[idx] = txt if isinstance(txt, unicode) else txt.decode('utf-8')

    def value(si, node):
        idx, _k, t = sig[si]
        if t == '{':
            return obj(si, node)
        if t == '[':
            return arr(si)
        scalar(idx, node)
        return si + 1

    def obj(si, node):
        si += 1
        while sig[si][2] != '}':
            keyname = json.loads(sig[si][2])
            si += 2
            child = node[keyname] if isinstance(node, dict) and keyname in node and keyname != 'configVersion' else _ABSENT
            si = value(si, child)
            if sig[si][2] == ',':
                si += 1

        return si + 1

    def arr(si):
        si += 1
        while sig[si][2] != ']':
            si = value(si, _ABSENT)
            if sig[si][2] == ',':
                si += 1

        return si + 1

    value(0, values)
    return ('').join(repl.get(i, t) for i, (_k, t) in enumerate(toks))


def _migrate(p, parsed, old_ver):
    """rewrite the file from the current template keeping the player's values; back the old one up. Best-effort:
    any failure leaves the file untouched (runtime still works via _merge)."""
    try:
        with open(p, 'rb') as (f):
            old = f.read()
        new_text = _inject(DEFAULT_TEXT, parsed)
        chk = json.loads(strip_comments(new_text))
        if not isinstance(chk, dict) or chk.get('configVersion') != CONFIG_VERSION:
            raise ValueError('rendered config invalid')
        with open(p + '.bak', 'wb') as (f):
            f.write(old)
        with io.open(p, 'w', encoding='utf-8', newline='\n') as (f):
            f.write(new_text)
        L.note(TAG, 'config migrated (version %r -> %d), backup %s' % (old_ver, CONFIG_VERSION, p + '.bak'))
        runtime.notify('Armor Flashlight: настройки обновлены до новой версии мода — ваши значения сохранены, прежний файл лежит рядом как %s.bak.' % FILE_NAME)
    except Exception:
        L.exception(TAG, 'config migrate (file left as is)')


def load():
    """-> the config, hotkeys parsed (tuples or None); defaults on any problem with the file. A file from an older
    schema version is migrated first (new keys added, the player's values kept)."""
    p = path()
    raw = {}
    if not os.path.exists(p):
        write_default()
    else:
        try:
            with open(p, 'rb') as (f):
                text = f.read().decode('utf-8-sig')
            parsed = json.loads(strip_comments(text))
            if not isinstance(parsed, dict):
                raise ValueError('the top level must be an object')
            if parsed.get('configVersion') != CONFIG_VERSION:
                _migrate(p, parsed, parsed.get('configVersion'))
            raw = _byteify(parsed)
        except (IOError, OSError, ValueError, UnicodeDecodeError) as ex:
            L.note(TAG, 'config %s unreadable (%s): defaults used' % (p, ex))
            raw = {}

    cfg = _merge(DEFAULTS, raw, '')
    L.DEBUG[0] = cfg['debugLog']
    return cfg