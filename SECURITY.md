# Security Policy

## Supported Use

Skills Manager is designed as a local-first management console for your own
`SKILL.md` files.

Default safe posture:

- Bind to `127.0.0.1`
- Store manager metadata outside managed skill directories
- Require explicit confirmation before writing back to protected skill roots
- Keep API keys in environment variables or `.env`, never in source files

## Important Boundaries

This project currently has no authentication layer. Do not expose it directly
to the public internet.

Some actions can overwrite a real `SKILL.md`:

- Restore historical version
- Restore baseline
- Apply candidate version
- Automatic evolution on non-protected skill roots

Use `SKILLS_MANAGER_PROTECTED_ROOTS` for installed or shared skill directories.
The default protected root is `~/.codex/skills`.

## Secrets

Never commit these values:

- `ANTHROPIC_API_KEY`
- `OPENAI_API_KEY`
- Local proxy credentials
- Any private model gateway token

The repository `.gitignore` excludes `.env`, `.venv`, and `runtime/`.

## Reporting Issues

If you find a security issue, open a private channel with the maintainer when
possible. If that is not available, file a GitHub issue with minimal
reproduction details and avoid posting secrets, private skill contents, or
real API keys.

## Local Deployment Checklist

Before running against real skills:

1. Confirm `APP_HOST=127.0.0.1` unless you have a separate access-control layer.
2. Confirm `SKILLS_PATH` points to the intended directory.
3. Confirm `SKILLS_MANAGER_META_DIR` is outside the managed skill directory.
4. Confirm `SKILLS_MANAGER_PROTECTED_ROOTS` includes any installed skill root
   that should not be overwritten silently.
5. Confirm model provider credentials are available only through local
   environment variables or `.env`.
