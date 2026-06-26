from pathlib import Path


def test_ui_react_espone_regia_operativa_e_payload_reale():
    source = Path("frontend/src/components/FascicoliPage.tsx").read_text(encoding="utf-8")
    data = Path("frontend/src/fascicoliData.ts").read_text(encoding="utf-8")
    assert "RegiaOperativaSection" in source
    assert "Regia Operativa" in source
    assert "Deposito non disponibile" not in source
    assert "RegiaActionCard" in source
    assert "preventivoHref" in source
    assert "conferimentoHref" in source
    assert "proformaHref" in source
    assert "paymentHref" in source
    assert "Contesto economico" in source
    assert "Evidence pack" in source
    assert "mock_fallback: false" in data
    assert "regia: normalizeRegia(payload.regia)" in data
    assert "href={item.href || '#'}" not in source


def test_ui_mostra_dati_regia_senza_placeholder_operativi():
    source = Path("frontend/src/components/FascicoliPage.tsx").read_text(encoding="utf-8")
    regia = source[source.index("function RegiaOperativaSection"):source.index("function fLabel")]
    assert "Rossi" not in regia
    assert "Bianchi" not in regia
    assert "Cliente demo" not in regia
    assert "Dati fittizi" not in regia
    assert "ACQUISITO" in regia
    assert "Checklist non ancora generata" not in regia
    assert "Nessuno slot documentale generato" not in regia


def test_ui_deposito_prepara_legge_intero_fascicolo_e_distingue_canale():
    source = Path("frontend/src/components/FascicoliPage.tsx").read_text(encoding="utf-8")
    css = Path("frontend/src/components/FascicoliPage.css").read_text(encoding="utf-8")
    assert "function DepositPreparePage" in source
    assert "include: 'all'" in source
    assert "Inventario fascicolo" in source
    assert "La preparazione legge tutti i documenti presenti nel fascicolo" in source
    assert "Documenti candidati alla busta" in source
    assert "Catalogo portale acquisito" in source
    assert "Ricevute e cancelleria" in source
    assert "deliveryPolicy" in source
    assert "Invio PEC da software" in source
    assert "Deposito su portale" in source
    assert "Busta ministeriale Atto.enc" in source
    assert "Documenti da inviare" in source
    assert "Documenti da inviare" in source
    assert "DatiAtto.xml" in source
    assert "IndiceDocumentiDepositati.PDF" in source
    assert "Indice generato dal software" in source
    assert 'type="checkbox"' in source
    assert "Ripristina proposta" in source
    assert "Invia tutto" in source
    assert "Salva classificazione" in source
    assert "DEPOSIT_DOCUMENT_ROLE_OPTIONS" in source
    role_options = source[
        source.index("const DEPOSIT_DOCUMENT_ROLE_OPTIONS"):
        source.index("function normaliseDepositRoleForUi")
    ]
    assert "Allegato / prova" not in role_options
    assert "allegato_prova" not in role_options
    assert "{ value: 'allegato', label: 'Allegato' }" in role_options
    assert "{ value: 'prova_notifica', label: 'Prova notifica' }" in role_options
    assert "normaliseDepositRoleForUi" in source
    assert "depositRoleDisplayLabelForDocument" in source
    assert "doc.catalogLabel} (allegato busta)" in source
    assert "const roleDisplayLabel = depositRoleDisplayLabelForDocument(doc, roleValue)" in source
    assert "function DepositRolePicker" in source
    assert "iu-fas-deposit-role-picker__menu" in css
    assert "iu-fas-deposit-role-picker__button" in css
    deposit_selection = source[
        source.index("className=\"iu-fas-deposit-selection__controls\""):
        source.index("className=\"iu-fas-deposit-selection__signed\"")
    ]
    assert "<select" not in deposit_selection
    assert "DepositRolePicker" in deposit_selection
    assert "defaultDepositRoleForDocument" in source
    assert "normaliseDepositClassificationMainAct" in source
    assert "deposito/classifica-documenti" in source
    assert "manualSelectableDocuments" in source
    assert "isDepositManualSelectableDocument" in source
    assert "documenti_selezionati_ids" in source
    assert 'id="slot-deposito"' not in source
    assert source.count('id="slot-deposito-rail"') == 1
    assert "iu-fas-deposit-support-panel" not in source
    assert "#slot-deposito-rail{display:none" not in css
    assert "#slot-deposito-rail {display:none" not in css
    assert ".iu-fas-deposit-step-layout>.iu-fas-detail-side{display:grid!important}" in css
    assert "updateDepositClassification(doc.id" in source
    assert "[doc.id]: event.currentTarget.checked" not in source
    assert "depositSelectionSatisfiesSlot" in source
    assert "Scegli documento" in source
    assert "Collega" in source
    assert "Atto principale" in source
    assert "Prova senza invio reale" in source
    assert "Simula invio PEC" in source
    assert "Invia deposito reale" in source
    assert "IUSENTRA firma solo quelli obbligatori o scelti" in source
    assert "function DepositBatchSignaturePanel" in source
    assert "localSignerEndpoint('/firma-batch')" in source
    assert "LOCAL_SIGNER_BATCH_TIMEOUT_MS = 45000" in source
    assert "new AbortController()" in source
    assert "signal: controller.signal" in source
    assert "Local Signer non ha risposto entro 45 secondi" in source
    assert "Firma ${documents.length} documenti" in source
    assert "pinInputRef.current?.focus()" in source
    assert "recoverLocalSignerAutomatically" in source
    assert "localSignerOutdated" in source
    assert "Riallinea automaticamente" in source
    assert "Riavvia Local Signer e premi Riverifica" not in source
    assert "Prima riavvia e riverifica Local Signer." not in source
    assert 'role="alert"' in source[source.index("function DepositBatchSignaturePanel"):source.index("function relataStatusDisplayLabel")]
    assert "Versione firmata tramite firma multipla deposito" in source
    assert "Firma e prepara prova" in source
    assert "Il software non seleziona se la classificazione non è certa." in source
    assert "portal_upload" not in source[source.index("function DepositPreparePage"):source.index("function NotificationRelataMonitor")]


def test_ui_deposito_prova_guidata_non_salta_firma_e_mostra_audit_pec_indice():
    source = Path("frontend/src/components/FascicoliPage.tsx").read_text(encoding="utf-8")
    css = Path("frontend/src/components/FascicoliPage.css").read_text(encoding="utf-8")

    deposit_page = source[source.index("function DepositPreparePage"):source.index("function NotificationRelataMonitor")]
    action_button = source[source.index("function DepositActionButton"):source.index("function DepositPdfPreviewButton")]
    preview_button = source[source.index("function DepositPdfPreviewButton"):source.index("function JsonPostForm")]

    assert "const officeRecipientReady" in deposit_page
    assert "PEC dell’ufficio non verificata" in deposit_page
    assert "const pecWorkflowAvailable = Boolean(data.depositOffice.verified && data.depositOffice.pec)" in deposit_page
    assert "directPecReady || guidedCompletion || pecWorkflowAvailable" in deposit_page
    assert "tribunale_pec: data.depositOffice.pec" in deposit_page
    assert "prova_senza_invio: '1'" in deposit_page
    assert "simula_invio_pec: '1'" in deposit_page
    assert "Simulazione PEC in corso" in deposit_page
    assert "Message-ID fittizio" not in deposit_page
    assert "packageDocumentSignatureLabel" in deposit_page
    assert "isSignedContainerDocument" not in deposit_page
    assert "Contenitore .p7m" not in deposit_page
    assert "File .p7m presente: non viene rifirmato" not in deposit_page
    assert "function documentHasSignedContainerExtension" in source
    assert "function documentExplicitlyRequiresSignature" in source
    signature_rule = source[
        source.index("function documentExplicitlyRequiresSignature"):
        source.index("function packageDocumentSignatureLabel")
    ]
    assert "doc.statusLabel" not in signature_rule
    assert "da firmare" not in signature_rule.lower()
    assert "non firmato" not in signature_rule.lower()
    assert "senza firma" not in signature_rule.lower()
    assert "documentHasSignedContainerExtension(doc)) return false" in signature_rule
    assert "documentExplicitlyRequiresSignature(doc)" in source
    assert "role === 'atto_principale' || role === 'procura' || documentExplicitlyRequiresSignature(doc)" in source
    assert "type BatchSignatureResult" in source
    assert "batchSignaturePinSessionRef" in source
    assert "pin_session_id: reusablePinSessionId || undefined" in source
    assert "const pinSessionId = recordText(payload, 'pin_session_id')" in source
    assert "if (result?.pinSessionId) batchSignaturePinSessionRef.current = result.pinSessionId" in source
    assert "const unsignedCandidateDocuments = unsignedPackageDocuments.length" in deposit_page
    assert "depositCandidateDocuments.filter((doc) => !doc.signed && requiresPackageSignature(doc)).length" not in deposit_page
    assert "metadato ministeriale della busta, non un allegato da scegliere" in deposit_page
    assert "const signatureLabel = willSign ? 'Da firmare' : packageDocumentSignatureLabel(doc)" in deposit_page
    assert "already_signed: Boolean(doc.signed)" in deposit_page
    assert "doc?.name.toLowerCase().match(/\\.(p7m|sig|pkcs7)$/)" not in source
    assert "Report compatibilità" in deposit_page
    assert "{pecWorkflowAvailable ? (" in deposit_page
    assert "deposito/indice-documenti" in deposit_page
    assert "DepositPdfPreviewButton" in deposit_page
    assert "url: previewUrl" in preview_button
    assert "downloadUrl: previewUrl" in preview_button
    assert "URL.createObjectURL" not in preview_button
    assert "onPackageReady={handlePackageReady}" in deposit_page
    assert "Prova senza invio PEC" in deposit_page
    assert "Testo PEC predisposto" in deposit_page
    assert "Documenti indicati nel pacchetto" in deposit_page
    assert "progressItems={['DatiAtto.xml', 'DatiAtto.xml.p7m', 'IndiceBusta.xml', 'IndiceDocumentiDepositati.PDF', ...packageDocumentNames, 'Atto.enc']}" in deposit_page
    assert "progressLabel=\"Invio deposito in corso\"" in deposit_page
    assert "iu-fas-package-progress__ticker" in action_button
    assert "const pctJsonPackageChannel" in deposit_page
    assert "const realSendAction = (directPecReady || guidedCompletion || pctJsonPackageChannel) ? jsonPecAction : downloadBustaAction" in deposit_page
    assert "result.requires_local_signature && completeLocalSignature" in action_button
    assert "setConfirming(false)\n      const completion = await completeLocalSignature(result, submittedPayload)" in action_button
    assert "setLocalSignaturePinRequest(null)\n    request.resolve(pinValue)" in deposit_page
    assert "if (!localSignerStatusCanSign(signerStatus))" in deposit_page
    assert "Token non pronto per firmare DatiAtto.xml" in deposit_page
    assert "Local Signer non raggiungibile dal browser per firmare DatiAtto.xml" in deposit_page
    assert "async function parseLocalSignerResponse" in source
    assert "const signaturePayload = await parseLocalSignerResponse(signatureResponse)" in deposit_page
    assert "const payload = await parseLocalSignerResponse(signResponse)" in deposit_page
    assert "certificato_windows_firma_selezionato" in source
    assert "status?.certificato_windows_firma_selezionato || status?.certificato_windows_selezionato" in source
    assert "result.requires_local_pec && completeLocalPec" in action_button
    assert "setConfirming(false)\n      const message = await completeLocalPec(result, submittedPayload)" in action_button
    assert "await completeLocalPec(result, submittedPayload)" in action_button
    assert "result.package_ready || result.requires_guided_completion || result.requires_local_pec" in action_button
    assert action_button.index("result.requires_local_pec && completeLocalPec") < action_button.index("result.package_ready || result.requires_guided_completion || result.requires_local_pec")
    assert action_button.index("result.package_ready || result.requires_guided_completion || result.requires_local_pec") < action_button.index("!responseOk || result.ok === false")
    assert "requiresGuidedCompletion: Boolean(payload.requires_guided_completion)" in deposit_page
    assert "requiresLocalPec: Boolean(payload.requires_local_pec)" in deposit_page
    assert "localPec: payload.local_pec" in deposit_page
    assert "completeDepositLocalPec" in deposit_page
    assert "l’avvocato completa solo il passaggio ministeriale" not in deposit_page
    assert "localSignerEndpoint('/pec/send')" in deposit_page
    assert "assertLocalPecAttoEncBase64(localPayload)" in deposit_page
    assert "function assertLocalPecAttoEncBase64" in source
    assert "Allegato Atto.enc non è base64 valido" in source
    assert "looksLikeCmsEnvelopedData" in source
    assert "CMS_ENVELOPED_DATA_OID" in source
    assert "Allegato Atto.enc non è un CMS EnvelopedData ministeriale valido" in source
    assert "window.prompt" not in deposit_page
    assert "Password PEC locale" in deposit_page
    assert "Username SMTP locale" in deposit_page
    assert "recordText(localPayload, 'username'" in deposit_page
    assert "Invia dal PC locale" in deposit_page
    assert "local_pec_confirmed" in deposit_page
    assert "local_pec_message_id" in deposit_page
    assert "completeLocalPec={completeDepositLocalPec}" in deposit_page
    assert "bustaAudit: payload.busta_audit" in deposit_page
    assert "const proofBlocksDirectSend = Boolean(" in deposit_page
    assert "function depositHasPersistedDryRunProof" in source
    assert "const persistedDryRunProofReady = recentDeposits.some(depositHasPersistedDryRunProof)" in deposit_page
    assert "const packageReadyForRealSend = Boolean(packagePreview?.packageReady || persistedDryRunProofReady)" in deposit_page
    assert "disabled={actionBlocked || !packageReadyForRealSend || !realSendAvailable}" in deposit_page
    assert "const realSendAvailable = pecWorkflowAvailable && !proofBlocksDirectSend" in deposit_page
    assert "directPecReady && !guidedCompletion" not in deposit_page
    assert "Invio reale non attivo: manca ancora il trasporto ministeriale conforme." not in deposit_page
    assert "packageConfirmedForReal" not in deposit_page
    assert "setPackageConfirmedForReal" not in deposit_page
    assert "Conferma il controllo positivo" not in deposit_page
    assert "Controlli software superati" in deposit_page
    assert "signatureInputRequired(" in source
    assert ".iu-fas-package-office" in css
    assert ".iu-fas-package-preview" in css
    assert ".iu-fas-package-progress" in css


def test_ui_notifiche_relata_firma_solo_con_prova_tecnica():
    source = Path("frontend/src/components/NotificheLegaliPage.tsx").read_text(encoding="utf-8")
    css = Path("frontend/src/components/NotificheLegaliPage.css").read_text(encoding="utf-8")
    signature_block = source[source.index("const handleSignedRelataFile"):source.index("const applyDepositFile")]

    assert "signatureHref" not in source
    assert "Apri firma digitale" not in source
    assert "Apri la firma digitale" not in source
    assert "lo stato si aggiorna solo con una prova CAdES o PAdES" in source
    assert "Verifica Local Signer" in source
    assert "fileContainsCadesSignedData" in source
    assert "pdfContainsPadesSignature" in source
    assert "signedDataOid" in source
    assert "non contiene una busta CAdES/PKCS#7 riconoscibile" in source
    assert "setNotifica((current) => ({ ...current, relata_firmata: false }))" in signature_block
    assert "<input type=\"checkbox\" checked={notifica.relata_firmata} readOnly disabled />" in source
    assert "Relata firmata acquisita con prova tecnica" in source
    assert ".iu-legal-signature-button" in css
    assert "hasNotifiableExtension" in source
    assert "hasSendableNotificationAttachmentExtension" in source
    assert "hasEmailEvidenceExtension" in source
    assert "automaticAttestationDocument" in source
    assert "Attestazione_conformita_" in source
    assert "deriveProceedingRg" in source
    assert "const notifiableDocuments = practice.documenti.filter(isNotifiableNotificationDocument)" in source
    assert "currentNotificationDocuments.every(isNotifiablePayloadDocument)" in source
    assert "hasPassingNotificationControl" in source
    assert "disabled={!canPrepareNotificationSend}" in source
    assert "Invio PEC bloccato" in source
    assert 'accept=".pdf,.pdfa,.p7m,.eml,.msg"' in source
    assert "Tutti notificabili" in source
