# AI

Logforge can answer questions about a tenant's own logs, alerts, cases and
threat intelligence with a language model, and **cites every source**.
AI is **off by default**: a deployment has to enable it and offer a
provider, and each tenant has to opt in. With AI off, questions get the
rule-based answer. It checks the permission each kind of question needs
(`logs:read`, `alerts:read`, `security:read`, `observability:read` for
latency), binds every value as a query parameter, and isn't available to
users whose role carries a data scope (the tables it reads aren't scoped).

![AI answer with citations](images/ai-answer.png)

<sub>The screenshot shows an answer from a scripted test stand-in running
in the deployment, not from a real model.</sub>

## Turning it on

1. **The deployment** lists the providers tenants may choose from in
   `apps/api/config/ai.yml` and sets `enabled: true`. API keys are never in
   the file; each provider names the environment variable that holds its
   key.

    ```yaml
    enabled: true
    providers:
      claude:
        kind: anthropic            # Claude, through the official SDK
        model: claude-opus-5-5
        api_key_env: ANTHROPIC_API_KEY
        label: Claude (Anthropic)
      gateway:
        kind: openai_compatible    # vLLM, LM Studio, LiteLLM, hosted gateways
        base_url: https://llm-gateway.internal/v1
        model: my-model
        api_key_env: LLM_GATEWAY_KEY
        external: false            # runs inside your network
      local:
        kind: ollama
        base_url: http://ollama:11434
        model: llama3.1
    ```

    `LOGFORGE_AI_ENABLED=false` switches AI off whatever the file says (the
    environment can't switch it on). `ollama` providers default to
    `external: false`; set `external: true` if yours runs outside your
    network, so users are told. `external` (true by default for hosted
    kinds) is shown to users with every answer. The Anthropic adapter turns
    on server-side refusal fallbacks by default (`fallbacks: false` turns
    them off) and takes an optional `effort`.

2. **A tenant admin** opens **Settings → AI**, ticks *Use AI for this
   tenant* and chooses a provider. The page warns when the provider is
   external.

Removing a provider from `ai.yml` turns AI off for the tenants that chose it.

## What happens when someone asks

```
question ──redact──▶ provider ──▶ "run_query(...)"         (tool call)
                                     │  runs as the person asking:
                                     │  their roles, their tenant
                                     ▼
            provider ◀──redact── result, each item tagged C1, C2 ...
                │
                ▼
answer "... [C1] ... [C2]"  ──▶ citations checked ──▶ shown with links and flags
every step ──▶ audit log (what was actually sent, after redaction)
```

* **Models see data only through read-only tools:** `run_query`
  (LogforgeQL, at most 50 rows), `get_alert`, `get_case` and
  `lookup_indicator`. Bulk logs are never handed to a model.
* **Each tool call is authorised like the HTTP request it stands for**
  (`run_query` as `POST /v1/query/logql`, the others as security reads),
  with the asking person's roles, in their tenant, using the middleware's
  own permission functions. A model can't read anything the person couldn't.
  A denied call goes back to the model as an error.
* **Citations:** every item a tool returns gets an id. The model has to put
  the ids after the sentences that use them; each id links to the event,
  alert, case, indicator or query it names. Answers with uncited sentences,
  citations no tool issued, or no citations at all are **flagged** and not
  marked as grounded.
* **Prompt injection:** log lines can contain text written by an attacker.
  The system prompt tells the model to treat tool results as data, and the
  tools can only read, as the person asking. An injected instruction can
  still distort an answer (even one that cites real sources), make the
  model run lookups the person didn't ask for, or spend the budget, which
  is why answers carry their sources and every step is audited. Answers
  are shown as plain text, and citation links are built by the server, so
  they always point inside Logforge.
* **Links:** a Log Explorer link opened from Logforge (an AI citation) runs
  its query; one opened from another site only fills it in.

## Data controls

* **Redaction** happens before anything leaves for a provider: the question,
  every tool result and every tool error, before long values are cut.
  * **Field names:** `password`, `token`, `authorization`, `cookie`,
    `api_key`, `ssn` and others from `ai.yml`, plus fields a tenant adds.
    Matches are case-insensitive, on any word of the key (`db_password`,
    `password_hash`, `sessionid`), or the end of a dotted path
    (`attrs.customer_email`, at any depth). A query that names a field the
    tenant added, or one the asker's role masks, is refused by `run_query`,
    since a renamed value (`| eval v = attrs.secret`) would no longer match
    by name.
  * **Secret-looking values anywhere in text:** `password=`, `"password":`,
    `access_token=` and "password is ..." pairs, bearer and basic
    credentials, cookies, credentials in URLs, private keys (even cut
    short), JWTs, and AWS, GitHub, GitLab, Slack and `sk-` keys.
  * **Not covered:** a value renamed by a query (`| eval v = attrs.password`)
    is no longer recognised by its field name; only the text patterns apply
    to it.
* **Opt-in per tenant** and a **global switch**, both checked on every
  request.
* **Visible indicator:** every answer says *External model: ...*,
  *Model in this deployment: ...* or *No model: rule-based answer*.

## Audit and cost

* **Audit log:** every prompt, response, tool call, tool result and error
  is written to `ai_audit_mt`, exactly as sent to the provider (after
  redaction), with the user, provider, model and token counts. Rows are
  kept for `audit_retention_days` (90 by default). Tenant admins read it
  under **Settings → AI** or at `GET /v1/ai/audit`.
* **Budgets:**
  * **Monthly token budget:** checked before a request and before every
    model call within it.
  * **Requests-per-minute limit:** a tenant admin can lower both, never
    raise them.
  * **Over a limit:** the request gets HTTP 429.
  * **Per request:** at most `max_request_tokens` tokens in all (200,000),
    `max_tool_calls` lookups and `max_tokens` tokens per reply; tool results
    are capped at 50 rows and 30,000 characters.
  * **Concurrency:** before every model call the request's usage is written
    and the month's usage re-read, so parallel requests can overshoot the
    budget by at most one model call each. The rate limit is one counter
    per tenant and minute in Redis, shared by every API replica (fixed
    one-minute windows, so a burst can straddle two). If Redis can't be
    reached, each process counts on its own and logs a warning.

## Evaluation

Each AI feature is scored against a dataset by the harness in
`tests/eval/ai` ([README](https://github.com/miteshpant/Logforge/blob/main/tests/eval/ai/README.md)).
In CI the features run from recordings of a real model, so there is no
network access and no cost; a feature that scores below its baseline fails
the build. **No recordings are committed yet** (recording needs a model API
key), so the gate currently reports both features as skipped.

## API

| Call | Permission | Does |
|---|---|---|
| `GET /v1/ai/status` | `ai:read` | whether AI is on for the tenant, why not, the provider, `external` |
| `POST /v1/ai/ask` | `ai:read` | a grounded answer (`mode: ai`) or the rule-based one (`mode: rule_based`) |
| `GET /v1/ai/usage` | `ai:read` | tokens and requests this month, the limits |
| `GET /v1/ai/settings` / `PUT` | `settings:read` / `settings:write` (tenant admin) | opt in or out, provider, redacted fields, lower limits |
| `GET /v1/ai/audit` | `settings:read` (tenant admin) | the audit log, optionally for one `request_id` |
| `POST /v1/ai/nl2query` | `ai:read` and `logs:read` | a LogforgeQL draft for a question, explained (`mode: ai` or `rule_based`) |
| `POST /v1/ai/triage` | `ai:read`; evidence read with the caller's own permissions | a cited triage summary of an alert or case (`mode: ai` or `template`) |
| `POST /v1/ai/explain` | `ai:read` and `logs:read` | a cited explanation of one event (`mode: ai` or `template`) |
| `POST /v1/ai/pipeline-draft` | `ai:read` and `logs:write` | a pipeline for sample lines, with its simulation report (`mode: ai` or `heuristic`) |
| `POST /v1/ai/copilot/plan` | `ai:read`; searches run with the caller's own permissions | proposed read-only searches for a case, alert or entity; nothing runs |
| `POST /v1/ai/copilot/run` | `ai:read` | runs the approved steps: cited timeline, root-cause candidates, hypotheses, next steps (`mode: ai` or `template`) |
| `POST /v1/ai/rule-draft` | `ai:read` and `security:write` | a Sigma rule with fixtures, tested; nothing saved (`mode: ai` or `heuristic`) |
| `POST /v1/ai/rule-draft/enable` | `ai:read` and `security:write` | re-checks a draft, backtests it, enables it; refuses (409) anything that fails |
| `POST /v1/ai/case-report` | `ai:read`; the case is read with the caller's own permissions | a management summary or post-incident review, cited, with Markdown |
| `DELETE /v1/security/cases/{id}/evidence/{pin}` | `security:write` | takes back a pin (it stays in the timeline, marked) |

Tenant admins, security analysts and DevOps engineers have `ai:read`.

## Features (Phase 9)

Each feature works with AI off, with less capability, and says which way an
answer was made: the model (and whether it is external), or the fallback
and why. Every model call is audited, budgeted and redacted as above.

| Feature | Where | With AI | With AI off |
|---|---|---|---|
| Ask in plain English | Log Explorer | the model drafts LogforgeQL from the question and the tenant's field catalogue (names, types, redacted example values; never log data); it must compile, with one repair round, and fields the catalogue hasn't seen are flagged | a rule-based translator for common shapes: time windows, levels, services, seen values, IPs, status classes, counts by a field, top values, trends, latest lines |
| Triage summary | Security events, case detail | the model writes the five sections from the evidence | each sentence built from one evidence item |
| Explain this event | Log Explorer, Explain on any row | the model writes what it is, why it matters and what to look at next, and suggests queries | reference entries, matching rules and intel, by template |
| Draft pipeline from samples | Pipeline editor | the model writes the pipeline, simulated on the samples, one repair round with the failures | candidate parsers simulated, the best kept |

The query a draft produces, not the model, produces the answer: the user
sees it and runs or edits it. Pipeline drafts are never saved by the
feature; they fill the editor.

**Triage** gathers its evidence through the assistant's tools, as the person
asking: the alert (or the case and its alerts), each entity's activity over
the last 24 hours (source and destination IP, user, host: by the fields
that hold them and in the message), and threat intelligence for its
addresses. Sections: what happened, ATT&CK context, entities, related
activity, next steps. A related lookup the caller may not make is skipped
and flagged.

**Explain** cites the event, reference entries (Windows and Sysmon event
IDs, auditd record types, sshd, sudo, cron, systemd and nginx messages,
HTTP statuses, OCSF classes), the shipped detection rules the event matches
(`packages/rules` and the content packs, evaluated with the detection
engine's matcher) and threat intelligence. Field meanings come from the
reference and are shown as a table.

**Citations, without exceptions:** in triage and explanations, a sentence
the model writes without a citation, or citing an id that wasn't issued,
is removed (and counted in `dropped`); if nothing cited is left, the
template is used. So no uncited claim reaches the analyst.

**Pipeline drafts** keep events they can't parse: the pipeline's
`on_failure` records the error in `attrs.parse_error` instead of
dead-lettering the event.

### Evaluation numbers

Measured on 2026-11-20 ([details](https://github.com/miteshpant/Logforge/blob/main/tests/eval/ai/README.md)).
The model column is empty because no model's answers are recorded yet
(recording needs an API key); each has a recorder script and a CI test that
scores the recording once it is committed.

| Feature | Set | Target | AI off (fallback) | Model |
|---|---|---|---|---|
| Ask in plain English | execution accuracy on 242 / 214 / 205 question-query pairs (auth, http, dns) | ≥ 85% | 0.4% / 9.8% / 11.2% | not recorded |
| Triage summary | 20 alerts and cases | 0 uncited claims | 0 uncited, 100% of required facts | not recorded (0 uncited by construction) |
| Pipeline draft | 14 held-out pack sample files, 85 lines | fields correctly extracted | 100% of lines parsed, 91.4% of recoverable values | not recorded |
| Explain this event | 83 pack sample events | (none set) | 0 uncited, 90.4% identified, 100% of expected rules named | not recorded |

The plain-English fallback is far below the target: without a model it
can't know which field holds what in a schema (that a sign-in is
`attrs.outcome` in the auth services). The target is for the model. The
triage set has no analyst ratings yet; the roadmap asks for analyst-rated
helpfulness and accuracy, which needs people.

## Investigation and authoring (Phase 10)

**Investigation copilot** (case detail; `POST /v1/ai/copilot/plan`, `/run`).
From a case, an alert or an entity (address, user, host, optionally at a
time), it proposes read-only searches around the anchor (the alert's time):
what else an address touched and its events, what happened on a host in the
six hours before, what a user did. The analyst keeps, drops or edits them,
then runs them; each runs through the assistant's tool as the analyst.
Events become a timeline, each a citation. Signals score them: a shipped
detection rule matches (weighted by its level), a login succeeds after
failures from the same source, an account is created or made admin,
credential dumping, logs or backups destroyed, an obfuscated or
reverse-shell command, a web shell, a download to /tmp, persistence. The
earliest strong signals are the root-cause candidates; the first of a burst
of failures is a lead when nothing stronger is found. Entities in
suspicious events become proposed next searches. With AI the model writes
the hypotheses, root cause and next steps; a root cause that isn't a fetched
event, or a sentence that cites nothing, is dropped. Nothing is written by
the copilot: pinning an event and recording a conclusion are the analyst's
buttons, and a pin can be taken back.

**Detection drafting** (Detection Rules → Draft a rule; `POST /v1/ai/rule-draft`).
"AI drafts, the gate verifies." From a description, the technique, attack
events and one known-good event, a Sigma rule with fixtures is drafted. It
passes only when the Phase 1 fixture gate accepts it, it fires on every
attack sample and not on the known-good one; two attempts, the second told
why the first failed. Without AI the rule comes from what the samples share
(fields with one value; tokens and word pairs every sample has and the
known-good one doesn't; a common domain suffix). Enabling
(`/rule-draft/enable`) checks everything again and backtests the rule over
the tenant's stored logs against a ceiling of alerts per day; a rule that
fails is refused and nothing is written, so no draft is enabled without
passing.

**Case reports** (case detail → Report; `POST /v1/ai/case-report`): a
summary for management (summary, impact, status) or a post-incident review
(detection, response times, findings, actions), every sentence citing the
case, an alert or a timeline entry, downloadable as Markdown.

**Grounded RCA** (`/v1/ai/analyze-incident`, `/v1/ai/investigate`): the
statistical engine's result stays the input; its findings become citations
and one search corroborates the root cause (the service's errors in the 30
minutes around it). The response's `analysis` is the cited statistical
reading without AI, or the model's with a provider, whose root cause and
recommendations then replace the heuristic text (the originals stay under
`statistical`).

### Evaluation numbers (Phase 10)

Measured on 2026-11-20 ([details](https://github.com/miteshpant/Logforge/blob/main/tests/eval/ai/README.md)).
No model's answers are recorded yet; each has a recorder and a CI test.

| Feature | Set | Target | AI off | Model |
|---|---|---|---|---|
| Investigation copilot | 20 seeded scenarios, live ClickHouse | root cause found in >= 80%, no fabricated evidence | found 90%, first 80%, 0 fabricated | not recorded (0 fabricated by construction) |
| Detection drafting | 20 behaviours, 17 techniques | >= 70% pass the gate within 2 attempts; 0% enabled without passing | 90% pass (all first attempt); held-out recall 88.9%, quiet 100%; enabling re-checks and refuses failing drafts | not recorded |

The scenarios and behaviours were written alongside the copilot's signals
and the drafter, so they show the methods work, not how they do on attacks
nobody anticipated.

## Security review

An independent review of the data flow and tenant isolation (2026-11-19)
found one high, two medium and several low issues. All are fixed, and each
fix has a test; what was found, fixed and left is in the
[platform roadmap](PLATFORM_ROADMAP.md) (Phase 8). A sign-off by your own
security team is still needed before turning AI on in production.
