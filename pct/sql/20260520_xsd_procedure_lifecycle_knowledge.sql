BEGIN;

CREATE TABLE IF NOT EXISTS legal_ministerial_xsd_objects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT,
    xsd_code TEXT NOT NULL UNIQUE,
    xsd_label TEXT NOT NULL,
    xsd_area_code TEXT,
    xsd_area_label TEXT,
    xsd_family_code TEXT,
    xsd_family_label TEXT,
    source_version TEXT NOT NULL,
    source_name TEXT NOT NULL,
    source_url TEXT,
    source_file TEXT,
    active INTEGER NOT NULL DEFAULT 1,
    last_verified_at TEXT,
    import_hash TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_lm_xsd_code ON legal_ministerial_xsd_objects (xsd_code);
CREATE INDEX IF NOT EXISTS idx_lm_tenant ON legal_ministerial_xsd_objects (tenant_id);
CREATE INDEX IF NOT EXISTS idx_lm_xsd_area_code ON legal_ministerial_xsd_objects (xsd_area_code);
CREATE INDEX IF NOT EXISTS idx_lm_xsd_family_code ON legal_ministerial_xsd_objects (xsd_family_code);
CREATE INDEX IF NOT EXISTS idx_lm_xsd_active ON legal_ministerial_xsd_objects (active);

CREATE TABLE IF NOT EXISTS legal_procedure_xsd_map (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT,
    xsd_code TEXT NOT NULL,
    procedure_code TEXT NOT NULL,
    channel_code TEXT,
    registry_code TEXT,
    workflow_code TEXT,
    is_default INTEGER NOT NULL DEFAULT 0,
    confidence_score INTEGER NOT NULL DEFAULT 50,
    mapping_source TEXT NOT NULL DEFAULT 'RULE',
    review_status TEXT NOT NULL DEFAULT 'needs_review',
    reviewer TEXT,
    reviewed_at TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    UNIQUE (xsd_code, procedure_code, channel_code)
);
CREATE INDEX IF NOT EXISTS idx_lpxm_xsd_code ON legal_procedure_xsd_map (xsd_code);
CREATE INDEX IF NOT EXISTS idx_lpxm_tenant ON legal_procedure_xsd_map (tenant_id);
CREATE INDEX IF NOT EXISTS idx_lpxm_procedure_code ON legal_procedure_xsd_map (procedure_code);
CREATE INDEX IF NOT EXISTS idx_lpxm_review_status ON legal_procedure_xsd_map (review_status);

CREATE TABLE IF NOT EXISTS legal_procedure_source_evidence (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT,
    procedure_code TEXT NOT NULL,
    xsd_code TEXT,
    source_id TEXT,
    source_type TEXT NOT NULL,
    source_url TEXT,
    source_title TEXT,
    source_author TEXT,
    source_date TEXT,
    last_checked_at TEXT,
    evidence_kind TEXT NOT NULL,
    extracted_principle TEXT,
    original_quote_short TEXT,
    copyright_policy TEXT NOT NULL DEFAULT 'summary_only',
    reliability_score INTEGER NOT NULL DEFAULT 50,
    review_status TEXT NOT NULL DEFAULT 'needs_review',
    reviewer TEXT,
    reviewed_at TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_lpse_procedure_code ON legal_procedure_source_evidence (procedure_code);
CREATE INDEX IF NOT EXISTS idx_lpse_tenant ON legal_procedure_source_evidence (tenant_id);
CREATE INDEX IF NOT EXISTS idx_lpse_xsd_code ON legal_procedure_source_evidence (xsd_code);
CREATE INDEX IF NOT EXISTS idx_lpse_source_type ON legal_procedure_source_evidence (source_type);
CREATE INDEX IF NOT EXISTS idx_lpse_review_status ON legal_procedure_source_evidence (review_status);

CREATE TABLE IF NOT EXISTS procedure_knowledge_cards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT,
    procedure_code TEXT NOT NULL,
    xsd_code TEXT,
    title TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT 'v1',
    status TEXT NOT NULL DEFAULT 'draft',
    risk_level TEXT NOT NULL DEFAULT 'MEDIUM',
    requires_human_review INTEGER NOT NULL DEFAULT 1,
    generated_from_sources_json TEXT NOT NULL DEFAULT '[]',
    card_json TEXT NOT NULL DEFAULT '{}',
    summary_original TEXT,
    validation_report_json TEXT NOT NULL DEFAULT '{}',
    reviewer TEXT,
    reviewed_at TEXT,
    review_reason TEXT,
    published_at TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_pkc_procedure_code ON procedure_knowledge_cards (procedure_code);
CREATE INDEX IF NOT EXISTS idx_pkc_tenant ON procedure_knowledge_cards (tenant_id);
CREATE INDEX IF NOT EXISTS idx_pkc_xsd_code ON procedure_knowledge_cards (xsd_code);
CREATE INDEX IF NOT EXISTS idx_pkc_status ON procedure_knowledge_cards (status);

CREATE TABLE IF NOT EXISTS procedure_lifecycle_templates (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT,
    procedure_code TEXT NOT NULL,
    xsd_code TEXT,
    channel_code TEXT NOT NULL,
    registry_code TEXT,
    workflow_code TEXT,
    name TEXT NOT NULL,
    version TEXT NOT NULL DEFAULT 'v1',
    active INTEGER NOT NULL DEFAULT 1,
    requires_human_review INTEGER NOT NULL DEFAULT 1,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_plt_procedure_code ON procedure_lifecycle_templates (procedure_code);
CREATE INDEX IF NOT EXISTS idx_plt_tenant ON procedure_lifecycle_templates (tenant_id);
CREATE INDEX IF NOT EXISTS idx_plt_xsd_code ON procedure_lifecycle_templates (xsd_code);
CREATE INDEX IF NOT EXISTS idx_plt_channel_code ON procedure_lifecycle_templates (channel_code);

CREATE TABLE IF NOT EXISTS procedure_lifecycle_steps (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT,
    template_id INTEGER NOT NULL,
    step_code TEXT NOT NULL,
    step_name TEXT NOT NULL,
    step_type TEXT NOT NULL,
    sort_order INTEGER NOT NULL,
    required INTEGER NOT NULL DEFAULT 1,
    trigger_event TEXT,
    deadline_rule_json TEXT NOT NULL DEFAULT '{}',
    validation_rule_json TEXT NOT NULL DEFAULT '{}',
    output_required_json TEXT NOT NULL DEFAULT '[]',
    next_step_on_success TEXT,
    next_step_on_error TEXT,
    human_review_required INTEGER NOT NULL DEFAULT 0,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT,
    UNIQUE(template_id, step_code)
);
CREATE INDEX IF NOT EXISTS idx_pls_template_id ON procedure_lifecycle_steps (template_id);
CREATE INDEX IF NOT EXISTS idx_pls_tenant ON procedure_lifecycle_steps (tenant_id);
CREATE INDEX IF NOT EXISTS idx_pls_step_type ON procedure_lifecycle_steps (step_type);

CREATE TABLE IF NOT EXISTS fascicolo_workflow_instances (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT,
    fascicolo_id TEXT NOT NULL,
    template_id INTEGER NOT NULL,
    procedure_code TEXT NOT NULL,
    xsd_code TEXT,
    current_step_code TEXT,
    status TEXT NOT NULL DEFAULT 'OPEN',
    opened_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    closed_at TEXT,
    assigned_lawyer_id TEXT,
    risk_level TEXT DEFAULT 'MEDIUM',
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_fwi_fascicolo_id ON fascicolo_workflow_instances (fascicolo_id);
CREATE INDEX IF NOT EXISTS idx_fwi_tenant ON fascicolo_workflow_instances (tenant_id);
CREATE INDEX IF NOT EXISTS idx_fwi_status ON fascicolo_workflow_instances (status);

CREATE TABLE IF NOT EXISTS fascicolo_workflow_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT,
    workflow_instance_id INTEGER NOT NULL,
    event_code TEXT NOT NULL,
    event_type TEXT NOT NULL,
    event_status TEXT NOT NULL,
    source TEXT,
    source_ref TEXT,
    event_payload_json TEXT NOT NULL DEFAULT '{}',
    occurred_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    created_by TEXT,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_fwe_instance_id ON fascicolo_workflow_events (workflow_instance_id);
CREATE INDEX IF NOT EXISTS idx_fwe_tenant ON fascicolo_workflow_events (tenant_id);
CREATE INDEX IF NOT EXISTS idx_fwe_event_code ON fascicolo_workflow_events (event_code);

CREATE TABLE IF NOT EXISTS digital_signature_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT,
    fascicolo_id TEXT NOT NULL,
    document_id TEXT NOT NULL,
    required INTEGER NOT NULL DEFAULT 1,
    signer_expected TEXT,
    signer_detected TEXT,
    signer_tax_code TEXT,
    signature_format TEXT,
    certificate_serial TEXT,
    hash_before TEXT,
    hash_after TEXT,
    verification_status TEXT NOT NULL,
    signed_at TEXT,
    verified_at TEXT,
    evidence_document_id TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_dse_fascicolo_id ON digital_signature_events (fascicolo_id);
CREATE INDEX IF NOT EXISTS idx_dse_tenant ON digital_signature_events (tenant_id);
CREATE INDEX IF NOT EXISTS idx_dse_document_id ON digital_signature_events (document_id);
CREATE INDEX IF NOT EXISTS idx_dse_status ON digital_signature_events (verification_status);

CREATE TABLE IF NOT EXISTS telematic_deposit_packages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT,
    fascicolo_id TEXT NOT NULL,
    procedure_code TEXT NOT NULL,
    xsd_code TEXT,
    channel_code TEXT NOT NULL,
    office_code TEXT,
    registry_code TEXT,
    dati_atto_xml_id TEXT,
    envelope_file_id TEXT,
    deposit_status TEXT NOT NULL DEFAULT 'DRAFT',
    deposit_mode TEXT,
    package_hash TEXT,
    sent_at TEXT,
    accepted_at TEXT,
    rejected_at TEXT,
    rejection_reason TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_tdp_fascicolo_id ON telematic_deposit_packages (fascicolo_id);
CREATE INDEX IF NOT EXISTS idx_tdp_tenant ON telematic_deposit_packages (tenant_id);
CREATE INDEX IF NOT EXISTS idx_tdp_xsd_code ON telematic_deposit_packages (xsd_code);
CREATE INDEX IF NOT EXISTS idx_tdp_status ON telematic_deposit_packages (deposit_status);

CREATE TABLE IF NOT EXISTS telematic_deposit_receipts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT,
    deposit_package_id INTEGER NOT NULL,
    receipt_type TEXT NOT NULL,
    receipt_status TEXT NOT NULL,
    pec_message_id TEXT,
    pec_subject TEXT,
    sender TEXT,
    recipient TEXT,
    received_at TEXT,
    event_time TEXT,
    document_id TEXT,
    parsed_payload_json TEXT NOT NULL DEFAULT '{}',
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_tdr_package_id ON telematic_deposit_receipts (deposit_package_id);
CREATE INDEX IF NOT EXISTS idx_tdr_tenant ON telematic_deposit_receipts (tenant_id);
CREATE INDEX IF NOT EXISTS idx_tdr_type ON telematic_deposit_receipts (receipt_type);

CREATE TABLE IF NOT EXISTS post_acceptance_obligations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT,
    fascicolo_id TEXT NOT NULL,
    procedure_code TEXT NOT NULL,
    xsd_code TEXT,
    trigger_event TEXT NOT NULL,
    obligation_type TEXT NOT NULL,
    obligation_status TEXT NOT NULL DEFAULT 'PENDING',
    deadline_at TEXT,
    legal_basis TEXT,
    required_documents_json TEXT NOT NULL DEFAULT '[]',
    evidence_required_json TEXT NOT NULL DEFAULT '[]',
    human_review_required INTEGER NOT NULL DEFAULT 1,
    generated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    completed_at TEXT,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_pao_fascicolo_id ON post_acceptance_obligations (fascicolo_id);
CREATE INDEX IF NOT EXISTS idx_pao_tenant ON post_acceptance_obligations (tenant_id);
CREATE INDEX IF NOT EXISTS idx_pao_status ON post_acceptance_obligations (obligation_status);
CREATE INDEX IF NOT EXISTS idx_pao_type ON post_acceptance_obligations (obligation_type);

CREATE TABLE IF NOT EXISTS notification_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT,
    fascicolo_id TEXT NOT NULL,
    obligation_id INTEGER,
    notification_type TEXT NOT NULL,
    recipient_name TEXT,
    recipient_tax_code TEXT,
    recipient_address TEXT,
    recipient_address_source TEXT,
    act_document_id TEXT NOT NULL,
    relata_document_id TEXT,
    sent_at TEXT,
    delivered_at TEXT,
    status TEXT NOT NULL DEFAULT 'DRAFT',
    proof_bundle_id TEXT,
    notes TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT
);
CREATE INDEX IF NOT EXISTS idx_ne_fascicolo_id ON notification_events (fascicolo_id);
CREATE INDEX IF NOT EXISTS idx_ne_tenant ON notification_events (tenant_id);
CREATE INDEX IF NOT EXISTS idx_ne_obligation_id ON notification_events (obligation_id);
CREATE INDEX IF NOT EXISTS idx_ne_status ON notification_events (status);

CREATE TABLE IF NOT EXISTS evidence_documents (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT,
    fascicolo_id TEXT NOT NULL,
    evidence_type TEXT NOT NULL,
    document_id TEXT NOT NULL,
    source_event_id INTEGER,
    hash TEXT,
    filename_original TEXT,
    storage_path TEXT,
    acquired_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    legal_relevance TEXT,
    retention_policy TEXT,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_ed_fascicolo_id ON evidence_documents (fascicolo_id);
CREATE INDEX IF NOT EXISTS idx_ed_tenant ON evidence_documents (tenant_id);
CREATE INDEX IF NOT EXISTS idx_ed_document_id ON evidence_documents (document_id);
CREATE INDEX IF NOT EXISTS idx_ed_type ON evidence_documents (evidence_type);

CREATE TABLE IF NOT EXISTS procedure_audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tenant_id TEXT,
    entity_type TEXT NOT NULL,
    entity_id TEXT,
    action TEXT NOT NULL,
    actor TEXT,
    source TEXT,
    before_json TEXT NOT NULL DEFAULT '{}',
    after_json TEXT NOT NULL DEFAULT '{}',
    diff_json TEXT NOT NULL DEFAULT '{}',
    event_hash TEXT,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    notes TEXT
);
CREATE INDEX IF NOT EXISTS idx_pal_entity ON procedure_audit_log (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS idx_pal_tenant ON procedure_audit_log (tenant_id);
CREATE INDEX IF NOT EXISTS idx_pal_action ON procedure_audit_log (action);
CREATE INDEX IF NOT EXISTS idx_pal_hash ON procedure_audit_log (event_hash);

DROP TRIGGER IF EXISTS trg_pl_signature_block_insert_verified;
DROP TRIGGER IF EXISTS trg_pl_signature_block_update_verified_without_guard;
DROP TRIGGER IF EXISTS trg_pl_tdp_block_insert_office_accepted;
DROP TRIGGER IF EXISTS trg_pl_tdp_block_insert_office_rejected;
DROP TRIGGER IF EXISTS trg_pl_tdp_block_insert_protected_status;
DROP TRIGGER IF EXISTS trg_pl_tdp_block_update_office_accepted;
DROP TRIGGER IF EXISTS trg_pl_tdp_block_update_office_rejected;
DROP TRIGGER IF EXISTS trg_pl_tdp_block_update_protected_without_guard;
DROP TRIGGER IF EXISTS trg_pl_notification_block_insert_proof_without_evidence;
DROP TRIGGER IF EXISTS trg_pl_notification_block_insert_proof_status;
DROP TRIGGER IF EXISTS trg_pl_notification_block_update_proof_without_evidence;
DROP TRIGGER IF EXISTS trg_pl_notification_block_update_proof_without_guard;
DROP TRIGGER IF EXISTS trg_pl_workflow_block_insert_firmato_without_verified_signature;
DROP TRIGGER IF EXISTS trg_pl_workflow_block_update_firmato_without_verified_signature;
DROP TRIGGER IF EXISTS trg_pl_workflow_block_insert_accepted_without_receipt;
DROP TRIGGER IF EXISTS trg_pl_workflow_block_update_accepted_without_receipt;
DROP TRIGGER IF EXISTS trg_pl_workflow_block_insert_notification_without_sent_event;
DROP TRIGGER IF EXISTS trg_pl_workflow_block_update_notification_without_sent_event;
DROP TRIGGER IF EXISTS trg_pl_workflow_block_insert_proof_without_evidence;
DROP TRIGGER IF EXISTS trg_pl_workflow_block_update_proof_without_evidence;
DROP TRIGGER IF EXISTS trg_pl_workflow_block_insert_close_with_pending_obligations;
DROP TRIGGER IF EXISTS trg_pl_workflow_block_update_close_with_pending_obligations;
DROP TRIGGER IF EXISTS trg_pl_workflow_block_insert_protected_status;
DROP TRIGGER IF EXISTS trg_pl_workflow_block_update_protected_without_guard;

CREATE TRIGGER IF NOT EXISTS trg_pl_signature_block_insert_verified
BEFORE INSERT ON digital_signature_events
WHEN NEW.verification_status = 'VERIFIED'
BEGIN
    SELECT RAISE(ABORT, 'VERIFIED richiede record_signature_result validato.');
END;

CREATE TRIGGER IF NOT EXISTS trg_pl_signature_block_update_verified_without_guard
BEFORE UPDATE OF verification_status ON digital_signature_events
WHEN NEW.verification_status = 'VERIFIED'
 AND (
    iusentra_validated_transition('digital_signature_events', NEW.id, NEW.verification_status) != 1
    OR NEW.signer_detected IS NULL
    OR NEW.hash_after IS NULL
 )
BEGIN
    SELECT RAISE(ABORT, 'VERIFIED richiede record_signature_result validato e hash/firma verificati.');
END;

CREATE TRIGGER IF NOT EXISTS trg_pl_tdp_block_insert_protected_status
BEFORE INSERT ON telematic_deposit_packages
WHEN NEW.deposit_status IN ('READY', 'OFFICE_ACCEPTED', 'OFFICE_REJECTED', 'TECHNICAL_ERROR')
BEGIN
    SELECT RAISE(ABORT, 'Stato deposito protetto richiede funzione validata.');
END;

CREATE TRIGGER IF NOT EXISTS trg_pl_tdp_block_update_protected_without_guard
BEFORE UPDATE OF deposit_status ON telematic_deposit_packages
WHEN NEW.deposit_status IN ('READY', 'OFFICE_ACCEPTED', 'OFFICE_REJECTED', 'TECHNICAL_ERROR')
 AND (
    iusentra_validated_transition('telematic_deposit_packages', NEW.id, NEW.deposit_status) != 1
    OR (
        NEW.deposit_status = 'READY'
        AND (
            COALESCE(NEW.xsd_code, '') = ''
            OR COALESCE(NEW.dati_atto_xml_id, '') = ''
            OR COALESCE(NEW.envelope_file_id, '') = ''
            OR NOT EXISTS (
                SELECT 1 FROM legal_ministerial_xsd_objects
                WHERE xsd_code = NEW.xsd_code
                  AND active = 1
            )
            OR (
                (
                    substr(COALESCE(NEW.xsd_code, ''), 1, 3) IN ('010','011','012','014','015','017','019','020','030','050','051','052','053','055','059')
                    OR EXISTS (
                        SELECT 1 FROM digital_signature_events
                        WHERE fascicolo_id = NEW.fascicolo_id
                          AND required = 1
                    )
                )
                AND NOT EXISTS (
                    SELECT 1 FROM digital_signature_events
                    WHERE fascicolo_id = NEW.fascicolo_id
                      AND required = 1
                      AND verification_status = 'VERIFIED'
                )
            )
        )
    )
    OR (
        NEW.deposit_status = 'OFFICE_ACCEPTED'
        AND NOT EXISTS (
            SELECT 1 FROM telematic_deposit_receipts
            WHERE deposit_package_id = NEW.id
              AND receipt_type = 'ACCETTAZIONE_DEPOSITO'
        )
    )
    OR (
        NEW.deposit_status = 'OFFICE_REJECTED'
        AND NOT EXISTS (
            SELECT 1 FROM telematic_deposit_receipts
            WHERE deposit_package_id = NEW.id
              AND receipt_type IN ('RIFIUTO_DEPOSITO', 'ERRORE_TECNICO')
        )
    )
    OR (
        NEW.deposit_status = 'TECHNICAL_ERROR'
        AND NOT EXISTS (
            SELECT 1 FROM telematic_deposit_receipts
            WHERE deposit_package_id = NEW.id
              AND receipt_type = 'ERRORE_TECNICO'
        )
    )
 )
BEGIN
    SELECT RAISE(ABORT, 'Stato deposito protetto richiede evidenza e funzione validata.');
END;

CREATE TRIGGER IF NOT EXISTS trg_pl_notification_block_insert_proof_status
BEFORE INSERT ON notification_events
WHEN NEW.status IN ('PROOF_ACQUIRED', 'PROOF_DEPOSIT_REQUIRED', 'PROOF_DEPOSITED')
BEGIN
    SELECT RAISE(ABORT, 'Stato prova notifica richiede evidence vault validato.');
END;

CREATE TRIGGER IF NOT EXISTS trg_pl_notification_block_update_proof_without_guard
BEFORE UPDATE OF status, proof_bundle_id ON notification_events
WHEN NEW.status IN ('PROOF_ACQUIRED', 'PROOF_DEPOSIT_REQUIRED', 'PROOF_DEPOSITED')
 AND (
    iusentra_validated_transition('notification_events', NEW.id, NEW.status) != 1
    OR NEW.proof_bundle_id IS NULL
    OR NOT EXISTS (
        SELECT 1 FROM evidence_documents
        WHERE fascicolo_id = NEW.fascicolo_id
          AND (document_id = NEW.proof_bundle_id OR CAST(id AS TEXT) = NEW.proof_bundle_id)
    )
 )
BEGIN
    SELECT RAISE(ABORT, 'Stato prova notifica richiede evidence_documents collegati e funzione validata.');
END;

CREATE TRIGGER IF NOT EXISTS trg_pl_workflow_block_insert_protected_status
BEFORE INSERT ON fascicolo_workflow_instances
WHEN NEW.current_step_code IN (
    'FIRMATO',
    'DEPOSITO_ACCETTATO',
    'DEPOSITO_RIFIUTATO',
    'NOTIFICA_EFFETTUATA',
    'PROVA_NOTIFICA_ACQUISITA',
    'CHIUSA'
)
 OR NEW.status = 'COMPLETED'
BEGIN
    SELECT RAISE(ABORT, 'Stato workflow finale richiede transition_workflow validato.');
END;

CREATE TRIGGER IF NOT EXISTS trg_pl_workflow_block_update_protected_without_guard
BEFORE UPDATE OF current_step_code, status ON fascicolo_workflow_instances
WHEN (
    NEW.current_step_code IN (
        'FIRMATO',
        'DEPOSITO_ACCETTATO',
        'DEPOSITO_RIFIUTATO',
        'NOTIFICA_EFFETTUATA',
        'PROVA_NOTIFICA_ACQUISITA',
        'CHIUSA'
    )
    OR NEW.status = 'COMPLETED'
)
 AND (
    iusentra_validated_transition(
        'fascicolo_workflow_instances',
        NEW.id,
        CASE WHEN NEW.current_step_code = 'CHIUSA' OR NEW.status = 'COMPLETED' THEN 'CHIUSA' ELSE NEW.current_step_code END
    ) != 1
    OR (
        NEW.current_step_code = 'FIRMATO'
        AND (
            substr(COALESCE(NEW.xsd_code, ''), 1, 3) IN ('010','011','012','014','015','017','019','020','030','050','051','052','053','055','059')
            OR EXISTS (
                SELECT 1 FROM digital_signature_events
                WHERE fascicolo_id = NEW.fascicolo_id
                  AND required = 1
            )
        )
        AND NOT EXISTS (
            SELECT 1 FROM digital_signature_events
            WHERE fascicolo_id = NEW.fascicolo_id
              AND required = 1
              AND verification_status = 'VERIFIED'
        )
    )
    OR (
        NEW.current_step_code = 'DEPOSITO_ACCETTATO'
        AND NOT EXISTS (
            SELECT 1
            FROM telematic_deposit_packages p
            JOIN telematic_deposit_receipts r ON r.deposit_package_id = p.id
            WHERE p.fascicolo_id = NEW.fascicolo_id
              AND r.receipt_type = 'ACCETTAZIONE_DEPOSITO'
        )
    )
    OR (
        NEW.current_step_code = 'DEPOSITO_RIFIUTATO'
        AND NOT EXISTS (
            SELECT 1
            FROM telematic_deposit_packages p
            JOIN telematic_deposit_receipts r ON r.deposit_package_id = p.id
            WHERE p.fascicolo_id = NEW.fascicolo_id
              AND r.receipt_type IN ('RIFIUTO_DEPOSITO', 'ERRORE_TECNICO')
        )
    )
    OR (
        NEW.current_step_code = 'NOTIFICA_EFFETTUATA'
        AND NOT EXISTS (
            SELECT 1 FROM notification_events
            WHERE fascicolo_id = NEW.fascicolo_id
              AND status IN ('SENT', 'DELIVERED', 'PROOF_ACQUIRED', 'PROOF_DEPOSIT_REQUIRED', 'PROOF_DEPOSITED')
        )
    )
    OR (
        NEW.current_step_code = 'PROVA_NOTIFICA_ACQUISITA'
        AND NOT EXISTS (
            SELECT 1 FROM evidence_documents
            WHERE fascicolo_id = NEW.fascicolo_id
              AND evidence_type IN ('NOTIFICATION_RECEIPT', 'PROOF_OF_DELIVERY')
        )
    )
    OR (
        (NEW.current_step_code = 'CHIUSA' OR NEW.status = 'COMPLETED')
        AND EXISTS (
            SELECT 1 FROM post_acceptance_obligations
            WHERE fascicolo_id = NEW.fascicolo_id
              AND obligation_status = 'PENDING'
        )
    )
 )
BEGIN
    SELECT RAISE(ABORT, 'Stato workflow finale richiede evidenza e transition_workflow validato.');
END;

COMMIT;
