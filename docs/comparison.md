# Related projects

StillTV started from the idea in Shubham Saboo's
[Take Back Your TV](https://github.com/Shubhamsaboo/awesome-llm-apps/tree/main/advanced_llm_apps/take-back-your-tv)
playbook, which uses [CleanYourTV](https://github.com/Gathin23/cleanyourtv).
Both are worth looking at before deciding what to put on your TV.

The playbook walks an AI agent through a custom setup. StillTV takes a different approach:
a standalone Android launcher, a config file, and a Python CLI. Once installed, it doesn't need
an agent, a model subscription or a cloud service.

The main work here is in the setup tool. Package plans include the TV's hardware identity and
current state. Changes are recorded before they're made, checked afterwards, and reversed on a
caught failure where possible. Tests cover stale plans, lost acknowledgements and interrupted
changes. That makes the process easier to repeat, but it isn't a fleet-management service.

There are tradeoffs:

- CleanYourTV has more device-specific knowledge. StillTV hasn't completed physical-TV testing yet.
- StillTV's default photo layout keeps the entire image visible. The landscape layout crops to fill
  the screen. Neither uses face detection, unlike the playbook's face-aware crop workflow.
- The package policy is conservative. It will refuse some changes an experienced owner might make
  by hand, rather than provide a force switch.
- No speed, memory or boot-time comparison has been run. Fewer packages doesn't automatically mean
  a faster or more reliable TV.

No CleanYourTV source is included in this repo. This comparison reflects the referenced playbook
as reviewed on 21 November 2026, not every feature in its underlying tools.
