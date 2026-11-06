# Good Mod 1.0.38 — мод и исходники

Мод «Good Mod» для «Мира танков» 1.46.0.0: полные исходники Python 2.7
и скрипт сборки. В репозитории лежит всё, что нужно для сборки, — код и ресурсы
(текстуры, шейдеры, `.swf`, нативный `.pyd`).

**Готовая сборка:** [Releases → v1.0.38](https://github.com/MeccCZ/goodmod-armorflashlight/releases/tag/v1.0.38) — если не хочешь компилить сам.

## Собирает НИЧЕГО — никаких данных

**Мод не собирает и никуда не отправляет никаких данных.** Нет HWID, нет
отпечатка железа, нет телеметрии, нет аналитики, нет данных аккаунта. Мод не
делает ни одного сетевого запроса: в этой сборке серверная часть SDK отключена
(`OFFLINE_DEV_MODE = True`), и любой сокет упал бы ещё до подключения — это
проверяется сокет-ловушкой в тестах (`27/27`).

**English:** This mod collects nothing. No HWID, no hardware fingerprint, no
telemetry, no analytics, no account data. It makes zero network requests — the
server-side SDK is disabled in this build (`OFFLINE_DEV_MODE = True`) and a socket
trap verifies that no connection is ever attempted.

## Почему это не вирус

* весь код — обычные `.py` в `src/`, можно прочитать каждую строку;
* сборка это `compile()` + `zip`: ни загрузок, ни установки, ни автозапуска;
* мод **не обращается к серверу авторизации**: `modsdk_hook._boot_sdk()` выходит
  до любого сетевого кода (флаг в `src/armorflashlight/offline_dev.py`);
* `build.py` и `verify.py` короткие и целиком в репозитории;
* готовую сборку можно не брать — собери сам за одну команду и сравни `sha256`.

## Что нужно

* Windows
* **Python 2.7** (`C:\Python27\python.exe`) — байткод в моде должен быть 2.7

Python 3 не подойдёт: `build.py` компилирует исходники в байткод 2.7.

## Сборка

```
C:\Python27\python.exe build.py
```

Результат: `dist\goodmod.armorflashlight_1.0.38.mtmod`

Ожидаемые параметры:

```
записей: 78   (77 из оригинального архива + offline_dev.pyc)
размер:  2 784 013 байт
sha256:  7a698f06dce29155b5183645ce3edbc6fc7eb7b68a0e26e04d20f1b92142b225
```

Сборка детерминирована: повторный запуск даёт тот же файл байт в байт
(фиксированная дата ZIP и метка времени в заголовках `.pyc`).

Если ресурсы лежат не в `assets/`, а в оригинальном архиве:

```
C:\Python27\python.exe build.py --original "C:\path\to\goodmod.armorflashlight_1.0.38.mtmod"
```

Проверка готового файла:

```
C:\Python27\python.exe verify.py
```

13 проверок: 78 записей, 16 модулей, магия 2.7, метка времени, офлайн-гарды,
наличие `.pyd` / `.swf` / 55 текстур / 4 шейдеров.

## Установка

1. `dist\goodmod.armorflashlight_1.0.38.mtmod` → `<игра>\mods\1.46.0.0\`
2. рядом положи `net.openwg.common_2.8.3.0000.mtmod` — он лежит в этом же релизе (даёт `LGC` и shim `wot.common`/`python27.dll` для ускорителя отрисовки; без него сборка данных идёт на Python)
3. конфиг: `config\ArmorFlashlight.json` (из репозитория или релиза) → `<игра>\mods\configs\goodmod.armorflashlight\ArmorFlashlight.json`. Если не положить — мод создаст дефолтный сам, но с готовым файлом настройки (клавиши, включение подсветки/инспектора) применяются сразу
4. запустить клиент

Старый файл мода с тем же id удалить — два архива рядом держать нельзя.

## Офлайн-режим

`src/armorflashlight/offline_dev.py`:

```python
OFFLINE_DEV_MODE = True
```

При включённом флаге:

* `modsdk_hook._boot_sdk()` возвращает `False` до любого сетевого кода — ни `wss://`,
  ни TLS-хендшейка, ни реконнектов;
* `__init__._start_modsdk()` пишет в `python.log` строку
  `OFFLINE_DEV_MODE: 3 server feature(s) unavailable: ...` и не запускает миньон.

Отключено: загрузка `sdk_core` с сервера, серверный attest/лицензия, серверные
обновления модулей. Лицензирование не обходится и не подделывается — серверная часть
просто не запускается.

Работает локально: подсветка в бою, инспектор брони в ангаре, окно настроек,
хоткеи, файл конфигурации, нативный ускоритель.

Чтобы вернуть штатное поведение — `OFFLINE_DEV_MODE = False` и пересобрать.

## Структура

```
src/
  mod_armorflashlight.py      точка входа загрузчика модов
  armorflashlight/
    __init__.py               запуск/остановка, хоткеи, сообщения
    afl_battle.py             подсветка в бою: кадр, цели, материалы
    afl_data.py               разбор данных танка, BVH
    afl_fwdpack.py            упаковка данных для forward-рендера
    afl_havok.py              парсер havok/varint
    afl_accel.py              загрузка нативного ускорителя
    afl_settings.py           настройки в клиенте
    afl_settings_ui.py        окно настроек (Scaleform)
    lai_models.py             модели для инспектора брони
    lai_inspector.py          инспектор брони в ангаре
    config.py                 ArmorFlashlight.json
    runtime.py                пути, кэш, копирование в res_mods
    log.py                    журнал
    modsdk_hook.py            миньон SDK (в офлайн-режиме не стартует)
    offline_dev.py            флаг OFFLINE_DEV_MODE
assets/
  meta.xml + res/**           ресурсы мода: текстуры, шейдеры, swf, pyd
build.py                      сборка .mtmod
verify.py                     проверка архива
order.txt                     порядок записей (как в оригинале)
dfiles.json                   co_filename для каждого модуля
```

## Что проверено

* 16/16 модулей импортируются и выполняют код уровня модуля (с заглушками
  BigWorld/ResMgr/CGF/AvatarInputHandler);
* 27/27 проверок офлайн-режима, включая отсутствие сетевых вызовов (сокет-ловушка);
* 7/7 тестов varint-парсера;
* `_frame`, `_enqueue`, `_rd_vint` совпадают с байткодом выпущенной сборки
  инструкция в инструкцию.

Не проверено: бой на живом клиенте, работа нативного `.pyd`, другие версии игры.

## English (short)

Full Python 2.7 sources and assets of the Good Mod for World of Tanks
1.46.0.0, plus a build script. Build is `compile()` + `zip`, no downloads, no autostart.

```
C:\Python27\python.exe build.py     → dist\goodmod.armorflashlight_1.0.38.mtmod
C:\Python27\python.exe verify.py
```

Offline mode contacts no server and does not bypass licensing: server-side parts are
simply disabled, local features keep working.

## Права

Мод, его код и ресурсы — собственность автора (владельца репозитория).
К «Миру танков» / Lesta Games проект отношения не имеет.
