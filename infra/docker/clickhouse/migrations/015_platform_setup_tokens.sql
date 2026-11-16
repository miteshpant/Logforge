-- Migration 015: persist platform setup tokens
--
-- SetupTokenManager kept bootstrap tokens in process memory, so a token was
-- lost on restart and rejected by any other API replica. Tokens are stored
-- here as SHA-256 hashes (never the token itself), with an expiry and a
-- used_at marker that makes them single-use. Rows are dropped a week after
-- they expire.

CREATE TABLE IF NOT EXISTS platform_setup_tokens_mt
(
    token_hash String,
    created_at DateTime64(3),
    expires_at DateTime64(3),
    used_at Nullable(DateTime64(3))
)
ENGINE = MergeTree
ORDER BY token_hash
TTL toDateTime(expires_at) + INTERVAL 7 DAY;
