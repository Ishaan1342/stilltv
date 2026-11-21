# How it works

The Android app is native Java, targeting API 26 and later. It has no third-party runtime libraries
or requested permissions. The Python tool uses the standard library, with Pillow as an optional
photo-processing dependency. Neither needs an AI service at runtime.

## Configuration and photos

```
Original photos → local framing and metadata removal → prepared JPEGs
Config + JPEGs → ADB upload → validation → replace active config
                                      ↓
                           Home screen and screensaver
```

The app stores config and photos in its private storage. Its content provider requires
`WRITE_SECURE_SETTINGS`, so ordinary apps can't configure it. The provider checks that permission
explicitly for `call()` as well as file access. Paths, image sizes and config fields are validated.
Android backup is disabled.

Photos go into a separate upload directory first. Each file is checked against its SHA-256 before
publication; an existing photo is never overwritten. The provider checks every referenced file,
then uses `AtomicFile` to replace the active config and reads it back before reporting success.
Reads share the write lock and use `AtomicFile` recovery after an interrupted write.
Reopen Home to load the new one. Keep your original config and prepared photos if you want to
restore an older setup; the provider doesn't keep a version history.

Interrupted uploads can leave unused files behind. There isn't an automatic cleanup or free-space
preflight yet.

Photo decoding follows the actual Android surface, up to 4K. Each bitmap is limited to 32 MiB or
a quarter of the app's heap, whichever is smaller. A smaller decode is attempted if memory runs out.
A TV with a small app heap or a 1080p UI surface will use a lower-resolution decode.

## Package changes

```
Inspect TV → review profile → save plan → approve exact hash
                                             ↓
                               journal → change → check
                                             ↓ failure
                                 undo recorded changes
```

ADB commands use an explicit device serial, quoted shell arguments and bounded timeouts. StillTV
doesn't retry a refusal. A hash of the manufacturer and hardware serial identifies the TV, rather
than its IP address. That hash is still private metadata, not a way to authenticate the device;
ADB authorization handles access.

A plan records the device, a snapshot of its state, package changes, reasons and a SHA-256 hash.
The hash catches changes to a reviewed plan; it isn't a signature. The tool checks its package
policy again at apply time, even if someone has recomputed the hash.

Before applying, the tool rechecks the device and snapshot, acquires a per-device filesystem lock,
and saves a journal and settings backup. Each step is marked pending **before** the ADB command.
Afterwards, the tool reads back the package state. If a command fails or is interrupted, it tries
to undo the recorded changes in reverse order.

A command can succeed even if its acknowledgement gets lost. Recovery checks pending steps too.
Packages already disabled before the plan aren't recovery targets. Applying the same successful
plan again is a no-op only while the recorded result still holds. Every new plan gets a unique ID,
so it can be applied after an earlier plan was restored. An interrupted journal needs explicit recovery
and a new plan. Recovery attempts continue if a journal write or another package's restore fails;
the tool reports any remaining changes or unsaved recovery state.

## Changing Home

Home handover shares the package-operation lock. It saves the old Home component, optionally pauses
only Projectivy's Home override, changes the preference, sends one Home event and checks the resumed
activity. On failure it tries to restore the old preference.

Restoration adds back only the accessibility service it paused, preserving newer accessibility
choices. It refuses to replace a different Home app chosen since the handover. A completed restore
is a no-op if replayed, so an old journal can't undo a later Home or accessibility choice.
It doesn't disable the stock launcher.

## Where recovery stops

These are compensating changes, not an atomic Android transaction. Power loss, disconnection or
another ADB client can leave work for you to recover manually. The lock only coordinates StillTV
processes on the same computer, and a stale lock isn't removed automatically.

If another tool later disables the same package for its own reason, StillTV can't tell that apart
from its own recorded change. Read the journal before restoring in that situation.

Profiles can be shared; plans and journals belong to one TV. There's no network scanning, cloud
controller or unattended rollout. Supporting another TV still means testing on that hardware.
