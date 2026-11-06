# uncompyle6 version 3.7.4
# Python bytecode 2.7 (62211)
# Decompiled from: Python 3.10.6 (tags/v3.10.6:9c7b4bd, Aug  1 2022, 21:53:49) [MSC v.1932 64 bit (AMD64)]
# Embedded file name: scripts/client/gui/mods/armorflashlight/log.py
# Compiled at: 2026-01-01 04:00:00
import traceback
DEBUG = [
 False]

def _s(x):
    if isinstance(x, unicode):
        return x.encode('utf-8')
    return str(x)


def note(tag, *a):
    print '[%s] %s' % (tag, (' ').join(_s(x) for x in a))


def debug(tag, *a):
    if DEBUG[0]:
        note(tag, *a)


def exception(tag, stage):
    print '[%s] %s failed:\n%s' % (_s(tag), _s(stage), _s(traceback.format_exc()))