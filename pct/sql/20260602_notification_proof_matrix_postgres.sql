CREATE TABLE IF NOT EXISTS notification_cases (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT,
    fascicolo_id TEXT NOT NULL,
    notification_event_id BIGINT,
    case_uid TEXT NOT NULL UNIQUE,
    case_type TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    act_document_id TEXT,
    proof_bundle_id TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_nc_fascicolo_id ON notification_cases (fascicolo_id);
CREATE INDEX IF NOT EXISTS idx_nc_tenant ON notification_cases (tenant_id);
CREATE INDEX IF NOT EXISTS idx_nc_event_id ON notification_cases (notification_event_id);
CREATE INDEX IF NOT EXISTS idx_nc_status ON notification_cases (status);

CREATE TABLE IF NOT EXISTS notification_recipients (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT,
    notification_case_id BIGINT NOT NULL,
    notification_event_id BIGINT,
    fascicolo_id TEXT NOT NULL,
    recipient_name TEXT,
    recipient_tax_code TEXT,
    recipient_address TEXT,
    recipient_address_source TEXT,
    address_verified_at TIMESTAMPTZ,
    address_source_snapshot_hash TEXT,
    manual_reviewer TEXT,
    recipient_type TEXT NOT NULL DEFAULT 'ALTRO',
    status TEXT NOT NULL DEFAULT 'DRAFT',
    remediation_required BOOLEAN NOT NULL DEFAULT FALSE,
    remediation_reason TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_nr_case_id ON notification_recipients (notification_case_id);
CREATE INDEX IF NOT EXISTS idx_nr_event_id ON notification_recipients (notification_event_id);
CREATE INDEX IF NOT EXISTS idx_nr_fascicolo_id ON notification_recipients (fascicolo_id);
CREATE INDEX IF NOT EXISTS idx_nr_status ON notification_recipients (status);
CREATE INDEX IF NOT EXISTS idx_nr_tenant ON notification_recipients (tenant_id);

CREATE TABLE IF NOT EXISTS notification_delivery_attempts (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT,
    fascicolo_id TEXT NOT NULL,
    notification_case_id BIGINT NOT NULL,
    recipient_id BIGINT NOT NULL,
    attempt_number INTEGER NOT NULL DEFAULT 1,
    channel TEXT NOT NULL DEFAULT 'PEC',
    status TEXT NOT NULL DEFAULT 'DRAFT',
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    error_code TEXT,
    error_message TEXT,
    corrective_action TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_nda_case_id ON notification_delivery_attempts (notification_case_id);
CREATE INDEX IF NOT EXISTS idx_nda_recipient_id ON notification_delivery_attempts (recipient_id);
CREATE INDEX IF NOT EXISTS idx_nda_tenant ON notification_delivery_attempts (tenant_id);

CREATE TABLE IF NOT EXISTS notification_recipient_address_checks (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT,
    fascicolo_id TEXT NOT NULL,
    notification_case_id BIGINT NOT NULL,
    recipient_id BIGINT NOT NULL,
    address TEXT NOT NULL,
    address_source TEXT NOT NULL,
    checked_at TIMESTAMPTZ NOT NULL,
    source_snapshot_hash TEXT,
    reviewer TEXT,
    status TEXT NOT NULL DEFAULT 'VERIFIED',
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_nrac_recipient_id ON notification_recipient_address_checks (recipient_id);
CREATE INDEX IF NOT EXISTS idx_nrac_case_id ON notification_recipient_address_checks (notification_case_id);
CREATE INDEX IF NOT EXISTS idx_nrac_tenant ON notification_recipient_address_checks (tenant_id);

CREATE TABLE IF NOT EXISTS notification_messages (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT,
    fascicolo_id TEXT NOT NULL,
    notification_case_id BIGINT NOT NULL,
    recipient_id BIGINT,
    direction TEXT NOT NULL,
    channel TEXT NOT NULL,
    message_id TEXT,
    in_reply_to TEXT,
    references_header TEXT,
    sender TEXT,
    recipients_to JSONB NOT NULL DEFAULT '[]'::jsonb,
    recipients_cc JSONB NOT NULL DEFAULT '[]'::jsonb,
    recipients_bcc_hash_only TEXT,
    subject TEXT,
    sent_at TIMESTAMPTZ,
    received_at TIMESTAMPTZ,
    raw_eml_document_id TEXT,
    raw_msg_document_id TEXT,
    body_hash TEXT,
    attachments_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    parsed_payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    parse_status TEXT,
    verification_status TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_nm_case_id ON notification_messages (notification_case_id);
CREATE INDEX IF NOT EXISTS idx_nm_recipient_id ON notification_messages (recipient_id);
CREATE INDEX IF NOT EXISTS idx_nm_message_id ON notification_messages (message_id);
CREATE INDEX IF NOT EXISTS idx_nm_tenant ON notification_messages (tenant_id);

CREATE TABLE IF NOT EXISTS notification_receipts (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT,
    fascicolo_id TEXT NOT NULL,
    notification_case_id BIGINT NOT NULL,
    recipient_id BIGINT NOT NULL,
    pec_message_id BIGINT,
    original_message_id TEXT,
    receipt_message_id TEXT,
    receipt_type TEXT NOT NULL,
    receipt_completeness TEXT NOT NULL DEFAULT 'UNKNOWN',
    sender TEXT,
    recipient TEXT,
    event_time TIMESTAMPTZ,
    received_at TIMESTAMPTZ,
    provider TEXT,
    raw_eml_document_id TEXT,
    daticert_xml_document_id TEXT,
    original_message_attached_document_id TEXT,
    parsed_payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
    hash TEXT,
    verification_status TEXT NOT NULL DEFAULT 'NEEDS_REVIEW',
    correlation_status TEXT NOT NULL DEFAULT 'NEEDS_REVIEW',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_nrec_case_id ON notification_receipts (notification_case_id);
CREATE INDEX IF NOT EXISTS idx_nrec_recipient_id ON notification_receipts (recipient_id);
CREATE INDEX IF NOT EXISTS idx_nrec_type ON notification_receipts (receipt_type);
CREATE INDEX IF NOT EXISTS idx_nrec_tenant ON notification_receipts (tenant_id);

CREATE TABLE IF NOT EXISTS notification_relata (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT,
    fascicolo_id TEXT NOT NULL,
    notification_case_id BIGINT NOT NULL,
    recipient_id BIGINT,
    relata_type TEXT NOT NULL,
    document_id TEXT,
    xml_document_id TEXT,
    pdf_document_id TEXT,
    signed_file_document_id TEXT,
    signer_tax_code TEXT,
    signature_status TEXT,
    contains_conformity_attestation BOOLEAN NOT NULL DEFAULT FALSE,
    conformity_attestation_id BIGINT,
    related_act_document_id TEXT,
    related_recipient_id BIGINT,
    generated_at TIMESTAMPTZ,
    signed_at TIMESTAMPTZ,
    verified_at TIMESTAMPTZ,
    validation_status TEXT NOT NULL DEFAULT 'NEEDS_REVIEW',
    validation_errors_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_nrel_case_id ON notification_relata (notification_case_id);
CREATE INDEX IF NOT EXISTS idx_nrel_recipient_id ON notification_relata (recipient_id);
CREATE INDEX IF NOT EXISTS idx_nrel_tenant ON notification_relata (tenant_id);

CREATE TABLE IF NOT EXISTS conformity_attestations (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT,
    fascicolo_id TEXT NOT NULL,
    notification_case_id BIGINT,
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
    dati_atto_required BOOLEAN NOT NULL DEFAULT FALSE,
    dati_atto_inserted BOOLEAN NOT NULL DEFAULT FALSE,
    validation_status TEXT NOT NULL DEFAULT 'NEEDS_REVIEW',
    validation_errors_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_ca_case_id ON conformity_attestations (notification_case_id);
CREATE INDEX IF NOT EXISTS idx_ca_tenant ON conformity_attestations (tenant_id);

CREATE TABLE IF NOT EXISTS notification_proof_bundles (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT,
    fascicolo_id TEXT NOT NULL,
    notification_case_id BIGINT NOT NULL,
    recipient_id BIGINT,
    bundle_id TEXT NOT NULL UNIQUE,
    bundle_type TEXT NOT NULL,
    required_evidence_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    collected_evidence_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    missing_evidence_json JSONB NOT NULL DEFAULT '[]'::jsonb,
    validation_status TEXT NOT NULL DEFAULT 'DRAFT',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_npb_case_id ON notification_proof_bundles (notification_case_id);
CREATE INDEX IF NOT EXISTS idx_npb_bundle_id ON notification_proof_bundles (bundle_id);
CREATE INDEX IF NOT EXISTS idx_npb_tenant ON notification_proof_bundles (tenant_id);

CREATE TABLE IF NOT EXISTS notification_evidence_links (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT,
    fascicolo_id TEXT NOT NULL,
    bundle_id TEXT NOT NULL,
    notification_case_id BIGINT NOT NULL,
    recipient_id BIGINT,
    evidence_document_id BIGINT NOT NULL,
    evidence_role TEXT NOT NULL,
    document_hash TEXT,
    validation_status TEXT NOT NULL DEFAULT 'NEEDS_REVIEW',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_nel_bundle_id ON notification_evidence_links (bundle_id);
CREATE INDEX IF NOT EXISTS idx_nel_case_id ON notification_evidence_links (notification_case_id);
CREATE INDEX IF NOT EXISTS idx_nel_evidence_id ON notification_evidence_links (evidence_document_id);
CREATE INDEX IF NOT EXISTS idx_nel_role ON notification_evidence_links (evidence_role);
CREATE INDEX IF NOT EXISTS idx_nel_tenant ON notification_evidence_links (tenant_id);

CREATE TABLE IF NOT EXISTS notification_proof_deposits (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT,
    fascicolo_id TEXT NOT NULL,
    notification_case_id BIGINT NOT NULL,
    bundle_id TEXT NOT NULL,
    deposit_status TEXT NOT NULL DEFAULT 'DRAFT',
    dati_atto_xml_id TEXT,
    package_document_id TEXT,
    accepted_receipt_document_id TEXT,
    official_outcome_document_id TEXT,
    sent_at TIMESTAMPTZ,
    accepted_at TIMESTAMPTZ,
    rejected_at TIMESTAMPTZ,
    technical_error TEXT,
    notes TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at TIMESTAMPTZ
);
CREATE INDEX IF NOT EXISTS idx_npd_case_id ON notification_proof_deposits (notification_case_id);
CREATE INDEX IF NOT EXISTS idx_npd_bundle_id ON notification_proof_deposits (bundle_id);
CREATE INDEX IF NOT EXISTS idx_npd_status ON notification_proof_deposits (deposit_status);
CREATE INDEX IF NOT EXISTS idx_npd_tenant ON notification_proof_deposits (tenant_id);

CREATE TABLE IF NOT EXISTS notification_dati_atto_receipt_refs (
    id BIGSERIAL PRIMARY KEY,
    tenant_id TEXT,
    deposit_package_id BIGINT,
    notification_case_id BIGINT NOT NULL,
    recipient_id BIGINT NOT NULL,
    receipt_id BIGINT NOT NULL,
    receipt_type TEXT NOT NULL,
    message_id TEXT,
    event_time TIMESTAMPTZ,
    recipient_address TEXT,
    source_xml_path TEXT,
    validation_status TEXT NOT NULL DEFAULT 'NEEDS_REVIEW',
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS idx_ndar_case_id ON notification_dati_atto_receipt_refs (notification_case_id);
CREATE INDEX IF NOT EXISTS idx_ndar_recipient_id ON notification_dati_atto_receipt_refs (recipient_id);
CREATE INDEX IF NOT EXISTS idx_ndar_receipt_id ON notification_dati_atto_receipt_refs (receipt_id);
CREATE INDEX IF NOT EXISTS idx_ndar_tenant ON notification_dati_atto_receipt_refs (tenant_id);
