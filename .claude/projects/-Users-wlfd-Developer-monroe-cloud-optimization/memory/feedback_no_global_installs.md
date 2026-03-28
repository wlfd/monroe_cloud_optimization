---
name: no_global_installs
description: User does not want tools installed globally; always use Docker for project tooling
type: feedback
---

Never install tools globally on the user's machine (pip install, npm install -g, brew install, etc.).

**Why:** User wants to keep their system clean — all project tooling should run inside Docker containers only.

**How to apply:** When running linters, formatters, test runners, or any dev tooling:
- Use `docker compose run --rm <service>` to run commands in an existing service
- Or use `docker run --rm -v ...` with an appropriate image
- Update Makefile targets to use Docker
- Never suggest `pip install`, `pip3 install`, `npm install -g`, or `brew install` as a solution
