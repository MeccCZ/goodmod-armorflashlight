# uncompyle6 version 3.7.4
# -*- coding: utf-8 -*-
# Python bytecode 2.7 (62211)
# Decompiled from: Python 3.10.6 (tags/v3.10.6:9c7b4bd, Aug  1 2022, 21:53:49) [MSC v.1932 64 bit (AMD64)]
# Embedded file name: afl_settings
import BigWorld
ENABLED = 'armorFlashlightEnabled'
SCHEMA = 'armorFlashlightColorSchema'
FILL = 'armorFlashlightFill'
OPACITY = 'armorFlashlightOpacity'
MODE = 'armorFlashlightResolutionScaling'
FOLIAGE = 'armorFlashlightThroughFoliage'
DESTR = 'armorFlashlightThroughDestructibles'
NAMES = (ENABLED, SCHEMA, FILL, OPACITY, MODE, FOLIAGE, DESTR)
SECTION = 'LestaArmorFlashlight'
DEFAULTS = {ENABLED: True, SCHEMA: 0, FILL: 0, OPACITY: 0.7, MODE: 0, FOLIAGE: True, DESTR: True}
SCHEMA_OPTIONS = [{'label': 'Вся броня', 'data': 0, 'id': 'redYellowGreen', 'tooltip': None}, {'label': 'Только непробиваемые зоны', 'data': 1, 'id': 'redShades', 'tooltip': None}, {'label': 'Только пробиваемые зоны', 'data': 2, 'id': 'greenShades', 'tooltip': None}]
FILL_OPTIONS = [{'label': 'Сплошная', 'data': 0, 'id': 'pattern1', 'tooltip': None}, {'label': 'Редкая штриховка', 'data': 1, 'id': 'pattern2', 'tooltip': None}, {'label': 'Частая штриховка', 'data': 2, 'id': 'pattern3', 'tooltip': None}]
MODE_OPTIONS = [{'label': 'Обычный', 'data': 0, 'name': 'high'}, {'label': 'Экономичный', 'data': 1, 'name': 'low'}, {'label': 'Полный', 'data': 2, 'name': 'full'}, {'label': 'Для слабых ПК', 'data': 3, 'name': 'low'}]
TOGGLE_KEY = [
 'Y']
FOLIAGE_LABEL = 'Подсветка сквозь кусты'
DESTR_LABEL = 'Подсветка сквозь объекты'
FOLIAGE_TIP = '{HEADER}Подсветка сквозь кусты{/HEADER}{BODY}Подсветка не прячется за кустами и кронами деревьев: снаряд их пролетает, поэтому броню цели видно и сквозь листву. Отключите, если листва мешает.{/BODY}'
DESTR_TIP = '{HEADER}Подсветка сквозь объекты{/HEADER}{BODY}Заборы, стены, машины и другие разрушаемые объекты снаряд пробивает насквозь, поэтому подсветка показывает броню цели и за ними. Здания, камни и земля по-прежнему закрывают подсветку.{/BODY}'

def enabled_label():
    key = TOGGLE_KEY[0]
    return 'Включать подсветку брони в начале боя' + (' (клавиша %s)' % key.decode('utf-8') if key else '')


values = dict(DEFAULTS)
committed = dict(DEFAULTS)
_listeners = []

def _prefs():
    import Settings
    return (
     Settings.g_instance, Settings.g_instance.userPrefs)


def load():
    try:
        _, up = _prefs()
        sec = up[SECTION]
        if sec is None:
            return
        values[ENABLED] = sec.readBool(ENABLED, DEFAULTS[ENABLED])
        values[SCHEMA] = max(0, min(2, sec.readInt(SCHEMA, DEFAULTS[SCHEMA])))
        values[FILL] = max(0, min(2, sec.readInt(FILL, DEFAULTS[FILL])))
        values[OPACITY] = max(0.0, min(1.0, sec.readFloat(OPACITY, DEFAULTS[OPACITY])))
        values[MODE] = max(0, min(len(MODE_OPTIONS) - 1, sec.readInt(MODE, DEFAULTS[MODE])))
        values[FOLIAGE] = sec.readBool(FOLIAGE, DEFAULTS[FOLIAGE])
        values[DESTR] = sec.readBool(DESTR, DEFAULTS[DESTR])
        committed.update(values)
    except Exception as ex:
        print '[afl] settings load:', repr(ex)

    return


def save():
    try:
        g, up = _prefs()
        sec = up[SECTION] or up.createSection(SECTION)
        sec.writeBool(ENABLED, bool(committed[ENABLED]))
        sec.writeInt(SCHEMA, int(committed[SCHEMA]))
        sec.writeInt(FILL, int(committed[FILL]))
        sec.writeFloat(OPACITY, float(committed[OPACITY]))
        sec.writeInt(MODE, int(committed[MODE]))
        sec.writeBool(FOLIAGE, bool(committed[FOLIAGE]))
        sec.writeBool(DESTR, bool(committed[DESTR]))
        g.save()
    except Exception as ex:
        print '[afl] settings save:', repr(ex)


def listen(fn):
    if fn not in _listeners:
        _listeners.append(fn)


def _rebase_preview(name, value):
    """a hotkey is an accepted change: if the settings window previews this option, Cancel returns to the hotkey value"""
    try:
        from helpers import dependency
        from skeletons.account_helpers.settings_core import ISettingsCore
        cont = dependency.instance(ISettingsCore).options
        if cont is not None and name in cont.indices:
            opt = cont.getSetting(name)
            if getattr(opt, 'valueReal', None) is not None:
                opt.valueReal = value
    except Exception as ex:
        print '[afl] settings preview rebase:', repr(ex)

    return


def set_value(name, value, persist=True):
    """persist: an accepted change (hotkey, Apply) -> saved; else a preview of the settings window (values only)"""
    values[name] = value
    if persist:
        committed[name] = value
        _rebase_preview(name, value)
    for fn in list(_listeners):
        try:
            fn(name, value)
        except Exception:
            import traceback
            traceback.print_exc()

    if persist:
        save()


def _coerce(name, value):
    if name in (ENABLED, FOLIAGE, DESTR):
        return bool(value)
    if name == OPACITY:
        return max(0.0, min(1.0, float(value)))
    return int(value)


def _setting_class():
    from account_helpers.settings_core import options

    class AflSetting(options.SettingAbstract):

        def __init__(self, name, opts=None, extra=None):
            super(AflSetting, self).__init__(isPreview=True)
            self.name = name
            self.__opts = opts
            self.__extra = extra

        def _get(self):
            return values[self.name]

        def _getOptions(self):
            return self.__opts

        def _set(self, value):
            set_value(self.name, _coerce(self.name, value), persist=False)

        def _save(self, value):
            committed[self.name] = _coerce(self.name, value)
            save()

        def pack(self):
            d = {'current': self._get(), 'extraData': dict(self.__extra or {'enabled': True})}
            if self.__opts is not None:
                d['options'] = self.__opts
            return d

        def getDefaultValue(self):
            """Default value for this setting (looked up by name)."""
            return DEFAULTS[self.name]
        def getType(self):
            """No explicit type override."""
            return None
    return AflSetting


def register():
    """add the options to the running SettingsCore (its container is rebuilt per account, so check every time)"""
    from helpers import dependency
    from skeletons.account_helpers.settings_core import ISettingsCore
    core = dependency.instance(ISettingsCore)
    cont = core.options
    if cont is None or ENABLED in cont.indices:
        return core
    S = _setting_class()
    new = ((ENABLED, S(ENABLED, extra={'enabled': True, 'label': enabled_label(), 'tooltip': None})),
     (
      SCHEMA, S(SCHEMA, SCHEMA_OPTIONS)),
     (
      FILL, S(FILL, FILL_OPTIONS)),
     (
      OPACITY, S(OPACITY)),
     (
      MODE, S(MODE, MODE_OPTIONS)),
     (
      FOLIAGE, S(FOLIAGE, extra={'enabled': True, 'label': FOLIAGE_LABEL, 'tooltip': FOLIAGE_TIP})),
     (
      DESTR, S(DESTR, extra={'enabled': True, 'label': DESTR_LABEL, 'tooltip': DESTR_TIP})))
    base = len(cont.settings)
    cont.settings = tuple(cont.settings) + new
    for k, (n, _) in enumerate(new):
        cont.indices[n] = base + k

    return core