#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""goodmod.armorflashlight 1.0.38 — сборка .mtmod из исходников.

Два режима:

  1) рядом есть папка assets/ с ресурсами (meta.xml + res/**):
         C:\\Python27\\python.exe build.py

  2) ресурсов нет — берём их из своего экземпляра оригинального мода:
         C:\\Python27\\python.exe build.py --original "C:\\path\\goodmod.armorflashlight_1.0.38.mtmod"

На выходе: dist/goodmod.armorflashlight_1.0.38.mtmod

Скрипт ничего не качает, не запускает код мода и не трогает игру:
он компилирует src/**.py в байткод 2.7 и упаковывает вместе с ресурсами.
"""
import hashlib
import imp
import json
import marshal
import os
import struct
import sys
import zipfile

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "src")
ASSETS = os.path.join(HERE, "assets")
DIST = os.path.join(HERE, "dist")
OUT = os.path.join(DIST, "goodmod.armorflashlight_1.0.38.mtmod")

MODS = "res/scripts/client/gui/mods"
PKG = "armorflashlight"

MAGIC = imp.get_magic()       # b'\x03\xf3\r\n' для 2.7
MTIME = 1767225600            # фиксированная метка в заголовке .pyc
DATE = (2026, 1, 1, 0, 0, 0)  # дата записей ZIP (как в оригинале)
ATTR = 27525120               # 0o644 << 16


def sources():
    out = [f for f in sorted(os.listdir(SRC)) if f.endswith(".py")]
    pkg = os.path.join(SRC, PKG)
    out += [PKG + "/" + f for f in sorted(os.listdir(pkg)) if f.endswith(".py")]
    return out


def arc_for(rel):
    if rel.startswith(PKG + "/"):
        return "%s/%s/%s.pyc" % (MODS, PKG, rel.split("/")[1][:-3])
    return "%s/%s.pyc" % (MODS, rel[:-3])


def build_pyc(path, dfile):
    code = compile(open(path, "rb").read(), dfile, "exec")
    return MAGIC + struct.pack("<I", MTIME) + marshal.dumps(code)


def read_original(path):
    """-> (order, reader) из архива оригинального мода"""
    z = zipfile.ZipFile(path)
    order = [i.filename for i in z.infolist() if not i.filename.endswith("/")]
    return order, (lambda n: z.read(n))


def main(argv):
    if sys.version_info[:2] != (2, 7):
        sys.exit("нужен Python 2.7, запущено: %s" % sys.version.split()[0])

    orig = None
    if "--original" in argv:
        i = argv.index("--original")
        if i + 1 >= len(argv):
            sys.exit("после --original нужен путь к .mtmod")
        orig = argv[i + 1]
        if not os.path.isfile(orig):
            sys.exit("нет файла: %s" % orig)

    if orig:
        order, read_res = read_original(orig)
        print("ресурсы: %s" % orig)
    else:
        if not os.path.isdir(ASSETS):
            sys.exit("нет папки assets/ — укажи --original <путь к оригинальному .mtmod>")
        order = [l.strip() for l in open(os.path.join(HERE, "order.txt")) if l.strip()]

        def read_res(n):
            with open(os.path.join(ASSETS, n.replace("/", os.sep)), "rb") as f:
                return f.read()

        print("ресурсы: assets/")

    dfiles = json.load(open(os.path.join(HERE, "dfiles.json")))
    dfiles = dict((k.encode("utf-8") if isinstance(k, unicode) else k,
                   v.encode("utf-8") if isinstance(v, unicode) else v)
                  for k, v in dfiles.items())

    built = {}
    for rel in sources():
        arc = arc_for(rel)
        dfile = dfiles.get(arc) or arc[len("res/"):].replace(".pyc", ".py")
        built[arc] = build_pyc(os.path.join(SRC, rel.replace("/", os.sep)), dfile)

    extra = [a for a in built if a not in order]

    if not os.path.isdir(DIST):
        os.makedirs(DIST)
    if os.path.exists(OUT):
        os.remove(OUT)

    z = zipfile.ZipFile(OUT, "w", zipfile.ZIP_STORED)
    for name in order + sorted(extra):
        info = zipfile.ZipInfo(name, DATE)
        info.compress_type = zipfile.ZIP_STORED
        info.external_attr = ATTR
        info.create_system = 0
        z.writestr(info, built[name] if name in built else read_res(name))
    z.close()

    data = open(OUT, "rb").read()
    print("готово: %s" % OUT)
    print("  записей: %d, модулей: %d" % (len(order) + len(extra), len(built)))
    print("  размер: %d байт" % len(data))
    print("  sha256: %s" % hashlib.sha256(data).hexdigest())


if __name__ == "__main__":
    main(sys.argv[1:])
