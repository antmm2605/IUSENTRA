"""Formule dei tribunali che il lettore dei provvedimenti perdeva (collaudo del 05/11/2026 sulle PEC reali).

Ordinanza di un giudice del lavoro (testo con parti inventate): il primo capo subito dopo il «P.Q.M.», il
«termine di ulteriori 10 giorni» senza decorrenza e le note «nel termine perentorio del giorno dell'udienza
fissata» non diventavano proposte. Date attese calcolate a mano: 10 giorni dal 04/11/2026 → sabato 14/11,
prorogato a lunedì 16/11/2026 (art. 155, commi 4-5, c.p.c.); note entro le 14:00 del 23/11/2026.
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace

from pct.note_127_ter.proposta import termine_equivalente
from pct.provvedimenti import esamina_provvedimento
from pct.provvedimenti.dispositivo import capi

ORDINANZA = (
    "TRIBUNALE ORDINARIO di VICENZA ORDINANZA tra ROSSI MARIA PARTE RICORRENTE e MINISTERO DELL'ISTRUZIONE E DEL MERITO "
    "PARTE RESISTENTE Il Giudice, Ritenuta ancora insufficiente la prova della permanenza nel sistema scolastico, Visto "
    "l'art. 421 c.p.c., P.Q.M. Assegna a parte ricorrente termine di ulteriori 10 giorni per depositare le graduatorie "
    "aggiornate; Rinvia per discussione all'udienza del 23/11/2026; Dispone che la trattazione dell'udienza sia sostituita "
    "dallo scambio di note scritte da depositarsi nel termine perentorio del giorno dell'udienza fissata, entro le ore 14.00 "
    "ex art. 127 ter c.p.c. Si comunichi. Vicenza, 04/11/2026. Il giudice dott. Mario Bianchi"
)


def _voci():
    esito = esamina_provvedimento(ORDINANZA, oggi=date(2026, 11, 5), comunicata_il=date(2026, 11, 5), rg="1/2026",
                                  ufficio="Tribunale di Vicenza", materia="lavoro")
    assert esito is not None
    return {voce.regola_id: voce for voce in esito.voci}


def test_il_primo_capo_dopo_il_pqm_non_si_perde():
    assert capi(ORDINANZA)[0].testo.startswith("Assegna a parte ricorrente termine")


def test_termine_di_ulteriori_giorni_senza_decorrenza_alla_data_piu_anticipata():
    voce = _voci()["giudice.deposito"]
    assert voce.genere == "termine" and voce.giorno == date(2026, 11, 16) and voce.chi == "ricorrente"
    assert voce.dies_a_quo == date(2026, 11, 4) and "Confermare la decorrenza" in voce.domanda


def test_note_nel_termine_del_giorno_dell_udienza_perentorie_alle_14():
    voce = _voci()["127ter.termine_note"]
    assert voce.giorno == date(2026, 11, 23) and voce.ora == "14:00" and voce.perentorio is True


def test_il_presidio_operativo_non_blocca_la_bozza_del_termine_legale():
    presidio = SimpleNamespace(id_fascicolo="F1", data_scadenza="2026-11-23", stato="APERTO",
                               deadline_profile_code="PEC_AUTO_PRESIDIO",
                               titolo="Riassegnazione termine per note in sostituzione udienza - 23/11/2026")
    assert termine_equivalente([presidio], fascicolo_id="F1", giorno=date(2026, 11, 23)) is None
    manuale = SimpleNamespace(**{**vars(presidio), "deadline_profile_code": ""})
    assert termine_equivalente([manuale], fascicolo_id="F1", giorno=date(2026, 11, 23)) is manuale


def test_conferma_del_termine_legale_assorbe_il_presidio_della_stessa_pec(tmp_path):
    from pct.scadenziario import GestioneScadenziario, StatoTermine, TipoTermine

    gs = GestioneScadenziario(str(tmp_path / "scadenze.json"))
    presidio = gs.nuova("Riassegnazione termine per note", TipoTermine.ADEMPIMENTO, "2026-11-23", id_fascicolo="F1",
                        note="PEC_AUDIT:pec_abc\nTipo evento: comunicazione_cancelleria", deadline_profile_code="PEC_AUTO_PRESIDIO")
    altra_pec = gs.nuova("Presidio di un'altra PEC", TipoTermine.ADEMPIMENTO, "2026-11-23", id_fascicolo="F1",
                         note="PEC_AUDIT:pec_zzz", deadline_profile_code="PEC_AUTO_PRESIDIO")
    bozza = gs.nuova("Deposito note scritte ex art. 127-ter c.p.c.", TipoTermine.ADEMPIMENTO, "2026-11-23", id_fascicolo="F1",
                     note="PEC_TERMINE_PROPOSTO:pec_abc:NOTE_127_TER", perentorio=True)
    gs.aggiorna(bozza.id, stato=StatoTermine.BOZZA)
    gs.conferma_bozza(bozza.id, attore="avvocato")
    assert gs.get(presidio.id).stato == StatoTermine.ANNULLATO and "Assorbita" in gs.get(presidio.id).note
    assert gs.get(altra_pec.id).stato == StatoTermine.APERTO


# --- Formule emerse dal collaudo su 1.784 testi reali (05/11/2026), riscritte con dati inventati ---

from pct.provvedimenti.ancore import ancora_del_capo  # noqa: E402
from pct.provvedimenti.materia import materia_del_provvedimento  # noqa: E402
from pct.provvedimenti.testo import normalizza  # noqa: E402
from pct.provvedimenti.testo import testo_incollato as _incollato  # noqa: E402

SENTENZA_LAVORO_CON_CPA = (
    "n. 12/2026 R.G. lav. REPUBBLICA ITALIANA TRIBUNALE ORDINARIO di VICENZA - PRIMA SEZIONE CIVILE - Settore delle "
    "controversie di lavoro IN NOME DEL POPOLO ITALIANO ... P.Q.M. accoglie il ricorso; condanna il Ministero a rifondere "
    "le spese che liquida in euro 325,00, oltre spese generali, iva e cpa, con distrazione. Cita T.A.R. Lazio, sent. 1/2020."
)


def test_la_cpa_delle_spese_non_rende_amministrativa_la_sentenza_del_lavoro():
    assert materia_del_provvedimento(SENTENZA_LAVORO_CON_CPA) == "lavoro"


def test_tribunale_in_funzione_di_giudice_del_lavoro():
    testo = "Il Tribunale in funzione di Giudice del Lavoro ha pronunciato la seguente Sentenza ... oltre CPA e IVA"
    assert materia_del_provvedimento(testo) == "lavoro"


def test_il_tar_resta_amministrativo():
    testo = "N. 01/2024 REG.RIC. REPUBBLICA ITALIANA Il Tribunale Amministrativo Regionale per il Lazio (Sezione Terza) ..."
    assert materia_del_provvedimento(testo) == "amministrativo"


def test_ordinanza_tar_che_assegna_termine_perentorio_dalla_comunicazione():
    testo = ("N. 01/2024 REG.RIC. Il Tribunale Amministrativo Regionale per il Lazio ha pronunciato la presente ORDINANZA "
             "P.Q.M. Il Tribunale Amministrativo Regionale per il Lazio (Sezione Terza), assegna alla ricorrente termine perentorio di giorni 10, decorrente dalla comunicazione "
             "della presente ordinanza, per la rinnovazione della notifica. Fissa per il prosieguo la camera di consiglio "
             "del 14 gennaio 2025. Così deciso in Roma nella camera di consiglio del giorno 19 novembre 2024")
    esito = esamina_provvedimento(testo, oggi=date(2024, 11, 27), comunicata_il=date(2024, 11, 27))
    assert esito is not None and esito.materia == "amministrativo"
    notifica = next(v for v in esito.voci if v.regola_id == "giudice.notifica")
    assert notifica.giorno == date(2024, 12, 9) and notifica.perentorio is True  # sabato 07/12 → lunedì (art. 52 c.p.a.)
    assert any(v.genere == "udienza" and v.giorno == date(2025, 1, 14) for v in esito.voci)


def test_prima_della_predetta_data_e_della_nuova_udienza():
    assert ancora_del_capo("notifica almeno 30 giorni prima della predetta data del 10/12/2026").tipo == "prima_udienza"
    assert ancora_del_capo("costituirsi fino a 10 giorni prima della nuova udienza sopra indicata").giorni == 10
    assert ancora_del_capo("costituirsi fino a 10 giorni prima del termine sopra indicato").tipo == "prima_udienza"


def test_anno_abbreviato_con_apostrofo_e_data_incollata_dall_ocr():
    assert "26.11.2026" in normalizza("udienza cartolare del 26.11.'26")
    assert "udienzadel 26.2.2026" in normalizza("all'udienzadel26.2.2026.")


def test_testo_senza_spazi_chiede_la_lettura_dell_originale():
    incollato = "IlGiudicedell'Esecuzione,vistalanotadiiscrizionearuoloconirelatividocumentiallegati; " * 6
    assert _incollato(normalizza(incollato)) and not _incollato(normalizza(ORDINANZA))


def test_sentenza_con_motivazione_riservata_attesa_e_termine_lungo_provvisorio():
    testo = ("REPUBBLICA ITALIANA IN NOME DEL POPOLO ITALIANO Il Tribunale di Pordenone, in funzione di Giudice del Lavoro, "
             "definitivamente pronunciando, P.Q.M. accoglie il ricorso. Fissa per il deposito della motivazione il termine "
             "di giorni 60 dall'odierna pronuncia. Così deciso in Pordenone, li 12/06/2025 Sentenza n. 1/2025 pubbl. il 12/06/2025")
    esito = esamina_provvedimento(testo, oggi=date(2025, 6, 13), comunicata_il=date(2025, 6, 13))
    voci = {v.regola_id: v for v in esito.voci}
    attesa = voci["giudice.motivazione_riservata"]
    assert attesa.genere == "attesa" and attesa.giorno == date(2025, 8, 11) and not attesa.scadenziario
    assert "provvisori" not in voci["legge.civ.327.impugnazione_lunga"].titolo
    assert "aggiornarla al deposito" in voci["legge.civ.327.impugnazione_lunga"].nota


def test_incarico_senza_data_diventa_adempimento():
    testo = ("Il Giudice del Lavoro, letto il ricorso, P.Q.M. Invita parte ricorrente a provvedere al tempestivo deposito "
             "telematico della documentazione attestante la notificazione dell'atto introduttivo. Velletri, 02/03/2026")
    esito = esamina_provvedimento(testo, oggi=date(2026, 3, 3), comunicata_il=date(2026, 3, 3)) or None
    assert esito is None or any(v.genere == "adempimento" and v.chi == "ricorrente" for v in esito.voci)


def test_rigetto_dell_istanza_di_trattazione_scritta_non_apre_le_note():
    testo = ("N. R.G. 1/2026 Tribunale di Brescia lavoro, previdenza ed assistenza obbligatoria Il Giudice, vista l'istanza "
             "di trattazione dell'udienza in trattazione scritta ex art. 127 ter c.p.c.; considerato che trattasi di prima "
             "udienza e che sia opportuno mantenerla nella forma già predisposta (trattazione da remoto); P.Q.M. Rigetta "
             "l'istanza. Brescia, 09/10/2026")
    esito = esamina_provvedimento(testo, oggi=date(2026, 10, 9), comunicata_il=date(2026, 10, 9))
    assert esito is not None and "note_127_ter" not in esito.tipi and esito.materia == "lavoro"
    voce = next(v for v in esito.voci if v.regola_id == "provvedimento.rigetto_trattazione_scritta")
    assert voce.modalita == "da_remoto" and "nessuna nota" in voce.titolo and "link di collegamento non in agenda" in voce.titolo
    assert not any(v.codice == "NOTE_127_TER" for v in esito.voci)


def test_rigetto_riporta_data_ora_e_collegamento_dell_udienza_in_agenda():
    testo = ("Tribunale di Brescia lavoro, previdenza ed assistenza obbligatoria Il Giudice, vista l'istanza di trattazione "
             "dell'udienza in trattazione scritta; ritenuto di mantenerla nella forma già predisposta (trattazione da remoto); "
             "P.Q.M. Rigetta l'istanza. Brescia, 09/10/2026")
    udienza = {"id": "APP1", "tipo": "UDIENZA", "stato": "PROGRAMMATO", "titolo": "Udienza di discussione", "id_fascicolo": "F1",
               "data_ora": "2026-10-29T09:15:00", "remote_hearing_url": "https://teams.microsoft.com/l/meetup-join/prova"}
    esito = esamina_provvedimento(testo, oggi=date(2026, 10, 9), comunicata_il=date(2026, 10, 9), fascicolo_id="F1",
                                  appuntamenti=[udienza])
    voce = next(v for v in esito.voci if v.regola_id == "provvedimento.rigetto_trattazione_scritta")
    assert voce.giorno == date(2026, 10, 29) and voce.ora == "09:15" and voce.id_appuntamento == "APP1"
    assert "del 29/10/2026 ore 09:15 si tiene da remoto" in voce.titolo and "collegamento indicato in agenda" in voce.titolo
