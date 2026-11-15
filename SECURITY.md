# Security Policy

## Reporting a vulnerability

Please **do not** report security vulnerabilities through public GitHub issues.

Use GitHub's private vulnerability reporting instead: go to the repository's
**Security** tab and click **Report a vulnerability**.

Include as much of the following as you can:

- Affected component (API, UI, admin UI, ingestion, rules, ...)
- Steps to reproduce or a proof of concept
- Impact and any suggested fix

We aim to acknowledge reports within 5 business days.

## Supported versions

Only the latest `main` branch receives security fixes at this time.

## Deployment notes

The Docker Compose stack in `infra/docker/` ships with **development-only
default credentials** (ClickHouse, MinIO, etc.). Before exposing Logforge
beyond localhost you must:

- Change all default passwords in `infra/docker/compose.yml` / `config/`.
- Set `LOGFORGE_SECRET_KEY` to a strong random value (used to encrypt stored
  notification-channel credentials).
- Put the API and UIs behind TLS.
