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
    assert "const [savedRelataDraftText, setSavedRelataDraftText]" in source
    assert "const discardedManualDraft = relataDraftDirtyRef.current || Boolean(savedRelataDraftText.trim())" in source
    assert "setSavedRelataDraftText('')" in source
    assert "setRelataDraftText('')" in source
    assert "setRelataDraftDirty(false)" in source
    assert "refreshRelataPreview(true, { useSavedDraft: !inputsChanged })" in source
    assert "La bozza manuale precedente non è più valida" in source
    assert "La relata è cambiata: firma nuovamente il documento aggiornato." in source
    assert "value={previewIsAligned ? relataDraftText : ''}" in source
    assert "disabled={!previewIsAligned || relataPreviewWorking}" in source
    assert "}, 250)" in source


def test_relata_saved_draft_becomes_current_preview_and_payload() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert "const effectiveRelataDraftText = relataDraftDirty" in source
    assert "payload.relata_override_text = effectiveRelataDraftText" in source
    assert "setSavedRelataDraftText(draftText)" in source
    assert "previewText: draftText" in source
    assert "Bozza relata salvata e applicata all’anteprima di questa notifica." in source
    assert "Bozza salvata applicata all’anteprima" in source
    assert "Bozza salvata per questa notifica" in source


def test_notifica_control_result_is_cleared_when_payload_changes() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert "const resultHasVisibleOutput = Boolean(" in source
    assert "lastControlPayloadKey === currentNotificationControlPayloadKey" in source
    assert "setResult(emptyResult)" in source
    assert "Dati della notifica modificati: riesegui il controllo relata per aggiornare i requisiti." in source


def test_relata_ui_names_applied_model_case_and_all_recipient_pecs() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert "Modello applicato: {previewAppliedTemplateLabel}" in source
    assert "Caso applicato: {previewAppliedCaseLabel}" in source
    assert "notificationRecipientsForDisplay.length" in source
    assert "distinctNotificationRecipientPecCount" in source
    assert "PEC distinte" in source
    assert "L'elenco completo entra nella relata e nel controllo prima dell'invio." in source


def test_manual_recipient_replaces_stale_destination_fields() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert "destinatario_cf: recipient.codiceFiscalePiva || current.destinatario_cf" not in source
    assert "destinatario_pec: recipient.pec || current.destinatario_pec" not in source
    assert "manualNameTyped\n        ? manualRecipientDraft.codiceFiscalePiva" in source
    assert "destinatario_cf: recipient.codiceFiscalePiva || ''" in source
    assert "codice_fiscale_piva: isActive ? notifica.destinatario_cf : recipient.codiceFiscalePiva" in source


def test_attestazione_preview_descrive_tipo_ufficio_data_e_rg() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert "function canonicalProvisionTitle" in source
    assert "if (haystack.includes('sentenza')) return 'Sentenza'" in source
    assert "function attestationOfficeIntro" in source
    assert "const attestationDocumentTitleDetail" in source
    assert "documento.provvedimentoDataDeposito" in source
    assert "detail = `${participle} ${attestationOfficeIntro(notifica.ufficio_giudiziario)}`" in source
    assert "if (notifica.sezione) detail += ` Sez. ${notifica.sezione}`" in source
    assert "if (documentDate) detail += ` in data ${documentDate}`" in source
    assert "del relativo procedimento ${attestationRg}" in source


def test_result_panel_marks_blocked_delivery_plan_as_visible_simulation() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert "function blockedSimulation(outputPlan: Record<string, unknown>)" in source
    assert "result.ok ? 'Passaggi effettuati' : 'Passaggi previsti'" in source
    assert "result.ok ? 'Piano PEC locale pronto' : 'Piano PEC locale previsto'" in source
    assert "Orario PEC e perfezionamento" not in source
    assert "Piano PEC preparato: la trasmissione resta sul PC locale dell'avvocato." in source


def test_notification_control_waits_for_public_register_confirmation() -> None:
    source = PAGE.read_text(encoding="utf-8")

    assert "const notificationControlBusy = working || publicRegisterConfirmationWorking || pecVerificationWorking" in source
    assert "disabled={notificationControlBusy}" in source
    assert "const canPrepareNotificationSend = !notificationControlBusy" in source
    assert "sendDisabledReasons" not in source
