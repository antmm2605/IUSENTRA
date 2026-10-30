"""Audit fonti 29/10/2026: vigenza alla data, provenienza ufficiale, norme fuori Fonti, estremi giurisprudenziali,
articoli abrogati. Solo fixture sintetiche: nessun archivio reale, nessuna rete."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
from types import SimpleNamespace as N

import pytest

from lex.guards.hallucination_guard import HallucinationGuard, extract_legal_references
from lex.guards.legal_reference_guard import LegalReferenceGuard
from lex.procedura_atti.controlla_atto import chiave_atto
from lex.procedura_atti.fonti_scheda import FontiScheda, fonti_per_scheda
from lex.procedura_atti.provenienza import sha256_testo, url_ufficiale, verifica_provenienza
from lex.procedura_atti.revisione_indipendente import rivedi
from lex.procedura_atti.stesura_blocchi import scrivi_blocchi
from lex.retrieval.abrogazione import abrogazione, tagga_abrogazione
from pct.schede_fonti.verifica import EsitoNorma

OGGI = dt.date(2026, 10, 29)
URL_CC = "https://www.normattiva.it/uri-res/N2Ls?urn:nir:stato:regio.decreto:1942-03-16;262"
TESTO_1219 = "Art. 1219. (Costituzione in mora) Il debitore e' costituito in mora mediante intimazione o richiesta fatta per iscritto."
AVVISO_2409 = "Art. 2409. ((ARTICOLO ABROGATO DAL D.LGS. 27 MARZO 2026, N. 47))"


# --- 1. vigenza dell'edizione alla data di oggi -------------------------------------------------------------

def _edizione(dal: str, al: str | None) -> dict:
    e = {"catena_ufficiale_completa": True, "xml_sha256": "a" * 64, "versione_formale_dal": dal, "redazione_id": "2026-10-01"}
    if al:
        e["versione_formale_al_escluso"] = al
    return e


def _esito(articolo: str, edizione: dict, origine: str = "base_normativa") -> EsitoNorma:
    return EsitoNorma(scheda="X", atto="codice_civile", articolo=articolo, origine=origine, perche="mora", stato="presente",
                      sha256=hashlib.sha256(TESTO_1219.encode()).hexdigest(), url=URL_CC, aggiornato_al="2026-10-01",
                      testo=TESTO_1219, acquisita_il="2026-10-01", document_id=1, article_id=1,
                      edizione_archiviata=edizione)


@pytest.fixture
def scheda(tmp_path):
    (tmp_path / "X.json").write_text(json.dumps({"id": "X", "titolo": "Diffida", "base_normativa": [], "campi": []}))
    return tmp_path


def _con_esiti(monkeypatch, esiti):
    from pct.schede_fonti import verifica

    monkeypatch.setattr(verifica, "verifica_schede", lambda *a, **k: list(esiti))


def test_edizione_non_vigente_oggi_esclusa_dalle_fonti(monkeypatch, scheda):
    _con_esiti(monkeypatch, [_esito("1219", _edizione("2020-01-01", "2026-01-01"), origine="campo:mora")])
    f = fonti_per_scheda("X", scheda / "db.sqlite", cartella=scheda, oggi=OGGI)
    assert f.fonti == {} and f.fonti_ref == [] and f.requisiti == []
    assert any("non vigente al 29/10/2026" in p for p in f.pendenze)


def test_edizione_vigente_oggi_entra_senza_pendenza(monkeypatch, scheda):
    _con_esiti(monkeypatch, [_esito("1219", _edizione("2020-01-01", "2027-01-01"))])
    f = fonti_per_scheda("X", scheda / "db.sqlite", cartella=scheda, oggi=OGGI)
    assert list(f.fonti) == [1] and f.fonti_ref[0]["provenienza"]["riscontro_alla_data"] is True
    assert f.pendenze == []
    assert verifica_provenienza({"fonti": f.fonti, "fonti_ref": f.fonti_ref}, oggi=OGGI) == []


def test_vigenza_non_documentata_resta_fonte_ma_pendente(monkeypatch, scheda):
    _con_esiti(monkeypatch, [_esito("1219", {"redazione_id": "2026-10-01"})])
    f = fonti_per_scheda("X", scheda / "db.sqlite", cartella=scheda, oggi=OGGI)
    assert list(f.fonti) == [1] and f.fonti_ref[0]["provenienza"]["riscontro_alla_data"] is None
    assert any("vigenza al 29/10/2026 non riscontrata" in p for p in f.pendenze)


def test_pendenza_di_vigenza_impedisce_pronta(monkeypatch, scheda):
    _con_esiti(monkeypatch, [_esito("1219", {"redazione_id": "2026-10-01"})])
    f = fonti_per_scheda("X", scheda / "db.sqlite", cartella=scheda, oggi=OGGI)
    bozza = ("### Diritto\nIl sig. Mario Rossi, creditore, intima a Beta srl il pagamento entro quindici giorni: "
             "il debitore e' costituito in mora [1]. Spett. Beta srl, si invita al pagamento. " * 3)
    risolta = {"titolo": "Diffida", "scrive_lex": [{"blocco": "Diritto", "compito": "diritto"}], "campi": []}
    e = scrivi_blocchi(chiama_modello=lambda s, m: (bozza, "finto"), oggetto="diffida", risolta=risolta, fonti=f,
                       blocco_scadenze="", termini=[], fatti_testo="Mario Rossi creditore", oggi=OGGI,
                       assistito="Mario Rossi", controparte="Beta srl", campi_modello=["legal_arguments"])
    assert e.stato_consegna["stato"] != "pronta_per_revisione_avvocato"
    assert any("vigenza" in m for m in e.stato_consegna["motivi"])


# --- 1b. provenienza: URL ufficiale http(s) e acquisizione non futura ---------------------------------------

def _caso(url: str = URL_CC, acquisita: str = "01/10/2026") -> dict:
    testo = "c.c. art. 1219\n" + TESTO_1219
    return {"fonti": {1: testo}, "fonti_ref": [{"n": 1, "atto": "codice_civile", "articolo": "1219", "provenienza": {
        "tipo": "norma", "url": url, "versione": "edizione 01/10/2026", "acquisita_il": acquisita, "sha256": sha256_testo(testo)}}]}


@pytest.mark.parametrize("url", ["non-un-url", "ftp://www.normattiva.it/x", "https://example.org/normattiva",
                                 "https://www.normattiva.it.example.org/x", "https://utente:pw@www.normattiva.it/x",
                                 "javascript:alert(1)"])
def test_url_non_ufficiale_bloccato(url):
    assert not url_ufficiale(url)
    assert any("non ufficiale" in e for e in verifica_provenienza(_caso(url), oggi=OGGI))


@pytest.mark.parametrize("url", [URL_CC, "https://eur-lex.europa.eu/eli/reg/2016/679/oj", "https://www.gazzettaufficiale.it/x"])
def test_url_ufficiale_ammesso(url):
    assert url_ufficiale(url) and verifica_provenienza(_caso(url), oggi=OGGI) == []


def test_acquisizione_successiva_a_oggi_bloccata():
    errori = verifica_provenienza(_caso(acquisita="30/10/2026"), oggi=OGGI)
    assert any("dopo la data di riferimento 29/10/2026" in e for e in errori)
    caso = _caso(acquisita="30/10/2026")
    caso["oggi"] = "31/10/2026"
    assert verifica_provenienza(caso) == []  # la data del caso fa da riferimento


# --- 2. revisione della bozza: forme estese, atto diverso, requisiti -----------------------------------------

T1 = "c.c. · art. 1219 · edizione del 01/10/2026\n" + TESTO_1219
T2 = "Cost. · art. 24\nArt. 24. Tutti possono agire in giudizio per la tutela dei propri diritti."
CASO_REV = {"fonti": {1: T1, 2: T2},
            "fonti_ref": [{"n": 1, "atto": "codice_civile", "articolo": "1219", "sigla": "c.c."},
                          {"n": 2, "atto": "costituzione", "articolo": "24", "sigla": "Cost."}],
            "fatti": "Mario Rossi creditore di 1.000 euro.", "richiesta": "diffida", "oggi": "29/10/2026",
            "parte_assistita": {"nome": "Mario Rossi", "ruolo": "creditore"}, "controparte": {"nome": "Beta srl"}}
BASE = ("Il sig. Mario Rossi, creditore, intima il pagamento. Il debitore e' costituito in mora ai sensi "
        "dell'art. 1219 c.c. [1]. Il diritto di agire e' garantito [2]. ") * 3


@pytest.mark.parametrize("aggiunta", [
    "Si chiede il controllo giudiziario ai sensi dell'articolo 2409 del codice civile.",
    "Si richiamano gli articoli 2409 e 2410 c.c.",
    "Si richiamano gli artt. 2409 e 2410 c.c.",
    "La mediazione e' disciplinata dall'art. 24 d.lgs. 28/2010.",
    "Si richiama altresi' l'art. 1219 c.p.c.",
    "Si veda l'art. 24 della legge 20 maggio 1970, n. 300.",
])
def test_norma_fuori_fonti_in_ogni_forma_e_grave(aggiunta):
    r = rivedi(BASE + aggiunta, CASO_REV, {"termini": [], "importi": []})
    assert any(g[0] == "norma_fuori_fonti" for g in r["gravi"]), r


@pytest.mark.parametrize("aggiunta", ["Si richiama l'art. 1219 c.c. anche per la mora.",
                                      "Si richiama l'articolo 24 della Costituzione.",
                                      "Ai sensi dell'art. 5 del contratto la consegna era dovuta."])
def test_stesso_atto_senza_richiamo_resta_avviso(aggiunta):
    r = rivedi(BASE + aggiunta, CASO_REV, {"termini": [], "importi": []})
    assert r["gravi"] == []


def test_chiave_atto_forme():
    assert chiave_atto(" del codice civile") == "cc" and chiave_atto(", comma 2, c.p.c.") == "cpc"
    assert chiave_atto(" d.lgs. 28/2010") == chiave_atto(" del decreto legislativo n. 28 del 2010") == "dlgs:28/2010"
    assert chiave_atto(" della legge 20 maggio 1970, n. 300") == chiave_atto(" l. 300/1970") == "l:300/1970"
    assert chiave_atto(" del contratto") is None


def test_requisiti_dell_atto_nel_percorso_di_stesura():
    testo = "c.c. art. 1219\n" + TESTO_1219
    fonti = FontiScheda("X", "Diffida", fonti={1: testo}, fonti_ref=[{"n": 1, "atto": "codice_civile", "articolo": "1219", "sigla": "c.c.",
        "provenienza": {"tipo": "norma", "url": URL_CC, "versione": "v", "acquisita_il": "01/10/2026", "sha256": sha256_testo(testo)}}])
    bozza = "### Diritto\nIl sig. Mario Rossi vanta un credito verso Beta srl; il debitore e' in mora [1]. " * 4
    risolta = {"titolo": "Diffida", "scrive_lex": [{"blocco": "Diritto", "compito": "diritto"}], "campi": []}
    e = scrivi_blocchi(chiama_modello=lambda s, m: (bozza, "finto"), oggetto="diffida", risolta=risolta, fonti=fonti,
                       blocco_scadenze="", termini=[], fatti_testo="Mario Rossi creditore", oggi=OGGI,
                       assistito="Mario Rossi", controparte="Beta srl", campi_modello=["legal_arguments"])
    assert e.stato_consegna["stato"] == "bozza_incompleta"
    assert any("richiesta e termine" in m for m in e.stato_consegna["motivi"])


# --- 3/4. estremi giurisprudenziali: forme lunghe e organo --------------------------------------------------

@pytest.mark.parametrize("testo", ["Si veda Cass. civ., sez. III, n. 9999/2021.", "Cass., Sez. Un., 12 marzo 2021, n. 9999",
                                   "Cass. sez. lav. n. 9999/2021", "Cass. pen., sez. V, sent. n. 9999/2021",
                                   "Cass. civ., Sez. III, 5 maggio 2021 n. 9999"])
def test_cassazione_estratta_in_forma_lunga(testo):
    assert "cassazione:9999:2021" in {r.key for r in extract_legal_references(testo)}


def test_consiglio_di_stato_con_sezione():
    chiavi = {r.key for r in extract_legal_references("Cons. Stato, sez. IV, n. 1234/2020")}
    assert "consiglio di stato:1234:2020" in chiavi


def _guardie(testo, items):
    req = N(query="domanda", require_citations=False, require_official_sources=False)
    ev = {"items": items, "citations": []}
    d = N(text=testo, metadata={})
    return (HallucinationGuard().check(request=req, workflow="normativa", evidence=ev, draft=d),
            LegalReferenceGuard().check(request=req, workflow="normativa", evidence=ev, draft=d))


CDS = {"title": "Cons. Stato n. 1234/2020", "content": "Consiglio di Stato sentenza n. 1234/2020",
       "official_url": "https://www.giustizia-amministrativa.it/x", "verified_reference": True}


def test_stesso_numero_organo_diverso_bloccato():
    h, l = _guardie("Si veda Cass. civ. n. 1234/2020.", [CDS])
    assert h.allowed is False and l.allowed is False


def test_stesso_organo_ammesso():
    h, l = _guardie("Si veda Cons. Stato, sez. IV, n. 1234/2020.", [CDS])
    assert h.allowed is True and l.allowed is True


def test_ecli_identifica_organo():
    riga = {"title": "Pronuncia", "content": "Massima sul nesso causale.", "metadata": {"ecli": "ECLI:IT:CASS:2021:9999CIV"},
            "official_url": "https://www.cortedicassazione.it/x", "verified_reference": True}
    h, l = _guardie("Cass. civ., sez. III, n. 9999/2021 richiede la prova del nesso.", [riga])
    assert h.allowed is True and l.allowed is True
    h, l = _guardie("Cons. Stato n. 9999/2021 richiede la prova del nesso.", [riga])
    assert h.allowed is False and l.allowed is False


def test_pronuncia_assente_dalle_fonti_verificate_bloccata_da_legal_reference():
    norma = {"title": "c.c. art. 2043", "content": "Art. 2043. Qualunque fatto doloso o colposo...",
             "official_url": "https://www.normattiva.it/x", "verified_reference": True, "source_level": 1}
    _, l = _guardie("In base all'art. 2043 c.c. (Cass. civ., sez. III, n. 9999/2021) occorre il nesso causale.", [norma])
    assert l.allowed is False


# --- 5. articoli abrogati -----------------------------------------------------------------------------------

def test_tag_abrogazione():
    assert abrogazione(AVVISO_2409) == {"abrogato": True, "abrogato_da": "D.LGS. 27 MARZO 2026, N. 47"}
    assert abrogazione(TESTO_1219) is None
    riga = tagga_abrogazione({"testo": AVVISO_2409, "metadata": {}})
    assert riga["abrogato"] is True and riga["metadata"]["abrogato_da"].endswith("N. 47")
    # Righe non strutturate o senza avviso restano come sono.
    assert tagga_abrogazione(None) is None
    assert tagga_abrogazione({"testo": TESTO_1219}) == {"testo": TESTO_1219}
    # Rubrica fra numero e avviso; testo patologico con molte tabulazioni senza rallentamenti.
    assert abrogazione("Art. 12 (Rubrica) ((ARTICOLO ABROGATO DALLA L. 1/2020))")["abrogato_da"] == "L. 1/2020"
    assert abrogazione("art-" + "\t" * 100_000) is None


def test_ricerca_normattiva_marca_gli_abrogati(monkeypatch):
    import lex.retrieval.official_sources_retriever as r

    monkeypatch.setattr(r, "_search_normattiva_rows", lambda *a, **k: [
        {"titolo": "c.c.", "articolo_o_chunk": "2409", "testo": AVVISO_2409, "metadata": {}},
        {"titolo": "c.c.", "articolo_o_chunk": "1219", "testo": TESTO_1219, "metadata": {}}])
    righe = r.search_normattiva("art. 2409 c.c.", db_path="/inesistente.sqlite")
    assert righe[0]["abrogato"] is True and "abrogato" not in righe[1]


ABROGATO = {"title": "c.c. art. 2409", "content": AVVISO_2409, "official_url": "https://www.normattiva.it/x", "verified_reference": True}


def test_articolo_abrogato_citato_come_vigente_bloccato():
    h, _ = _guardie("Il socio puo' denunziare le gravi irregolarita' al tribunale ai sensi dell'art. 2409 c.c.", [ABROGATO])
    assert h.allowed is False and "abrogat" in h.warnings[0]


def test_articolo_abrogato_dichiarato_tale_ammesso():
    h, _ = _guardie("L'art. 2409 c.c. e' stato abrogato: la denunzia al tribunale non e' piu' disponibile in quella forma.", [ABROGATO])
    assert h.allowed is True


def test_flag_abrogato_della_riga_basta():
    riga = {"title": "c.c. art. 2409", "content": "Art. 2409. Denunzia al tribunale.", "abrogato": True,
            "abrogato_da": "d.lgs. 47/2026", "official_url": "https://www.normattiva.it/x"}
    h, _ = _guardie("Si applica l'art. 2409 c.c.", [riga])
    assert h.allowed is False
