"""Schede di istituto (lex/conoscenza): generazione dalle fonti, controllore anti-invenzione, riconvalida, revisioni,
annotazioni che sopravvivono, ricerca senza embeddings, viste index.md/log.md, API e uso in Lex."""
from __future__ import annotations

import json
import sqlite3
from dataclasses import replace

import pytest

from lex.conoscenza import annotazioni, consultazione, deposito, generatore
from lex.conoscenza.istituti import Istituto, carica, id_scheda


@pytest.fixture(autouse=True)
def _senza_archivio_vivo(monkeypatch):
    monkeypatch.setenv("LEX_HARNESS_ARCHIVIO_VIVO", "0")
    monkeypatch.setenv("LEX_HARNESS_GIURISPRUDENZA", "0")


def _istituto(ident: str) -> Istituto:
    return next(i for i in carica()[1] if i.id == ident)


def _passaggi(monkeypatch, norme: dict) -> None:
    generatore._passaggi.cache_clear()
    consultazione._norme_delle_pronunce.cache_clear()
    monkeypatch.setattr(generatore, "_passaggi", lambda: {"norme": norme})
    monkeypatch.setattr(consultazione, "pronunce_per_norma", lambda k: list(norme.get(k, [])))


def _pronuncia(numero: str, testo: str, tipo: str = "testo integrale") -> dict:
    return {"organo": "Corte di Cassazione — civile", "sezione": "L", "numero": numero, "anno": "2025", "data": "2025-03-01",
            "url": f"https://www.italgiure.giustizia.it/x{numero}", "estremi": f"Corte di Cassazione — civile, sez. L, n. {numero}/2025",
            "citazione_norma": "art. 14 d.l. 669/1996", "passaggio": testo, "tipo_testo": tipo, "versione": "v" + numero}


# ------------------------------------------------------------------------------------------------ generazione
def test_scheda_esecuzione_contro_pa_dalle_regole_con_fonti_versionate(monkeypatch):
    _passaggi(monkeypatch, {})
    s = generatore.genera_scheda(_istituto("esecuzione_contro_pa"))
    assert s["id"] == "ist-esecuzione-contro-pa" and s["materia"] == "esecuzione contro la PA"
    termini = s["sezioni"]["termini"]
    assert termini["stato"] == "compilata"
    voce = next(v for v in termini["voci"] if v.get("calcolo"))
    assert voce["calcolo"]["quantita"] == 120 and voce["calcolo"]["calcolatore"] == "/scadenziario/calcola-termini"
    f = voce["fonti"][0]
    assert f["chiave"] == "dl669:14" and len(f["versione"]) == 16 and f["url"].startswith("https://www.normattiva.it")
    # Ogni voce compilata porta fonte e tipo di verifica; ogni sezione vuota è dichiarata con il motivo.
    for nome, sez in s["sezioni"].items():
        if sez["stato"] == "compilata":
            assert all(v["provenienza"] and v["verifica"] for v in sez["voci"])
        else:
            assert sez["motivo"] and nome in dict(generatore.SEZIONI)
    assert s["dipendenze"]["norma:dl669:14"] == f["versione"]
    assert any(x["tipo"] == "calcolatore" for x in s["strumenti"])


def test_istituto_senza_regola_riporta_solo_le_norme_e_lo_dichiara(monkeypatch):
    _passaggi(monkeypatch, {})
    ist = Istituto("prova_senza_regola", "civile ordinario", "Istituto di prova", (), _istituto("citazione").norme)
    s = generatore.genera_scheda(ist)
    assert all(sez["stato"] == "mancante" for sez in s["sezioni"].values())
    assert s["lacune"][0].startswith("Nessuna regola di Lex") and s["stato_verifica"] == "lacune"
    assert s["fonti"] and all(f["tipo"] == "norma" for f in s["fonti"])


# ------------------------------------------------------------------------------------------------ anti-invenzione
def test_citazione_falsa_bloccata():
    voce, perche = generatore._voce_testo_libero("Si applica l'art. 9999 c.c. sulla prescrizione.", "regola x")
    assert voce is None and "non presente" in perche
    voce, perche = generatore._voce_testo_libero("Va sempre fatta attenzione.", "regola x")
    assert voce is None and perche == "senza norma citata"
    voce, _ = generatore._voce_testo_libero("La sospensione feriale non vale (art. 3 l. 742/1969).", "regola x")
    assert voce and "non ancorata" in voce["verifica"]


def test_ancora_inventata_esclusa_dal_controllore(monkeypatch):
    from lex.harness.modello import Analisi, Punto, Rif

    def analizza(c, f):
        a = Analisi("finta", "lavoro")
        a.conclusione = [Punto("Affermazione vera.", [Rif("dl669:14", "centoventi giorni")]),
                         Punto("Affermazione inventata.", [Rif("dl669:14", "parole che la norma non contiene affatto")])]
        return a

    generatore._regole.cache_clear()
    monkeypatch.setattr(generatore, "_regole", lambda: {"finta": ("finta", lambda c, f: 9, analizza)})
    s = generatore.genera_scheda(Istituto("finto", "lavoro", "Istituto finto", ("finta",)))
    testi = [v["testo"] for v in s["sezioni"]["rimedi"]["voci"]]
    assert testi == ["Affermazione vera."]
    assert any("Affermazione esclusa dal controllore" in x and "parole che la norma" in x for x in s["lacune"])
    assert s["stato_verifica"] == "lacune"


# ------------------------------------------------------------------------------------------------ pronunce
def test_solo_massima_limite_dichiarato_e_orientamenti_difformi_senza_prevalenza(monkeypatch):
    _passaggi(monkeypatch, {"dl669:14": [
        _pronuncia("100", "L'art. 14 d.l. 669/1996 non si applica agli enti pubblici economici.", "massima"),
        _pronuncia("200", "Ai sensi dell'art. 14 d.l. 669/1996 il termine vale anche per gli enti pubblici economici."),
    ]})
    s = generatore.genera_scheda(_istituto("esecuzione_contro_pa"))
    voci = s["sezioni"]["orientamenti"]["voci"]
    assert [v["fonti"][0]["citazione"].split("n. ")[1] for v in voci] == ["100/2025", "200/2025"]  # ordine dell'archivio
    assert voci[0]["verifica"].startswith("massima") and "non letti" in voci[0]["verifica"]
    assert voci[1]["verifica"].startswith("passaggio letto")
    assert all(v["orientamento"].startswith("non classificato") for v in voci)
    assert not any("prevalen" in json.dumps(v["fonti"]) for v in voci)
    assert any("solo la massima" in x for x in s["lacune"])


def test_pronuncia_senza_passaggio_non_entra(monkeypatch):
    p = _pronuncia("300", "")
    _passaggi(monkeypatch, {"dl669:14": [p]})
    s = generatore.genera_scheda(_istituto("esecuzione_contro_pa"))
    assert s["sezioni"]["orientamenti"]["stato"] == "mancante"


# ------------------------------------------------------------------------------------------------ revisioni
def _percorsi(tmp_path):
    return {"archivio": tmp_path / "schede.json", "registro": tmp_path / "registro.jsonl"}


def test_fonte_modificata_scheda_da_riesaminare_e_nuova_revisione(tmp_path, monkeypatch):
    _passaggi(monkeypatch, {})
    p = _percorsi(tmp_path)
    s = generatore.genera_scheda(_istituto("esecuzione_contro_pa"))
    deposito.aggiorna([s], ora="2026-11-23T10:00:00+01:00", **p)
    rec = deposito.leggi_archivio(p["archivio"])["schede"][s["id"]]
    assert rec["revisione"] == 1
    # Oggi il testo della norma è cambiato: la scheda è da riesaminare finché non si rigenera.
    vecchia = rec["dipendenze"]["norma:dl669:14"]
    st = consultazione.stato_attuale(rec, versioni=lambda d: "cambiata" if d == "norma:dl669:14" else rec["dipendenze"][d])
    assert st["stato"] == "da_riesaminare" and st["fonti_cambiate"] == ["norma:dl669:14"]
    assert consultazione.stato_attuale(rec)["stato"] == rec["stato_verifica"]
    # Rigenerazione con la fonte nuova: revisione 2, evento con la fonte cambiata.
    nuova = dict(s, dipendenze={**s["dipendenze"], "norma:dl669:14": "cambiata"}, impronta="x" * 64)
    deposito.aggiorna([nuova], ora="2026-11-24T10:00:00+01:00", **p)
    rec2 = deposito.leggi_archivio(p["archivio"])["schede"][s["id"]]
    assert rec2["revisione"] == 2 and rec2["storia"][-1]["motivo"].startswith("fonti cambiate: norma:dl669:14")
    ev = [e for e in deposito.leggi_registro(p["registro"]) if e["operazione"] == "aggiornamento"]
    assert ev and ev[0]["cambiate"] == ["norma:dl669:14"] and ev[0]["revisione_precedente"] == 1 and vecchia != "cambiata"


def test_stesso_passaggio_ripetuto_non_duplica_eventi(tmp_path, monkeypatch):
    _passaggi(monkeypatch, {})
    p = _percorsi(tmp_path)
    s = generatore.genera_scheda(_istituto("carta_docente"))
    deposito.aggiorna([s], ora="2026-11-23T10:00:00+01:00", **p)
    deposito.aggiorna([s], ora="2026-11-23T11:00:00+01:00", **p)
    eventi = deposito.leggi_registro(p["registro"])
    assert [e["operazione"] for e in eventi] == ["generazione", "controllo", "controllo"]
    rec = deposito.leggi_archivio(p["archivio"])["schede"][s["id"]]
    assert rec["revisione"] == 1 and rec["ultimo_controllo"] == "2026-11-23T11:00:00+01:00"


def test_istituto_tolto_dal_catalogo_resta_come_storico(tmp_path, monkeypatch):
    _passaggi(monkeypatch, {})
    p = _percorsi(tmp_path)
    s = generatore.genera_scheda(_istituto("carta_docente"))
    deposito.aggiorna([s], ora="2026-11-23T10:00:00+01:00", **p)
    deposito.aggiorna([], ora="2026-11-23T11:00:00+01:00", **p)
    rec = deposito.leggi_archivio(p["archivio"])["schede"][s["id"]]
    assert rec["stato_ciclo"] == "ritirata"
    assert consultazione.stato_attuale(rec)["stato"] == "da_riesaminare"


class _Studio:
    def __init__(self, percorso):
        self.conn = sqlite3.connect(percorso)


def test_annotazione_e_rinomina_sopravvivono_alla_rigenerazione(tmp_path, monkeypatch):
    _passaggi(monkeypatch, {})
    p = _percorsi(tmp_path)
    ist = _istituto("carta_docente")
    s = generatore.genera_scheda(ist)
    deposito.aggiorna([s], ora="2026-11-23T10:00:00+01:00", **p)
    db = _Studio(tmp_path / "studio.db")
    voce = next(f"{f['tipo']}:{f['chiave']}" for f in s["fonti"])
    nota = annotazioni.Annotazioni(db).aggiungi(s["id"], sezione="fonti", voce=voce, testo="Verificata in udienza.",
                                                esito="", attore="Avv. Prova", revisione_scheda=1)
    # Rinomina dell'istituto: l'ID non cambia, la revisione sì, i collegamenti e la nota restano.
    rinominato = replace(ist, nome="Carta del docente (supplenti e personale di ruolo)")
    s2 = generatore.genera_scheda(rinominato)
    assert s2["id"] == s["id"] == id_scheda("pubblico impiego", "carta_docente")
    deposito.aggiorna([s2], ora="2026-11-24T10:00:00+01:00", **p)
    rec = deposito.leggi_archivio(p["archivio"])["schede"][s["id"]]
    assert rec["revisione"] == 2 and rec["titolo"].startswith("Carta del docente (supplenti")
    assert [e["operazione"] for e in deposito.leggi_registro(p["registro"]) if e["operazione"] != "controllo"] == ["generazione", "rinomina"]
    note = annotazioni.con_stato(annotazioni.Annotazioni(db).elenco(s["id"]), rec)
    assert [n["id"] for n in note] == [nota["id"]] and note[0]["voce_presente"] and note[0]["scheda_cambiata_dopo"]
    # Una correzione sostituisce la nota, la precedente resta nello storico del database.
    annotazioni.Annotazioni(db).aggiungi(s["id"], sezione="fonti", voce=voce, testo="Corretta.", esito="", attore="Avv. Prova",
                                         revisione_scheda=2, sostituisce=nota["id"])
    assert [n["testo"] for n in annotazioni.Annotazioni(db).elenco(s["id"])] == ["Corretta."]
    assert db.conn.execute("SELECT count(*) FROM conoscenza_annotazioni").fetchone()[0] == 2
    with pytest.raises(ValueError):
        annotazioni.Annotazioni(db).aggiungi(s["id"], sezione="inventata", voce="", testo="x", esito="", attore="A", revisione_scheda=1)


# ------------------------------------------------------------------------------------------------ viste e ricerca
def test_viste_index_e_log_ricostruibili(tmp_path, monkeypatch):
    _passaggi(monkeypatch, {})
    p = _percorsi(tmp_path)
    s = generatore.genera_scheda(_istituto("carta_docente"))
    deposito.aggiorna([s], ora="2026-11-23T10:00:00+01:00", **p)
    esito = deposito.scrivi_viste(["pubblico impiego"], cartella=tmp_path / "viste", **p)
    assert esito == {"materie": 1, "pagine": 1}
    indice = (tmp_path / "viste" / "index.md").read_text(encoding="utf-8")
    assert f"`{s['id']}`" in indice and "pubblico-impiego/index.md" in indice
    log = (tmp_path / "viste" / "log.md").read_text(encoding="utf-8")
    assert [r for r in log.splitlines() if r.startswith("## [")][0].startswith("## [2026-11-23T10:00:00+01:00] generazione |")
    pagina = (tmp_path / "viste" / "pubblico-impiego" / f"{s['id']}.md").read_text(encoding="utf-8")
    assert "## Limiti e lacune dichiarate" in pagina and "## Fonti con versione" in pagina


def test_ricerca_testuale_senza_embeddings(tmp_path, monkeypatch):
    _passaggi(monkeypatch, {})
    p = _percorsi(tmp_path)
    nuove = [generatore.genera_scheda(_istituto(i)) for i in ("licenziamento", "carta_docente", "esecuzione_contro_pa")]
    deposito.aggiorna(nuove, ora="2026-11-23T10:00:00+01:00", **p)
    monkeypatch.setenv("LEX_EMBEDDINGS_DISABLED", "1")
    r = consultazione.cerca("impugnare il licenziamento", percorso=p["archivio"])
    assert r and r[0]["id"] == "ist-licenziamento"
    r = consultazione.cerca("centoventi giorni pubblica amministrazione", percorso=p["archivio"])
    assert [x["id"] for x in r] == ["ist-esecuzione-contro-pa"] and r[0]["frammento"]
    assert consultazione.cerca("parola-che-non-esiste", percorso=p["archivio"]) == []
    assert consultazione.cerca("licenzia", materia="pubblico impiego", percorso=p["archivio"]) == []


def test_passaggio_della_norma_con_ancora():
    d = consultazione.passaggio_norma("dl669:14", "centoventi giorni dalla notificazione del titolo esecutivo")
    assert d and d["inizio"] >= 0 and "centoventi" in d["testo"][d["inizio"]:d["fine"]].lower()


# ------------------------------------------------------------------------------------------------ dati pubblicati
def test_archivio_pubblicato_copre_tutte_le_materie_e_regole():
    from lex.harness.fattispecie import REGOLE

    materie, istituti = carica()
    elenco = consultazione.schede()
    assert len(elenco) == len(istituti) and {s["materia"] for s in elenco} == set(materie)
    assert materie[:5] == ["pubblico impiego", "lavoro", "previdenza", "esecuzione contro la PA", "amministrativo"]
    regole = {r for s in elenco for r in s["regole"]}
    assert {r[0] for r in REGOLE} <= regole
    for s in elenco:
        assert s["fonti_dirette"] == len(s["fonti"]) and s["revisione"] >= 1 and s["ultimo_controllo"]
        for sez in s["sezioni"].values():
            for v in sez["voci"]:
                if not v["verifica"].startswith("dato da raccogliere"):
                    assert v["fonti"], (s["id"], v["testo"])


# ------------------------------------------------------------------------------------------------ Lex e API
def test_lex_consulta_la_scheda_prima_di_rispondere():
    from lex.harness import rispondi

    r = rispondi("Devo pignorare un'amministrazione pubblica che non paga la sentenza: quanti giorni devo aspettare dopo la "
                 "notifica del titolo prima del precetto?")
    assert r is not None
    scheda = r.registro.get("0_scheda_istituto")
    assert scheda and scheda["id"].startswith("ist-") and scheda["collegamento"].endswith(scheda["id"])
    assert "Scheda di istituto consultata" in r.testo


def test_api_conoscenza(tmp_path):
    from tests.test_revisione_2410_sicurezza import _app
    from tests.test_topbar_operational_api import _login
    from web.blueprints import react_shell
    from web.bootstrap.react_route_gate import _excluded, _is_react_route

    assert _is_react_route("/ricerca-legale/conoscenza") and not _excluded("/ricerca-legale/conoscenza")
    assert react_shell._route_component_key("/ricerca-legale/conoscenza") == "src/components/ConoscenzaPage.tsx"
    app = _app(tmp_path)
    with app.test_client() as client:
        assert client.get("/api/v1/ui/conoscenza").status_code == 401
        _login(client)
        dati = client.get("/api/v1/ui/conoscenza").get_json()
        assert dati["ok"] and dati["materie"][0]["materia"] == "pubblico impiego" and dati["totale"] >= 150
        r = client.get("/api/v1/ui/conoscenza/cerca?q=licenziamento").get_json()
        assert r["ok"] and r["risultati"] and "senza embeddings" in r["modalita"]
        ident = dati["materie"][0]["schede"][0]["id"]
        s = client.get(f"/api/v1/ui/conoscenza/schede/{ident}").get_json()
        assert s["ok"] and s["scheda"]["id"] == ident and s["stato_attuale"]["stato"]
        assert client.get("/api/v1/ui/conoscenza/schede/ist-non-esiste").status_code == 404
        n = client.get("/api/v1/ui/conoscenza/norma/dl669:14?ancora=centoventi giorni").get_json()
        assert n["ok"] and n["norma"]["inizio"] >= 0
        assert client.get("/api/v1/ui/conoscenza/norma/inesistente:1").status_code == 404
        assert client.get("/api/v1/ui/conoscenza/registro").get_json()["eventi"]
        r = client.post(f"/api/v1/ui/conoscenza/schede/{ident}/annotazioni", json={"sezione": "generale", "testo": "Nota di prova."})
        assert r.status_code == 200 and r.get_json()["ok"], r.get_json()
        assert client.post(f"/api/v1/ui/conoscenza/schede/{ident}/annotazioni", json={"sezione": "x", "testo": "y"}).status_code == 400
        s = client.get(f"/api/v1/ui/conoscenza/schede/{ident}").get_json()
        assert [a["testo"] for a in s["annotazioni"]] == ["Nota di prova."]


def test_nessuna_norma_abrogata_come_riferimento():
    """Gli ordini di protezione stanno negli artt. 473-bis.69 ss. c.p.c.: gli artt. 342-bis e 342-ter c.c. (abrogati dal
    d.lgs. 164/2024) restano solo come storico; nessuna norma di riferimento del catalogo è abrogata."""
    _, istituti = carica()
    ordini = next(i for i in istituti if i.id == "ordini_protezione")
    assert {n.chiave for n in ordini.norme} == {"cpc:473bis69", "cpc:473bis70"}
    assert {a["chiave"] for a in ordini.norme_abrogate} == {"cc:342bis", "cc:342ter"}
    for i in istituti:
        for n in i.norme:
            f = generatore.fonte_norma(n.chiave)
            assert f is not None and f["stato"] == "vigente" and n.stato_biblioteca != "abrogato", (i.id, n.chiave)
    s = consultazione.scheda("ist-ordini-protezione")
    assert not any(f["chiave"].startswith("cc:342") for f in s["fonti"]) and s["norme_abrogate"]


def test_norma_abrogata_citata_e_dichiarata():
    f = generatore.fonte_norma("dlgs546:17bis")
    assert f["stato"] == "abrogata" and not f["vigente"] and "220" in f["nota_abrogazione"]
