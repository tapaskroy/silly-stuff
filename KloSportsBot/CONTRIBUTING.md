# Contributing

Thanks for your interest. This is a small hobby framework, but it touches a real WhatsApp
account and a live pool session, so the contribution rules are deliberately strict about
secrets.

## Workflow: PR-only

- **`main` is protected. No direct pushes.** Every change goes through a branch → pull request → review → merge.
- **Tapas Roy is a required reviewer.** At least one approving review (his) is needed before any merge. A `CODEOWNERS` entry auto-requests him on every PR touching `KloSportsBot/`.
- Stale approvals are dismissed on new commits; keep your branch up to date with `main`.
- No force-pushes to or deletion of `main`.

## Before you open a PR — sanitization checklist

Run the full pre-commit sanitization checklist in [`SECURITY.md`](SECURITY.md). At minimum:

- [ ] No new hardcoded **credentials**, **phone numbers**, or **WhatsApp JIDs/LIDs** (`@s.whatsapp.net`, `@lid`, `@g.us`).
- [ ] No absolute machine paths (`/Users/...`, `/home/...`) in shipped code — use `import.meta.url` / `$(dirname "$0")` / config.
- [ ] No real `auth.json`, `.env`, `bridge.config.sh`, `events.ndjson`, `triggers.ndjson`, logs, or personal screenshots.
- [ ] New configuration goes into a `*.example` / `*.template` file, never a real one.
- [ ] `git status --ignored` confirms `.gitignore` still covers every secret/personal pattern.

A quick grep to run from the repo root before pushing:

```sh
grep -rIn -E '@s\.whatsapp\.net|@lid|@g\.us|/Users/|/home/[a-z]|password|secret' . \
  --exclude-dir=node_modules --exclude='*.example*' --exclude='*.template*'
```

PRs that introduce a secret will be closed without merge until the history is clean.

## Code style

- Keep scripts **small and single-purpose**. One tool, one job.
- New pool integrations go **behind config** (the DOM contract in `docs/ARCHITECTURE.md`), not as forks of the scrapers.
- Prefer adding a config knob over hardcoding a value.
- Match the existing terse style; comments should explain *why*, not *what*.

## Reporting issues

For non-security bugs, open an issue. For anything that looks like a leaked secret in the
repo or its history, see the responsible-disclosure note in [`SECURITY.md`](SECURITY.md) —
do **not** open a public issue with the secret in it.
