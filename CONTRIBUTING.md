# Contributing to Logforge

Thanks for your interest in improving Logforge! Bug reports, docs fixes,
detection rules, and code changes are all welcome.

## Getting started

1. Fork the repository and create a branch from `main`.
2. Bring up the local stack (ClickHouse, MinIO, RedPanda, Redis, API, UIs):

   ```bash
   ./deploy.sh
   ```

3. See the [README](./README.md) for creating the first admin user and for
   running the API / UIs outside Docker.

## Running tests

```bash
# API tests
pytest

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
