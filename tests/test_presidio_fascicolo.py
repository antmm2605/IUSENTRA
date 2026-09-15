"""Il presidio del fascicolo dice la verità: la busta si valida quando si deposita.

Tre difetti visti in produzione sul fascicolo di lavoro FF6E8CC0:
il presidio bloccava il fascicolo per PDF/A e firma di documenti che nessuno
stava depositando; la percentuale restava al 33% con tutte le voci «da
completare»; il deposito risultava «non inviato» mentre era stato inviato e
accettato dalla cancelleria. Qui si verifica che non possano tornare.
"""

from __future__ import annotations

from types import SimpleNamespace

from pct.fascicoli import EsitoDepositoPCT, TipoDocumento
from pct.practice_engine.completamento import completamento
from pct.practice_engine.deposit_readiness import run_predeposit_check
from pct.practice_engine.evaluator import build_regia_payload
from pct.practice_engine.fase_deposito import deposito_reale, fase_deposito
from pct.practice_engine.models import ValidatorStatus
from pct.practice_engine.voci_checklist import controlli_della_voce, stato_voce

from tests.regia_test_utils import link_required_documents, make_simple_fascicolo, pdfa_bytes, prepara_busta


# Il profilo del fascicolo visto in produzione: la checklist è fatta di voci
# che riassumono i controlli della busta telematica.
PROCEDURA_RETRIBUZIONE = "PROC_LAV_RETRIB_001"


def _cliente():
    return SimpleNamespace(codice_fiscale="RSSMRA80A01H501U", email="cliente@example.test")


def _deposito(stato: str, *, timestamp: str = "2026-09-01T10:00:00", documenti: list[str] | None = None) -> EsitoDepositoPCT:
    return EsitoDepositoPCT(
        id=f"dep-{stato.lower()}",
        timestamp=timestamp,
        stato=stato,
        tipo_atto="RICORSO",
        pec_destinatario="tribunale.palmi@giustiziacert.it",
        documenti_ids=list(documenti or []),
    )


# ── Fase di deposito ────────────────────────────────────────────────────────

def test_senza_busta_preparata_non_si_e_in_fase_di_deposito(tmp_path):
    _gf, _repo, fascicolo, profile = make_simple_fascicolo(tmp_path)
    fase = fase_deposito(fascicolo, profilo=profile)
    assert fase.codice == "non_richiesta"
    assert fase.in_deposito is False
    assert "quando prepari il deposito" in fase.motivo


def test_con_la_busta_preparata_si_e_in_fase_di_deposito(tmp_path):
    gf, repo, fascicolo, profile = make_simple_fascicolo(tmp_path)
    atto, _procura = link_required_documents(gf, repo, fascicolo)
    fascicolo = prepara_busta(gf, gf.get(fascicolo.id), documenti=[atto])
    fase = fase_deposito(fascicolo, profilo=profile)
    assert fase.codice == "preparazione"
    assert fase.in_deposito is True
    assert fase.documenti_busta == (atto.id,)


def test_i_documenti_non_scelti_non_entrano_nella_busta(tmp_path):
    gf, repo, fascicolo, profile = make_simple_fascicolo(tmp_path)
    atto, procura = link_required_documents(gf, repo, fascicolo)
    fascicolo = gf.get(fascicolo.id)
    profilo = dict(fascicolo.profilo_deposito or {})
    profilo["preparazione_busta"] = {
        "tipo_deposito_telematico_key": "RicorsoLavoro",
        "documents": [
            {"documentId": atto.id, "selected": True, "role": "atto_principale"},
            {"documentId": procura.id, "selected": False, "role": "procura"},
        ],
    }
    fascicolo = gf.aggiorna_preparazione_deposito(fascicolo.id, document_updates=[], profilo_deposito=profilo)
    assert fase_deposito(fascicolo, profilo=profile).documenti_busta == (atto.id,)


def test_un_deposito_gia_accettato_non_riapre_la_fase_di_deposito(tmp_path):
    gf, _repo, fascicolo, profile = make_simple_fascicolo(tmp_path)
    fascicolo = gf.aggiorna(fascicolo.id, depositi_pct=[_deposito("ACCETTATO_CANCELLERIA")])
    fase = fase_deposito(fascicolo, profilo=profile)
    assert fase.in_deposito is False
    assert "già stato eseguito" in fase.motivo


def test_un_deposito_in_attesa_di_ricevute_tiene_aperta_la_fase(tmp_path):
    gf, _repo, fascicolo, profile = make_simple_fascicolo(tmp_path)
    fascicolo = gf.aggiorna(fascicolo.id, depositi_pct=[_deposito("CONSEGNATO", documenti=["doc-1"])])
    fase = fase_deposito(fascicolo, profilo=profile)
    assert fase.codice == "in_corso"
    assert fase.documenti_busta == ("doc-1",)


# ── Stato reale del deposito ────────────────────────────────────────────────

def test_il_deposito_accettato_non_puo_risultare_non_inviato(tmp_path):
    gf, _repo, fascicolo, _profile = make_simple_fascicolo(tmp_path)
    fascicolo = gf.aggiorna(
        fascicolo.id,
        depositi_pct=[_deposito("INVIATO", timestamp="2026-08-01T09:00:00"), _deposito("ACCETTATO_CANCELLERIA", timestamp="2026-08-03T11:30:00")],
    )
    deposito = deposito_reale(fascicolo)
    assert deposito.presente is True
    assert deposito.stato == "ACCETTATO_CANCELLERIA"
    assert deposito.etichetta == "Accettato dalla cancelleria"
    assert deposito.stato_operativo == "ACQUISITO"


def test_senza_depositi_il_deposito_reale_e_assente(tmp_path):
    _gf, _repo, fascicolo, _profile = make_simple_fascicolo(tmp_path)
    assert deposito_reale(fascicolo).presente is False


# ── Controlli di predeposito ────────────────────────────────────────────────

def test_fuori_dal_deposito_nessun_controllo_della_busta_blocca(tmp_path):
    gf, repo, fascicolo, profile = make_simple_fascicolo(tmp_path)
    readiness = run_predeposit_check(repo, fascicolo=fascicolo, profile=profile, cliente=_cliente(), fascicoli_manager=gf)
    assert readiness["status"] == "NON_IN_DEPOSITO"
    assert readiness["blockers"] == []
    rinviati = [item for item in readiness["results"] if item.source == "practice_engine.fase_deposito"]
    assert rinviati and all(item.status == ValidatorStatus.NOT_APPLICABLE.value for item in rinviati)


def test_in_fase_di_deposito_i_controlli_della_busta_tornano_a_valere(tmp_path):
    gf, repo, fascicolo, profile = make_simple_fascicolo(tmp_path)
    fascicolo = prepara_busta(gf, fascicolo)
    readiness = run_predeposit_check(repo, fascicolo=fascicolo, profile=profile, cliente=_cliente(), fascicoli_manager=gf)
    assert readiness["status"] == "BLOCCANTE"
    assert any(item.status == ValidatorStatus.BLOCK.value for item in readiness["blockers"])


# ── Voci della checklist ────────────────────────────────────────────────────

def test_ogni_voce_di_busta_ha_i_suoi_controlli():
    for chiave, etichetta in (
        ("CODICE_OGGETTO_PST", "Codice oggetto PST ufficiale"),
        ("CLASSIFICAZIONE_ATTI", "Classificazione atti e allegati"),
        ("FIRMA_E_BUSTA", "Firma digitale e busta ministeriale"),
        ("VERIFICA_DATI", "Verifica dati cliente e parti"),
    ):
        voce = SimpleNamespace(key=chiave, label=etichetta, message="", suggested_action="")
        assert controlli_della_voce(voce), f"voce senza controlli: {chiave}"


def test_una_voce_si_completa_quando_i_suoi_controlli_sono_verdi():
    voce = SimpleNamespace(key="VERIFICA_DATI", label="Verifica dati cliente e parti", message="", suggested_action="")
    verdi = [
        SimpleNamespace(key=chiave, status=ValidatorStatus.OK.value, blocking=False, message="", suggested_action="")
        for chiave in controlli_della_voce(voce)
    ]
    esito = stato_voce(voce, verdi)
    assert esito["stato"] == "COMPLETATO"
    assert esito["misurabile"] is True


def test_una_voce_di_busta_fuori_dal_deposito_e_rinviata_non_da_completare():
    voce = SimpleNamespace(key="FIRMA_E_BUSTA", label="Firma digitale e busta ministeriale", message="", suggested_action="")
    esito = stato_voce(voce, [], in_deposito=False, motivo_rinvio="Nessun deposito in preparazione.")
    assert esito["stato"] == "NON_PERTINENTE"
    assert esito["misurabile"] is False
    assert esito["messaggio"] == "Nessun deposito in preparazione."


def test_una_voce_bloccata_riporta_il_messaggio_del_controllo():
    voce = SimpleNamespace(key="FIRMA_E_BUSTA", label="Firma digitale e busta ministeriale", message="", suggested_action="")
    blocco = SimpleNamespace(
        key="firma_digitale_presente", status=ValidatorStatus.BLOCK.value, blocking=True,
        message="Atto principale non firmato digitalmente.", suggested_action="Firma l'atto principale.",
    )
    esito = stato_voce(voce, [blocco])
    assert esito["stato"] == "BLOCCATO"
    assert esito["messaggio"] == "Atto principale non firmato digitalmente."


# ── Percentuale di completamento ────────────────────────────────────────────

def test_la_percentuale_conta_solo_le_verifiche_misurabili():
    voci = [
        {"status": "COMPLETATO", "measured": True},
        {"status": "COMPLETATO", "measured": True},
        {"status": "NON_PERTINENTE", "measured": False},
        {"status": "DA_COMPLETARE", "measured": False},
    ]
    percentuale, dettaglio = completamento(voci, [], in_deposito=False, motivo_fase="Nessun deposito in preparazione.")
    assert percentuale == 100
    assert dettaglio["checklistMeasured"] == 2
    assert dettaglio["deferred"] == 1
    assert dettaglio["manual"] == 1


def test_la_percentuale_scende_quando_una_verifica_misurabile_non_e_superata():
    voci = [{"status": "COMPLETATO", "measured": True}, {"status": "BLOCCATO", "measured": True}]
    percentuale, dettaglio = completamento(voci, [])
    assert percentuale == 50
    assert dettaglio["checked"] == 1
    assert dettaglio["total"] == 2


def test_fuori_dal_deposito_i_documenti_non_collegati_non_abbassano_la_percentuale():
    slot_collegato = SimpleNamespace(required=True, document_id="doc-1", status="VALIDO")
    slot_vuoto = SimpleNamespace(required=True, document_id="", status="MANCANTE")
    percentuale, dettaglio = completamento([{"status": "COMPLETATO", "measured": True}], [slot_collegato, slot_vuoto], in_deposito=False)
    assert dettaglio["slotsRelevant"] == 1
    assert percentuale == 100


# ── Presidio completo ───────────────────────────────────────────────────────

def test_il_presidio_di_un_fascicolo_senza_deposito_non_e_bloccato(tmp_path):
    gf, repo, fascicolo, _profile = make_simple_fascicolo(tmp_path, procedure_code=PROCEDURA_RETRIBUZIONE)
    link_required_documents(gf, repo, fascicolo)
    payload = build_regia_payload(repo, fascicolo=gf.get(fascicolo.id), cliente=_cliente(), fascicoli_manager=gf)
    assert payload["validation"]["status"] == "NON_IN_DEPOSITO"
    assert payload["deposit"]["blockReasons"] == []
    assert payload["header"]["depositPhase"]["inDeposito"] is False
    assert payload["header"]["completion"] >= 50
    voci_busta = [voce for voce in payload["checklist"] if voce["status"] == "NON_PERTINENTE"]
    assert voci_busta, "le voci della busta devono risultare rinviate, non da completare"


def test_il_presidio_mostra_il_deposito_accettato(tmp_path):
    gf, repo, fascicolo, _profile = make_simple_fascicolo(tmp_path)
    link_required_documents(gf, repo, fascicolo)
    gf.aggiorna(fascicolo.id, depositi_pct=[_deposito("ACCETTATO_CANCELLERIA", timestamp="2026-08-03T11:30:00")])
    payload = build_regia_payload(repo, fascicolo=gf.get(fascicolo.id), cliente=_cliente(), fascicoli_manager=gf)
    assert payload["deposit"]["status"] == "ACCETTATO_CANCELLERIA"
    assert payload["deposit"]["statusLabel"] == "Accettato dalla cancelleria"
    assert payload["deposit"]["lastDeposit"]["presente"] is True
    assert payload["header"]["operationalState"] == "ACQUISITO"
    assert "Non inviato" not in payload["deposit"]["message"]


def test_il_completamento_del_presidio_e_spiegato(tmp_path):
    gf, repo, fascicolo, _profile = make_simple_fascicolo(tmp_path)
    link_required_documents(gf, repo, fascicolo)
    payload = build_regia_payload(repo, fascicolo=gf.get(fascicolo.id), cliente=_cliente(), fascicoli_manager=gf)
    dettaglio = payload["header"]["completionDetail"]
    assert dettaglio["total"] == dettaglio["checklistMeasured"] + dettaglio["slotsRelevant"]
    assert dettaglio["checked"] == dettaglio["checklistPassed"] + dettaglio["slotsPassed"]
    assert payload["header"]["completion"] == (int(round(dettaglio["checked"] / dettaglio["total"] * 100)) if dettaglio["total"] else 100)


def test_un_documento_non_pdfa_blocca_solo_quando_si_deposita(tmp_path):
    gf, repo, fascicolo, _profile = make_simple_fascicolo(tmp_path)
    non_conforme = gf.aggiungi_documento(fascicolo.id, "copia_portale.pdf", TipoDocumento.ATTO_GIUDIZIARIO, b"%PDF-1.4\n1 0 obj<<>>endobj\n%%EOF", firmato=False)
    repo.link_slot(fascicolo.id, "ATTO_PRINCIPALE", non_conforme.id, actor="test")
    payload = build_regia_payload(repo, fascicolo=gf.get(fascicolo.id), cliente=_cliente(), fascicoli_manager=gf)
    assert payload["deposit"]["blocked"] is False

    prepara_busta(gf, gf.get(fascicolo.id), documenti=[non_conforme])
    payload = build_regia_payload(repo, fascicolo=gf.get(fascicolo.id), cliente=_cliente(), fascicoli_manager=gf)
    assert payload["deposit"]["blocked"] is True
    assert payload["deposit"]["blockReasons"]


def test_i_motivi_di_blocco_non_si_ripetono(tmp_path):
    gf, repo, fascicolo, _profile = make_simple_fascicolo(tmp_path)
    prepara_busta(gf, fascicolo)
    payload = build_regia_payload(repo, fascicolo=gf.get(fascicolo.id), cliente=_cliente(), fascicoli_manager=gf)
    motivi = payload["deposit"]["blockReasons"]
    assert len(motivi) == len(set(motivi))


def test_pdfa_bytes_resta_conforme():
    assert b"pdfaid:part" in pdfa_bytes()


def test_la_data_del_deposito_si_mostra_in_formato_italiano(tmp_path):
    gf, _repo, fascicolo, _profile = make_simple_fascicolo(tmp_path)
    fascicolo = gf.aggiorna(fascicolo.id, depositi_pct=[_deposito("ACCETTATO_CANCELLERIA", timestamp="2026-08-03T11:30:00")])
    deposito = deposito_reale(fascicolo)
    assert deposito.data_it == "03/08/2026"
    assert deposito.to_dict()["dataIt"] == "03/08/2026"


def test_il_messaggio_del_deposito_non_mostra_date_iso(tmp_path):
    gf, repo, fascicolo, _profile = make_simple_fascicolo(tmp_path)
    link_required_documents(gf, repo, fascicolo)
    gf.aggiorna(fascicolo.id, depositi_pct=[_deposito("ACCETTATO_CANCELLERIA", timestamp="2026-08-03T11:30:00")])
    payload = build_regia_payload(repo, fascicolo=gf.get(fascicolo.id), cliente=_cliente(), fascicoli_manager=gf)
    assert "2026-08-03" not in payload["deposit"]["message"]
    assert "03/08/2026" in payload["deposit"]["message"]
