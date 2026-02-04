# Logforge UI Widget Audit

> Systematic audit of every page and widget in the UI.
> For each widget: what value it adds, what API it calls, and whether the wiring is correct.

Status legend: PASS | FAIL | PARTIAL | DEAD-END (API exists but service not implemented)

---

## Audit Order (by user-facing priority)

| # | Page | Widgets | Status |
|---|------|---------|--------|
| 1 | `/centrum` | 6 | pending |
| 2 | `/observability/logs` | 4 | pending |
| 3 | `/observability/metrics` | 2 | pending |
| 4 | `/observability/traces` | 2 | pending |
| 5 | `/observability/apm` | 5 | pending |
| 6 | `/observability/service-map` | 1 | pending |
| 7 | `/alerts/rules` | 3 | pending |
| 8 | `/alerts/instances` | 3 | pending |
| 9 | `/alerts/channels` | 2 | pending |
| 10 | `/security/siem` | 4 | pending |
| 11 | `/security/events` | 4 | pending |
| 12 | `/security/rules` | 4 | pending |
| 13 | `/security/threat-hunting` | 5 | pending |
| 14 | `/security/threat-intel` | 4 | pending |
| 15 | `/ai/investigations` | 6 | pending |
| 16 | `/ai/ml-models` | 6 | pending |
| 17 | `/ai/predictive-analytics` | 5 | pending |
| 18 | `/ai/alert-correlation` | 5 | pending |
| 19 | `/dashboards` | 2 | pending |
| 20 | `/dashboards/system` | 5 | pending |
| 21 | `/settings/compliance` | 5 | pending |
| 22 | `/settings/costs` | 5 | pending |
| 23 | `/settings/integrations` | 4 | pending |
| 24 | `/settings/roles` | 5 | pending |

**Total: 24 auditable pages, ~120 widgets**

---

## Audit Results

*(to be filled in as each page is audited)*
