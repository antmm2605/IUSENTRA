-- Indici consultivi: nessuna modifica a notificazioni, ricevute o catene audit.
CREATE INDEX IF NOT EXISTS idx_pec_notification_query_due
    ON pec_legal_notification_presidia(tenant_id,status,explicit_due_at,id);
CREATE INDEX IF NOT EXISTS idx_pec_notification_query_rac
    ON pec_legal_notification_transitions(tenant_id,next_status,presidio_id,occurred_at);
