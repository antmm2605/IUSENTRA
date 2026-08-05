from pathlib import Path
from types import SimpleNamespace

import pytest

from web.blueprints.api_v1_react import _deposit_datiatto_extra
from web.services.react_fascicoli_bridge import _deposit_office_payload


def test_deposito_dati_specifici_persistibili_sono_json_limitato():
    payload = {"terzi": [{"codice_fiscale": "TRZPLA80A01H501B"}], "esente": False}

    assert _deposit_datiatto_extra(payload) == payload

    with pytest.raises(ValueError, match="dimensione consentita"):
        _deposit_datiatto_extra({"testo": "x" * (64 * 1024)})


def test_deposito_resolver_ufficio_completa_pec_e_codice_da_catalogo():
    payload = _deposit_office_payload(SimpleNamespace(tribunale="Tribunale di Milano"))

    assert payload["name"] == "Tribunale di Milano"
    assert payload["pec"] == "tribunale.milano@civile.ptel.giustiziacert.it"
    assert payload["code"] == "0580010"
    assert payload["ministerialCode"] == "0151460094"
    assert payload["verified"] is True
    assert "risolti automaticamente dal catalogo uffici" in payload["message"]


def test_deposito_resolver_non_si_ferma_a_pec_profilo_senza_codice():
    fascicolo = SimpleNamespace(
        tribunale="Tribunale di Palmi",
        profilo_deposito={
            "ufficio": {
                "nome": "Tribunale di Palmi",
                "pec": "tribunale.palmi@civile.ptel.giustiziacert.it",
            }
        },
    )

    payload = _deposit_office_payload(fascicolo)

    assert payload["name"] == "Tribunale di Palmi"
    assert payload["pec"] == "tribunale.palmi@civile.ptel.giustiziacert.it"
    assert payload["code"] == "0910011"
    assert payload["ministerialCode"] == "0800570094"
    assert payload["verified"] is True
    assert "codice ufficio" in payload["message"]


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
    shell_source = Path("frontend/src/components/FascicoliPage.tsx").read_text(encoding="utf-8")
    source = Path("frontend/src/components/FascicoloDepositoPage.tsx").read_text(encoding="utf-8")
    data = Path("frontend/src/fascicoliData.ts").read_text(encoding="utf-8")
    css = Path("frontend/src/components/FascicoliPage.css").read_text(encoding="utf-8")
    local_signer = Path("frontend/src/features/impostazioni/localSigner.ts").read_text(encoding="utf-8")
    api = Path("web/blueprints/api_v1_react.py").read_text(encoding="utf-8")
    bridge = Path("web/services/react_fascicoli_bridge.py").read_text(encoding="utf-8")
    assert "function DepositPreparePage" in source
    assert "FascicoloDepositoPage" in shell_source
    assert "include: 'all'" in shell_source
    assert "Inventario fascicolo" in source
    assert "La preparazione legge tutti i documenti presenti nel fascicolo" in source
    assert "Documenti candidati alla busta" in source
    assert "Documenti acquisiti dal portale" in source
    assert "Ricevute e cancelleria" in source
    assert "deliveryPolicy" in source
    assert "Invio PEC da software" in source
    assert "Deposito su portale" in source
    assert "Pacchetto deposito" in source
    assert "Documenti da inviare" in source
    assert "Documenti da inviare" in source
    assert "function mobilePreviewUrl" in source
    assert "const viewerUrl = mobileUrl || preview.url" in source
    assert "isMobileReader" not in source
    assert "quickorganizer_deposito_catalogo_ui.json" not in source
    assert "depositCatalog: normalizeDepositCatalog" in data
    assert "catalog={data.depositCatalog}" in source
    assert "selectedDepositTypeKey" in source
    assert "tipo_deposito_telematico_key" in source
    assert "tipo_deposito_telematico_real_send_allowed" in source
    assert "buildDepositCatalogPreviewState" in source
    assert "buildDepositCatalogPreviewMacroareasFromEntries" in source
    assert "Elenco depositi non disponibile." in source
    assert "Controlli automatici" in source
    assert "Logica Studio Telematico" not in source
    assert "Esplodi tutto" in source
    assert ".iu-fas-deposit-type-panel" in css
    assert "Dati deposito" in source
    assert "Indice documenti" in source
    assert "Indice generato dal software" in source
    assert 'type="checkbox"' in source
    assert "Ripristina documenti collegati" in source
    assert "Invia tutto" not in source
    assert "Deseleziona tutto" in source
    assert "Salva classificazione" in source
    assert "function DepositSpecificDataForm" in source
    assert "Mostriamo solo i dati necessari per il tipo selezionato" in source
    assert "missingRequiredDepositSpecificFields" in source
    assert "datiatto_extra: JSON.stringify(depositSpecificData)" in source
    assert "datiatto_extra: depositSpecificData" in source
    assert "requiredSpecificDataNotice" in source
    assert ".iu-fas-deposit-specific__field input:focus-visible" in css
    assert ".iu-fas-deposit-specific__repeat-row" in css
    assert "datiattoExtra" in data
    assert '"datiatto_extra": datiatto_extra' in api
    assert '"datiattoExtra": preparation_datiatto_extra' in bridge
    assert "deselectAllDepositDocuments" in source
    assert "const selectAllDepositDocuments" not in source
    assert "onClick={selectAllDepositDocuments}" not in source
    assert "Il software segnala i candidati; l'avvocato sceglie cosa entra nella busta" in source
    assert "const linkedDefaultDocuments = uniqueFascicoloDocuments(usableLinkedSlotDocuments.map((row) => row.document))" in source
    assert "const explicitDocumentSelection = requestedDocumentSelectionTokens.length > 0" in source
    assert "const defaultDepositSelectionIds = explicitDocumentSelection" in source
    assert "? requestedDepositSelectionIds" in source
    assert ": data.depositPreparation.saved" in source
    assert "Aggiungi documenti al deposito" in source
    assert "Cerca nel fascicolo" in source
    assert "includeDepositDocumentsByIds" in source
    assert "Carica da PC e inserisci nella busta" in source
    assert "onDone={handleDepositUploadDone}" in source
    assert "resultRecord.documenti_id" in source
    assert ".iu-fas-package-document-tools" in css
    assert ".iu-fas-package-docs__actions button" in css
    assert ": []" in source
    assert ": defaultMainActDocumentId ? [defaultMainActDocumentId] : []" not in source
    assert "depositCandidateDocuments]).map((doc) => doc.id)" not in source
    assert "buildDepositCatalogSlots(selectedDepositType, regia.documentSlots)" in source
    assert 'count={sortedSlots.length}' in source
    assert ".map((slot) => ({ ...slot, required: false, catalogAdvisory: true }))" in source
    assert 'catalogOnly' in source
    assert 'catalogRequirementKind' in source
    assert 'canLinkSlot' in source
    assert "ATTO_DA_NOTIFICARE" in source
    assert "atto_da_notificare" in source
    assert "baseSlotKey = slotKey === 'ATTO_DA_NOTIFICARE' ? 'ATTO_PRINCIPALE' : slotKey" in source
    assert "mainActBaseSlot" in source
    assert "actualBaseKey" in source
    assert "useCatalogLabel = slotKey === 'ATTO_DA_NOTIFICARE'" in source
    assert "catalogUsesNotifiableAct" in source
    assert "catalogUsesNotifiableAct && /atto principale|atto_principale/.test(text)" in source
    assert "regia.documentSlots.length" not in source[source.index('id="slot-deposito-rail"'):source.index('id="audit-deposito"')]
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
    assert ".iu-fas-deposit-selection__tools button.is-primary:hover" in css
    assert ".iu-fas-deposit-selection__tools button.is-primary:focus-visible" in css
    assert ".iu-fas-deposit-selection__tools button:focus-visible" in css
    assert "updateDepositClassification(doc.id" in source
    assert "[doc.id]: event.currentTarget.checked" not in source
    assert "depositSelectionSatisfiesSlot" in source
    assert "Scegli documento" in source
    assert "Collega" in source
    assert "Atto principale" in source
    assert "Prova senza invio reale" in source
    assert "Simula invio PEC" in source
    assert "Invia deposito reale" in source
    assert "IUSENTRA firma solo quelli scelti" in source
    assert "function DepositBatchSignaturePanel" in source
    assert "LOCAL_SIGNER_DEFAULT_BASE_URLS = ['http://127.0.0.1:27272', 'http://localhost:27272']" in source
    assert "LOCAL_SIGNER_BROWSER_PROBE_TIMEOUT_MS = 9000" in source
    assert "function localSignerCandidateBaseUrls" in source
    assert "window.setTimeout(() => controller.abort(), probeTimeoutMs)" in source
    assert "localSignerEndpointForPayload(endpoint, '/firma', signerStatus)" in source
    assert "localSignerEndpointForPayload(endpoint, '/pec/send', signerStatus)" in source
    assert "localSignerEndpointForStatus('/firma-batch', localSigner)" in source
    assert "LOCAL_SIGNER_BATCH_TIMEOUT_MS = 45000" in source
    assert "new AbortController()" in source
    assert "signal: controller.signal" in source
    assert "Local Signer non ha risposto entro 45 secondi" in source
    assert "Firma ${documents.length} documenti" in source
    assert "pinInputRef.current?.focus()" in source
    assert "recoverLocalSignerAutomatically" in source
    assert "localSignerOutdated" in source
    assert "Riallinea automaticamente" in source
    assert "canRequestLocalSignerProtocol" in source
    assert "if (signableDocuments.length) void checkLocalSigner(false)" in source
    assert "if (signableDocuments.length) void checkLocalSigner(true)" not in source
    assert "window.setTimeout(() => { void checkLocalSigner(false) }, delay)" in source
    assert "canRequestProtocolStart" in local_signer
    assert "activation?.isActive !== false" in local_signer
    assert "Riavvia Local Signer e premi Riverifica" not in source
    assert "Prima riavvia e riverifica Local Signer." not in source
    assert 'role="alert"' in source[source.index("function DepositBatchSignaturePanel"):source.index("function documentHasSignedContainerExtension")]
    assert "Versione firmata tramite firma multipla deposito" in source
    assert "Firma e prepara prova" in source
    assert "Il software non seleziona se la classificazione non è certa." in source
    assert "portal_upload" not in source[source.index("function DepositPreparePage"):source.index("function DepositBatchSignaturePanel")]


def test_ui_deposito_local_signer_usa_alias_sano_e_una_sola_sessione_pin():
    source = Path("frontend/src/components/FascicoloDepositoPage.tsx").read_text(encoding="utf-8")

    probe = source[
        source.index("async function fetchLocalSignerStatus"):
        source.index("async function pollLocalSignerStatus")
    ]
    assert "const probeTimeoutMs = candidateEndpoints.length > 1" in probe
    assert "if (!response.ok || payload?.ok !== true)" in probe
    assert "continue" in probe
    assert probe.index("if (!response.ok || payload?.ok !== true)") < probe.index("ok: true")
    assert "__iusentra_base_url: candidate.baseUrl" in probe
    assert "localSignerDetectedBaseUrl = candidate.baseUrl" in probe
    assert "ok: response.ok ? payload.ok : false" not in probe

    loopback_contract = source[
        source.index("function isLocalSignerLoopbackBaseUrl"):
        source.index("function localSignerLatestVersion")
    ]
    assert "parsed.protocol === 'http:'" in loopback_contract
    assert "['127.0.0.1', 'localhost'].includes(parsed.hostname)" in loopback_contract
    assert "parsed.port === '27272'" in loopback_contract
    assert "localSignerDetectedBaseUrl" in loopback_contract
    assert "LOCAL_SIGNER_DEFAULT_BASE_URLS[0]" in loopback_contract
    assert "isLocalSignerLoopbackBaseUrl(configured) ? configured : ''" in loopback_contract
    endpoint_payload = loopback_contract[
        loopback_contract.index("function localSignerEndpointForPayload"):
        loopback_contract.index("function localSignerProbeFailureMessage")
    ]
    assert endpoint_payload.count("return fallback") == 3
    assert "return raw" not in endpoint_payload

    deposit_page = source[
        source.index("function DepositPreparePage"):
        source.index("function DepositBatchSignaturePanel")
    ]
    complete_signature = deposit_page[
        deposit_page.index("const completeDepositLocalSignature"):
        deposit_page.index("const completeDepositLocalPec")
    ]
    assert "const reusablePinSessionId = batchSignaturePinSessionRef.current.trim()" in complete_signature
    assert "&& !reusablePinSessionId" in complete_signature
    assert "if (signerStatus && !reusablePinSessionId)" in complete_signature
    assert "if (!reusablePinSessionId && !localSignerStatusCanSign(signerStatus))" in complete_signature
    assert "pin_session_id: reusablePinSessionId || undefined" in complete_signature
    assert complete_signature.count("signatureResponse = await fetch(endpoint, requestOptions)") == 1
    assert "if (reusablePinSessionId) batchSignaturePinSessionRef.current = ''" in complete_signature

    prepare_signature = deposit_page[
        deposit_page.index("const runBatchSignatureBeforeDeposit"):
        deposit_page.index("const resetDepositSelectionToProposal")
    ]
    assert "batchSignaturePinSessionRef.current = ''" in prepare_signature
    assert "if (!result?.pinSessionId)" in prepare_signature
    assert "senza aprire la sessione PIN unica richiesta per DatiAtto.xml" in prepare_signature
    assert "batchSignaturePinSessionRef.current = result.pinSessionId" in prepare_signature

    batch_panel = source[
        source.index("function DepositBatchSignaturePanel"):
        source.index("function documentHasSignedContainerExtension")
    ]
    sign_all = batch_panel[batch_panel.index("const signAll = async () =>"):batch_panel.index("useEffect(() => {", batch_panel.index("const signAll = async () =>"))]
    assert sign_all.count("signResponse = await fetch(localSignerEndpointForStatus('/firma-batch', localSigner), requestOptions)") == 1
    assert "const pinSessionId = recordText(payload, 'pin_session_id')" in sign_all
    assert "pinSessionId: pinSessionId || undefined" in sign_all

    package_actions = deposit_page[
        deposit_page.index('className="iu-fas-package-actions"'):
        deposit_page.index("{packagePreview ? (")
    ]
    assert package_actions.count("completeLocalPec={completeDepositLocalPec}") == 1
    assert package_actions.index("completeLocalPec={completeDepositLocalPec}") > package_actions.index('confirmTitle="Invia deposito reale"')


def test_ui_deposito_avvisi_classificazione_non_spengono_prova_e_non_autoselezionano_tutto():
    source = Path("frontend/src/components/FascicoloDepositoPage.tsx").read_text(encoding="utf-8")
    slot_logic = source[source.index("function depositSelectionSatisfiesSlot"):source.index("type MissingDepositSlotsInput")]
    deposit_page = source[source.index("function DepositPreparePage"):source.index("function DepositBatchSignaturePanel")]

    assert "const actionBlocked = !selectedDepositType || !mainActDocument || !officeRecipientReady" in deposit_page
    assert "const proofActionBlocked = loading || !f.id || !dryRunBustaAction" in deposit_page
    assert "const requiredDepositDataBlocked = missingRequiredSlots.length > 0" in deposit_page
    assert deposit_page.count("disabled={proofActionBlocked}") >= 2
    assert "disabled={actionBlocked || requiredDepositDataBlocked || !packageReadyForRealSend || !realSendAvailable}" in deposit_page
    assert "La prova resta eseguibile: il controllo segnalerà il requisito mancante senza inviare nulla." in deposit_page
    assert "Durante la prova il dispositivo firma i dati del deposito" in deposit_page
    assert "Boolean(missingRequiredSlots.length) || !officeRecipientReady" not in deposit_page
    assert "requiredChoicesNotice" in deposit_page
    assert "La scelta salvata dall’avvocato nei Documenti da inviare resta prevalente" in deposit_page
    assert "Avviso non bloccante" in deposit_page
    assert "Avviso da verificare" in deposit_page
    assert "scelte obbligatorie richiedono la selezione dell’avvocato" not in source
    assert "scelte obbligatorie richiedono la conferma dell’avvocato" not in source
    assert slot_logic.index("if (/atto principale") < slot_logic.index("const linkedDocumentId")
    assert "documenti_selezionati_ids: packageDocuments.map((doc) => doc.id)" in deposit_page
    assert "const defaultDepositSelectionIds = uniqueFascicoloDocuments([...softwareProposedDocuments, ...depositCandidateDocuments]).map((doc) => doc.id)" not in source
    assert "depositCandidateDocuments]).map((doc) => doc.id)" not in source
    assert "Invia tutto" not in source


def test_ui_deposito_tipo_e_documenti_richiedono_la_scelta_dell_avvocato():
    source = Path("frontend/src/components/FascicoloDepositoPage.tsx").read_text(encoding="utf-8")
    panel = source[source.index("function DepositTypePreviewPanel"):source.index("function DepositActionButton")]

    assert "if (selectedKey !== selectedType.key) onSelect(selectedType.key)" not in panel
    assert "const selectedType = selectedByKey?.type" in panel
    assert '<option value="">Scegli il tipo di deposito</option>' in panel
    assert "onSelect('')" in panel
    assert "suggestedDepositTypeKey" not in source
    assert "autoSelectedDepositTypeKeyRef" not in source
    assert "const actionBlocked = !selectedDepositType || !mainActDocument || !officeRecipientReady" in source
    assert "Scegli il tipo di deposito prima di preparare la prova." in source


def test_ui_deposito_prova_guidata_non_salta_firma_e_mostra_audit_pec_indice():
    source = Path("frontend/src/components/FascicoloDepositoPage.tsx").read_text(encoding="utf-8")
    css = Path("frontend/src/components/FascicoliPage.css").read_text(encoding="utf-8")

    deposit_page = source[source.index("function DepositPreparePage"):source.index("function DepositBatchSignaturePanel")]
    action_button = source[source.index("function DepositActionButton"):source.index("function DepositPdfPreviewButton")]
    preview_button = source[source.index("function DepositPdfPreviewButton"):source.index("function JsonPostForm")]

    assert "const officeRecipientReady" in deposit_page
    assert "const depositOfficePecAvailable = Boolean(data.depositOffice.pec)" in deposit_page
    assert "const depositOfficeCodeAvailable = Boolean(data.depositOffice.code || data.depositOffice.ministerialCode)" in deposit_page
    assert "const depositOfficeVerified = Boolean(data.depositOffice.verified && depositOfficePecAvailable)" in deposit_page
    assert "const pecWorkflowAvailable = depositOfficePecAvailable" in deposit_page
    assert "directPecAllowed || guidedCompletion || pctJsonPackageChannel" in deposit_page
    assert "IUSENTRA non ha risolto automaticamente la PEC dell’ufficio" in deposit_page
    assert "IUSENTRA non ha risolto automaticamente il codice dell’ufficio" in deposit_page
    assert "Manca la PEC dell’ufficio" not in deposit_page
    assert "Manca il codice dell’ufficio" not in deposit_page
    assert "PEC ufficio da indicare" not in deposit_page
    assert "Codice ufficio da indicare" not in deposit_page
    assert "Codice ufficio presente: il certificato viene controllato nella prova." in deposit_page
    assert "const pecWorkflowAvailable = Boolean(data.depositOffice.verified && data.depositOffice.pec)" not in deposit_page
    assert "PEC dell’ufficio non verificata" not in deposit_page
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
    assert "if (!result?.pinSessionId)" in source
    assert "batchSignaturePinSessionRef.current = result.pinSessionId" in source
    assert "const unsignedCandidateDocuments = unsignedPackageDocuments.length" in deposit_page
    assert "depositCandidateDocuments.filter((doc) => !doc.signed && requiresPackageSignature(doc)).length" not in deposit_page
    assert "metadato ministeriale della busta, non un allegato da scegliere" not in deposit_page
    assert "Il software firma i dati del deposito sul PC in uso" in deposit_page
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
    assert "progressItems={DEPOSIT_PROGRESS_USER_STEPS}" in deposit_page
    assert "progressItems={['DatiAtto.xml'" not in deposit_page
    assert "progressLabel=\"Invio deposito in corso\"" in deposit_page
    assert "iu-fas-package-progress__ticker" in action_button
    assert 'id="dati-specifici-deposito"' in source
    assert "goToDepositPhase('proposta-busta', 'auto')" in deposit_page
    assert "message.startsWith('Completa i dati obbligatori del deposito:')" in action_button
    assert "Completa dati deposito" in deposit_page
    assert "const pctJsonPackageChannel" in deposit_page
    assert "const realSendAction = (directPecReady || guidedCompletion || pctJsonPackageChannel) ? jsonPecAction : downloadBustaAction" in deposit_page
    assert "result.requires_local_signature && completeLocalSignature" in action_button
    assert "setConfirming(false)\n      const completion = await completeLocalSignature(result, submittedPayload)" in action_button
    assert "setLocalSignaturePinRequest(null)\n    request.resolve(pinValue)" in deposit_page
    assert "if (!reusablePinSessionId && !localSignerStatusCanSign(signerStatus))" in deposit_page
    assert "Dispositivo non pronto per firmare i dati del deposito" in deposit_page
    assert "Local Signer non raggiungibile dal browser per firmare i dati del deposito" in deposit_page
    assert "async function parseLocalSignerResponse" in source
    assert "const signaturePayload = await parseLocalSignerResponse(signatureResponse)" in deposit_page
    assert "const payload = await parseLocalSignerResponse(signResponse)" in source
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
    assert "Pacchetto deposito non valido" in source
    assert "looksLikeCmsEnvelopedData" in source
    assert "CMS_ENVELOPED_DATA_OID" in source
    assert "Pacchetto deposito non conforme" in source
    assert "Pacchetto deposito non verificato" in source
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
    proof_start = deposit_page.index("const proofBlocksDirectSend = Boolean(")
    proof_end = deposit_page.index("  const compatibilityReport", proof_start)
    proof_block = deposit_page[proof_start:proof_end]
    assert "packagePreview?.requiresGuidedCompletion" not in proof_block
    assert "packagePreview?.pecSenderReady === false" in proof_block
    assert "recordBool(packagePreview?.bustaAudit, 'blocks_direct_send')" in proof_block
    assert "recordBool(packagePreview?.bustaAudit, 'guided_completion_required')" in proof_block
    assert "function depositHasPersistedDryRunProof" not in source
    assert "setDepositProofInvalidated(true)" in deposit_page
    assert "const packageReadyForRealSend = Boolean(packagePreview?.packageReady && !depositProofInvalidated)" in deposit_page
    assert "disabled={actionBlocked || requiredDepositDataBlocked || !packageReadyForRealSend || !realSendAvailable}" in deposit_page
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


def test_ui_deposito_controlla_i_dati_prima_di_qualsiasi_scrittura_e_abilita_invio_solo_dopo_prova_corrente():
    source = Path("frontend/src/components/FascicoloDepositoPage.tsx").read_text(encoding="utf-8")
    start = source.index("const prepareDepositBeforeSubmit = async () => {")
    end = source.index("const selectedDepositPayload", start)
    block = source[start:end]

    assert block.index("if (missingRequiredDepositSpecificFields.length)") < block.index("await submitDepositClassification()")
    assert "goToDepositPhase('proposta-busta', 'auto')" in block
    assert "const packageReadyForRealSend = Boolean(packagePreview?.packageReady && !depositProofInvalidated)" in source
    assert "setDepositProofInvalidated(false)" in source


def test_ui_notifiche_relata_firma_solo_con_prova_tecnica():
    source = Path("frontend/src/components/NotificheLegaliPage.tsx").read_text(encoding="utf-8")
    css = Path("frontend/src/components/NotificheLegaliPage.css").read_text(encoding="utf-8")
    api_source = Path("web/blueprints/api_v1_react.py").read_text(encoding="utf-8")
    signature_block = source[source.index("const signCurrentRelataWithLocalSigner = async ("):source.index("const sendNotificationTitle")]

    assert "signatureHref" not in source
    assert "Apri firma digitale" not in source
    assert "Apri la firma digitale" not in source
    assert "IUSENTRA genera la relata corrente e la salva nel fascicolo dopo la firma sul PC." in source
    assert "PIN dispositivo" in source
    assert "ensureRelataSignerReady()" in signature_block
    assert "relataLocalSignerEndpoint('/firma')" in signature_block
    assert "fileContainsCadesSignedData" in source
    assert "pdfContainsPadesSignature" in source
    assert "signedDataOid" in source
    assert "Relata firmata non verificabile." in source
    assert "non contiene una busta CAdES/PKCS#7 riconoscibile" not in source
    assert "setNotifica((current) => ({ ...current, relata_firmata: false }))" in signature_block
    assert "<input type=\"checkbox\" checked={notifica.relata_firmata} readOnly disabled />" not in source
    assert "Relata da firmare" not in source
    assert "Conferma avvocato registrata" not in source
    assert "Relata firmata e salvata nel fascicolo" in source
    assert ".iu-legal-signature-button" in css
    assert "hasNotifiableExtension" in source
    assert "hasEmailEvidenceExtension" in source
    assert "automaticAttestationDocument" not in source
    assert "Elenco finale atti della relata" in source
    assert "finalRelataRows" in source
    assert "Relata di notifica.pdf" in source
    assert "Attestazione di conformità.pdf" in source
    assert "Attestazione unica nella relata" not in source
    assert "Una sola dichiarazione comprende" in source
    assert "Salva nel fascicolo" in source
    assert "Scarica PDF" not in source
    assert "saveLegalAttestationPdfToFile" in source
    assert "attestazione_conformita_file" in source
    assert "attestazione_multipla: notificationNeedsAttestazione" in source
    assert "deriveProceedingRg" in source
    apply_practice = source[source.index("const applyPractice"):source.index("const buildNotificaPayload")]
    assert "setSelectedNotificationDocumentIds([])" in apply_practice
    hydration = source[source.index("useEffect(() => {\n    if (!selectedPracticeId"):source.index("const applyDocument")]
    assert "autoSelectableDocuments" not in hydration
    assert "setNotifica" not in hydration
    notification_payloads = source[source.index("const notificationDocumentPayloads"):source.index("const addManualNotificationDocument")]
    assert "const rows = [...selectedRows, ...uploadedRows]" in notification_payloads
    assert "manualNotificationDocument()" not in notification_payloads
    toggle_notification = source[source.index("const toggleNotificationDocument"):source.index("const applyPractice")]
    assert "setNotifica" not in toggle_notification
    assert "solo quelli spuntati entrano nella relata" in source
    assert "disabled={!canPrepareNotificationSend}" in source
    assert "const canPrepareNotificationSend = !notificationControlBusy && !localPecPasswordRequest" in source
    assert "Invia PEC reale dal PC locale con flusso Studio Telematico" in source
    assert "localPecEndpointForStudioTelematico" in source
    assert "relataLocalSignerEndpoint('/pec/send')" in source
    assert "data.azioni.invioPecLocale" in source
    assert "data.azioni.confermaInvioPecLocale" in source
    assert "Piano PEC non coerente con Studio Telematico" in source
    assert "Message-ID" in source
    assert "Avanzamento invio PEC" in source
    assert "LOCAL_PEC_PROGRESS_STEPS" in source
    assert "iu-legal-local-pec-progress__bar" in source
    assert "Conferma invio PEC dal PC locale" in source
    assert ".iu-legal-local-pec-progress" in css
    assert ".iu-legal-local-pec-panel" in css
    assert "Invio PEC bloccato" not in source
    assert 'accept=".pdf,.pdfa,.p7m,.eml,.msg"' in source
    assert "Tutti notificabili" not in source
    assert "Scegli i documenti del fascicolo: solo quelli spuntati entrano nella relata." in source
    assert "Calcolo impronte degli allegati" not in source
    assert "Allegati aggiunti alla notifica." in source
    assert "non blocca l'invio PEC" in source
    assert "Impronta diversa per" not in api_source
    assert "allegato non coincidente" not in api_source
    assert "<em>Fascicolo</em>" in source
    assert "<em>Presidio</em>" in source
    assert "<em>Manuale</em>" in source
    assert "const visibleModelFields = useMemo" in source
    assert "modelFieldIsCoveredByGuidedNotification" in source
    assert "'avvocato.full.name'" in source
    assert "'procedimento.numero.rg'" in source
    assert "'procedimento.anno.rg'" in source
    assert "'provvedimento.tipo'" in source
    assert "{visibleModelFields.length ? (" in source
    assert "selectedTemplate?.fields.length ? (" not in source
    assert "const modelFieldsForPayload = useMemo" in source
    assert "String(value || '').trim()" in source
    assert "template_fields: modelFieldsForPayload" in source
    assert "template_fields: modelFields," not in source


def test_ui_notifiche_mantiene_indirizzi_generali_e_preselezione_documenti():
    source = Path("frontend/src/components/NotificheLegaliPage.tsx").read_text(encoding="utf-8")
    css = Path("frontend/src/components/NotificheLegaliPage.css").read_text(encoding="utf-8")

    assert "const visibleRecipientSuggestions = useMemo" in source
    assert "if (!query) return recipientSuggestions" in source
    assert "practiceRecipientSuggestionKeys" in source
    assert "Cerca indirizzo o soggetto" in source
    assert "Uffici NEP / UNEP" in source
    assert "getNotificheLegaliPracticeDocuments(selectedPracticeId, requestedDocumentSelectionTokens)" in source
    assert "documentMatchesSelectionTokens(documento, requestedDocumentSelectionTokens)" in source
    assert "if (!data.precompilazione.indicePratiche.length || selectedPracticeId) return" not in source
    assert "documentViewHref(documento)" in source
    assert "openDocumentPreview(documento)" in source
    assert "iu-legal-document-preview-modal" in source
    assert "<iframe title={`Documento ${documentPreview.title}`} src={documentPreview.href} />" in source
    assert "Visualizza documento" in source
    assert "Eye size={15}" in source
    assert "event.stopPropagation()" in source
    assert 'className="iu-legal-document-view"\n                                  href={viewHref}\n                                  target="_blank"' not in source
    assert ".iu-legal-unep-quick" in css
    assert ".iu-legal-document-view" in css
    assert ".iu-legal-document-preview-modal" in css


def test_ui_fascicolo_notifica_e_deposito_partono_da_documenti_scelti():
    source = Path("frontend/src/components/FascicoliPage.tsx").read_text(encoding="utf-8")
    css = Path("frontend/src/components/FascicoliPage.css").read_text(encoding="utf-8")

    assert "DocumentFlowSelectionModal" in source
    assert "appendSelectedDocumentsToHref" in source
    assert "parsed.searchParams.set('documenti', documentIds.join(','))" in source
    assert 'href={targetHref}' in source
    assert 'href={baseHref}>Apri senza selezione' in source
    assert "openDocumentFlow('notifica')" in source
    assert "openDocumentFlow('deposito')" in source
    assert "compareDocumentFlowByRecentDate" in source
    assert "documentFlowDateTimestamp(doc.documentDate)" in source
    assert "|| documentFlowDateTimestamp(doc.uploadedAt)" in source
    assert "|| documentFlowDateTimestamp(doc.portalDate)" in source
    assert "const sortedDocuments = useMemo(() => [...documents].sort(compareDocumentFlowByRecentDate), [documents])" in source
    assert "if (!tokens.length) return sortedDocuments" in source
    assert "const suggestedIds = useMemo(() => sortedDocuments" in source
    assert "const selectedDocuments = sortedDocuments.filter" in source
    assert "Documenti ordinati dal più recente" in source
    assert ".iu-fas-document-flow-modal" in css


def test_ui_fascicolo_menu_contestuale_azioni_reali():
    source = Path("frontend/src/components/FascicoliPage.tsx").read_text(encoding="utf-8")
    office_source = Path("frontend/src/components/OfficeDocumentsPanel.tsx").read_text(encoding="utf-8")
    css = Path("frontend/src/components/FascicoliPage.css").read_text(encoding="utf-8")

    assert "FascicoloContextMenu" in source
    assert 'onContextMenu={openFascicoloContextMenu}' in source
    assert "shouldUseNativeContextMenu(event.target)" in source
    assert "const menuHeight = Math.min(620, window.innerHeight * 0.86)" in source
    assert "const menuRef = useRef<HTMLElement | null>(null)" in source
    assert "firstItem?.focus({ preventScroll: true })" in source
    assert "Escape" in source
    assert "const onScroll = (event: Event)" in source
    assert "event.target instanceof Element && event.target.closest('.iu-fas-context-menu')" in source
    assert "Deposito telematico" in source
    assert "Modifica anagrafica cliente" in source
    assert "Soggetti" in source
    assert "Fascicolo d’ufficio" in source
    assert "Apri Portale Servizi" in source
    assert "Notifica" in source
    assert "PagoPA" in source
    assert "Controllo economico" in source
    assert "Calcola contributo unificato" in source
    assert "ContributoUnificatoModal" in source
    assert "onContributoUnificato" in source
    assert "openContributoUnificatoFromContext" in source
    assert "fetch('/strumenti-legali/api/contributo-unificato'" in source
    assert "fetch(`/strumenti-legali/api/prefill/${encodeURIComponent(fascicolo.id)}`" in source
    assert "CONTRIBUTION_MEMORY_STORAGE_PREFIX" in source
    assert "sessionStorage.setItem(contributionStorageKey(memory.fascicoloId)" in source
    assert "copyTextForUser(memory.copyText)" in source
    assert "Copia e apri PagoPA" in source
    assert "Calcolo contributo in memoria" in source
    assert "iu-fas-embedded-modal--pagopa-memory" in source
    assert "iu-fas-embedded-modal--fullscreen" in source
    assert "Tutto schermo" in source
    assert "tryPrefillPagoPaFrame" in source
    assert "Oggetto del ricorso" in source
    assert "Totale da usare per PagoPA" in source
    assert "Nuovo pagamento PagoPA PST" in source
    assert "Nuova scadenza" in source
    assert "Nuovo appuntamento" in source
    assert "openDocumentFlow('deposito')" in source
    assert "openDocumentFlow('notifica')" in source
    assert "openOfficePortalFromContext" in source
    assert "setOfficePortalOpenRequest((current) => current + 1)" in source
    assert "openPortalRequest={officePortalOpenRequest}" in source
    assert "setEmbeddedRecord({ kind: 'cliente', title: 'Modifica anagrafica cliente'" in source
    assert "setEmbeddedRecord({ kind: 'soggetti', title: 'Soggetti e parti'" in source
    assert "setEmbeddedRecord({ kind: 'pagopa', title: 'Nuovo pagamento PagoPA PST'" in source
    assert "onEconomicControl" in source
    assert "EconomicControlModal" in source
    assert "Modifica controllo economico" in source
    assert "EconomicEditorPanel row={f}" in source
    assert "Riepilogo controllo" in source
    assert "Proforma da preparare" in source
    assert "Importo o fonte economica letta dal fascicolo: verifica se emettere la proforma." in source
    assert "Presidio operativo aggiornato" in source
    assert "remainingActions.slice(0, 5)" in source
    assert "Ricevuta pagoPA" in source
    assert "Parcella da emettere" in source
    assert "Import pratiche" in source
    assert "onSection('documenti', 'documenti')" in source

    assert "openPortalRequest?: number" in office_source
    assert "openPortalRequest = 0" in office_source
    assert "lastOpenPortalRequest" in office_source
    assert "void openAssistedPortal()" in office_source

    assert ".iu-fas-context-menu" in css
    assert ".iu-fas-context-menu__item" in css
    assert ".iu-fas-contributo-modal" in css
    assert ".iu-fas-contributo-result__metrics" in css
    assert ".iu-fas-pagopa-memory" in css
    assert ".iu-fas-embedded-modal--pagopa-memory .iu-fas-embedded-modal__body{grid-template-rows:auto auto minmax(0,1fr)}" in css
    assert ".iu-fas-embedded-modal--fullscreen" in css
    assert ".iu-fas-pagopa-prefill" in css
    assert ".iu-fas-economic-control-modal" in css
    assert ".iu-fas-economic-control-modal__rows" in css
    assert ".iu-fas-economic-control-modal__editor" in css
    assert ".iu-fas-economic-control-modal__editor-head span,.iu-fas-economic-control-modal__editor-head p" in css
    assert "@media(max-width:900px)" in css and ".iu-fas-context-menu{left:8px!important" in css
    assert ".iu-fas-contributo-form{grid-template-columns:1fr}" in css


def test_ui_deposito_accetta_documenti_preselezionati_da_query_fascicolo():
    source = Path("frontend/src/components/FascicoloDepositoPage.tsx").read_text(encoding="utf-8")

    assert "documentSelectionTokensFromUrl" in source
    assert "requestedDepositSelectionIds" in source
    assert "explicitDocumentSelection" in source
    assert "fascicoloDocumentMatchesSelectionTokens(doc, requestedDocumentSelectionTokens)" in source
    assert "Scelta dal fascicolo" in source
