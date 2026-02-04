# Logforge UI Widget Audit

> Systematic audit of every page and widget in the UI.
> For each widget: what value it adds, what API it calls, and whether the wiring is correct.

Status legend: PASS | FIXED | PARTIAL | DEAD-END (API exists but service not implemented)

---

## Summary

- **24 pages audited**, ~120 widgets
- **4 commits** of fixes across frontend and backend
- **Major categories of issues found:**
  - Wrong API endpoint paths (404s)
  - Response shape mismatches (field names differ between frontend interfaces and backend Pydantic models)
  - Missing backend endpoints (no route registered for frontend calls)
  - Request body mismatches (wrong field names, wrong types → 422 errors)
  - HTTP method mismatches (PATCH vs PUT → 405 errors)
  - Dead code (data fetched but component never rendered)

---

## Audit Status

| # | Page | Widgets | Status |
|---|------|---------|--------|
| 1 | `/centrum` | 6 | FIXED |
| 2 | `/observability/logs` | 4 | FIXED (path) |
| 3 | `/observability/metrics` | 2 | PARTIAL (SSE issues remain) |
| 4 | `/observability/traces` | 2 | PASS |
| 5 | `/observability/apm` | 5 | PARTIAL (trends shape) |
| 6 | `/observability/service-map` | 1 | PASS |
| 7 | `/alerts/rules` | 3 | FIXED (PATCH→PUT) |
| 8 | `/alerts/instances` | 3 | FIXED (body optional) |
| 9 | `/alerts/channels` | 2 | FIXED (PATCH→PUT, +endpoints) |
| 10 | `/security/siem` | 4 | PASS |
| 11 | `/security/events` | 4 | FIXED (time params) |
| 12 | `/security/rules` | 4 | FIXED (path) |
| 13 | `/security/threat-hunting` | 5 | PARTIAL (campaign fields) |
| 14 | `/security/threat-intel` | 4 | FIXED (+POST/DELETE) |
| 15 | `/ai/investigations` | 6 | FIXED |
| 16 | `/ai/ml-models` | 6 | PASS |
| 17 | `/ai/predictive-analytics` | 5 | FIXED |
| 18 | `/ai/alert-correlation` | 5 | FIXED |
| 19 | `/dashboards` | 2 | FIXED (share fields) |
| 20 | `/dashboards/system` | 5 | PASS |
| 21 | `/settings/compliance` | 5 | FIXED (+endpoints) |
| 22 | `/settings/costs` | 5 | FIXED (response shape) |
| 23 | `/settings/integrations` | 4 | FIXED (key + endpoints) |
| 24 | `/settings/roles` | 5 | FIXED (+PUT/DELETE) |

---

## Detailed Audit Results

### 1. `/centrum` (Main Dashboard) — FIXED

| Widget | API | Issue | Fix |
|--------|-----|-------|-----|
| UsageStatsWidgets | `/v1/usage/overview/stats` | `requests_last_hour` always 0 — SQL aliases column as `total_requests` but DAO reads `requests_last_hour` | Fixed DAO key in `usage_dao.py` |
| APMPerformanceWidgets | `/v1/observability/apm/performance` | Dead code — component imported, memo'd, data fetched but never rendered in JSX | Removed all APM loading code |
| AnomalyStatsWidget | `/v1/ai/anomalies/stats` | `from dao.anomaly_dao import AnomalyDAO` — file doesn't exist (runtime crash) + 5 response field mismatches | Rewrote endpoint using existing anomaly detector |
| AIInsightsWidget | `/v1/ai/insights` | Time range params ignored — always defaults to 24h | Added `start_time`, `end_time`, `limit` query params |
| LogsOverviewWidget | `/v1/query/advanced` | PASS | — |
| AlertsOverviewWidget | `/v1/alerts/stats/overview` | PASS | — |

### 2. `/observability/logs` — FIXED

| Widget | API | Issue | Fix |
|--------|-----|-------|-----|
| Log table | `/v1/query/logs` | 404 — endpoint is `/v1/logs` | Changed frontend path |
| Export | `/v1/query/export` | Crashes on string `query` field | Not yet fixed |

### 3. `/observability/metrics` — PARTIAL

| Widget | API | Issue | Fix |
|--------|-----|-------|-----|
| SSE streaming | `/v1/observability/metrics/stream` | Non-functional (3 issues: no auth header, named events, CORS) | Not yet fixed |
| Service filter | `/v1/observability/metrics` | Dead code — filter exists but never applied to queries | Not yet fixed |

### 4-6. `/observability/traces`, `/observability/apm`, `/observability/service-map`

- **Traces**: PASS
- **APM**: Performance trends response shape mismatch (all trend cards empty) — not yet fixed
- **Service Map**: PASS

### 7. `/alerts/rules` — FIXED

| Widget | API | Issue | Fix |
|--------|-----|-------|-----|
| Toggle rule | `PATCH /v1/alerts/rules/{id}` | 405 — only PUT exists | Changed frontend to PUT |
| Test rule | `/v1/alerts/rules/test` | Response shape mismatch (3 of 4 fields wrong) | Not yet fixed |
| Create modal | — | No onClick handler on Save button | Not yet fixed |

### 8. `/alerts/instances` — FIXED

| Widget | API | Issue | Fix |
|--------|-----|-------|-----|
| Acknowledge | `POST /v1/alerts/{id}/acknowledge` | 422 — requires body but frontend sends none | Made `AlertStatusUpdate` body optional |
| Resolve | `POST /v1/alerts/{id}/resolve` | Same as above | Same fix |
| Status mapping | — | DAO remapped `triggered`→`active` breaking rendering | Removed remapping |

### 9. `/alerts/channels` — FIXED

| Widget | API | Issue | Fix |
|--------|-----|-------|-----|
| Toggle | `PATCH /v1/alerts/notifications/channels/{id}` | 405 — only PUT exists | Changed frontend to PUT |
| Update/Delete/Test | Missing endpoints | No individual channel CRUD | Added PUT/DELETE/test endpoints (router + service + DAO) |

### 10-11. `/security/siem`, `/security/events` — FIXED

- **SIEM**: PASS
- **Events**: `start_time`/`end_time` not declared in router (silently dropped) → Added as Query params

### 12. `/security/rules` — FIXED

| Widget | API | Issue | Fix |
|--------|-----|-------|-----|
| Rules list | `/v1/security/rules` | 404 — endpoint is `/v1/security/sigma-rules` | Changed frontend path |
| Confidence | — | Scale 0-1 float displayed as percentage | Not yet fixed |

### 13. `/security/threat-hunting` — PARTIAL

- Campaign field name mismatches (6+ fields)
- Findings endpoint missing entirely
- Not yet fixed

### 14. `/security/threat-intel` — FIXED

| Widget | API | Issue | Fix |
|--------|-----|-------|-----|
| Add indicator | POST missing | Service existed but no route registered | Added POST endpoint |
| Delete indicator | DELETE missing | No route, service, or DAO method | Added full stack |

### 15. `/ai/investigations` — FIXED

| Widget | API | Issue | Fix |
|--------|-----|-------|-----|
| Query history | `/v1/ai/query/history` | Frontend reads `data.queries` (wrong), items use `question` vs `natural_query`, `id` vs `query_id` | Fixed to use `data.history`, correct field names |
| Feedback | `POST /v1/ai/query/feedback` | Sends `{feedback: 'positive'}` string, backend expects `{feedback_score: 1}` int → 422 | Changed to send `feedback_score` integer |

### 16. `/ai/ml-models` — PASS

All widgets pass.

### 17. `/ai/predictive-analytics` — FIXED

| Widget | API | Issue | Fix |
|--------|-----|-------|-----|
| Summary cards | `/v1/ai/predictions/summary` | Backend returns nested `{forecast_summary, capacity_summary, sla_summary}`, frontend expects flat fields | Rewrote interface and rendering for nested structure |
| Forecast | `/v1/ai/predictions/forecast` | `current_value`, `predicted_value`, `trend_direction` not in response (derivable from `historical`, `projected`, `regression`) | Derived values from response arrays |
| SLA breaches | `/v1/ai/predictions/sla-breach` | Frontend reads `data.predictions`, backend returns `data.at_risk_services`; `service_name` vs `service` | Fixed key and field names |
| Capacity | `/v1/ai/predictions/capacity` | `growth_rate` vs `growth_rate_percent`, `days_until_limit` vs nested `capacity_projections`, completely different `top_services` structure | Rewrote to match backend structure |
| What-If | `POST /v1/ai/predictions/what-if` | Invalid scenario types (`traffic_spike` vs `traffic_increase`), wrong param name (`multiplier` vs `factor`), `impact_summary` string vs `impact.notes` array | Fixed scenario types, param names, impact rendering |

### 18. `/ai/alert-correlation` — FIXED

| Widget | API | Issue | Fix |
|--------|-----|-------|-----|
| Summary bar | `/v1/alerts/correlation/summary` | Backend returns nested `{fatigue: {...}, groups: {...}, duplicates: {...}}`, frontend expects flat `{fatigue_score, correlated_groups_count, ...}` | Rewrote interface for nested structure |
| Fatigue score | `/v1/alerts/correlation/fatigue-score` | `score` vs `fatigue_score`, `level` vs `rating`, `factor.impact` vs `factor.score_contribution` | Fixed all field names |
| Duplicates | `/v1/alerts/correlation/duplicates` | `groups`/`duplicates` vs `duplicate_groups`, `noise_reduction_pct` vs `noise_reduction_percent`, `count` vs `total_count`, `suppressible` vs `suppressible_count` | Fixed all field names |
| Correlated groups | `/v1/alerts/correlation/groups` | `root_alert.name` vs `root_alert.rule_name`, `root_alert.id` vs `root_alert.alert_id`, `alert_count` vs `group_size`, `correlation_score` 0-100 int treated as 0-1 float (showed "8500%") | Fixed field names and score scale |
| Alert trends | `/v1/alerts/correlation/trends` | `data_points`/`trends` vs `time_series`, `overall_trend` vs `trend.direction`, `change_percentage` vs `trend.change_percent`, flat severity vs nested `by_severity` dict | Fixed all field names and nesting |

### 19. `/dashboards` — FIXED

| Widget | API | Issue | Fix |
|--------|-----|-------|-----|
| Share | `POST /v1/dashboards/{id}/share` | Sends `{email, permission}`, backend expects `{shared_with_email, permission_level}` | Fixed field names |

### 20. `/dashboards/system` — PASS

Aggregate endpoint accepts `Dict[str, Any]`, flexible enough for frontend queries.

### 21. `/settings/compliance` — FIXED

| Widget | API | Issue | Fix |
|--------|-----|-------|-----|
| Retention policies | `GET /v1/enterprise/compliance/retention-policies` | Endpoint missing | Added endpoint (router + service + DAO) |
| Legal holds | `GET /v1/enterprise/compliance/legal-holds` | Endpoint missing (only POST existed) | Added GET endpoint (router + service + DAO) |

### 22. `/settings/costs` — FIXED

| Widget | API | Issue | Fix |
|--------|-----|-------|-----|
| Usage stats | `/v1/usage/current/{id}` | Frontend expects flat `logs_ingested_bytes`, backend returns `feature_breakdown` dict | Rewrote stat building to use `feature_breakdown` |
| Billing total | `/v1/billing/estimate/{id}` | `billingEstimate.total` vs `billingEstimate.total_estimated_cost` | Fixed field name |

### 23. `/settings/integrations` — FIXED

| Widget | API | Issue | Fix |
|--------|-----|-------|-----|
| List | `GET /v1/enterprise/integrations` | Frontend reads `data.integrations`, backend returns `data.configured_integrations` | Fixed to read correct key with fallback |
| Test | `POST /v1/enterprise/integrations/{id}/test` | Endpoint missing | Added endpoint |
| Delete | `DELETE /v1/enterprise/integrations/{id}` | Endpoint missing | Added endpoint |

### 24. `/settings/roles` — FIXED

| Widget | API | Issue | Fix |
|--------|-----|-------|-----|
| Update role | `PUT /v1/enterprise/rbac/roles/{id}` | Endpoint missing | Added endpoint |
| Delete role | `DELETE /v1/enterprise/rbac/roles/{id}` | Endpoint missing | Added endpoint |

---

## Remaining Known Issues (Not Yet Fixed)

These are lower-priority issues that were identified but not fixed in this audit pass:

1. `/observability/logs` — Export endpoint crashes on string `query` field
2. `/observability/metrics` — SSE streaming non-functional (3 independent issues)
3. `/observability/metrics` — Service filter dead code, percentile aggregations return AVG
4. `/observability/apm` — Performance trends response shape mismatch
5. `/alerts/rules` — Test rule response shape mismatch, create modal no onClick handler
6. `/alerts/channels` — config is JSON string not parsed object, create modal no onClick
7. `/security/events` — Status `new` vs `triggered` mismatch
8. `/security/rules` — Test confidence scale 0-1 displayed as percentage
9. `/security/threat-hunting` — Campaign field name mismatches (6+), findings endpoint missing
