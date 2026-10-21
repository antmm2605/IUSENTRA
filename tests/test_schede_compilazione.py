"""Schede di compilazione dei 5 atti pilota."""
import json
from pathlib import Path

from pct.schede_compilazione import FONTI, campi_da_chiedere, carica_schede, scheda_per_template

CATALOGO = {t["id"] for t in json.loads(Path("pct/template_atti_catalogo_data/catalogo_master.json").read_text(encoding="utf-8"))["template"]}


def test_schede_coerenti_col_catalogo():
    schede = carica_schede()
    assert {"CIV_ORD_001", "CIV_ORD_009", "ESE_001", "LAV_001", "MON_001"} <= set(schede)
    coperti = [t for s in schede.values() for t in s["template"]]
    assert len(coperti) == len(set(coperti)), "ogni modello è coperto da una sola scheda"
    for s in schede.values():
        assert set(s["template"]) <= CATALOGO
        assert s["base_normativa"] and s["scrive_lex"] and s["astensione"]
        for campo in s["campi"]:
            assert campo["fonte"]["tipo"] in FONTI
            for norma in campo.get("norma", []) + s["base_normativa"]:
                assert norma["atto"] and norma["articolo"]


def test_domande_solo_per_i_dati_mancanti():
    s = scheda_per_template("MON_002")
    assert s["id"] == "MON_001"
    valori = {"difensore": "Avv. Rossi", "procura": "procura.pdf", "data_luogo": "Bari", "ricorrente": "Alfa srl",
              "debitore": "Beta srl", "fonte_credito": "contratto", "capitale": "1000", "prova_scritta": "fatture.pdf"}
    assert [m["campo"] for m in campi_da_chiedere(s, valori)] == ["interessi"]


def test_risoluzione_usa_gestionale_letture_documenti_e_chiede_il_resto():
    from pct.registro_letture.fatti_repository import Fatto
    from pct.schede_compilazione import risolvi_scheda, scheda_per_modello

    s = scheda_per_modello("CIV_COM_001")
    assert s["id"] == "CIV_ORD_009"
    fatti = [Fatto(categoria="ruolo", campo="rg_civile", valore="123/2026", etichetta="R.G. 123/2026"),
             Fatto(categoria="data", campo="udienza", valore="2027-01-10", etichetta="Udienza", verifica="respinto")]
    r = risolvi_scheda(s, {"defendant": "Rossi", "lawyer": "Avv. Bianchi", "place": "Bari"}, fatti=fatti,
                       documenti=["Atto di citazione notificato.pdf", "Procura.pdf"])
    stati = {c["campo"]: c["stato"] for c in r["campi"]}
    assert stati["convenuto"] == "compilato" and stati["procura"] == "documento_presente"
    assert stati["dati_causa"] == "da_confermare" and stati["termine_costituzione"] == "calcolo"
    assert stati["eccezioni"] == "proposta_lex"
    assert [d["campo"] for d in r["domande"]] == ["linea_difensiva", "fatti_contrari", "terzo"]


def test_luogo_di_sottoscrizione_e_la_citta_dello_studio():
    catalogo = json.loads(Path("pct/template_atti_catalogo_data/catalogo_master.json").read_text(encoding="utf-8"))
    assert all(t["prefill_bindings"]["place"][0] == "studio.citta" for t in catalogo["template"])


def test_registro_fonti_cita_rito_lavoro_e_precetto():
    from pct.template_atti_legal_sources import template_atti_sources_for_model

    lavoro = template_atti_sources_for_model(model_code="LAV_001", model_name="Ricorso rito lavoro", area="Diritto del lavoro")
    precetto = template_atti_sources_for_model(model_code="ESE_001", model_name="Atto di precetto", area="Diritto civile")
    assert any("414" in s["article"] for s in lavoro)
    assert any("480" in s["article"] for s in precetto)


def test_valori_zero_e_fatti_completi_non_vanno_persi():
    from copy import deepcopy
    from types import SimpleNamespace

    from pct.schede_compilazione import risolvi_scheda, scheda_per_modello
    s = deepcopy(scheda_per_modello("CIV_COM_001"))
    s["campi"] = [dict(campo="conteggio", etichetta="Conteggio", obbligatorio=True,
                        fonte=dict(tipo="database"), compilatore=["conteggio"]),
                  dict(campo="dati_causa", etichetta="Dati causa", obbligatorio=True,
                       fonte=dict(tipo="archivio_letture"), fatti=[dict(categoria="ruolo", campo="rg_civile")])]
    fatti = [SimpleNamespace(categoria="ruolo", campo="rg_civile", valore=str(i), etichetta=f"R.G. {i}", verifica="confermato") for i in range(1, 5)]
    r = risolvi_scheda(s, {"conteggio": 0}, fatti=fatti)
    assert r["campi"][0]["stato"] == "compilato"
    assert r["campi"][0]["valore"] == 0
    assert r["campi"][1]["valore"] == "R.G. 1; R.G. 2; R.G. 3; R.G. 4"
    assert r["domande"] == []


def test_civile_ordinario_monitorio_cautelare_giudice_di_pace_coperti():
    famiglie = ("CIV_ORD", "MON", "CAU", "GDP")
    attesi = {t for t in CATALOGO if t.rsplit("_", 1)[0] in famiglie}
    assert attesi <= {t for s in carica_schede().values() for t in s["template"]}


def test_termini_cautelari_senza_sospensione_feriale():
    reclamo = scheda_per_template("CAU_002")
    assert any(n["atto"] == "legge_742_1969" and n["articolo"] == "3" for n in reclamo["base_normativa"])


def test_termine_calcolato_dal_software_con_festivi_e_ferie():
    from datetime import date

    from pct.registro_letture.fatti_repository import Fatto
    from pct.schede_compilazione import risolvi_scheda

    comparsa = scheda_per_template("CIV_ORD_009")
    fatti = [Fatto(categoria="data", campo="udienza", valore="2027-04-18", etichetta="Udienza del 18/04/2027")]
    r = risolvi_scheda(comparsa, {}, fatti=fatti, oggi=date(2026, 10, 19))
    termine = next(c for c in r["campi"] if c["campo"] == "termine_costituzione")
    # 70 giorni a ritroso: domenica 07/02/2027, anticipata a venerdì 05/02/2027
    assert termine["stato"] == "calcolato" and termine["valore"] == "05/02/2027" and not termine["scaduto"]

    opposizione = scheda_per_template("MON_011")
    notifica = [Fatto(categoria="data", campo="notifica", valore="2026-07-20", etichetta="Notifica del decreto")]
    r = risolvi_scheda(opposizione, {}, fatti=notifica, oggi=date(2026, 10, 19))
    scadenza = next(c for c in r["campi"] if c["campo"] == "scadenza_opposizione")
    # 40 giorni con agosto sospeso: martedì 29/09/2026, già passato al 19/10/2026
    assert scadenza["valore"] == "29/09/2026" and scadenza["scaduto"]


def test_termini_dichiarati_validi():
    from pct.schede_termini import valida_termine

    for s in carica_schede().values():
        for c in s["campi"]:
            if c["fonte"].get("termine"):
                assert valida_termine(c["fonte"]["termine"]) == [], (s["id"], c["campo"])


def test_impugnazione_delibera_societaria_comprende_la_sospensione_feriale():
    from datetime import date

    from pct.schede_termini import calcola
    from scripts.schede_compilazione.impresa import SCHEDE

    salvata = scheda_per_template("SOC_005")
    generata = next(s for s in SCHEDE if s["id"] == "SOC_005")
    for scheda in (salvata, generata):
        campo = next(c for c in scheda["campi"] if c["campo"] == "termine")
        termine = campo["fonte"]["termine"]
        assert termine["feriale"] is True
        assert calcola(termine, date(2026, 7, 29))["scadenza"] == "2026-11-27"


def test_regola_di_calcolo_consultabile_anche_prima_della_data_di_partenza():
    from pct.schede_compilazione import risolvi_scheda

    risolta = risolvi_scheda(scheda_per_template("SOC_005"), {})
    termine = next(c for c in risolta["campi"] if c["campo"] == "termine")
    assert termine["stato"] == "calcolo"
    assert "valore" not in termine
    assert "con sospensione feriale" in termine["spiegazione"]
    assert "19100.pdf" in termine["spiegazione"]


def test_esecuzioni_e_locazioni_coperte():
    attesi = {t for t in CATALOGO if t.rsplit("_", 1)[0] in ("ESE", "LOC")}
    assert attesi <= {t for s in carica_schede().values() for t in s["template"]}
    sfratto = scheda_per_template("LOC_001")
    assert any(n["atto"] == "legge_742_1969" and n["articolo"] == "3" for n in sfratto["base_normativa"])


def test_famiglia_volontaria_lavoro_coperti():
    attesi = {t for t in CATALOGO if t.rsplit("_", 1)[0] in ("FAM", "VGS", "LAV")}
    assert attesi <= {t for s in carica_schede().values() for t in s["template"]}
    licenziamento = scheda_per_template("LAV_003")
    assert any(n["atto"] == "legge_604_1966" and n["articolo"] == "6" for n in licenziamento["base_normativa"])
    termine = next(c for c in licenziamento["campi"] if c["campo"] == "termine_impugnazione")
    assert termine["fonte"]["termine"]["feriale"] is False


def test_penale_amministrativo_tributario_coperti():
    attesi = {t for t in CATALOGO if t.rsplit("_", 1)[0] in ("PEN", "AMM", "TRI")}
    assert attesi <= {t for s in carica_schede().values() for t in s["template"]}
    ricorso = scheda_per_template("TRI_018")
    assert any(n["atto"] == "175/2024" and n["articolo"] == "67" for n in ricorso["base_normativa"])


def test_tutti_i_modelli_del_catalogo_hanno_una_scheda():
    coperti = {t for s in carica_schede().values() for t in s["template"]}
    assert set(CATALOGO) - coperti == set()


def test_norme_integrate_il_20_ottobre():
    def atti(t):
        return {(n["atto"], n["articolo"]) for n in scheda_per_template(t)["base_normativa"]}
    assert ("dpr_639_1970", "47") in atti("LAV_013") and ("dl_269_2003", "42") in atti("LAV_014")
    assert ("legge_1185_1967", "3") in atti("FAM_024")
    assert ("dpr_396_2000", "95") in atti("VGS_017")
    assert ("dlgs_168_2003", "3") in atti("SOC_005")


def test_il_costruttore_scarta_gli_articoli_abrogati(tmp_path):
    import sqlite3

    from scripts.schede_compilazione.costruisci import _articoli
    db = tmp_path / "n.sqlite"
    c = sqlite3.connect(db)
    c.execute("CREATE TABLE normative_documents (id INTEGER, collection_name TEXT)")
    c.execute("CREATE TABLE normative_articles (document_id INTEGER, article_number TEXT, article_text TEXT)")
    c.execute("INSERT INTO normative_documents VALUES (1, 'Lex fonti: codice_civile')")
    c.executemany("INSERT INTO normative_articles VALUES (1, ?, ?)", [
        ("2409", "Art. 2409. ((ARTICOLO ABROGATO DAL D.LGS. 27 MARZO 2026, N. 47))"),
        ("2396quater", "Art. 2396-quater. (Denunzia al tribunale) Se vi è fondato sospetto...")])
    c.commit()
    assert _articoli(db)["codice_civile"] == {"2396quater"}
