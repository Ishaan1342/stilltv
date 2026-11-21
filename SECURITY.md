# Security reporting

Do not file public issues containing private device data, credentials or exploitable details.
Use GitHub's **Report a vulnerability** privately if enabled. If it is unavailable, first open a
metadata-only issue asking for a private channel; do not include the vulnerability itself.

This is an early MVP, not a security audit or a promise to protect a device from a malicious ADB host.
An authorized ADB host already has extensive device control. Protect the host and close debugging
after setup. See [the operational security notes](docs/security.md).
