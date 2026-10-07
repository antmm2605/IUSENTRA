-- Catalogo posta: solo struttura, nessun import di dati storici.
CREATE TABLE IF NOT EXISTS email_mailbox_records (
        tenant_key TEXT NOT NULL, mailbox_kind TEXT NOT NULL,
        message_key TEXT NOT NULL, folder TEXT NOT NULL, read_state TEXT NOT NULL,
        message_date TEXT NOT NULL, payload_json TEXT NOT NULL, updated_at TEXT NOT NULL,
        PRIMARY KEY (tenant_key,mailbox_kind,message_key));

CREATE INDEX IF NOT EXISTS idx_email_mailbox_folder_state
        ON email_mailbox_records (tenant_key,mailbox_kind,folder,read_state);

CREATE TABLE IF NOT EXISTS email_mailbox_bootstrap (
        tenant_key TEXT NOT NULL, mailbox_kind TEXT NOT NULL,
        source_of_truth TEXT NOT NULL, initialized_at TEXT NOT NULL,
        PRIMARY KEY (tenant_key,mailbox_kind));

CREATE TABLE IF NOT EXISTS email_mailbox_audit (
        audit_key TEXT PRIMARY KEY, tenant_key TEXT NOT NULL,
        mailbox_kind TEXT NOT NULL, message_key TEXT NOT NULL,
        action TEXT NOT NULL, actor_key TEXT NOT NULL,
        changed_fields_json TEXT NOT NULL, created_at TEXT NOT NULL);
