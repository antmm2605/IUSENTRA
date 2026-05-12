CREATE TABLE IF NOT EXISTS notifications (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    type TEXT NOT NULL,
    priority TEXT NOT NULL CHECK (priority IN ('normal', 'important', 'urgent')),
    title TEXT NOT NULL,
    body TEXT NOT NULL,
    href TEXT NOT NULL DEFAULT '',
    source_type TEXT NOT NULL DEFAULT '',
    source_id TEXT NOT NULL DEFAULT '',
    dedupe_key TEXT NOT NULL,
    created_at TEXT NOT NULL,
    read_at TEXT NOT NULL DEFAULT '',
    expires_at TEXT NOT NULL DEFAULT '',
    payload_json TEXT NOT NULL DEFAULT '{}'
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_notifications_dedupe
    ON notifications(tenant_id, user_id, dedupe_key);

CREATE INDEX IF NOT EXISTS idx_notifications_user_created
    ON notifications(tenant_id, user_id, created_at);

CREATE INDEX IF NOT EXISTS idx_notifications_user_read
    ON notifications(tenant_id, user_id, read_at);

CREATE TABLE IF NOT EXISTS push_subscriptions (
    id TEXT PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    p256dh TEXT NOT NULL,
    auth TEXT NOT NULL,
    user_agent TEXT NOT NULL DEFAULT '',
    device_label TEXT NOT NULL DEFAULT '',
    enabled INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    last_seen_at TEXT NOT NULL,
    revoked_at TEXT NOT NULL DEFAULT ''
);

CREATE UNIQUE INDEX IF NOT EXISTS idx_push_subscriptions_endpoint
    ON push_subscriptions(tenant_id, user_id, endpoint);

CREATE INDEX IF NOT EXISTS idx_push_subscriptions_active
    ON push_subscriptions(tenant_id, user_id, enabled, revoked_at);

CREATE TABLE IF NOT EXISTS notification_preferences (
    tenant_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    push_enabled INTEGER NOT NULL DEFAULT 1,
    notify_urgent INTEGER NOT NULL DEFAULT 1,
    notify_important INTEGER NOT NULL DEFAULT 1,
    notify_normal INTEGER NOT NULL DEFAULT 0,
    quiet_hours_enabled INTEGER NOT NULL DEFAULT 0,
    quiet_hours_start TEXT NOT NULL DEFAULT '22:00',
    quiet_hours_end TEXT NOT NULL DEFAULT '07:00',
    updated_at TEXT NOT NULL,
    PRIMARY KEY (tenant_id, user_id)
);

CREATE TABLE IF NOT EXISTS notification_deliveries (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT NOT NULL,
    user_id TEXT NOT NULL,
    notification_id TEXT NOT NULL,
    channel TEXT NOT NULL,
    status TEXT NOT NULL,
    detail TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL,
    FOREIGN KEY (notification_id) REFERENCES notifications(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_notification_deliveries_notification
    ON notification_deliveries(tenant_id, user_id, notification_id, channel, created_at);
