# Contributing to Logforge

Thanks for your interest in improving Logforge! Bug reports, docs fixes,
detection rules, and code changes are all welcome.

## Getting started

1. Fork the repository (or, if you have write access, create a branch) and
   branch off the latest `main`. Use a descriptive name such as
   `fix/live-tail-endpoint` or `feat/mitre-coverage-api`.
2. Bring up the local stack (ClickHouse, MinIO, RedPanda, Redis, API, UIs):

   ```bash
   ./deploy.sh
   ```

3. See the [README](./README.md) for creating the first admin user and for
   running the API / UIs outside Docker.

## Running tests

```bash
# API tests that need no infrastructure (run from the repo root)
pytest tests/ --ignore=tests/routes_tests

# UI end-to-end tests
cd apps/ui && npx playwright test
```

Some standalone scripts at the repository root (`simulate_tenant_logs.py`,
`data_generator.py`, `test_*_flow.py`, ...) talk to a running local stack.
Configure them with environment variables instead of editing the files:

| Variable             | Purpose                                  |
| -------------------- | ---------------------------------------- |
| `LOGFORGE_API_URL`   | API base URL (default `http://localhost:7080`) |
| `LOGFORGE_TENANT_ID` | Tenant / customer ID                     |
| `LOGFORGE_TOKEN`     | JWT or `lf_` API key                     |
| `LOGFORGE_EMAIL`     | Login email                              |
| `LOGFORGE_PASSWORD`  | Login password                           |

**Never commit real credentials, tokens, or personal data.**

## Pull requests

`main` is a protected branch: nobody pushes to it directly, maintainers included.
Every change lands through a pull request that

- targets `main`,
- passes CI (API tests, OpenAPI freshness check, lint, security scans, UI builds),
- is approved by a maintainer (see [CODEOWNERS](./.github/CODEOWNERS)), and
- is up to date with `main` before merging.

If you changed an API endpoint, regenerate the published spec and commit it:

```bash
python scripts/export_openapi.py
```

Looking for something to work on? See [docs/ROADMAP.md](./docs/ROADMAP.md).

- Keep PRs focused; one logical change per PR.
- Add or update tests for behaviour changes. CI must pass.
- Update docs when you change APIs or configuration.
- Write clear commit messages describing *why*, not just *what*.

## Reporting bugs and requesting features

Open a GitHub issue using one of the templates. For security issues, **do not**
open a public issue - see [SECURITY.md](./SECURITY.md).

## License

By contributing, you agree that your contributions will be licensed under the
[Apache License 2.0](./LICENSE).

## Code of Conduct

This project follows the [Code of Conduct](./CODE_OF_CONDUCT.md).
