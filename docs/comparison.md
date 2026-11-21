# Scope of the comparison

Reference reviewed 21 November 2026:
[Take Back Your TV](https://github.com/Shubhamsaboo/awesome-llm-apps/tree/main/advanced_llm_apps/take-back-your-tv).
It is a useful agent-guided playbook that uses [CleanYourTV](https://github.com/Gathin23/cleanyourtv)
as its launcher/tooling base. CleanYourTV itself is a much larger project with device-specific knowledge.
We do **not** pretend its features are absent or that StillTV has broader compatibility.

| Dimension | Referenced playbook | StillTV 0.1 |
|---|---|---|
| Delivery | Agent instructions for a custom build | Native launcher + executable Python CLI |
| Runtime AI dependency | Agent needed to carry out setup | No model needed for documented CLI operations |
| Package review | Agent inspects and asks | Explicit reviewed profile, protected policy, exact plan hash |
| Wrong-device defense | Agent procedure | Hardware identity + snapshot bound into every package plan |
| Recovery | Backup/disable/restore procedure, underlying tooling | Write-ahead per-transition journal, verified compensations and failure-injection tests |
| Repeated apply | Agent-managed | Explicit verified no-op for the same successful plan |
| Photos | Local face-aware crop instructions | Deterministic contain framing, preserves entire foreground, strips metadata; **no face detector** |
| Visual customization | Agent-built layout from specification | Configurable native cinematic/quiet/contrast layouts |
| Device coverage | Playbook states one TCL Android 11 test | Build supports API 26+; hardware claims only in verification record |
| Performance superiority | Author reports a faster TV | **Not claimed**; needs controlled hardware benchmarks |
| Secure teardown | Explicit debugging closure instructions | Documented closure/verification; not silently executed during incomplete recovery |

The concrete improvement over a prose-only workflow is **repeatable execution and testable failure
behavior**. There are tradeoffs: conservative protection blocks some possible cleanup; photos appear
framed rather than filling the screen with optimized face crops; no unattended fleet writes exist.

All code here was written for StillTV; no CleanYourTV launcher source is vendored. Architecture and
safety ideas from both references are credited. Please compare the shipped code and verified device
matrix, not the number of packages a demo happened to disable.
