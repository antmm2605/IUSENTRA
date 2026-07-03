CREATE TABLE IF NOT EXISTS notification_cases (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT,
    fascicolo_id TEXT NOT NULL,
    notification_event_id INTEGER,
    case_uid TEXT NOT NULL UNIQUE,
    case_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    act_document_id TEXT,
    proof_bundle_id TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_nc_fascicolo_id ON notification_cases (fascicolo_id);
CREATE INDEX IF NOT EXISTS idx_nc_tenant ON notification_cases (tenant_id);
CREATE INDEX IF NOT EXISTS idx_nc_event_id ON notification_cases (notification_event_id);
CREATE INDEX IF NOT EXISTS idx_nc_status ON notification_cases (status);

CREATE TABLE IF NOT EXISTS notification_recipients (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT,
    notification_case_id INTEGER NOT NULL,
    notification_event_id INTEGER,
    fascicolo_id TEXT NOT NULL,
    recipient_name TEXT,
    recipient_tax_code TEXT,
    recipient_address TEXT,
    recipient_address_source TEXT,
    address_verified_at TEXT,
    address_source_snapshot_hash TEXT,
    manual_reviewer TEXT,
    recipient_type TEXT NOT NULL DEFAULT 'ALTRO',
    status TEXT NOT NULL DEFAULT 'DRAFT',
    remediation_required INTEGER NOT NULL DEFAULT 0,
    remediation_reason TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_nr_case_id ON notification_recipients (notification_case_id);
CREATE INDEX IF NOT EXISTS idx_nr_event_id ON notification_recipients (notification_event_id);
CREATE INDEX IF NOT EXISTS idx_nr_fascicolo_id ON notification_recipients (fascicolo_id);
CREATE INDEX IF NOT EXISTS idx_nr_status ON notification_recipients (status);
CREATE INDEX IF NOT EXISTS idx_nr_tenant ON notification_recipients (tenant_id);

CREATE TABLE IF NOT EXISTS notification_delivery_attempts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT,
    fascicolo_id TEXT NOT NULL,
    notification_case_id INTEGER NOT NULL,
    recipient_id INTEGER NOT NULL,
    attempt_number INTEGER NOT NULL DEFAULT 1,
    channel TEXT NOT NULL DEFAULT 'PEC',
    status TEXT NOT NULL DEFAULT 'DRAFT',
    started_at TEXT,
    completed_at TEXT,
    error_code TEXT,
    error_message TEXT,
    corrective_action TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_nda_case_id ON notification_delivery_attempts (notification_case_id);
CREATE INDEX IF NOT EXISTS idx_nda_recipient_id ON notification_delivery_attempts (recipient_id);
CREATE INDEX IF NOT EXISTS idx_nda_tenant ON notification_delivery_attempts (tenant_id);

CREATE TABLE IF NOT EXISTS notification_recipient_address_checks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT,
    fascicolo_id TEXT NOT NULL,
    notification_case_id INTEGER NOT NULL,
    recipient_id INTEGER NOT NULL,
    address TEXT NOT NULL,
    address_source TEXT NOT NULL,
    checked_at TEXT NOT NULL,
    source_snapshot_hash TEXT,
    reviewer TEXT,
    status TEXT NOT NULL DEFAULT 'VERIFIED',
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_nrac_recipient_id ON notification_recipient_address_checks (recipient_id);
CREATE INDEX IF NOT EXISTS idx_nrac_case_id ON notification_recipient_address_checks (notification_case_id);
CREATE INDEX IF NOT EXISTS idx_nrac_tenant ON notification_recipient_address_checks (tenant_id);

CREATE TABLE IF NOT EXISTS notification_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT,
    fascicolo_id TEXT NOT NULL,
    notification_case_id INTEGER NOT NULL,
    recipient_id INTEGER,
    direction TEXT NOT NULL,
    channel TEXT NOT NULL,
    message_id TEXT,
    in_reply_to TEXT,
    references_header TEXT,
    sender TEXT,
    recipients_to TEXT NOT NULL DEFAULT '[]',
    recipients_cc TEXT NOT NULL DEFAULT '[]',
    recipients_bcc_hash_only TEXT,
    subject TEXT,
    sent_at TEXT,
    received_at TEXT,
    raw_eml_document_id TEXT,
    raw_msg_document_id TEXT,
    body_hash TEXT,
    attachments_json TEXT NOT NULL DEFAULT '[]',
    parsed_payload_json TEXT NOT NULL DEFAULT '{}',
    parse_status TEXT,
    verification_status TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_nm_case_id ON notification_messages (notification_case_id);
CREATE INDEX IF NOT EXISTS idx_nm_recipient_id ON notification_messages (recipient_id);
CREATE INDEX IF NOT EXISTS idx_nm_message_id ON notification_messages (message_id);
CREATE INDEX IF NOT EXISTS idx_nm_tenant ON notification_messages (tenant_id);

CREATE TABLE IF NOT EXISTS notification_receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT,
    fascicolo_id TEXT NOT NULL,
    notification_case_id INTEGER NOT NULL,
    recipient_id INTEGER NOT NULL,
    pec_message_id INTEGER,
    original_message_id TEXT,
    receipt_message_id TEXT,
    receipt_type TEXT NOT NULL,
    receipt_completeness TEXT NOT NULL DEFAULT 'UNKNOWN',
    sender TEXT,
    recipient TEXT,
    event_time TEXT,
    received_at TEXT,
    provider TEXT,
    raw_eml_document_id TEXT,
    daticert_xml_document_id TEXT,
    original_message_attached_document_id TEXT,
    parsed_payload_json TEXT NOT NULL DEFAULT '{}',
    hash TEXT,
    verification_status TEXT NOT NULL DEFAULT 'NEEDS_REVIEW',
    correlation_status TEXT NOT NULL DEFAULT 'NEEDS_REVIEW',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_nrec_case_id ON notification_receipts (notification_case_id);
CREATE INDEX IF NOT EXISTS idx_nrec_recipient_id ON notification_receipts (recipient_id);
CREATE INDEX IF NOT EXISTS idx_nrec_type ON notification_receipts (receipt_type);
CREATE INDEX IF NOT EXISTS idx_nrec_tenant ON notification_receipts (tenant_id);

CREATE TABLE IF NOT EXISTS notification_relata (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT,
    fascicolo_id TEXT NOT NULL,
    notification_case_id INTEGER NOT NULL,
    recipient_id INTEGER,
    relata_type TEXT NOT NULL,
    document_id TEXT,
    xml_document_id TEXT,
    pdf_document_id TEXT,
    signed_file_document_id TEXT,
    signer_tax_code TEXT,
    signature_status TEXT,
    contains_conformity_attestation INTEGER NOT NULL DEFAULT 0,
    conformity_attestation_id INTEGER,
    related_act_document_id TEXT,
    related_recipient_id INTEGER,
    generated_at TEXT,
    signed_at TEXT,
    verified_at TEXT,
    validation_status TEXT NOT NULL DEFAULT 'NEEDS_REVIEW',
    validation_errors_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_nrel_case_id ON notification_relata (notification_case_id);
CREATE INDEX IF NOT EXISTS idx_nrel_recipient_id ON notification_relata (recipient_id);
CREATE INDEX IF NOT EXISTS idx_nrel_tenant ON notification_relata (tenant_id);

CREATE TABLE IF NOT EXISTS conformity_attestations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT,
    fascicolo_id TEXT NOT NULL,
    notification_case_id INTEGER,
    document_attested_id TEXT,
    attestation_document_id TEXT,
    attestation_mode TEXT NOT NULL,
    description TEXT,
    attested_filename TEXT,
    document_hash TEXT,
    temporal_reference TEXT,
    signer TEXT,
    signature_status TEXT,
    destination TEXT NOT NULL DEFAULT 'NOTIFICA',
    dati_atto_required INTEGER NOT NULL DEFAULT 0,
    dati_atto_inserted INTEGER NOT NULL DEFAULT 0,
    validation_status TEXT NOT NULL DEFAULT 'NEEDS_REVIEW',
    validation_errors_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_ca_case_id ON conformity_attestations (notification_case_id);
CREATE INDEX IF NOT EXISTS idx_ca_tenant ON conformity_attestations (tenant_id);

CREATE TABLE IF NOT EXISTS notification_proof_bundles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT,
    fascicolo_id TEXT NOT NULL,
    notification_case_id INTEGER NOT NULL,
    recipient_id INTEGER,
    bundle_id TEXT NOT NULL UNIQUE,
    bundle_type TEXT NOT NULL,
    required_evidence_json TEXT NOT NULL DEFAULT '[]',
    collected_evidence_json TEXT NOT NULL DEFAULT '[]',
    missing_evidence_json TEXT NOT NULL DEFAULT '[]',
    validation_status TEXT NOT NULL DEFAULT 'DRAFT',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_npb_case_id ON notification_proof_bundles (notification_case_id);
CREATE INDEX IF NOT EXISTS idx_npb_bundle_id ON notification_proof_bundles (bundle_id);
CREATE INDEX IF NOT EXISTS idx_npb_tenant ON notification_proof_bundles (tenant_id);

CREATE TABLE IF NOT EXISTS notification_evidence_links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT,
    fascicolo_id TEXT NOT NULL,
    bundle_id TEXT NOT NULL,
    notification_case_id INTEGER NOT NULL,
    recipient_id INTEGER,
    evidence_document_id INTEGER NOT NULL,
    evidence_role TEXT NOT NULL,
    document_hash TEXT,
    validation_status TEXT NOT NULL DEFAULT 'NEEDS_REVIEW',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_nel_bundle_id ON notification_evidence_links (bundle_id);
CREATE INDEX IF NOT EXISTS idx_nel_case_id ON notification_evidence_links (notification_case_id);
CREATE INDEX IF NOT EXISTS idx_nel_evidence_id ON notification_evidence_links (evidence_document_id);
CREATE INDEX IF NOT EXISTS idx_nel_role ON notification_evidence_links (evidence_role);
CREATE INDEX IF NOT EXISTS idx_nel_tenant ON notification_evidence_links (tenant_id);

CREATE TABLE IF NOT EXISTS notification_proof_deposits (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT,
    fascicolo_id TEXT NOT NULL,
    notification_case_id INTEGER NOT NULL,
    bundle_id TEXT NOT NULL,
    deposit_status TEXT NOT NULL DEFAULT 'DRAFT',
    dati_atto_xml_id TEXT,
    package_document_id TEXT,
    accepted_receipt_document_id TEXT,
    official_outcome_document_id TEXT,
    sent_at TEXT,
    accepted_at TEXT,
    rejected_at TEXT,
    technical_error TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_npd_case_id ON notification_proof_deposits (notification_case_id);
CREATE INDEX IF NOT EXISTS idx_npd_bundle_id ON notification_proof_deposits (bundle_id);
CREATE INDEX IF NOT EXISTS idx_npd_status ON notification_proof_deposits (deposit_status);
CREATE INDEX IF NOT EXISTS idx_npd_tenant ON notification_proof_deposits (tenant_id);

CREATE TABLE IF NOT EXISTS notification_dati_atto_receipt_refs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT,
    deposit_package_id INTEGER,
    notification_case_id INTEGER NOT NULL,
    recipient_id INTEGER NOT NULL,
    receipt_id INTEGER NOT NULL,
    receipt_type TEXT NOT NULL,
    message_id TEXT,
    event_time TEXT,
    recipient_address TEXT,
    source_xml_path TEXT,
    validation_status TEXT NOT NULL DEFAULT 'NEEDS_REVIEW',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_ndar_case_id ON notification_dati_atto_receipt_refs (notification_case_id);
CREATE INDEX IF NOT EXISTS idx_ndar_recipient_id ON notification_dati_atto_receipt_refs (recipient_id);
CREATE INDEX IF NOT EXISTS idx_ndar_receipt_id ON notification_dati_atto_receipt_refs (receipt_id);
CREATE INDEX IF NOT EXISTS idx_ndar_tenant ON notification_dati_atto_receipt_refs (tenant_id);

CREATE TABLE IF NOT EXISTS notification_unep_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT,
    fascicolo_id TEXT NOT NULL,
    notification_case_id INTEGER,
    request_uid TEXT NOT NULL UNIQUE,
    notification_type TEXT NOT NULL,
    unep_office TEXT NOT NULL,
    act_filename TEXT,
    act_hash TEXT,
    request_filename TEXT,
    request_hash TEXT,
    recipient_name TEXT NOT NULL,
    recipient_tax_code TEXT,
    recipient_address_json TEXT NOT NULL DEFAULT '{}',
    recipient_pec TEXT,
    recipient_address_source TEXT,
    precetto_notified_at TEXT,
    fee_due INTEGER NOT NULL DEFAULT 0,
    payment_filename TEXT,
    payment_hash TEXT,
    portal_receipt_document_id TEXT,
    office_return_document_id TEXT,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    source_payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_nur_case_id ON notification_unep_requests (notification_case_id);
CREATE INDEX IF NOT EXISTS idx_nur_fascicolo_id ON notification_unep_requests (fascicolo_id);
CREATE INDEX IF NOT EXISTS idx_nur_status ON notification_unep_requests (status);
CREATE INDEX IF NOT EXISTS idx_nur_tenant ON notification_unep_requests (tenant_id);

CREATE TABLE IF NOT EXISTS notification_non_pec_tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT,
    fascicolo_id TEXT NOT NULL,
    notification_case_id INTEGER,
    track_uid TEXT NOT NULL UNIQUE,
    notification_type TEXT NOT NULL,
    notification_id TEXT NOT NULL,
    recipient_name TEXT NOT NULL,
    recipient_tax_code TEXT,
    act_filename TEXT,
    act_hash TEXT,
    notified_at TEXT NOT NULL,
    registered_mail_number TEXT,
    registered_mail_sent_at TEXT,
    registered_mail_received_at TEXT,
    unep_office TEXT,
    chronological_number TEXT,
    hand_recipient TEXT,
    foreign_country TEXT,
    foreign_authority_or_channel TEXT,
    proof_filename TEXT,
    proof_hash TEXT,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    source_payload_json TEXT NOT NULL DEFAULT '{}',
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_nnpt_case_id ON notification_non_pec_tracks (notification_case_id);
CREATE INDEX IF NOT EXISTS idx_nnpt_fascicolo_id ON notification_non_pec_tracks (fascicolo_id);
CREATE INDEX IF NOT EXISTS idx_nnpt_notification_id ON notification_non_pec_tracks (notification_id);
CREATE INDEX IF NOT EXISTS idx_nnpt_status ON notification_non_pec_tracks (status);
CREATE INDEX IF NOT EXISTS idx_nnpt_tenant ON notification_non_pec_tracks (tenant_id);

DROP TRIGGER IF EXISTS trg_pl_notification_block_insert_proof_status;
CREATE TRIGGER trg_pl_notification_block_insert_proof_status
BEFORE INSERT ON notification_events
WHEN NEW.status IN ('PROOF_ACQUIRED', 'PROOF_DEPOSIT_REQUIRED', 'PROOF_DEPOSITED')
BEGIN
    SELECT RAISE(ABORT, 'Stato prova notifica richiede matrice probatoria validata.');
END;

DROP TRIGGER IF EXISTS trg_pl_notification_block_update_proof_without_guard;
CREATE TRIGGER trg_pl_notification_block_update_proof_without_guard
BEFORE UPDATE OF status, proof_bundle_id ON notification_events
WHEN NEW.status IN ('PROOF_ACQUIRED', 'PROOF_DEPOSIT_REQUIRED', 'PROOF_DEPOSITED')
 AND (
    iusentra_validated_transition('notification_events', NEW.id, NEW.status) != 1
    OR NEW.proof_bundle_id IS NULL
    OR NOT EXISTS (
        SELECT 1
        FROM notification_proof_bundles b
        JOIN notification_cases c ON c.id = b.notification_case_id
        WHERE b.fascicolo_id = NEW.fascicolo_id
          AND b.bundle_id = NEW.proof_bundle_id
          AND b.validation_status = 'VERIFIED'
          AND c.notification_event_id = NEW.id
    )
    OR (
        NEW.status = 'PROOF_DEPOSITED'
        AND NOT EXISTS (
            SELECT 1
            FROM notification_proof_deposits d
            JOIN notification_cases c ON c.id = d.notification_case_id
            WHERE d.bundle_id = NEW.proof_bundle_id
              AND d.deposit_status = 'OFFICE_ACCEPTED'
              AND c.notification_event_id = NEW.id
        )
    )
 )
BEGIN
    SELECT RAISE(ABORT, 'Stato prova notifica richiede bundle probatorio verificato e funzione validata.');
END;
