"""Crediti dalla sentenza: niente doppioni, registrazione automatica solo quando certa, annullabile.

Esempi costruiti sulle formule ufficiali dei dispositivi: art. 132 c.p.c. (sentenza), art. 91 c.p.c.
(condanna alle spese), art. 93 c.p.c. (distrazione al difensore antistatario), art. 429 c.p.c.
(sentenza del giudice del lavoro). Nessun dato reale di clienti.
"""
from __future__ import annotations

import hashlib
from types import SimpleNamespace

import pytest

from pct.fascicoli import StatoFascicolo
from pct.registro_letture import RegistroLetture
from pct.registro_letture.modello import Oggetto
from pct.sentenza_automatica import AUTORE, STATO_DOPPIONE, doppioni_da_chiudere, fondi_doppioni, gruppi_crediti
from pct.sentenza_economic_repository import SentenzaEconomicRepository
from tests.test_sentenza_proposte_definizione import TESTA_LAVORO, TESTA_TRIBUNALE, _Gestore, _fascicolo

LAVORO_DISTRAZIONE = TESTA_LAVORO + (
    "P.Q.M. Il Tribunale, in funzione di giudice del lavoro, definitivamente pronunciando, accoglie il ricorso e condanna "
    "ALFA S.R.L. al pagamento delle spese di lite, che liquida in € 258,00 per compensi, oltre accessori di legge, "
    "con distrazione in favore del procuratore antistatario.")
CIVILE_CONDANNA = TESTA_TRIBUNALE + (
    "P.Q.M. Il Tribunale, definitivamente pronunciando, accoglie la domanda e condanna ALFA S.R.L. alla rifusione delle "
    "spese di lite in favore di ROSSI MARIO, che liquida in euro 2.500,00 per compensi, oltre accessori.")
# Parte condannata non nominata: il software non può dire con certezza chi paga.
CIVILE_INCERTA = TESTA_TRIBUNALE + (
    "P.Q.M. Il Tribunale, definitivamente pronunciando, accoglie la domanda e condanna la convenuta alla rifusione delle "
    "spese di lite, che liquida in euro 2.500,00 per compensi, oltre accessori.")


def _sha(testo: str) -> str:
    return hashlib.sha256(testo.encode()).hexdigest()


# --- 1. niente doppioni ------------------------------------------------------------------------------

def _evento(eid, source, status="to_review", amount=258.0, tipo="apri_credito_avvocato_antistatario", creato="2026-10-20"):
    return {"id": eid, "source_id": source, "event_type": tipo, "beneficiary_type": "avvocato", "amount": amount,
            "status": status, "created_at": creato, "source_type": "sentenza_economic_audit"}


def test_stesso_credito_da_due_vie_compare_una_volta():
    audits = [{"id": "A1", "document_hash_sha256": "a" * 64, "message_id": "M1"},
              {"id": "A2", "document_hash_sha256": "a" * 64, "documento_id": "D1"}]
    eventi = [_evento("E1", "A1"), _evento("E2", "A2", creato="2026-10-21"), _evento("CU", "A2", tipo="verifica_contributo_unificato")]
    assert len(gruppi_crediti(eventi, audits)) == 1
    fusi = fondi_doppioni(eventi, audits)
    assert [e["id"] for e in fusi] == ["E1", "CU"] and fusi[0]["duplicati"] == ["E2"]
    # Importo diverso: due crediti distinti.
    assert len(gruppi_crediti([_evento("E1", "A1"), _evento("E2", "A2", amount=300.0)], audits)) == 2


def test_la_decisione_dell_avvocato_prevale_sul_doppione():
    audits = [{"id": "A1", "document_hash_sha256": "a" * 64}, {"id": "A2", "document_hash_sha256": "a" * 64}]
    eventi = [_evento("E1", "A1"), _evento("E2", "A2", status="confirmed", creato="2026-10-22")]
    assert fondi_doppioni(eventi, audits)[0]["id"] == "E2"
    assert doppioni_da_chiudere(eventi, audits) == [("E1", "E2")]


@pytest.fixture()
def repo(tmp_path):
    return SentenzaEconomicRepository(tmp_path / "economia.sqlite", decisions_path=tmp_path / "decisioni.jsonl")


def test_creazione_idempotente_da_pec_e_da_documento(repo):
    from web.services.sentenza_economic_runtime import run_analysis

    fascicolo = _fascicolo()
    fascicolo.controparte = "Alfa S.r.l."
    sha = _sha(LAVORO_DISTRAZIONE)
    run_analysis(fascicolo=fascicolo, testo=LAVORO_DISTRAZIONE, repo=repo, fonte="PEC", message_id="M1",
                 document_hash_sha256=sha, tenant_id="studio")
    run_analysis(fascicolo=fascicolo, testo=LAVORO_DISTRAZIONE, repo=repo, fonte="ARCHIVIO_LETTURE", documento_id="D1",
                 document_hash_sha256=sha, tenant_id="studio")
    crediti = [e for e in repo.list_economic_events("studio", fascicolo_id="F1") if e["event_type"].startswith("apri_credito")]
    assert len(repo.list_sentenza_audits("studio", fascicolo_id="F1")) == 2
    assert len(crediti) == 1


def test_riconvalida_fonde_i_doppioni_gia_salvati_senza_perdere_decisioni(repo):
    from web.services.sentenza_economic_runtime import _fondi_doppioni_salvati

    sha = "b" * 64
    ids = []
    for fonte, chiave in (("PEC", {"message_id": "M1"}), ("ARCHIVIO_LETTURE", {"documento_id": "D1"})):
        audit = repo.save_sentenza_audit("studio", fascicolo_id="F1", document_hash_sha256=sha, fonte=fonte, **chiave)
        ids.append(repo.add_economic_event("studio", fascicolo_id="F1", event_type="apri_credito_avvocato_antistatario",
                                           source_id=audit["id"], beneficiary_type="avvocato", amount=258.0)["id"])
    repo.update_event_status("studio", ids[1], status="confirmed", reviewed_by="avv1")
    assert _fondi_doppioni_salvati(repo, "studio", "F1") == 1
    stati = {e["id"]: (e["status"], e["reviewed_by"]) for e in repo.list_economic_events("studio", fascicolo_id="F1")}
    assert stati[ids[1]] == ("confirmed", "avv1") and stati[ids[0]][0] == STATO_DOPPIONE
    assert _fondi_doppioni_salvati(repo, "studio", "F1") == 0


# --- 2. automatico quando certo, da confermare altrimenti, annullabile ----------------------------------

@pytest.fixture()
def studio(tmp_path, monkeypatch, repo):
    import web.helpers
    import web.services.archivio_letture_runtime as archivio
    import web.services.registro_letture_runtime as registro_runtime
    import web.services.sentenza_economic_runtime as economia
    import web.services.sentenza_proposte_runtime as runtime

    registro = RegistroLetture(tmp_path / "registro.db")
    fascicolo = _fascicolo()
    fascicolo.controparte = "Alfa S.r.l."
    fascicolo.documenti = [SimpleNamespace(id="D1", tipo="ALLEGATO", nome="sentenza.pdf")]
    gestore = _Gestore(fascicolo)
    testi: dict[str, str] = {}
    decisioni = []
    monkeypatch.setattr(archivio, "testi_indice_archivio", lambda _f: testi)
    monkeypatch.setattr(runtime, "_catalogo", lambda _fid: {})
    monkeypatch.setattr(runtime, "_cliente", lambda _f: {})
    monkeypatch.setattr(runtime, "_parcelle_per_evento", lambda _fid: {})
    monkeypatch.setattr(runtime, "_dopo_decisione", lambda *a, **k: decisioni.append((a, k)))
    monkeypatch.setattr(registro_runtime, "registro_corrente", lambda **_: registro)
    monkeypatch.setattr(registro_runtime, "tenant_corrente", lambda: "studio")
    monkeypatch.setattr(web.helpers, "get_fascicoli", lambda: gestore)
    monkeypatch.setattr(economia, "_flag_on", lambda: True)
    monkeypatch.setattr(economia, "_tenant_id", lambda: "studio")
    monkeypatch.setattr(economia, "_repo", lambda: repo)
    monkeypatch.setattr(economia, "_resolve_fascicolo", lambda *_a, **_k: None)

    def carica(testo):
        sha = _sha(testo)
        testi["D1"] = testo
        registro.registra_inventario("studio", "F1", [Oggetto(tipo="documento", oggetto_id="D1", nome="sentenza.pdf", sha256=sha)])
        economia.run_analysis(fascicolo=fascicolo, testo=testo, repo=repo, fonte="ARCHIVIO_LETTURE", documento_id="D1",
                              document_hash_sha256=sha, tenant_id="studio")
        return runtime.aggiorna_proposte_definizione(fascicolo, registro, "studio")

    return SimpleNamespace(runtime=runtime, registro=registro, fascicolo=fascicolo, gestore=gestore, repo=repo,
                           carica=carica, decisioni=decisioni)


def _crediti(repo):
    return [e for e in repo.list_economic_events("studio", fascicolo_id="F1") if e["event_type"].startswith("apri_credito")]


@pytest.mark.parametrize("testo,tipo,norma,importo", [
    (LAVORO_DISTRAZIONE, "apri_credito_avvocato_antistatario", "art. 93 c.p.c.", "€ 258,00"),
    (CIVILE_CONDANNA, "apri_credito_cliente", "art. 91 c.p.c.", "€ 2.500,00"),
])
def test_sentenza_certa_registra_credito_e_definisce(studio, testo, tipo, norma, importo):
    report = studio.carica(testo)
    assert report["automatiche"] == 1 and report["proposte"] == 0
    (credito,) = _crediti(studio.repo)
    assert credito["event_type"] == tipo and credito["status"] == "confirmed" and credito["reviewed_by"] == AUTORE
    traccia = credito["evidence"][-1]
    assert traccia["sha256"] == _sha(testo) and traccia["norma"] == norma
    # Definito con la data della sentenza e la fonte in cronologia (art. 132 c.p.c.).
    assert studio.fascicolo.stato == StatoFascicolo.DEFINITO and studio.fascicolo.data_chiusura == "2026-10-15"
    (_, stato, nota, autore), = studio.gestore.chiamate
    assert autore == AUTORE and "Definito automaticamente dalla sentenza n. 123/2026" in nota and "sentenza.pdf" in nota
    proposte = studio.runtime.proposte_sentenza_payload(studio.fascicolo)
    assert proposte["definizione"] == [] and proposte["crediti"] == []
    (voce,) = proposte["automatiche"]
    assert voce["href"].startswith("/fascicoli/F1/documenti/D1/visualizza#passo=") and voce["numero"] == "123" and voce["data"] == "2026-10-15"
    assert voce["importoLabel"] == importo and norma in voce["etichetta"] and "liquida" in voce["citazione"]
    assert voce["definito"] and voce["dataDefinizione"] == "2026-10-15"


def test_credito_incerto_resta_da_confermare_ma_la_definizione_e_automatica(studio):
    report = studio.carica(CIVILE_INCERTA)
    assert report["automatiche"] == 1 and report["proposte"] == 0
    # La causa è decisa e l'identità coincide: il fascicolo si definisce (art. 132 c.p.c.).
    assert studio.fascicolo.stato == StatoFascicolo.DEFINITO
    proposte = studio.runtime.proposte_sentenza_payload(studio.fascicolo)
    assert proposte["definizione"] == []
    (voce,) = proposte["automatiche"]
    assert voce["definito"] and voce["importoLabel"] == "" and voce["etichetta"] == ""
    (credito,) = proposte["crediti"]
    assert credito["stato"] == "to_review" and credito["href"].startswith("/fascicoli/F1/documenti/D1/visualizza#passo=")
    assert "liquida in euro 2.500,00" in credito["citazione"] and credito["numero"] == "123" and credito["data"] == "2026-10-15"
    assert all(e["reviewed_by"] != AUTORE for e in _crediti(studio.repo))


@pytest.mark.parametrize("testo", [
    LAVORO_DISTRAZIONE.replace("ALFA S.R.L.", "ROSSI MARIO"),  # condannato il cliente: mai un credito automatico
    CIVILE_CONDANNA.replace("oltre accessori.", "oltre accessori; liquida altresì euro 300,00 per la fase cautelare."),
    CIVILE_CONDANNA.replace("accoglie la domanda", "accoglie in parte la domanda, compensa per la metà le spese,"),
])
def test_mai_credito_automatico_con_beneficiario_o_importo_ambiguo(studio, testo):
    studio.carica(testo)
    assert all(e["reviewed_by"] != AUTORE for e in _crediti(studio.repo))
    # La definizione segue la sola certezza della decisione e dell'identità del procedimento.
    assert studio.fascicolo.stato == StatoFascicolo.DEFINITO


def test_spese_compensate_definiscono_senza_credito(studio):
    testo = TESTA_TRIBUNALE + "P.Q.M. Il Tribunale, definitivamente pronunciando, rigetta la domanda. Spese compensate."
    assert studio.carica(testo)["automatiche"] == 1
    assert studio.fascicolo.stato == StatoFascicolo.DEFINITO and _crediti(studio.repo) == []


def test_fascicolo_sospeso_resta_una_proposta(studio):
    studio.fascicolo.stato = StatoFascicolo.SOSPESO
    report = studio.carica(CIVILE_INCERTA)
    assert report["automatiche"] == 0 and report["proposte"] == 1
    assert studio.fascicolo.stato == StatoFascicolo.SOSPESO and not studio.gestore.chiamate


def test_sentenza_arrivata_come_allegato_pec_definisce_il_fascicolo(studio, monkeypatch):
    """La sentenza comunicata dalla cancelleria solo via PEC (art. 133 c.p.c.) non è un documento del fascicolo."""
    import web.services.sentenza_economic_runtime as economia

    testo = LAVORO_DISTRAZIONE
    sha = _sha(testo)
    studio.fascicolo.documenti = []
    monkeypatch.setattr(studio.runtime, "_allegati_pec_con_testo", lambda _fid: {
        "A1": {"id": "A1", "filename": "123s.pdf.zip", "ocr_text": testo},
        "A2": {"id": "A2", "filename": "daticert.xml", "ocr_text": "<postacert/>"},
    })
    studio.registro.registra_inventario("studio", "F1", [
        Oggetto(tipo="allegato_pec", oggetto_id="A1", nome="123s.pdf.zip", sha256=sha, origine="pec_M1"),
        Oggetto(tipo="allegato_pec", oggetto_id="A2", nome="daticert.xml", sha256="c" * 64, origine="pec_M1"),
    ])
    economia.run_analysis(fascicolo=studio.fascicolo, testo=testo, repo=studio.repo, fonte="PEC", message_id="pec_M1",
                          document_hash_sha256=sha, tenant_id="studio")
    report = studio.runtime.aggiorna_proposte_definizione(studio.fascicolo, studio.registro, "studio")
    assert report["automatiche"] == 1 and report["esaminati"] == 2
    assert studio.fascicolo.stato == StatoFascicolo.DEFINITO
    (credito,) = _crediti(studio.repo)
    assert credito["status"] == "confirmed" and credito["reviewed_by"] == AUTORE
    (voce,) = studio.runtime.proposte_sentenza_payload(studio.fascicolo)["automatiche"]
    assert voce["href"].startswith("/api/v1/ui/email/source/pec_M1?name=123s.pdf.zip&sha256=" + sha + "#passo=")
    # Annullabile anche quando la fonte è un allegato PEC.
    studio.runtime.decidi_definizione(studio.fascicolo, voce["id"], esito="annulla", utente="avv1")
    assert studio.fascicolo.stato == StatoFascicolo.IN_CORSO


def test_annulla_ripristina_e_la_registrazione_non_rinasce(studio, monkeypatch):
    from pct.fascicolo_sentenza_archiviazione import VERSIONE_PROPOSTA

    studio.carica(LAVORO_DISTRAZIONE)
    (voce,) = studio.runtime.proposte_sentenza_payload(studio.fascicolo)["automatiche"]
    esito = studio.runtime.decidi_definizione(studio.fascicolo, voce["id"], esito="annulla", utente="avv1")
    assert esito["esito"] == "annullata"
    assert studio.fascicolo.stato == StatoFascicolo.IN_CORSO and studio.fascicolo.data_chiusura == ""
    assert "annullata dall'avvocato" in studio.gestore.chiamate[-1][2] and studio.gestore.chiamate[-1][3] == "avv1"
    (credito,) = _crediti(studio.repo)
    assert credito["status"] == "to_review" and credito["reviewed_by"] == ""
    proposte = studio.runtime.proposte_sentenza_payload(studio.fascicolo)
    assert proposte["automatiche"] == [] and len(proposte["crediti"]) == 1 and len(proposte["definizione"]) == 1
    # Regola nuova sullo storico: la fonte si riesamina, l'automatismo annullato non si ripete.
    monkeypatch.setattr(studio.runtime, "VERSIONE_PROPOSTA", VERSIONE_PROPOSTA + "+prova")
    assert studio.runtime.aggiorna_proposte_definizione(studio.fascicolo, studio.registro, "studio")["automatiche"] == 0
    assert _crediti(studio.repo)[0]["status"] == "to_review" and studio.fascicolo.stato == StatoFascicolo.IN_CORSO
    with pytest.raises(ValueError):
        studio.runtime.decidi_definizione(studio.fascicolo, voce["id"], esito="annulla", utente="avv1")


def test_annulla_bloccato_se_la_parcella_e_gia_generata(studio, monkeypatch):
    studio.carica(LAVORO_DISTRAZIONE)
    (voce,) = studio.runtime.proposte_sentenza_payload(studio.fascicolo)["automatiche"]
    monkeypatch.setattr(studio.runtime, "_parcelle_per_evento", lambda _fid: {voce["eventId"]: "2026/0009"})
    with pytest.raises(ValueError, match="2026/0009"):
        studio.runtime.decidi_definizione(studio.fascicolo, voce["id"], esito="annulla", utente="avv1")
    assert studio.fascicolo.stato == StatoFascicolo.DEFINITO


def test_fascicolo_gia_definito_registra_solo_il_credito(studio):
    studio.fascicolo.stato = StatoFascicolo.DEFINITO
    assert studio.carica(LAVORO_DISTRAZIONE)["automatiche"] == 1
    assert not studio.gestore.chiamate and _crediti(studio.repo)[0]["reviewed_by"] == AUTORE
    (voce,) = studio.runtime.proposte_sentenza_payload(studio.fascicolo)["automatiche"]
    assert not voce["definito"]


# --- 3. lo storico: lotto proprio e leggero, idempotente ---------------------------------------------

def test_storico_di_settanta_fascicoli_si_completa_in_pochi_giri(tmp_path, monkeypatch, repo):
    import web.services.archivio_letture_runtime as archivio
    import web.services.sentenza_economic_runtime as economia
    import web.services.sentenza_proposte_runtime as runtime
    from pct.fascicolo_sentenza_archiviazione import VERSIONE_PROPOSTA
    from web.services.proposte_storico_runtime import esamina_proposte_storico, fascicoli_da_esaminare

    registro = RegistroLetture(tmp_path / "registro.db")
    fascicoli, testi = {}, {}
    for indice in range(70):
        fid = f"F{indice:02d}"
        fascicolo = _fascicolo()
        fascicolo.id, fascicolo.controparte = fid, "Alfa S.r.l."
        fascicolo.documenti = [SimpleNamespace(id=f"D{fid}", tipo="ALLEGATO", nome="sentenza.pdf")]
        fascicoli[fid] = fascicolo
        testi[fid] = LAVORO_DISTRAZIONE + f" Fascicolo {fid}."
        registro.registra_inventario("studio", fid, [Oggetto(tipo="documento", oggetto_id=f"D{fid}", nome="sentenza.pdf",
                                                             sha256=_sha(testi[fid]))])
        registro.segna_fascicolo("studio", fid, archivio.LETTORE_DOCUMENTI, impronta="i", oggetti_totali=1, oggetti_letti=1)
        # Esaminato con la regola precedente (2.476.0): lo storico va riesaminato.
        registro.segna_fascicolo("studio", fid, "proposta_definizione", impronta="vecchia", oggetti_totali=1,
                                 oggetti_letti=1, stato="completa", versione="sentenza-propria-da-archiviare-v3-conclusiva+proposta-avvocato.v1")
        economia.run_analysis(fascicolo=fascicolo, testo=testi[fid], repo=repo, fonte="ARCHIVIO_LETTURE", documento_id=f"D{fid}",
                              document_hash_sha256=_sha(testi[fid]), tenant_id="studio")
    monkeypatch.setattr(archivio, "testi_indice_archivio", lambda f: {f"D{f.id}": testi[f.id]})
    monkeypatch.setattr(runtime, "_catalogo", lambda _fid: {})
    monkeypatch.setattr(runtime, "_cliente", lambda _f: {})
    monkeypatch.setattr(runtime, "_dopo_decisione", lambda *a, **k: None)
    monkeypatch.setattr(economia, "_flag_on", lambda: True)
    monkeypatch.setattr(economia, "_tenant_id", lambda: "studio")
    monkeypatch.setattr(economia, "_repo", lambda: repo)
    import web.helpers

    class _Tutti:
        def get(self, fid):
            return fascicoli.get(fid)

        def cambia_stato(self, fid, stato, note="", avvocato="", **_):
            fascicoli[fid].stato = stato

    monkeypatch.setattr(web.helpers, "get_fascicoli", lambda: _Tutti())
    monkeypatch.setattr("web.services.proposte_storico_runtime._controllo_economico", lambda _fid: None)

    giri = []
    while fascicoli_da_esaminare(registro, "studio", limite=100) and len(giri) < 5:
        giri.append(esamina_proposte_storico(registro, "studio", fascicoli.get))
    assert [g["fascicoli"] for g in giri] == [50, 20]
    assert sum(g["automatiche"] for g in giri) == 70 and not any(g["errori"] for g in giri)
    assert all(f.stato == StatoFascicolo.DEFINITO for f in fascicoli.values())
    righe = registro.righe_fascicoli("studio", lettore="proposta_definizione")
    assert all(r["versione_lettore"] == VERSIONE_PROPOSTA and r["stato"] == "completa" for r in righe)
    # Idempotente: un giro in più non trova nulla e non registra nulla.
    assert esamina_proposte_storico(registro, "studio", fascicoli.get)["fascicoli"] == 0


def test_storico_parziale_non_si_ripete_a_ogni_giro(tmp_path):
    from datetime import datetime, timedelta, timezone

    import web.services.archivio_letture_runtime as archivio
    from pct.fascicolo_sentenza_archiviazione import VERSIONE_PROPOSTA
    from web.services.proposte_storico_runtime import fascicoli_da_esaminare

    registro = RegistroLetture(tmp_path / "registro.db")
    for fid in ("NUOVO", "PARZIALE"):
        registro.segna_fascicolo("studio", fid, archivio.LETTORE_DOCUMENTI, impronta="i", oggetti_totali=1, oggetti_letti=1)
    registro.segna_fascicolo("studio", "PARZIALE", "proposta_definizione", impronta="x", oggetti_totali=1, oggetti_letti=0,
                             stato="parziale", versione=VERSIONE_PROPOSTA)
    assert fascicoli_da_esaminare(registro, "studio", limite=10) == ["NUOVO"]
    dopo = datetime.now(timezone.utc) + timedelta(hours=7)
    assert fascicoli_da_esaminare(registro, "studio", limite=10, adesso=dopo) == ["NUOVO", "PARZIALE"]


# --- 4. la citazione inizia e finisce su parole intere (FAS-39) ----------------------------------------

def test_brano_del_capo_spese_a_parole_intere():
    from pct.spese_liquidate_lettura import estrai_spese_liquidate, rifila_brano

    _importo, brano = estrai_spese_liquidate(LAVORO_DISTRAZIONE.replace("P.Q.M.", "P.Q.M. " + "premessa lunga " * 20))
    parole = set(LAVORO_DISTRAZIONE.replace("P.Q.M.", "").split()) | {"premessa", "lunga"}
    assert brano.split()[0] in parole and brano.split()[-1].rstrip(".,;") in {p.rstrip(".,;") for p in parole}
    # Brani salvati fino alla 2.477 con i bordi tagliati a metà parola.
    assert rifila_brano("nna il Ministero alla rifusione delle spese, con distrazi") == "il Ministero alla rifusione delle spese, con"
    assert rifila_brano("Condanna il Ministero alle spese.") == "Condanna il Ministero alle spese."
