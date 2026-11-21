# Operational security and teardown

- Keep photos, settings backups, journals, screenshots, authorizations and signing keys out of Git.
  Settings backups can contain private account/network information. The CLI refuses private output
  inside any Git checkout. Do not bypass that by copying its output into a commit.
- Do not expose ADB to the internet. A host authorized by ADB can do much more than this CLI permits.
  This tool's policy is an accidental-change guard, not a sandbox around a malicious host.
- After launcher, HDMI, remote and rollback checks are complete, use the TV's Developer options to turn
  off **USB debugging**, **Network/ADB debugging** and **Wireless debugging**, where present; revoke
  debugging authorizations. Restart the TV and confirm normal operation.
- From the same LAN, verify TCP port 5555 refuses connection. A timeout is **unverified**, not evidence
  of a closed port. Wireless-debugging TLS ports are separate and can change after a restart; check the
  actual port shown in Developer options too. Merely running `adb disconnect` does not close TV access.
- Do not turn access off while an install or recovery remains unverified. Re-enabling it later needs
  the remote and a fresh on-screen authorization.

StillTV itself has no Internet permission, analytics SDK, local HTTP server or network listener. It
does not imply that the rest of Android, the manufacturer's services or streaming apps are offline.
There is no automatic firmware update removal, root, factory menu, DNS rewrite or universal debloat list.

No paid service, account or subscription is required by StillTV. Streaming subscriptions are independent.
