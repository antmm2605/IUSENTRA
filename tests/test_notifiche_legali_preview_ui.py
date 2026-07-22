from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PAGE = ROOT / "frontend" / "src" / "components" / "NotificheLegaliPage.tsx"
DATA = ROOT / "frontend" / "src" / "notificheLegaliData.ts"


def test_relata_preview_uses_complete_legal_payload_and_rejects_stale_responses() -> None:
    source = PAGE.read_text(encoding="utf-8")
    data_source = DATA.read_text(encoding="utf-8")

    assert "documenti: notificationDocumentPayloads()" in source
    assert "destinatari: notificationRecipientPayloads()" in source
    assert "const previewPayloadKey = notificationControlPayloadKey(buildNotificaPayload(false))" in source
    assert "inputPayloadKey: notificationControlPayloadKey(buildNotificaPayload(false, overrides))" in source

    assert "const relataPreviewAbortRef = useRef<AbortController | null>(null)" in source
    assert "relataPreviewAbortRef.current?.abort()" in source
    assert "requestId !== relataPreviewRequestIdRef.current" in source
    assert "previewLegalRelata(payload, controller.signal)" in source
    assert "completedRelataPreviewKeyRef.current === previewPayloadKey" in source
    assert "signal?: AbortSignal" in data_source
    assert "signal," in data_source


def test_relata_preview_invalidates_old_manual_draft_and_updates_quickly() -> None:
    source = PAGE.read_text(encoding="utf-8")

    # Il ref viene aggiornato insieme allo stato negli handler: un effetto
    # asincrono sul vecchio stato potrebbe riattivare una bozza già scartata.
    assert "relataDraftDirtyRef.current = relataDraftDirty" not in source
    assert "setRelataDraftText(response.relataText)\n        relataDraftDirtyRef.current = false" in source
    assert "const discardedManualDraft = relataDraftDirtyRef.current" in source
    assert "setRelataDraftText('')" in source
    assert "setRelataDraftDirty(false)" in source
    assert "La bozza manuale precedente non è più valida" in source
    assert "La relata è cambiata: firma nuovamente il documento aggiornato." in source
    assert "value={previewIsAligned ? relataDraftText : ''}" in source
    assert "disabled={!previewIsAligned || relataPreviewWorking}" in source
    assert "}, 250)" in source


def test_relata_ui_names_applied_model_case_and_all_recipient_pecs() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert "Modello applicato: {previewAppliedTemplateLabel}" in source
    assert "Caso applicato: {previewAppliedCaseLabel}" in source
    assert "notificationRecipientsForDisplay.length" in source
    assert "distinctNotificationRecipientPecCount" in source
    assert "PEC distinte" in source
    assert "L'elenco completo entra nella relata e nel controllo prima dell'invio." in source
