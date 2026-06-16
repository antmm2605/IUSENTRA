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
    assert "Genera busta pronta" in source
    assert "comando finale" in source
    assert "function DepositBatchSignaturePanel" in source
    assert "localSignerEndpoint('/firma-batch')" in source
    assert "Firma ${documents.length} documenti" in source
    assert "pinInputRef.current?.focus()" in source
    assert "recoverLocalSignerAutomatically" in source
    assert "localSignerOutdated" in source
    assert "Riallinea automaticamente" in source
    assert "Riavvia Local Signer e premi Riverifica" not in source
    assert "Prima riavvia e riverifica Local Signer." not in source
    assert 'role="alert"' in source[source.index("function DepositBatchSignaturePanel"):source.index("function relataStatusDisplayLabel")]
    assert "Versione firmata tramite firma multipla deposito" in source
    assert "Genera controllo e indice" in source
    assert "Il software non seleziona se la classificazione non è certa." in source
    assert "portal_upload" not in source[source.index("function DepositPreparePage"):source.index("function NotificationRelataMonitor")]
