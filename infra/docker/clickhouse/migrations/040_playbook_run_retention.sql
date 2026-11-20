-- Keep playbook run history 400 days instead of 180: long enough for an annual
-- audit period (SOC 2 Type II, ISO 27001) with a margin. The runs are the
-- record of what automation did and who approved containment.
ALTER TABLE playbook_runs_mt MODIFY TTL toDateTime(created_at) + INTERVAL 400 DAY;
