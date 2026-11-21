# Architecture and recovery contract

```
Local photos → local contain/EXIF-strip → private JPEGs
Private config → staged provider writes → validated atomic config commit
                       ↓
             Native offline Home + PhotoDream

ADB inspect → manufacturer profile → hardware/snapshot-bound plan
                                         ↓ exact SHA approval
                               write-ahead journal → apply → verify
                                         ↓ failure
                              compensate owned package changes
```

## Boundaries

The Android app is native Java, API 26+, no third-party runtime libraries and no requested permissions.
The Python core uses only the standard library. Pillow is an optional, local-only photo-processing
dependency. No AI model, API key, cloud photo store or unattended agent is required at runtime.

`Adb` uses an explicit serial and shell-quoted remote arguments. It has bounded command timeouts and
does not retry refusals. Identity uses a SHA-256 of manufacturer + hardware serial (not IP alone).
This pseudonymous hash is still private device metadata. It is not a cryptographic authentication
mechanism; the ADB authorization is the trust boundary.

Plans include schema, identity, state digest, transitions, reasons and their complete SHA-256. The
digest is a review/change-control mechanism, not a signature or authorization service. Runtime policy
is rechecked even when someone recomputes the plan hash. A plan is never transferable between TVs.

## Mutation and replay

1. Capture inventory; revalidate identity, policy, state and exact approval.
2. Acquire one filesystem lock per device. Package changes and Home handover share that lock.
3. Write a journal and private settings backup before package mutation.
4. Persist a `pending` entry **before** each `pm disable-user`.
5. Verify the actual package state; mark `applied`.
6. On a caught failure/interrupt, compensate in reverse order and verify state.

A pending step can have succeeded remotely before its acknowledgement was lost. Recovery inspects it
instead of assuming it failed. A previously disabled package never becomes this tool's rollback target.
Repeated apply after a successful journal is a no-op only if its recorded states still hold. A stale
or interrupted journal requires explicit recovery and a fresh plan, not silent re-execution.

Recovery is **not transaction isolation from other ADB clients**. TV power loss, disconnection or another
actor's changes can defeat compensation. Re-enabling a package disabled by our recorded transition
cannot distinguish a subsequent independent decision to keep that same package disabled; review the
journal if other tools have changed the TV. Filesystem locks coordinate StillTV on one host only.

Home handover journals the old component, pauses only an explicitly selected Projectivy override,
sets the new preference, injects one Home event and checks the resumed activity. Failure restores the
old preference. Restoration merges back only the service it paused, preserving newer screen readers
and other accessibility choices. It refuses to overwrite an unrelated newer Home choice.

## Android configuration

The exported content provider is protected by `WRITE_SECURE_SETTINGS`. `call()` also enforces that
permission explicitly, because framework read/write enforcement does not consistently cover calls.
Normal installed apps cannot configure the launcher. Path names are tightly validated, no arbitrary
filesystem paths are accepted, and Android backup is disabled.

Photos are staged first. `config.pending` is validated (schema, labels, bounded intervals, path-safe
names, image dimensions and asset presence). `AtomicFile` commits it last. Failure leaves the active
config unchanged. Reopening Home reloads the config. This is atomic configuration publication, not
a versioned configuration rollback service. Save your source config/photos to reapply an older look.

## Scaling model

Reusable profiles + generated per-TV plans + isolated per-device journals. This scales the **procedure**,
not unattended fleet administration. We do not scan networks or fan out writes. New OEM support needs
real hardware validation. There is no central controller, managed-device policy server or remote cloud.
