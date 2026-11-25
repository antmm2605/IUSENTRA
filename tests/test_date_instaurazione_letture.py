"""Date dell'atto introduttivo lette nelle fonti certe del procedimento (testi inventati).

Servono a stabilire se alla causa si applica il testo anteriore o successivo al d.lgs. 149/2022
(art. 35, comma 1: procedimenti instaurati dopo il 28/02/2023).
"""
from types import SimpleNamespace

import pytest

from pct.archivio_letture.date_campi_modello import estrai_date_modello


def matter(**extra):
    dati = dict(id="f", id_cliente="", nome_cliente="Rossi Maria", numero_rg="321",
                anno_rg="2025", tribunale="TRIBUNALE DI VELLETRI")
    return SimpleNamespace(**{**dati, **extra})


def campi(testo, **kw):
    return [(f.campo, f.valore, f.verifica) for f in estrai_date_modello(testo, fascicolo=matter(), **kw)]


DECRETO_ASSEGNAZIONE = """TRIBUNALE DI VELLETRI
Sezione Lavoro
DECRETO
Causa n. 321/2025 R.G. promossa da ROSSI MARIA
Il Presidente della Sezione assegna la causa introdotta con il ricorso depositato in data 23/01/2025
e iscritta a ruolo in data 23/01/2025 al giudice designato.
Velletri, 27 gennaio 2025
"""


def test_decree_of_assignment_gives_deposit_and_enrolment():
    assert campi(DECRETO_ASSEGNAZIONE) == [
        ("data_deposito_ricorso", "2025-01-23", "verificata"),
        ("data_iscrizione_ruolo", "2025-01-23", "verificata"),
    ]


def test_optical_decree_stays_candidate():
    assert {v for _, _, v in campi(DECRETO_ASSEGNAZIONE, origine="ocr")} == {"plausibile"}


SENTENZA_CITAZIONE = """TRIBUNALE DI VELLETRI
SENTENZA
nella causa iscritta al n. 321/2025 R.G. promossa da ROSSI MARIA contro BIANCHI SRL
Con atto di citazione ritualmente notificato in data 10.03.2023 l'attrice conveniva in giudizio la società.
La causa, iscritta a ruolo il 20/03/2023, veniva istruita.
"""


def test_judgment_gives_service_of_summons_and_enrolment():
    assert campi(SENTENZA_CITAZIONE) == [
        ("data_notifica_citazione", "2023-03-10", "verificata"),
        ("data_iscrizione_ruolo", "2023-03-20", "verificata"),
    ]


@pytest.mark.parametrize("frase", [
    # la data è di un altro atto, non della citazione o del ricorso
    "Con ricorso avverso il decreto ingiuntivo depositato il 05/02/2025 la parte proponeva opposizione.",
    "Con atto di citazione per chiamata del terzo notificato il 05/02/2025 la convenuta estendeva il contraddittorio.",
    "La memoria depositata il 05/02/2025 non è tempestiva.",
    # nuova iscrizione dopo la cancellazione e termine per iscrivere: non instaurano la causa
    "Disposta la nuova iscrizione a ruolo del 05/02/2025 la causa proseguiva.",
    "Onera la parte di provvedere all'iscrizione a ruolo entro il 05/02/2025.",
])
def test_other_acts_and_later_enrolments_are_not_the_introductory_act(frase):
    testo = DECRETO_ASSEGNAZIONE.split("Il Presidente")[0] + frase + "\n"
    assert campi(testo) == []


SENTENZA_APPELLO = """CORTE D'APPELLO DI ROMA
SENTENZA
nella causa iscritta al n. 321/2025 R.G. promossa da ROSSI MARIA, appellante, contro BIANCHI SRL, appellata
Con atto di citazione notificato il 10.03.2021 l'attrice conveniva la società davanti al Tribunale di Velletri.
Con atto di citazione in appello notificato il 15/01/2025 l'appellante impugnava la sentenza.
"""


def test_appeal_keeps_only_the_appeal_dates():
    fascicolo = matter(tribunale="CORTE D'APPELLO DI ROMA")
    facts = estrai_date_modello(SENTENZA_APPELLO, fascicolo=fascicolo)
    assert [(f.campo, f.valore) for f in facts] == [("data_notifica_citazione", "2025-01-15")]


RELATA_CITAZIONE = """RELATA DI NOTIFICA EX ART. 3-BIS L. 53/1994
Io sottoscritto Avv. Paolo Verdi, quale difensore di ROSSI MARIA, ho notificato l'allegato atto di citazione
a comparire davanti al Tribunale di Velletri alla BIANCHI SRL, a mezzo posta elettronica certificata,
all'indirizzo bianchisrl@pec.esempio.it estratto dal registro INI-PEC.
Velletri, 09/03/2023
Avv. Paolo Verdi

Ricevuta di avvenuta consegna
Il giorno 10/03/2023 alle ore 09:15:02 (+0100) il messaggio "Notificazione ai sensi della legge n. 53 del 1994"
proveniente da "avv.verdi@pec.esempio.it" ed indirizzato a "bianchisrl@pec.esempio.it" è stato consegnato.
"""


def test_relata_of_the_summons_gives_the_delivery_date():
    fascicolo = matter(numero_rg="", anno_rg="")
    facts = estrai_date_modello(RELATA_CITAZIONE, fascicolo=fascicolo)
    assert [(f.campo, f.valore, f.verifica) for f in facts] == [("data_notifica_citazione", "2023-03-10", "verificata")]
    assert any(p["codice"] == "relata_notifica_citazione" for p in facts[0].prove)


@pytest.mark.parametrize("modifica", [
    ("atto di citazione", "ricorso con pedissequo decreto"),        # atto diverso
    ("atto di citazione", "atto di citazione per chiamata del terzo"),  # notifica di un altro atto
    ("ROSSI MARIA", "VERDI ANNA"),                                  # cliente di un'altra causa
    ("Tribunale di Velletri", "Tribunale di Latina"),               # ufficio diverso
    ("Ricevuta di avvenuta consegna", "Ricevuta di accettazione"),  # notifica non ancora consegnata
])
def test_relata_of_other_acts_or_cases_is_not_the_summons(modifica):
    fascicolo = matter(numero_rg="", anno_rg="")
    assert estrai_date_modello(RELATA_CITAZIONE.replace(*modifica), fascicolo=fascicolo) == []


DECRETO_SENZA_INTESTAZIONE = """r.g.l. 321 /2025
TRIBUNALE ORDINARIO DI VELLETRI
SEZIONE LAVORO
La Presidente, dott.ssa Laura Neri, assegna la causa introdotta con il ricorso depositato in data 23/01/2025
e iscritta a ruolo in data 23/01/2025 al giudice dott. Marco Gialli.
Velletri, 27 gennaio 2025
La Presidente
"""


def test_assignment_decree_without_parties_uses_role_and_office():
    facts = estrai_date_modello(DECRETO_SENZA_INTESTAZIONE, fascicolo=matter(), origine="ocr")
    assert [(f.campo, f.valore, f.verifica) for f in facts] == [
        ("data_deposito_ricorso", "2025-01-23", "plausibile"), ("data_iscrizione_ruolo", "2025-01-23", "plausibile")]
    assert {p["codice"] for p in facts[0].prove} >= {"identita_ruolo_ufficio", "tipo_fonte"}
    # ruolo di un'altra causa: nessuna data
    assert estrai_date_modello(DECRETO_SENZA_INTESTAZIONE.replace("321 /2025", "322 /2025"), fascicolo=matter()) == []


RELATA_CON_COPIE = """Oggetto: Notificazione ai sensi della legge n. 53/1994
RELATA DI NOTIFICA EX ART. 3-BIS L. 53/1994
Io sottoscritto Avv. Paolo VERDI, difensore per mandato come in atti di: Maria ROSSI
ho notificato i seguenti atti relativi al procedimento R.G. n. 321/2025 del Tribunale di Velletri:
A) - Ricorso Rossi (File: Ricorso Rossi.PDF) Natura del documento: Copia estratta dal fascicolo informatico
Contenuto del documento: Ricorso Rossi.PDF - Depositante: VERDI PAOLO; Tipologia: Atto principale; Data deposito: 19-06-2025 copia informatica scaricata dal PolisWeb in data 04/07/2025; Attesto che il presente documento è conforme.
B) - Decreto fissazione udienza (File: Decreto fissazione udienza.pdf) Natura del documento: Copia estratta dal fascicolo informatico
Contenuto del documento: 1234567s.pdf - Depositante: NERI LAURA; Tipologia: Atto principale; Data deposito: 27-06-2025 copia informatica scaricata dal PolisWeb in data 04/07/2025; Attesto che il presente documento è conforme.
C) - Memoria Bianchi (File: Memoria.PDF) Natura del documento: Copia estratta dal fascicolo informatico
Contenuto del documento: Memoria.PDF - Depositante: GIALLI MARCO; Tipologia: Atto principale; Data deposito: 30-06-2025 copia informatica scaricata dal PolisWeb in data 04/07/2025.
"""


def test_polisweb_copy_gives_the_ricorso_deposit_with_depositor():
    fascicolo = matter(avvocato_referente="Avv. Paolo Verdi")
    facts = estrai_date_modello(RELATA_CON_COPIE, fascicolo=fascicolo, origine="ocr")
    assert [(f.campo, f.valore) for f in facts] == [("data_deposito_ricorso", "2025-06-19")]
    prove = {p["codice"]: p for p in facts[0].prove}
    assert prove["depositante"]["dettaglio"] == "VERDI PAOLO"
    assert prove["depositante_dello_studio"]["esito"] == "ok"
    assert prove["tipo_fonte"]["dettaglio"] == "copia_polisweb"


def test_polisweb_copy_of_the_other_side_is_marked():
    fascicolo = matter(avvocato_referente="Avv. Anna Blu")
    facts = estrai_date_modello(RELATA_CON_COPIE, fascicolo=fascicolo, origine="ocr")
    prove = {p["codice"]: p for p in facts[0].prove}
    assert prove["depositante_dello_studio"]["esito"] == "attenzione"


def test_polisweb_copy_of_another_client_is_ignored():
    assert estrai_date_modello(RELATA_CON_COPIE.replace("Maria ROSSI", "Anna VERDI"), fascicolo=matter()) == []


INVIO_DEPOSITO = """Oggetto: DEPOSITO TELEMATICO: Ricorso [AB1]
Mittente: "Avv. Paolo Verdi" <avv.verdi@pec.esempio.it>
Corpo email: Egregio sig. Cancelliere, allego il file "Atto.enc".
[Allegato: Nota d'iscrizione a ruolo.PDF] TRIBUNALE DI VELLETRI Nota di iscrizione a ruolo
Si chiede l'iscrizione nel ruolo "LAVORO" della seguente causa introdotta con: Ricorso
[ISCRITTA A RUOLO DA] 1) Rossi Maria
[Allegato: IndiceDocumentiDepositati.PDF] INDICE DEI DOCUMENTI ex art. 74 disp. attuazione c.p.c.
Relativi al deposito telematico inviato in data 23/01/2025: - Ricorso - Nota d'iscrizione a ruolo.PDF - Procura.PDF
"""


def test_deposit_index_is_a_cross_check_never_certain_alone():
    facts = estrai_date_modello(INVIO_DEPOSITO, fascicolo=matter(numero_rg="", anno_rg=""))
    assert [(f.campo, f.valore, f.verifica) for f in facts] == [
        ("data_iscrizione_ruolo", "2025-01-23", "plausibile"), ("data_deposito_ricorso", "2025-01-23", "plausibile")]
    # una voce per riga, come nell'indice generato dal redattore
    per_riga = INVIO_DEPOSITO.replace("- Ricorso - Nota d'iscrizione a ruolo.PDF", "\n\n- Ricorso\n- Nota d'iscrizione a ruolo.PDF")
    assert len(estrai_date_modello(per_riga, fascicolo=matter(numero_rg="", anno_rg=""))) == 2
    # un deposito successivo (note, memorie) non porta la nota d'iscrizione
    successivo = INVIO_DEPOSITO.replace("- Ricorso - Nota d'iscrizione a ruolo.PDF", "- Note scritte.PDF")
    assert estrai_date_modello(successivo, fascicolo=matter(numero_rg="", anno_rg="")) == []


# ---------------------------------------------------------------- riscontro fra fonti, archivio e rilettura mirata
def _registro_con(tmp_path, fatti_per_oggetto):
    from pct.registro_letture import Oggetto, RegistroLetture

    registro = RegistroLetture(tmp_path / "letture.sqlite")
    oggetti = []
    for oggetto_id, fatti in fatti_per_oggetto.items():
        oggetto = Oggetto(tipo="documento", oggetto_id=oggetto_id, sha256=oggetto_id[0] * 64)
        registro.registra_fatti("studio", "F1", oggetto, "documenti", fatti, versione="v1")
        oggetti.append(("documento", oggetto_id, oggetto.impronta))
    return registro, oggetti


def test_optical_decree_confirmed_by_deposit_index_becomes_certain(tmp_path):
    decreto = estrai_date_modello(DECRETO_SENZA_INTESTAZIONE, fascicolo=matter(), origine="ocr")
    indice = estrai_date_modello(INVIO_DEPOSITO, fascicolo=matter(numero_rg="", anno_rg=""), origine="ocr")
    registro, correnti = _registro_con(tmp_path, {"A1": decreto, "B2": indice})
    promossi = registro.concorda_instaurazione("studio", "F1", oggetti_correnti=correnti)
    assert {(f.oggetto_id, f.campo) for f in promossi} == {
        ("A1", "data_deposito_ricorso"), ("A1", "data_iscrizione_ruolo"),
        ("B2", "data_deposito_ricorso"), ("B2", "data_iscrizione_ruolo")}
    salvati = registro.fatti("studio", "F1", categoria="metadato_fascicolo")
    assert {f.verifica for f in salvati} == {"verificata"}
    prova = next(p for p in salvati[0].prove if p["codice"] == "concordanza_fonti")
    assert "23/01/2025" in prova["dettaglio"]
    assert registro.concorda_instaurazione("studio", "F1", oggetti_correnti=correnti) == []


def test_discordant_dates_stay_uncertain(tmp_path):
    decreto = estrai_date_modello(DECRETO_SENZA_INTESTAZIONE, fascicolo=matter(), origine="ocr")
    indice = estrai_date_modello(INVIO_DEPOSITO.replace("23/01/2025", "24/01/2025"),
                                 fascicolo=matter(numero_rg="", anno_rg=""), origine="ocr")
    registro, correnti = _registro_con(tmp_path, {"A1": decreto, "B2": indice})
    assert registro.concorda_instaurazione("studio", "F1", oggetti_correnti=correnti) == []


def test_deposit_index_alone_or_twice_is_never_certain(tmp_path):
    indice = estrai_date_modello(INVIO_DEPOSITO, fascicolo=matter(numero_rg="", anno_rg=""), origine="ocr")
    copia = estrai_date_modello(INVIO_DEPOSITO, fascicolo=matter(numero_rg="", anno_rg=""), origine="ocr")
    registro, correnti = _registro_con(tmp_path, {"B2": indice, "C3": copia})
    assert registro.concorda_instaurazione("studio", "F1", oggetti_correnti=correnti) == []


def test_lawyer_decisions_and_removed_sources_are_untouched(tmp_path):
    decreto = estrai_date_modello(DECRETO_SENZA_INTESTAZIONE, fascicolo=matter(), origine="ocr")
    indice = estrai_date_modello(INVIO_DEPOSITO, fascicolo=matter(numero_rg="", anno_rg=""), origine="ocr")
    registro, correnti = _registro_con(tmp_path, {"A1": decreto, "B2": indice})
    # il decreto non c'è più nel fascicolo: l'indice da solo non basta
    assert registro.concorda_instaurazione("studio", "F1", oggetti_correnti=[c for c in correnti if c[1] == "B2"]) == []


def test_polisweb_deposit_fact_carries_the_depositor():
    from pct.archivio_letture.collaudo import Contesto
    from pct.archivio_letture.motore_documenti import leggi_testo

    fatti = leggi_testo(RELATA_CON_COPIE, nome="relata.eml", origine="nativo",
                        contesto=Contesto(numero_rg="321", anno_rg="2025", ufficio_giudiziario="TRIBUNALE DI VELLETRI",
                                          cliente="Rossi Maria", avvocati_studio=("Avv. Paolo Verdi",)))
    depositi = {f.valore[:10]: f for f in fatti if f.categoria == "data" and f.campo == "deposito"}
    ricorso, memoria = depositi["2025-06-19"], depositi["2025-06-30"]
    assert "Atto principale depositato da VERDI PAOLO" in ricorso.etichetta
    assert {p["codice"]: p["esito"] for p in ricorso.prove}["depositante_dello_studio"] == "ok"
    assert {p["codice"]: p["esito"] for p in memoria.prove}["depositante_dello_studio"] == "attenzione"


def test_targeted_rereading_reopens_only_sources_with_introductory_dates():
    from pct.archivio_letture.motore_documenti import VERSIONE_MOTORE_DOCUMENTI
    from pct.archivio_letture.riletture_mirate import REGOLA_ATTO_INTRODUTTIVO, oggetti_da_rileggere
    from pct.registro_letture.fatti_repository import Fatto

    vecchia = VERSIONE_MOTORE_DOCUMENTI.replace("+" + REGOLA_ATTO_INTRODUTTIVO, "")
    fatti = [
        Fatto(categoria="data", campo="deposito", valore="2025-01-23", contesto="assegna la causa introdotta con il ricorso depositato in data 23/01/2025",
              tipo="documento", oggetto_id="A1"),
        Fatto(categoria="data", campo="deposito", valore="2023-06-19", contesto="Ricorso.PDF - Depositante: VERDI PAOLO; Tipologia: Atto principale; Data deposito: 19-06-2023",
              tipo="documento", oggetto_id="B2"),
        Fatto(categoria="data", campo="deposito", valore="2024-02-01", contesto="note di trattazione depositate il 01/02/2024",
              tipo="documento", oggetto_id="C3"),
    ]
    versioni = {("documento", i): vecchia for i in ("A1", "B2", "C3")}
    assert set(oggetti_da_rileggere(fatti, versioni)) == {("documento", "A1"), ("documento", "B2")}
    assert oggetti_da_rileggere(fatti, {k: VERSIONE_MOTORE_DOCUMENTI for k in versioni}) == {}


def test_new_rule_keeps_previous_readings_compatible():
    from pct.archivio_letture.motore_documenti import VERSIONE_MOTORE_DOCUMENTI, VERSIONI_MOTORE_DOCUMENTI_COMPATIBILI
    from pct.archivio_letture.riletture_mirate import REGOLA_ATTO_INTRODUTTIVO
    from pct.registro_letture.lettori import _versioni_compatibili_motore_pec
    from pct.archivio_letture.motore_pec import VERSIONE_MOTORE_PEC_PRE_ATTO_INTRODUTTIVO

    assert VERSIONE_MOTORE_DOCUMENTI.endswith("+" + REGOLA_ATTO_INTRODUTTIVO)
    assert VERSIONE_MOTORE_DOCUMENTI.removesuffix("+" + REGOLA_ATTO_INTRODUTTIVO) in VERSIONI_MOTORE_DOCUMENTI_COMPATIBILI
    assert VERSIONE_MOTORE_PEC_PRE_ATTO_INTRODUTTIVO in _versioni_compatibili_motore_pec()


def test_editor_shows_dates_in_italian_and_keeps_the_registry_value():
    from pct.editor_linked_fields import date_modello_da_fatti, linked_fields_catalog

    facts = estrai_date_modello(SENTENZA_CITAZIONE, fascicolo=matter())
    for f in facts:
        f.fascicolo_id, f.tipo, f.oggetto_id, f.sha256 = "f", "documento", "doc", "hash"
    dates = date_modello_da_fatti(facts, fascicolo_id="f", oggetti=[
        SimpleNamespace(tipo="documento", oggetto_id="doc", impronta="hash", presente=True)])
    campi_editor = {f["id"]: f for f in linked_fields_catalog(fascicolo=matter(), date_processuali=dates)}
    assert campi_editor["fascicolo.data_iscrizione_ruolo"]["value"] == "20/03/2023"
    assert campi_editor["fascicolo.data_notifica_citazione"]["value"] == "10/03/2023"
    assert sum(1 for k in campi_editor if k == "fascicolo.data_notifica_citazione") == 1
    # l'anagrafica scritta dallo studio prevale; se le fonti dicono altro lo si segnala
    scritta = {f["id"]: f for f in linked_fields_catalog(fascicolo=matter(data_notifica_citazione="2023-03-11"), date_processuali=dates)}
    assert scritta["fascicolo.data_notifica_citazione"]["conflict"]
    assert "10/03/2023" in scritta["fascicolo.data_notifica_citazione"]["missing_reason"]
    uguale = {f["id"]: f for f in linked_fields_catalog(fascicolo=matter(data_notifica_citazione="2023-03-10"), date_processuali=dates)}
    assert uguale["fascicolo.data_notifica_citazione"]["value"] == "10/03/2023"
    assert uguale["fascicolo.data_notifica_citazione"]["available"]


def test_new_rule_does_not_queue_every_case_for_rereading():
    from pct.archivio_letture.motore_documenti import VERSIONE_MOTORE_DOCUMENTI
    from pct.archivio_letture.riletture_mirate import REGOLA_ATTO_INTRODUTTIVO
    from web.services.archivio_letture_runtime import _versione_documenti_aggiornata

    # i fascicoli letti prima della regola restano aggiornati: si rileggono solo le fonti toccate
    assert _versione_documenti_aggiornata(VERSIONE_MOTORE_DOCUMENTI.removesuffix("+" + REGOLA_ATTO_INTRODUTTIVO))


def test_pec_message_gives_only_the_introductory_act_dates():
    from pct.archivio_letture.collaudo import Contesto
    from pct.archivio_letture.motore_documenti import leggi_testo

    pec = ("Oggetto: Notificazione ai sensi della legge n. 53/1994\nMittente: avv.verdi@pec.esempio.it\n"
           "Destinatari: ente@pec.esempio.it\nData: 05/07/2025 18:38\nCorpo email: " + RELATA_CON_COPIE
           + "\n[Allegato: Sentenza.pdf]\nTRIBUNALE DI VELLETRI\nSENTENZA\nCausa n. 321/2025 R.G. promossa da ROSSI MARIA\n"
           "Con ricorso depositato in data 18/06/2025 la parte chiedeva.\n")
    fascicolo = matter(avvocato_referente="Avv. Paolo Verdi")
    fatti = leggi_testo(pec, nome="notifica.eml", origine="ocr",
                        contesto=Contesto(numero_rg="321", anno_rg="2025", ufficio_giudiziario="TRIBUNALE DI VELLETRI",
                                          cliente="Rossi Maria", avvocati_studio=("Avv. Paolo Verdi",)),
                        metadata={"fascicolo": fascicolo})
    natura = {f.valore for f in fatti if f.campo == "natura_documentale"}
    date = sorted((f.campo, f.valore) for f in fatti if f.categoria == "metadato_fascicolo")
    assert "messaggio_pec" in natura
    # dalla PEC solo la copia PolisWeb, non la sentenza allegata
    assert date == [("data_deposito_ricorso", "2025-06-19")]
