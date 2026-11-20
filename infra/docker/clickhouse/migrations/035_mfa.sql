-- MFA (TOTP) per user: the secret sealed with LOGFORGE_SECRETS_KEY, whether
-- it's confirmed, hashed one-time backup codes, and the last time step used
-- (so a code can't be replayed). Latest version per user wins.

CREATE TABLE IF NOT EXISTS user_mfa_mt
(
    user_id String,
    secret String,
    confirmed UInt8,
    backup_hashes Array(String),
    last_step UInt64,
    deleted UInt8 DEFAULT 0,
    updated_at DateTime64(3, 'UTC') DEFAULT now64()
)
ENGINE = ReplacingMergeTree(updated_at)
ORDER BY user_id;
