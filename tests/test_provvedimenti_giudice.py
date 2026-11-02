"""Provvedimenti del giudice letti per l'avvocato, in tutte le materie (pct/provvedimenti).

Richiesta dell'avvocato del 02/11/2026: per ogni decreto, ordinanza, verbale o sentenza
arrivato via PEC o letto dal fascicolo, il software legge che cosa ordina il giudice e
propone i passi successivi (udienze e modalità, termini, adempimenti, attese), con
regola, norma, prova, dati e confidenza; se una data è ambigua chiede.

Le fixture in ``tests/fixtures/provvedimenti`` riproducono i modelli dei provvedimenti
(artt. 171-bis, 189, 415, 473-bis.14, 633 ss. c.p.c.; art. 552 c.p.p.; art. 71 c.p.a.;
art. 79 D.Lgs. 175/2024) con parti, uffici e numeri di ruolo inventati. Le date attese
sono quelle del motore ``pct/termini_processuali.py`` (giorni liberi, lettura prudenziale,
sabato e festivi, sospensione feriale).
"""

from __future__ import annotations

import json
import re
from datetime import date, datetime, timedelta
from email import message_from_bytes, policy
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from pct.procedura_fasi.fonti import FONTI
from pct.provvedimenti import esamina_provvedimento, proposte_scadenziario
from pct.provvedimenti.regole import PERCORSO_REGOLE
from pct.provvedimenti.tipi import TIPI
from pct.termini_processuali import DEFAULT_TEMPLATES

CARTELLA = Path(__file__).parent / "fixtures" / "provvedimenti"
DECRETO_127_TER = (Path(__file__).parent / "fixtures" / "pec" / "decreto_note_scritte_127_ter.txt").read_text(encoding="utf-8")
OGGI = date(2026, 11, 2)
ROME_TZ = ZoneInfo("Europe/Rome")


def _testo(nome: str) -> str:
    return (CARTELLA / nome).read_text(encoding="utf-8")


def _esame(testo: str, **campi):
    campi.setdefault("oggi", OGGI)
    esito = esamina_provvedimento(testo, **campi)
    assert esito is not None
    return esito


def _voci(esito, prefisso: str = "") -> dict[str, list]:
    trovate: dict[str, list] = {}
    for voce in esito.voci:
        if voce.regola_id.startswith(prefisso):
            trovate.setdefault(voce.regola_id, []).append(voce)
    return trovate


def _date(esito, prefisso: str) -> dict[str, str]:
    return {v.regola_id: v.giorno.isoformat() for v in esito.voci if v.regola_id.startswith(prefisso) and v.giorno}


# ── Tabella versionata e contratto d'uscita ───────────────────────────


def test_ogni_regola_cita_norme_registrate_tipi_noti_e_modelli_esistenti():
    tabella = json.loads(PERCORSO_REGOLE.read_text(encoding="utf-8"))
    modelli = {t.code for t in DEFAULT_TEMPLATES}
    identificativi = set()
    for regola in tabella["regole"]:
        assert regola["id"] not in identificativi, regola["id"]
        identificativi.add(regola["id"])
        assert regola["norme"] and all(n in FONTI for n in regola["norme"]), regola["id"]
        assert set(regola["tipi"]) <= set(TIPI), regola["id"]
        assert set(regola["materie"]) <= {"civile", "lavoro", "famiglia", "penale", "amministrativo", "tributario"}
        termine = regola.get("termine") or {}
        assert not termine.get("template") or termine["template"] in modelli, regola["id"]
    for verifica in tabella["verifiche_preavviso"]:
        assert all(n in FONTI for n in verifica["norme"])
    assert "Normattiva" in tabella["consultazione"] and "02/11/2026" in tabella["consultazione"]


def test_le_nuove_fonti_hanno_url_normattiva_data_ed_estratto():
    for chiave in ("cpc_127bis", "cpc_193", "cpc_201", "cpc_250", "dispatt_103", "cpc_473bis14", "cpc_473bis17",
                   "cpa_71", "cpa_73", "cpa_92_lungo", "tu175_art79", "tu175_art80", "tu175_art81", "cpp_468", "cpc_175"):
        voce = FONTI[chiave]
        assert voce["url"].startswith("https://www.normattiva.it/uri-res/N2Ls?urn:nir:")
        assert "02/11/2026" in voce["verifica"] and len(voce["estratto"]) > 80


def test_ogni_voce_porta_regola_norme_prova_e_confidenza():
    for nome in sorted(p.name for p in CARTELLA.glob("*.txt")):
        esito = _esame(_testo(nome), comunicata_il=OGGI)
        assert esito.voci, nome
        for voce in esito.voci:
            assert voce.regola_id and voce.confidenza > 0, (nome, voce)
            assert all(n in FONTI for n in voce.norme), (nome, voce.regola_id)
            assert voce.norme or voce.regola_id.startswith("giudice."), (nome, voce.regola_id)
            riga = voce.come_dizionario("F1")
            assert riga["chiave"].startswith(voce.regola_id) and riga["stato"] in {"proposto", "da_confermare", "da_chiedere"}
            if voce.genere == "da_verificare":
                assert voce.domanda and riga["stato"] == "da_chiedere"


# ── Civile: verifiche preliminari e memorie dell'art. 171-ter ─────────


def test_decreto_171_bis_udienza_in_presenza_e_tre_memorie_a_ritroso():
    esito = _esame(_testo("civile_171bis.txt"))
    assert esito.tipi[0] == "verifiche_171bis" and esito.materia == "civile"
    [udienza] = [v for v in esito.voci if v.genere == "udienza"]
    assert (udienza.giorno, udienza.ora, udienza.modalita) == (date(2027, 4, 15), "10:00", "in_presenza")
    assert _date(esito, "legge.civ.171ter") == {
        "legge.civ.171ter.memoria_1": "2027-03-05", "legge.civ.171ter.memoria_2": "2027-03-25", "legge.civ.171ter.memoria_3": "2027-04-02",
    }
    prima = _voci(esito)["legge.civ.171ter.memoria_1"][0]
    assert prima.norme == ("cpc_171ter",) and "171-ter" in prima.prova and prima.perentorio and prima.facoltativo
    assert ("Udienza", "15/04/2027 ore 10:00", "provvedimento") in prima.dati


# ── Lavoro: decreto ex art. 415 c.p.c. ─────────────────────────────────


def test_decreto_415_notifica_e_costituzione_senza_sospensione_feriale():
    esito = _esame(_testo("lavoro_415.txt"))
    assert esito.materia == "lavoro" and esito.data_pronuncia == date(2026, 10, 28)
    voci = {v.codice: v for v in esito.voci if v.codice}
    assert voci["LAV_415_NOTIFICA_DIECI_GIORNI"].giorno == date(2026, 11, 9)  # 07/11 è sabato
    assert voci["LAV_415_NOTIFICA_DIECI_GIORNI"].perentorio is False
    assert voci["LAV_415_NOTIFICA_TRENTA_GIORNI"].giorno == date(2027, 1, 18)
    costituzione = voci["LAV_416_COSTITUZIONE"]
    assert costituzione.giorno == date(2027, 2, 5) and costituzione.regola_id == "giudice.costituzione"
    assert costituzione.norme == ("cpc_416",) and costituzione.chi == "resistente"


def test_le_proposte_415_non_doppiano_quelle_gia_fatte_dalla_pipeline():
    esito = _esame(_testo("lavoro_415.txt"))
    bozze = proposte_scadenziario(esito, oggi=OGGI, fascicolo_id="F1",
                                  codici_gia_proposti=["LAV_415_NOTIFICA_DIECI_GIORNI", "LAV_415_NOTIFICA_TRENTA_GIORNI"])
    assert [b.code for b in bozze] == ["LAV_416_COSTITUZIONE"]
    assert bozze[0].marker("M1") == "PEC_TERMINE_PROPOSTO:M1:LAV_416_COSTITUZIONE" and "art. 416 c.p.c." in bozze[0].summary()


# ── Mezzi istruttori: testimoni e CTU ──────────────────────────────────


def test_ammissione_prove_intimazione_testi_e_calendario_della_consulenza():
    esito = _esame(_testo("ammissione_prove_ctu.txt"), comunicata_il=OGGI)
    assert {"ammissione_prove", "nomina_ctu"} <= set(esito.tipi)
    assert not _voci(esito, "legge.civ.171ter"), "la memoria ex 171-ter citata come storia non apre termini"
    intimazione = _voci(esito)["legge.civ.103.intimazione_testi"][0]
    assert intimazione.giorno == date(2027, 3, 2) and intimazione.norme == ("dispatt_103", "cpc_250")
    consulenza = [(v.giorno.isoformat(), v.chi) for v in esito.voci if v.regola_id == "giudice.relazione"]
    assert consulenza == [("2027-01-15", "consulente tecnico d'ufficio"), ("2027-02-01", "parti"),
                          ("2027-02-20", "consulente tecnico d'ufficio")]
    ctp = next(v for v in esito.voci if "consulente tecnico di parte" in v.titolo)
    assert ctp.giorno == date(2026, 11, 17) and ctp.norme == ("cpc_201",)
    assert next(v for v in esito.voci if v.regola_id == "giudice.pagamento").giorno == date(2026, 12, 2)
    assert "legge.civ.250.deposito_intimazione" in _voci(esito) and "legge.civ.193.giuramento_ctu" in _voci(esito)


def test_senza_data_di_comunicazione_i_termini_che_ne_decorrono_sono_domande():
    esito = _esame(_testo("ammissione_prove_ctu.txt"))
    domande = [v for v in esito.voci if v.genere == "da_verificare"]
    assert len(domande) == 2 and all("comunicazione" in v.domanda for v in domande)
    assert not proposte_scadenziario(esito, oggi=OGGI, fascicolo_id="F1", codici_gia_proposti=["PROVV_RELAZIONE",
                                     "PROVV_GIURAMENTO", "CIV_INTIMAZIONE_TESTI_103"])


# ── Rimessione in decisione (art. 189 c.p.c.) ──────────────────────────


def test_rimessione_in_decisione_tre_termini_dall_udienza_di_rimessione():
    esito = _esame(_testo("rimessione_189.txt"))
    assert _date(esito, "legge.civ.189") == {
        "legge.civ.189.note_conclusioni": "2027-03-19", "legge.civ.189.conclusionali": "2027-04-19", "legge.civ.189.repliche": "2027-05-04",
    }
    assert not [v for v in esito.voci if v.genere == "da_verificare"]


def test_termine_del_giudice_prevale_sul_limite_di_legge():
    testo = _testo("rimessione_189.txt").replace(
        "ASSEGNA alle parti i termini perentori di cui all'art. 189 c.p.c.",
        "ASSEGNA alle parti termine perentorio sino al 15/02/2027 per il deposito delle note di precisazione delle conclusioni; "
        "ASSEGNA alle parti i termini perentori di cui all'art. 189 c.p.c.")
    esito = _esame(testo)
    assert "legge.civ.189.note_conclusioni" not in _voci(esito)
    note = next(v for v in esito.voci if v.codice == "CIV_NOTE_CONCLUSIONI_189")
    assert note.giorno == date(2027, 2, 15) and note.regola_id == "giudice.note"


# ── Decreto ingiuntivo e sentenza ───────────────────────────────────────


def test_decreto_ingiuntivo_notifica_entro_60_giorni_e_opposizione_da_notifica():
    esito = _esame(_testo("decreto_ingiuntivo.txt"))
    assert esito.tipi[0] == "decreto_ingiuntivo"
    assert _date(esito, "legge.civ.644") == {"legge.civ.644.notifica_decreto_ingiuntivo": "2026-12-28"}
    [opposizione] = _voci(esito)["legge.civ.641.opposizione_decreto_ingiuntivo"]
    assert opposizione.genere == "da_verificare" and "notificazione" in opposizione.domanda and opposizione.giorno is None
    assert not _voci(esito, "giudice."), "l'avvertimento sull'opposizione è già la regola dell'art. 641"


@pytest.mark.parametrize("ufficio, regola, scadenza", [
    ("TRIBUNALE ORDINARIO DI LONTANO", "legge.civ.327.impugnazione_lunga", "2027-04-28"),
    ("TRIBUNALE AMMINISTRATIVO REGIONALE PER LA REGIONE LONTANA", "legge.amm.92.impugnazione_lunga", "2027-04-28"),
])
def test_sentenza_termine_lungo_per_giurisdizione_e_nessun_passo_dalla_storia(ufficio, regola, scadenza):
    esito = _esame(_testo("sentenza_civile.txt").replace("TRIBUNALE ORDINARIO DI LONTANO", ufficio))
    assert esito.tipi == ("sentenza",)
    assert _date(esito, regola) == {regola: scadenza}
    assert not [v for v in esito.voci if v.genere == "udienza" or v.regola_id.startswith(("127ter", "esclusione"))]
    assert any(v.genere == "attesa" and "notificazione" in (v.domanda + v.nota + v.titolo) for v in esito.voci)


def test_sentenza_penale_chiede_la_data_di_deposito_della_motivazione():
    testo = _testo("sentenza_civile.txt").replace("TRIBUNALE ORDINARIO DI LONTANO", "TRIBUNALE DI LONTANO IN COMPOSIZIONE MONOCRATICA PENALE") + "\nImputato: FALCHI DARIO (art. 544 c.p.p.)"
    esito = _esame(testo)
    assert esito.materia == "penale"
    [voce] = esito.voci
    assert voce.regola_id == "legge.pen.585.impugnazione" and voce.genere == "da_verificare" and voce.norme == ("cpp_585",)


# ── Famiglia, tributario, amministrativo, penale ───────────────────────


def test_famiglia_473_bis_notifica_costituzione_e_memorie():
    esito = _esame(_testo("famiglia_473bis.txt"))
    assert esito.materia == "famiglia"
    codici = {v.codice: v.giorno.isoformat() for v in esito.voci if v.codice}
    assert codici == {"FAM_473BIS_NOTIFICA": "2027-02-19", "FAM_473BIS_COSTITUZIONE": "2027-03-22",
                      "FAM_473BIS17_MEMORIA_1": "2027-04-01", "FAM_473BIS17_MEMORIA_2": "2027-04-09", "FAM_473BIS17_MEMORIA_3": "2027-04-16"}


def test_tributario_camera_di_consiglio_termini_liberi_e_preavviso():
    esito = _esame(_testo("tributario_avviso.txt"), comunicata_il=OGGI)
    [udienza] = [v for v in esito.voci if v.genere == "udienza"]
    assert udienza.modalita == "camera_di_consiglio" and udienza.norme == ("tu175_art79",)
    assert _date(esito, "legge.trib") == {
        "legge.trib.80.documenti": "2027-02-04", "legge.trib.80.memorie": "2027-02-12",
        "legge.trib.81.istanza_pubblica_udienza": "2027-02-12", "legge.trib.80.repliche": "2027-02-19",
    }
    assert not _voci(esito, "verifica.")
    tardivo = _esame(_testo("tributario_avviso.txt"), comunicata_il=date(2027, 2, 1))
    [verifica] = _voci(tardivo, "verifica.").values()
    assert verifica[0].norme == ("tu175_art79",) and "trenta giorni liberi" in verifica[0].titolo


def test_amministrativo_termini_dell_art_73_e_preavviso_di_sessanta_giorni():
    esito = _esame(_testo("amministrativo_avviso.txt"), comunicata_il=OGGI)
    assert esito.materia == "amministrativo"
    assert _date(esito, "legge.amm.73") == {"legge.amm.73.documenti": "2027-02-05", "legge.amm.73.memorie": "2027-02-15",
                                            "legge.amm.73.repliche": "2027-02-25"}
    assert not _voci(esito, "verifica.")
    assert _voci(_esame(_testo("amministrativo_avviso.txt"), comunicata_il=date(2027, 2, 1)), "verifica.amm.71")


def test_penale_lista_testimoni_sette_giorni_prima_senza_proroga_del_sabato():
    esito = _esame(_testo("penale_citazione.txt"))
    assert esito.materia == "penale" and esito.tipi[0] == "citazione_penale"
    [udienza] = [v for v in esito.voci if v.genere == "udienza"]
    assert (udienza.giorno, udienza.ora, udienza.norme) == (date(2027, 4, 12), "09:00", ("cpp_552",))
    assert _date(esito, "legge.pen") == {"legge.pen.468.lista_testimoni": "2027-04-03"}  # sabato: nel penale resta


def test_127_ter_citato_in_un_rito_escluso_diventa_domanda():
    testo = _testo("penale_citazione.txt").replace(
        "AVVISA", "DISPONE che l'udienza sia sostituita dal deposito di note scritte ai sensi dell'art. 127-ter c.p.c.;\nAVVISA")
    esito = _esame(testo)
    [esclusione] = _voci(esito, "esclusione.").values()
    assert esclusione[0].genere == "da_verificare" and "penale" in esclusione[0].domanda
    assert not _voci(esito, "127ter") and not _voci(esito, "legge.civ.127ter")


# ── Udienza da remoto e trattazione scritta ─────────────────────────────


def test_udienza_da_remoto_istanza_di_presenza_e_preavviso_di_quindici_giorni():
    esito = _esame(_testo("udienza_remota_127bis.txt"), comunicata_il=OGGI)
    [udienza] = [v for v in esito.voci if v.genere == "udienza"]
    assert udienza.modalita == "da_remoto" and udienza.norme == ("cpc_127bis",)
    assert _date(esito, "legge.civ.127bis") == {"legge.civ.127bis.istanza_presenza": "2026-11-09"}
    assert not _voci(esito, "giudice."), "l'avviso sull'istanza di presenza è già la regola dell'art. 127-bis"
    tardivo = _esame(_testo("udienza_remota_127bis.txt"), oggi=date(2027, 1, 8), comunicata_il=date(2027, 1, 10))
    assert _voci(tardivo, "verifica.civ.127bis.preavviso")


def test_decreto_127_ter_senza_data_e_un_caso_dello_strato_generico():
    udienza = {"id": "A1", "tipo": "UDIENZA", "stato": "PROGRAMMATO", "data_ora": "2026-12-15T09:00:00", "id_fascicolo": "F1"}
    esito = _esame(DECRETO_127_TER, comunicata_il=OGGI, fascicolo_id="F1", appuntamenti=[udienza])
    assert esito.note_127_ter is not None
    note = _voci(esito)["127ter.termine_note"][0]
    assert (note.giorno, note.ora, note.codice, note.id_appuntamento) == (date(2026, 12, 15), "09:30", "NOTE_127_TER", "A1")
    assert _voci(esito)["127ter.udienza_cartolare"][0].modalita == "cartolare"
    assert "127ter.adempimento.prova_notifica" in _voci(esito)
    bozze = proposte_scadenziario(esito, oggi=OGGI, fascicolo_id="F1")
    assert {b.code for b in bozze} == {"NOTE_127_TER", "CIV_OPPOSIZIONE_127_TER"}
    note_bozza = next(b for b in bozze if b.code == "NOTE_127_TER")
    assert note_bozza.campi_scadenza["operational_due_at"] == "2026-12-15T09:30:00"
    assert note_bozza.campi_scadenza["hearing_mode"] == "note_scritte"


def test_decreto_127_ter_con_due_udienze_future_chiede_quale():
    udienze = [{"id": f"A{i}", "tipo": "UDIENZA", "stato": "PROGRAMMATO", "data_ora": giorno, "id_fascicolo": "F1"}
               for i, giorno in enumerate(("2026-12-15T09:00:00", "2027-01-20T10:00:00+01:00"))]
    esito = _esame(DECRETO_127_TER, comunicata_il=OGGI, fascicolo_id="F1", appuntamenti=udienze)
    [domanda] = _voci(esito)["127ter.udienza_sostituita"]
    assert "15/12/2026" in domanda.domanda and "20/01/2027" in domanda.domanda
    assert not _voci(esito, "127ter.termine_note")
    assert "NOTE_127_TER" not in {b.code for b in proposte_scadenziario(esito, oggi=OGGI, fascicolo_id="F1")}


def test_decreto_127_ter_con_data_propria_e_termine_minimo_di_quindici_giorni():
    testo = DECRETO_127_TER.replace("sino alla data della predetta udienza", "sino al 10/11/2026").replace(
        "che l’udienza già fissata sia sostituita", "che l’udienza del 10/11/2026 sia sostituita")
    esito = _esame(testo, comunicata_il=OGGI)
    assert esito.note_127_ter is None
    note = next(v for v in esito.voci if v.codice == "NOTE_127_TER")
    assert (note.giorno, note.ora, note.perentorio) == (date(2026, 11, 10), "09:30", True)
    assert _voci(esito, "127ter.termine_minimo")


# ── Ambiguità: nessuna data indovinata ───────────────────────────────────


def test_termine_senza_decorrenza_e_udienza_ambigua_diventano_domande():
    testo = ("TRIBUNALE ORDINARIO DI LONTANO\nR.G. n. 77/2026\nIl Giudice\nP.Q.M.\n"
             "ASSEGNA alle parti termine di giorni 20 per il deposito di note illustrative;\n"
             "ORDINA a parte ricorrente di depositare i documenti almeno 10 giorni prima dell'udienza;\n"
             "FISSA l'udienza del 10/02/2027 ore 9:30 e l'udienza del 10/03/2027 ore 9:30 per la discussione.\n")
    esito = _esame(testo)
    domande = [v.domanda for v in esito.voci if v.genere == "da_verificare"]
    assert any("senza dire da quando" in d for d in domande)
    assert any("10/02/2027" in d and "10/03/2027" in d for d in domande)
    assert not proposte_scadenziario(esito, oggi=OGGI, fascicolo_id="F1")


def test_udienza_del_fascicolo_usata_se_il_provvedimento_non_la_scrive():
    testo = ("TRIBUNALE ORDINARIO DI LONTANO\nR.G. n. 77/2026\nIl Giudice\nP.Q.M.\n"
             "ORDINA a parte ricorrente di depositare i documenti almeno 10 giorni prima dell'udienza.\nLontano, 30/10/2026\n")
    esito = esamina_provvedimento(testo, oggi=OGGI, fascicolo_id="F1", prossima_udienza="2027-01-21T09:00:00+01:00")
    assert esito is None  # nessun tipo di provvedimento riconosciuto: nessuna voce
    testo = testo.replace("ORDINA", "RINVIA la causa a nuovo ruolo; ORDINA")
    esito = _esame(testo, fascicolo_id="F1", prossima_udienza="2027-01-21T09:00:00+01:00")
    voce = next(v for v in esito.voci if v.regola_id == "giudice.deposito")
    assert voce.giorno == date(2027, 1, 8) and ("Udienza", "21/01/2027 ore 09:00", "agenda e scadenziario del fascicolo") in voce.dati


# ── Nessun doppione e nessuna scrittura silenziosa ───────────────────────


def test_stesso_provvedimento_due_volte_nessun_doppione():
    esito = _esame(_testo("civile_171bis.txt"))
    prima = proposte_scadenziario(esito, oggi=OGGI, fascicolo_id="F1")
    assert [b.code for b in prima] == ["CIV_MEMORIA_171_TER_1", "CIV_MEMORIA_171_TER_2", "CIV_MEMORIA_171_TER_3"]
    esistenti = [{"id_fascicolo": "F1", "data_scadenza": b.due_date, "deadline_profile_code": b.code, "stato": "BOZZA"} for b in prima]
    assert proposte_scadenziario(_esame(_testo("civile_171bis.txt")), oggi=OGGI, fascicolo_id="F1", scadenze=esistenti) == []
    scartata = [{**esistenti[0], "stato": "ANNULLATO"}]
    assert "CIV_MEMORIA_171_TER_1" not in {b.code for b in proposte_scadenziario(esito, oggi=OGGI, fascicolo_id="F1", scadenze=scartata)}


def _decreto_415_mime(tag: str, oggi: date) -> bytes:
    from tests.test_pec_change_receipt import _cancelleria_mime

    udienza, pronuncia = oggi + timedelta(days=70), oggi - timedelta(days=1)
    testo = _testo("lavoro_415.txt").replace("18/02/2027", f"{udienza:%d/%m/%Y}").replace("28/10/2026", f"{pronuncia:%d/%m/%Y}")
    mime = message_from_bytes(_cancelleria_mime(
        "ATTO NON CODIFICATO", "DECRETO", rg="523/2026/LAV", ufficio="TRIBUNALE ORDINARIO DI VICENZA",
        when=oggi.strftime("%a, %d %b %Y") + " 09:10:00 +0100", tag=tag, ricorrente="BARILARO FRANCESCO",
    ), policy=policy.SMTP)
    mime.add_attachment(testo.encode(), maintype="text", subtype="plain", filename="decreto.txt")
    return mime.as_bytes(policy=policy.SMTP)


def test_pec_con_decreto_415_propone_le_bozze_una_volta_sola(tmp_path):
    from pct.scadenziario import GestioneScadenziario, StatoTermine
    from tests.test_pec_audit_pipeline import _repo_con_fascicolo
    from tests.test_pec_change_receipt import _run_cancelleria

    repo, _ = _repo_con_fascicolo(tmp_path)
    oggi = datetime.now(ROME_TZ).date()

    def bozze():
        return [s for s in GestioneScadenziario(str(tmp_path / "scadenze.json")).tutte(solo_aperte=False)
                if re.match(r"LAV_41[56]_", str(s.deadline_profile_code or ""))]

    primo = _run_cancelleria(repo, _decreto_415_mime("415-1", oggi), "INBOX:UID:4151")
    repo.link_fascicolo(primo, threshold=0.5, actor="pytest")
    codici = sorted(s.deadline_profile_code for s in bozze())
    assert codici == ["LAV_415_NOTIFICA_DIECI_GIORNI", "LAV_415_NOTIFICA_TRENTA_GIORNI", "LAV_416_COSTITUZIONE"]
    assert all(s.stato == StatoTermine.BOZZA for s in bozze())
    repo.record_pec_schedule_change_receipts(since="2026-01-01T00:00:00Z", actor="pytest")
    secondo = _run_cancelleria(repo, _decreto_415_mime("415-2", oggi), "INBOX:UID:4152")
    repo.link_fascicolo(secondo, threshold=0.5, actor="pytest")
    assert len(bozze()) == 3
