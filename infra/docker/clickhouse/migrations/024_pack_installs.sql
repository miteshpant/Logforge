-- Migration 024: source pack installs (Phase 7)
--
-- One row per install, upgrade or removal of a pack for a tenant; the
-- current state is the latest row (ORDER BY ... seq DESC LIMIT 1 BY pack_id),
-- and a removal is a row with removed = 1. objects holds the manifest:
-- {"kind:key": {"pack_hash", "installed_hash", "ref"}}, which the pack
-- manager uses to tell the tenant's own changes from the pack's.

CREATE TABLE IF NOT EXISTS pack_installs_mt
(
    tenant_id String,
    pack_id String,
    seq UInt64,
    version String,
    objects String,
    removed UInt8 DEFAULT 0,
    installed_at DateTime64(3, 'UTC'),
    installed_by String
)
ENGINE = MergeTree
ORDER BY (tenant_id, pack_id, seq);
