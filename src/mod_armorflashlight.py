# uncompyle6 version 3.7.4
# Python bytecode 2.7 (62211)
# Decompiled from: Python 3.10.6 (tags/v3.10.6:9c7b4bd, Aug  1 2022, 21:53:49) [MSC v.1932 64 bit (AMD64)]
# Embedded file name: scripts/client/gui/mods/mod_armorflashlight.py
# Compiled at: 2026-01-01 04:00:00
VERSION = '1.0.38'

def init():
    try:
        from gui.mods.armorflashlight import start
        start()
    except Exception:
        import traceback
        print '[armorflashlight] start failed:\n' + traceback.format_exc()


def fini():
    try:
        from gui.mods.armorflashlight import stop
        stop()
    except Exception:
        import traceback
        print '[armorflashlight] stop failed:\n' + traceback.format_exc()