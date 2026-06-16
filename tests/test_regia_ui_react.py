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
    assert "defaultDepositRoleForDocument" in source
    assert "normaliseDepositClassificationMainAct" in source
    assert "deposito/classifica-documenti" in source
    assert "manualSelectableDocuments" in source
    assert "isDepositManualSelectableDocument" in source
    assert "documenti_selezionati_ids" in source
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
    assert "Riavvia Local Signer e premi Riverifica" in source
    assert "Prima riavvia e riverifica Local Signer." in source
    assert 'role="alert"' in source[source.index("function DepositBatchSignaturePanel"):source.index("function relataStatusDisplayLabel")]
    assert "Versione firmata tramite firma multipla deposito" in source
    assert "Genera controllo e indice" in source
    assert "Il software non seleziona se la classificazione non è certa." in source
    assert "portal_upload" not in source[source.index("function DepositPreparePage"):source.index("function NotificationRelataMonitor")]
