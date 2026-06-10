# Contributing

## Development Setup

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
```

Run the app locally:

```bash
APP_HOST=127.0.0.1 APP_PORT=7890 ./.venv/bin/python app.py
```

Use `SKILLS_PATH` to point at a test skill directory:

```bash
SKILLS_PATH=/path/to/skills ./.venv/bin/python app.py
```

## Verification

Run these checks before opening a pull request:

```bash
python3 -m py_compile app.py scripts/smoke_local.py scripts/e2e_local.py
bash -n scripts/deploy.sh
./.venv/bin/python scripts/smoke_local.py
./.venv/bin/python scripts/e2e_local.py
```

`scripts/smoke_local.py` covers the core metadata, write-protection, candidate,
and evolution paths without starting a server.

`scripts/e2e_local.py` covers the Flask routes with a temporary skill directory
and a fake Codex CLI. It does not call real model providers or touch real
skills.

## Change Scope

Keep changes small and focused.

When changing behavior that can write to `SKILL.md`, include tests for:

- Protected root without confirmation
- Protected root with `confirm_write=true`
- Pre-restore or pre-apply snapshot creation
- Metadata staying outside the managed skill directory

When changing AI provider behavior, include tests for:

- Provider resolution
- JSON-returning calls
- Text-returning calls
- Failure messages that help the user fix local configuration

## Safety Rules

- Do not commit `.env`, `runtime/`, `.venv`, or generated local metadata.
- Do not add real API keys or private skill contents to tests.
- Do not make public-network binding the default.
- Do not silently write to protected skill roots.
