# Detection evaluation

Measures what Logforge's shipped detection rules catch, and how noisy they
are, using the same rule set and matching logic as the running platform.

| File | What it is |
|---|---|
| `eval_harness.py` | Builds the default rules with the startup loader (vendored SigmaHQ + `packages/rules/`), runs them over the corpus, and compares with the baseline |
| `benign.py` | Deterministic generator of ordinary activity (2,000 events: logins, sudo, cron, web, process starts, DNS, flows). Any alert on it is a false positive |
| `scenarios/*.yml` | Labelled attack scenarios: the ATT&CK techniques each should be detected as, and its events in Logforge field names |
| `baseline.json` | The committed results that CI compares against |

```bash
python tests/eval/detection/eval_harness.py                    # report + regression check
python tests/eval/detection/eval_harness.py --update-baseline  # record improved results
```

CI (`tests/test_detection_eval_baseline.py`) fails when, compared with the
baseline:

- a scenario stops being detected as a technique it used to be detected as;
- a rule detects fewer scenarios than before, even if another rule still
  covers them, or disappears from the rule set;
- a rule fires on more benign events than before.

Better results are allowed; record them with `--update-baseline` in the same
change.

## Current results

274 rules · 2,000 benign events · 12 scenarios

- **Detected: 10 of 12 scenarios.** Missing techniques: T1105 (certutil and
  PowerShell downloads), T1059.004 (Linux reverse shell), T1569.002 (PsExec
  service execution), T1069.002 (domain group discovery).
- **False positives: 127 (63.5 per 1,000 benign events), all from one rule:**
  `logforge_pe001-privilege-escalation` fires on every successful `sudo`.
  Every other rule raised none.

## Adding a scenario

Write `scenarios/<name>.yml` with `title`, `techniques` (what the activity
*is*, not what the rules happen to catch) and `events`, then run the harness.
A scenario that isn't detected yet is a useful, honest gap; record it with
`--update-baseline`.
