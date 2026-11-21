# Debugging access and private files

Keep photos, settings backups, journals, screenshots, signing keys and ADB authorizations out of Git.
Backups can include account and network settings. The CLI refuses private output inside Git checkouts,
but it can't stop you copying those files into one later.

Don't expose ADB to the internet. An authorized ADB computer has much more access than StillTV uses.
The CLI's checks aren't a sandbox for that computer.

## After setup

Finish checking Home, HDMI, the remote and recovery before closing the debugging connection.
Then, in the TV's Developer options:

1. Turn off USB debugging, network/ADB debugging and wireless debugging, where available.
2. Revoke debugging authorizations.
3. Restart the TV and check normal operation.
4. From the same LAN, check that port 5555 refuses connections. A timeout alone doesn't prove it's
   closed. If wireless debugging showed a separate TLS port, check that too; it may change on restart.

`adb disconnect` only disconnects your client. It doesn't turn off debugging on the TV.
You'll need the remote and a new on-screen authorization if you enable it again.

StillTV has no Internet permission or network listener. That says nothing about Android, the TV
manufacturer's services or your streaming apps, which can still connect as usual.
