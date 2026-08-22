-- ENH-021: reconcile the two conflicting definitions of security_events_mt.
--
-- THE PROBLEM
-- Two different CREATE TABLE statements existed for the same table:
--
--   init_simple.sql:636               migrations/003_seed_mitre_rules.sql:40
--     raw_log_data      String          artifact_data      String
--     enrichment_data   String          matched_fields     String
--     mitre_techniques  Array(String)   attack_techniques  Array(String)
--     artifacts         Array(String)   kill_chain_phases  Array(String)
--     event_type  Enum8('detection'..)  event_type         String
--     status      Enum8('new'..)        status       Enum8('open'..)
--
-- Both use CREATE TABLE IF NOT EXISTS, so whichever ran first won and the other
-- silently did nothing. A deployment's actual schema therefore depended on
-- execution order.
--
-- THE DECISION
-- `init_simple.sql` is authoritative. Two reasons:
--   1. It is the only file infra/docker/compose.yml mounts (line 13), so it is
--      what real deployments have.
--   2. It is the shape apps/api/dao/security_dao.py reads and writes -- the
--      main security event path.
-- Application code that used the migration-003 shape
-- (events/management/processors/sigma_processor.py) has been corrected to match.
--
-- THIS MIGRATION IS NON-DESTRUCTIVE.
-- It only ADDs columns, and only if they are missing. It drops nothing and
-- rewrites no data, so it is safe on a deployment of either shape:
--   * On an init_simple.sql table: every ADD is a no-op (columns exist).
--   * On a migration-003 table: the missing columns are added, so the
--     application's queries resolve instead of failing on unknown columns.
--
-- Legacy columns from migration 003 are deliberately LEFT IN PLACE. Dropping
-- them would destroy data on any deployment that used that shape, and they are
-- harmless once unused. Removing them is a separate, explicitly-approved
-- cleanup once no deployment is on the old shape.

ALTER TABLE security_events_mt
    ADD COLUMN IF NOT EXISTS raw_log_data String DEFAULT '';

ALTER TABLE security_events_mt
    ADD COLUMN IF NOT EXISTS enrichment_data String DEFAULT '';

ALTER TABLE security_events_mt
    ADD COLUMN IF NOT EXISTS mitre_techniques Array(String);

ALTER TABLE security_events_mt
    ADD COLUMN IF NOT EXISTS assigned_to Nullable(String);

ALTER TABLE security_events_mt
    ADD COLUMN IF NOT EXISTS investigation_notes Array(String);

ALTER TABLE security_events_mt
    ADD COLUMN IF NOT EXISTS artifacts Array(String);
