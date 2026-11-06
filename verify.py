#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""Проверка собранного .mtmod: структура, байткод, ресурсы.

    C:\\Python27\\python.exe verify.py [путь_к_.mtmod]
"""
import marshal
import os
import struct
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT = os.path.join(HERE, "dist", "goodmod.armorflashlight_1.0.38.mtmod")
MODS = "res/scripts/client/gui/mods/armorflashlight/"

ok = []
bad = []


def check(name, cond, extra=""):
    (ok if cond else bad).append(name)
    print(("  OK   " if cond else "  FAIL ") + name + (("   " + extra) if extra else ""))


def main(path):
    z = zipfile.ZipFile(path)
    names = z.namelist()
    pycs = [n for n in names if n.endswith(".pyc")]

    check("архив читается", True, "%d записей" % len(names))
    check("meta.xml на месте", "meta.xml" in names)
    check("модулей 16", len(pycs) == 16, str(len(pycs)))
    check("offline_dev на месте", MODS + "offline_dev.pyc" in names)
    check("нативный .pyd на месте",
          any(n.endswith("afl_native.pyd") for n in names))
    check("Scaleform .swf на месте", any(n.endswith(".swf") for n in names))
    check("текстуры на месте", sum(1 for n in names if n.endswith(".png")) == 55)
    check("шейдеры на месте", sum(1 for n in names if n.endswith(".fxo")) == 4)

    magics, loaded, no_x = 0, 0, 0
    for n in pycs:
        data = z.read(n)
        if data[:4] == "\x03\xf3\r\n":
            magics += 1
        if struct.unpack("<I", data[4:8])[0] == 1767225600:
            loaded += 1
        try:
            co = marshal.loads(data[8:])
            if "_x" not in co.co_names:
                no_x += 1
        except Exception:
            pass

    check("магия 2.7 у всех модулей", magics == len(pycs), "%d/%d" % (magics, len(pycs)))
    check("метка времени в заголовке", loaded == len(pycs), "%d/%d" % (loaded, len(pycs)))
    check("marshal разбирается", no_x == len(pycs), "%d/%d" % (no_x, len(pycs)))

    hook = z.read(MODS + "modsdk_hook.pyc")
    init = z.read(MODS + "__init__.pyc")

    def has_guard(co, name):
        if name in co.co_names:
            return True
        for k in co.co_consts:
            if hasattr(k, "co_code") and has_guard(k, name):
                return True
        return False

    check("офлайн-гард в modsdk_hook", has_guard(marshal.loads(hook[8:]), "offline_dev"))
    check("офлайн-гард в __init__", has_guard(marshal.loads(init[8:]), "offline_dev"))

    print("\nпроверок: %d, провалов: %d" % (len(ok) + len(bad), len(bad)))
    return 0 if not bad else 1


if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else DEFAULT
    if not os.path.isfile(p):
        sys.exit("нет файла: %s (сначала build.py)" % p)
    sys.exit(main(p))
