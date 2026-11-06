# -*- coding: utf-8 -*-
"""OFFLINE_DEV_MODE for goodmod.armorflashlight (test build).

With this flag the mod performs no network activity at all: the modsdk minion is
never started, so sdk_core is never requested and no reconnects are attempted.

Licensing, attestation and signature checks are NOT bypassed. Without the SDK
every server-side feature is simply unavailable; local features keep working.
"""

OFFLINE_DEV_MODE = True

DISABLED_FEATURES = (
    'sdk_core bootstrap (server-supplied module)',
    'server attestation / license grant',
    'server-side module updates',
)


def describe():
    return 'OFFLINE_DEV_MODE: %d server feature(s) unavailable: %s' % (
        len(DISABLED_FEATURES), ', '.join(DISABLED_FEATURES))
