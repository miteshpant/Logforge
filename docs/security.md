# Security

How Logforge's own supply chain is checked, how releases are signed, and the
threat model. To report a vulnerability, see
[SECURITY.md](https://github.com/miteshpant/Logforge/blob/main/SECURITY.md).

## Checks in CI

| Check | Fails the build on |
|---|---|
| `pip-audit` on the API's requirements | any known vulnerability |
| `npm audit` on the UI and admin UI, through `scripts/audit_gate.py` | a high or critical advisory not in `security/audit-allowlist.json`, or an allowlist entry that has expired |
| Trivy on the API, UI and admin UI images | a critical vulnerability that has a fix |
| gitleaks | a committed secret |
| bandit | nothing; it reports medium and high findings |

Each CI run also writes an SPDX SBOM per image (Syft), kept as a build
artifact.

**The allowlist** is for advisories that can't be fixed yet. Each entry
names the package and the GHSA advisory, says why it's accepted, and has an
expiry date, after which CI fails again. Today it holds Next.js 14
advisories:

- Their fixes need Next.js 15.5 or later, a migration that's on the roadmap.
- Most don't apply to Logforge:
  - the image optimizer is turned off (`images.unoptimized`, and
    `/_next/image` answers 404);
  - the apps use no Server Actions, middleware, rewrites or i18n;
  - the images run on Linux.
- Three Server Components denial-of-service advisories do apply. Until the
  upgrade, run the UIs behind a proxy with request limits.
- The rest are two build-time PostCSS advisories.

## Signed releases

A `v*` tag runs `.github/workflows/release.yml`:

1. The API, UI and admin UI images are built and pushed to GHCR.
2. Each image is signed with [cosign](https://github.com/sigstore/cosign)
   (keyless: the signature is tied to the workflow's GitHub OIDC identity).
3. Each image's SPDX SBOM is attached to the GitHub release.

Verify an image before running it:

```bash
cosign verify ghcr.io/miteshpant/logforge-api:v0.3.0 \
  --certificate-identity-regexp 'https://github.com/miteshpant/Logforge/.github/workflows/release.yml@refs/tags/v.*' \
  --certificate-oidc-issuer https://token.actions.githubusercontent.com
```

The workflow hasn't run yet: the first tag will be its first run.

## Threat model

### What's protected

| Asset | Where |
|---|---|
| Tenants' logs, traces, metrics, alerts and cases | ClickHouse; Parquet archives in object storage |
| Credentials | user passwords (bcrypt), API keys (hashed), refresh tokens (hashed), SCIM tokens (SHA-256), integration and SSO client secrets (Fernet, `LOGFORGE_SECRETS_KEY`) |
| The ability to act | containment playbooks, ticket systems, notifications |
| Identity | sessions (JWT, `JWT_SECRET`), SSO providers, roles |

### Trust boundaries

1. **Browser ↔ UI and API.** Users, and anyone on the internet who can reach
   them.
2. **Log shippers ↔ ingest.** API keys; the contents of a log are attacker
   controlled.
3. **API ↔ IdPs, ticket systems, chat, LLM providers.** Outbound calls, and
   webhooks coming in.
4. **API ↔ ClickHouse, Redpanda, Redis, object storage.** Inside the
   deployment.
5. **Tenant ↔ tenant.** The same API, database and caches.

### Threats and what stands against them (STRIDE)

- **Spoofing**
  - ID tokens are checked against the IdP's keys, with issuer, audience,
    expiry and nonce, and public-key algorithms only.
  - PKCE and a signed state cookie.
  - SCIM and ingest tokens are hashed and tenant scoped.
  - Webhooks are HMAC-signed.
  - An IdP can't sign in as another tenant's user.
- **Tampering**
  - LogforgeQL compiles to parameterised SQL with the tenant and time window
    in the innermost SELECT.
  - Templates can't reach Python internals, and a log value can't inject a
    template.
  - Data scope service names are escaped literals.
- **Repudiation**
  - The audit log records case actions, approvals (who and when), AI
    prompts, responses and tool calls, playbook decisions and role changes.
- **Information disclosure**
  - The tenant filter is on every query.
  - Data scopes are enforced by ClickHouse; caches are keyed by tenant and
    scope.
  - Secrets are write-only in every API.
  - Redaction runs before anything reaches an LLM.
  - Integrations may not call private addresses unless allowed.
  - The user list is tenant scoped (Phase 14 fixed a cross-tenant listing).
  - `/metrics` is unauthenticated: keep it on the internal network.
- **Denial of service**
  - Request size limits and query cost limits (`EXPLAIN ESTIMATE`).
  - Rate limits and token budgets for AI.
  - Bounded joins and lookups.
  - The UIs' Next.js Server Components DoS advisories (above) remain until
    the upgrade.
- **Elevation of privilege**
  - Containment needs a person's approval, checked against roles.
  - Custom roles can't grant platform permissions.
  - SSO and SCIM can't grant platform roles.
  - Failing to read custom roles fails closed (503).

### Known gaps

- **API key scopes** aren't enforced: a key acts with its creator's roles.
- **Data scopes** don't cover traces, metrics, alerts or archive search
  (refused), and there's no field-level masking.
- **Sign-in:** no SAML, and MFA enrollment exists but isn't enforced at
  sign-in.
- **`/metrics`** has no authentication.
- **Prompt injection** from log content is mitigated (tools are read-only and
  answers are cited), not prevented.
- **Next.js 14:** the UIs run it until the Next.js 15 migration.
