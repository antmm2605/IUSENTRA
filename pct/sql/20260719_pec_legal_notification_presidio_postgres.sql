CREATE TABLE IF NOT EXISTS pec_legal_notification_presidia (
    id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    fascicolo_id TEXT NOT NULL,
    legal_event_id TEXT NOT NULL DEFAULT '',
    source_message_id TEXT NOT NULL,
    source_parsed_version_id TEXT NOT NULL DEFAULT '',
    trigger_type TEXT NOT NULL,
    notification_case TEXT NOT NULL,
    channel TEXT NOT NULL DEFAULT 'pec',
    status TEXT NOT NULL CHECK (status IN (
        'DETECTED','NEEDS_REVIEW','ORIGINAL_TO_ACQUIRE','ORIGINAL_ACQUIRED',
        'NOTIFICATION_CONFIRMED','RECIPIENTS_TO_VERIFY','READY_FOR_RELATA',
        'RELATA_DRAFTED','RELATA_SIGNED','READY_TO_SEND','SENT_WAITING_RAC',
        'RAC_RECEIVED','PARTIAL_DELIVERY','DELIVERY_COMPLETE','DELIVERY_FAILED',
        'PROOF_TO_DEPOSIT','PROOF_DEPOSITED','CLOSED','NOT_REQUIRED','CANCELLED',
        'LEGACY_ASSUMED_HANDLED','LEGACY_REVIEW_REQUIRED'
    )),
    priority TEXT NOT NULL CHECK (priority IN ('P0','P1','P2','P3')),
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (confidence >= 0 AND confidence <= 1),
    human_review_required BOOLEAN NOT NULL DEFAULT FALSE,
    source_effective_at TIMESTAMPTZ,
    explicit_due_at TIMESTAMPTZ,
    rulepack_version TEXT NOT NULL,
    legal_basis_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    detection_reason TEXT NOT NULL DEFAULT '',
    evidence_summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    dedupe_key TEXT NOT NULL,
    notification_instance_key TEXT NOT NULL,
    assigned_user_id TEXT NOT NULL DEFAULT '',
    confirmed_at TIMESTAMPTZ,
    resolved_at TIMESTAMPTZ,
    resolution_code TEXT NOT NULL DEFAULT '',
    resolution_reason TEXT NOT NULL DEFAULT '',
    legacy_policy_id TEXT NOT NULL DEFAULT '',
    legacy_assumed_handled BOOLEAN NOT NULL DEFAULT FALSE,
    proof_deposit_required BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (tenant_id, id),
    UNIQUE (tenant_id, dedupe_key),
    UNIQUE (tenant_id, notification_instance_key)
);

CREATE TABLE IF NOT EXISTS pec_legal_notification_documents (
    id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    presidio_id TEXT NOT NULL,
    identity_key TEXT NOT NULL,
    fascicolo_document_id TEXT NOT NULL DEFAULT '',
    document_role TEXT NOT NULL CHECK (document_role IN (
        'office_pec_copy','portal_original','notified_act','relata','attestation',
        'sent_pec','rac','rdac','delivery_failure','proof_deposit_receipt'
    )),
    document_version TEXT NOT NULL DEFAULT '1',
    outer_sha256 TEXT NOT NULL DEFAULT '',
    content_sha256 TEXT NOT NULL DEFAULT '',
    zip_sha256 TEXT NOT NULL DEFAULT '',
    zip_member_path TEXT NOT NULL DEFAULT '',
    portal_document_id TEXT NOT NULL DEFAULT '',
    portal_reference TEXT NOT NULL DEFAULT '',
    original_filename TEXT NOT NULL DEFAULT '',
    authoritative BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (tenant_id, id),
    UNIQUE (tenant_id, presidio_id, identity_key),
    FOREIGN KEY (tenant_id, presidio_id)
        REFERENCES pec_legal_notification_presidia (tenant_id, id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS pec_legal_notification_recipients (
    id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    presidio_id TEXT NOT NULL,
    recipient_identity_key TEXT NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    fiscal_id TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL DEFAULT '',
    pec_address TEXT NOT NULL DEFAULT '',
    public_register TEXT NOT NULL DEFAULT '',
    public_register_verified_at TIMESTAMPTZ,
    required BOOLEAN NOT NULL DEFAULT TRUE,
    send_status TEXT NOT NULL DEFAULT 'pending' CHECK (send_status IN ('pending','sent','failed')),
    rac_status TEXT NOT NULL DEFAULT 'pending' CHECK (rac_status IN ('pending','received','failed')),
    delivery_status TEXT NOT NULL DEFAULT 'pending' CHECK (delivery_status IN ('pending','delivered','failed')),
    failure_reason TEXT NOT NULL DEFAULT '',
    failure_attribution TEXT NOT NULL DEFAULT '' CHECK (
        failure_attribution IN ('','attributable_to_recipient','not_attributable_to_recipient','uncertain')
    ),
    sent_message_id TEXT NOT NULL DEFAULT '',
    rac_message_id TEXT NOT NULL DEFAULT '',
    rdac_message_id TEXT NOT NULL DEFAULT '',
    failure_message_id TEXT NOT NULL DEFAULT '',
    evidence_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    updated_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (tenant_id, id),
    UNIQUE (tenant_id, presidio_id, id),
    UNIQUE (tenant_id, presidio_id, recipient_identity_key),
    FOREIGN KEY (tenant_id, presidio_id)
        REFERENCES pec_legal_notification_presidia (tenant_id, id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS pec_legal_notification_evidence (
    id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    presidio_id TEXT NOT NULL,
    recipient_id TEXT,
    evidence_key TEXT NOT NULL,
    evidence_type TEXT NOT NULL,
    source_type TEXT NOT NULL,
    source_id TEXT NOT NULL,
    message_id TEXT NOT NULL DEFAULT '',
    eml_sha256 TEXT NOT NULL DEFAULT '',
    attachment_sha256 TEXT NOT NULL DEFAULT '',
    text_excerpt TEXT NOT NULL DEFAULT '',
    source_locator TEXT NOT NULL DEFAULT '',
    confidence DOUBLE PRECISION NOT NULL DEFAULT 0 CHECK (confidence >= 0 AND confidence <= 1),
    created_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (tenant_id, id),
    UNIQUE (tenant_id, presidio_id, evidence_key),
    FOREIGN KEY (tenant_id, presidio_id)
        REFERENCES pec_legal_notification_presidia (tenant_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, presidio_id, recipient_id)
        REFERENCES pec_legal_notification_recipients
            (tenant_id, presidio_id, id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS pec_legal_notification_transitions (
    id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    presidio_id TEXT NOT NULL,
    previous_status TEXT NOT NULL DEFAULT '',
    next_status TEXT NOT NULL,
    actor TEXT NOT NULL,
    chain_index BIGINT NOT NULL CHECK (chain_index > 0),
    reason TEXT NOT NULL DEFAULT '',
    evidence_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    occurred_at TIMESTAMPTZ NOT NULL,
    prev_hash TEXT NOT NULL CHECK (length(prev_hash) = 64),
    entry_hash TEXT NOT NULL CHECK (length(entry_hash) = 64),
    idempotency_key TEXT NOT NULL,
    PRIMARY KEY (tenant_id, id),
    UNIQUE (tenant_id, presidio_id, idempotency_key),
    UNIQUE (tenant_id, presidio_id, chain_index),
    UNIQUE (tenant_id, presidio_id, entry_hash),
    FOREIGN KEY (tenant_id, presidio_id)
        REFERENCES pec_legal_notification_presidia (tenant_id, id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS pec_legal_notification_jobs (
    id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    job_type TEXT NOT NULL CHECK (job_type IN (
        'detect','reconcile_message','reconcile_unmatched','retry','backfill_batch'
    )),
    status TEXT NOT NULL CHECK (status IN ('queued','running','completed','dead')),
    priority INTEGER NOT NULL DEFAULT 0,
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    idempotency_key TEXT NOT NULL,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    max_attempts INTEGER NOT NULL DEFAULT 5 CHECK (max_attempts > 0),
    available_at TIMESTAMPTZ NOT NULL,
    worker_id TEXT NOT NULL DEFAULT '',
    locked_at TIMESTAMPTZ,
    heartbeat_at TIMESTAMPTZ,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    last_error TEXT NOT NULL DEFAULT '',
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    PRIMARY KEY (tenant_id, id),
    UNIQUE (tenant_id, idempotency_key)
);

CREATE TABLE IF NOT EXISTS pec_legal_notification_unmatched_receipts (
    id TEXT NOT NULL,
    tenant_id TEXT NOT NULL,
    receipt_key TEXT NOT NULL,
    receipt_type TEXT NOT NULL CHECK (receipt_type IN (
        'sent','rac','rdac','delivery_failure','proof_deposit_receipt'
    )),
    receipt_message_id TEXT NOT NULL,
    original_message_id TEXT NOT NULL DEFAULT '',
    recipient_identity_key TEXT NOT NULL DEFAULT '',
    payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    status TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','matched','dead')),
    worker_id TEXT NOT NULL DEFAULT '',
    locked_at TIMESTAMPTZ,
    attempts INTEGER NOT NULL DEFAULT 0 CHECK (attempts >= 0),
    matched_presidio_id TEXT,
    matched_recipient_id TEXT,
    created_at TIMESTAMPTZ NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL,
    resolved_at TIMESTAMPTZ,
    PRIMARY KEY (tenant_id, id),
    UNIQUE (tenant_id, receipt_key),
    FOREIGN KEY (tenant_id, matched_presidio_id)
        REFERENCES pec_legal_notification_presidia (tenant_id, id) ON DELETE RESTRICT,
    FOREIGN KEY (tenant_id, matched_presidio_id, matched_recipient_id)
        REFERENCES pec_legal_notification_recipients
            (tenant_id, presidio_id, id) ON DELETE RESTRICT
);

CREATE TABLE IF NOT EXISTS pec_legal_notification_config (
    tenant_id TEXT PRIMARY KEY,
    policy_id TEXT NOT NULL,
    historical_cutoff TIMESTAMPTZ NOT NULL,
    strict_tracking_from TIMESTAMPTZ NOT NULL,
    legacy_declaration TEXT NOT NULL DEFAULT '',
    rulepack_version TEXT NOT NULL DEFAULT '',
    correlation_thresholds_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    backfill_status TEXT NOT NULL DEFAULT 'not_started' CHECK (
        backfill_status IN ('not_started','dry_run','running','completed','failed')
    ),
    backfill_cursor_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    rollout_enabled BOOLEAN NOT NULL DEFAULT FALSE,
    rollout_mode TEXT NOT NULL DEFAULT 'off' CHECK (rollout_mode IN ('off','shadow','primary')),
    version INTEGER NOT NULL DEFAULT 1 CHECK (version > 0),
    updated_by TEXT NOT NULL,
    updated_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_pec_notification_presidia_queue
    ON pec_legal_notification_presidia (tenant_id, status, priority, updated_at, id);
CREATE INDEX IF NOT EXISTS idx_pec_notification_presidia_fascicolo
    ON pec_legal_notification_presidia (tenant_id, fascicolo_id, updated_at, id);
CREATE INDEX IF NOT EXISTS idx_pec_notification_presidia_assignee
    ON pec_legal_notification_presidia (tenant_id, assigned_user_id, updated_at, id);
CREATE INDEX IF NOT EXISTS idx_pec_notification_presidia_channel
    ON pec_legal_notification_presidia (tenant_id, channel, updated_at, id);
CREATE INDEX IF NOT EXISTS idx_pec_notification_presidia_review
    ON pec_legal_notification_presidia (tenant_id, human_review_required, updated_at, id);
CREATE INDEX IF NOT EXISTS idx_pec_notification_presidia_legacy
    ON pec_legal_notification_presidia (tenant_id, legacy_assumed_handled, updated_at, id);
CREATE INDEX IF NOT EXISTS idx_pec_notification_presidia_effective_at
    ON pec_legal_notification_presidia (tenant_id, source_effective_at, updated_at, id);
CREATE INDEX IF NOT EXISTS idx_pec_notification_presidia_source_message
    ON pec_legal_notification_presidia (tenant_id, source_message_id);
CREATE INDEX IF NOT EXISTS idx_pec_notification_documents_content_hash
    ON pec_legal_notification_documents (tenant_id, content_sha256);
CREATE INDEX IF NOT EXISTS idx_pec_notification_documents_portal
    ON pec_legal_notification_documents (tenant_id, portal_document_id);
CREATE INDEX IF NOT EXISTS idx_pec_notification_recipients_pec
    ON pec_legal_notification_recipients (tenant_id, presidio_id, pec_address);
CREATE INDEX IF NOT EXISTS idx_pec_notification_recipients_identity
    ON pec_legal_notification_recipients (tenant_id, recipient_identity_key, presidio_id);
CREATE INDEX IF NOT EXISTS idx_pec_notification_recipients_sent_message
    ON pec_legal_notification_recipients (tenant_id, sent_message_id, pec_address);
CREATE INDEX IF NOT EXISTS idx_pec_notification_recipients_receipts
    ON pec_legal_notification_recipients
       (tenant_id, rac_message_id, rdac_message_id, failure_message_id);
CREATE INDEX IF NOT EXISTS idx_pec_notification_evidence_message
    ON pec_legal_notification_evidence (tenant_id, message_id);
CREATE INDEX IF NOT EXISTS idx_pec_notification_transitions_timeline
    ON pec_legal_notification_transitions (tenant_id, presidio_id, occurred_at, id);
CREATE INDEX IF NOT EXISTS idx_pec_notification_jobs_claim
    ON pec_legal_notification_jobs (tenant_id, status, available_at, priority DESC, id);
CREATE INDEX IF NOT EXISTS idx_pec_notification_unmatched_claim
    ON pec_legal_notification_unmatched_receipts
       (tenant_id, status, original_message_id, recipient_identity_key, created_at, id);

CREATE OR REPLACE FUNCTION guard_pec_legal_notification_transitions_monotonic()
RETURNS TRIGGER AS $$
DECLARE
    expected_index BIGINT;
    expected_hash TEXT;
    expected_status TEXT;
BEGIN
    SELECT chain_index, entry_hash, next_status
    INTO expected_index, expected_hash, expected_status
    FROM pec_legal_notification_transitions
    WHERE tenant_id=NEW.tenant_id AND presidio_id=NEW.presidio_id
    ORDER BY chain_index DESC LIMIT 1 FOR UPDATE;
    expected_index := COALESCE(expected_index, 0) + 1;
    expected_hash := COALESCE(
        expected_hash,
        '0000000000000000000000000000000000000000000000000000000000000000'
    );
    expected_status := COALESCE(expected_status, '');
    IF NEW.chain_index <> expected_index
       OR NEW.prev_hash <> expected_hash
       OR NEW.previous_status <> expected_status THEN
        RAISE EXCEPTION 'transition chain non monotona';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS pec_legal_notification_transitions_monotonic
    ON pec_legal_notification_transitions;
CREATE TRIGGER pec_legal_notification_transitions_monotonic
BEFORE INSERT ON pec_legal_notification_transitions
FOR EACH ROW EXECUTE FUNCTION guard_pec_legal_notification_transitions_monotonic();

CREATE OR REPLACE FUNCTION guard_pec_legal_notification_transitions_append_only()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION 'pec_legal_notification_transitions is append-only';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS pec_legal_notification_transitions_no_update
    ON pec_legal_notification_transitions;
CREATE TRIGGER pec_legal_notification_transitions_no_update
BEFORE UPDATE ON pec_legal_notification_transitions
FOR EACH ROW EXECUTE FUNCTION guard_pec_legal_notification_transitions_append_only();

DROP TRIGGER IF EXISTS pec_legal_notification_transitions_no_delete
    ON pec_legal_notification_transitions;
CREATE TRIGGER pec_legal_notification_transitions_no_delete
BEFORE DELETE ON pec_legal_notification_transitions
FOR EACH ROW EXECUTE FUNCTION guard_pec_legal_notification_transitions_append_only();
