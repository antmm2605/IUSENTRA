-- Shared portable SQLite/PostgreSQL schema. No JSON fallback.
CREATE TABLE IF NOT EXISTS offline_state (
 tenant_key TEXT PRIMARY KEY, revision BIGINT NOT NULL DEFAULT 0
);
CREATE TABLE IF NOT EXISTS offline_devices (
 tenant_key TEXT NOT NULL, device_id TEXT NOT NULL, actor_key TEXT NOT NULL,
 label TEXT NOT NULL, public_key TEXT NOT NULL, fingerprint TEXT NOT NULL,
 status TEXT NOT NULL CHECK(status IN ('pending','approved','revoked')),
 proven BIGINT NOT NULL DEFAULT 0, generation BIGINT NOT NULL DEFAULT 1,
 created_at BIGINT NOT NULL, approved_by TEXT NOT NULL DEFAULT '',
 revoked_by TEXT NOT NULL DEFAULT '', PRIMARY KEY(tenant_key,device_id)
);
CREATE INDEX IF NOT EXISTS offline_devices_actor ON offline_devices(tenant_key,actor_key,status);
CREATE TABLE IF NOT EXISTS offline_challenges (
 tenant_key TEXT NOT NULL, challenge_id TEXT NOT NULL, device_id TEXT NOT NULL,
 actor_key TEXT NOT NULL, message TEXT NOT NULL, purpose TEXT NOT NULL,
 expires_at BIGINT NOT NULL, PRIMARY KEY(tenant_key,challenge_id)
);
CREATE TABLE IF NOT EXISTS offline_notes (
 tenant_key TEXT NOT NULL, actor_key TEXT NOT NULL, note_id TEXT NOT NULL,
 revision BIGINT NOT NULL, deleted BIGINT NOT NULL DEFAULT 0,
 payload_json TEXT NOT NULL, PRIMARY KEY(tenant_key,actor_key,note_id)
);
CREATE INDEX IF NOT EXISTS offline_notes_delta ON offline_notes(tenant_key,actor_key,revision);
CREATE TABLE IF NOT EXISTS offline_commands (
 tenant_key TEXT NOT NULL, device_id TEXT NOT NULL, command_id TEXT NOT NULL,
 request_hash TEXT NOT NULL, result_json TEXT NOT NULL,
 PRIMARY KEY(tenant_key,device_id,command_id)
);
CREATE TABLE IF NOT EXISTS offline_audit (
 tenant_key TEXT NOT NULL, event_id TEXT NOT NULL, actor_key TEXT NOT NULL,
 device_id TEXT NOT NULL, action TEXT NOT NULL, details_json TEXT NOT NULL,
 created_at BIGINT NOT NULL, PRIMARY KEY(tenant_key,event_id)
);
