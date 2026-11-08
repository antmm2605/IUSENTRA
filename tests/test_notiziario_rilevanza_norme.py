"""Rilevanza professionale delle notizie e norme citate negli atti del fascicolo (lettore «norme_citate»)."""

from __future__ import annotations

from datetime import date
from pathlib import Path
from types import SimpleNamespace

import pytest

from pct.notiziario import fonti
from pct.notiziario.adattatori import notizia
from pct.notiziario.archivio import ArchivioNotiziario
from pct.notiziario.classifica import citazioni_atti
from pct.notiziario.norme_fascicolo import LETTORE, VERSIONE, atti_dai_riepiloghi, esito_documento, riepilogo_fascicolo
from pct.notiziario.pertinenza import costruisci_indice, pertinenza
from pct.notiziario.rilevanza import ALTA, SERVIZIO, UTILE, emittente_e_tipo, rilevanza
from pct.registro_letture.lettori import LETTORI, versione_lettore
from pct.registro_letture.modello import Oggetto
from pct.registro_letture.repository import RegistroLetture
from web.services import notiziario_runtime as vista
from web.services.notiziario_norme_runtime import aggiorna_norme_citate, atti_per_fascicolo


@pytest.mark.parametrize(("titolo", "sintesi", "livello"), [
    ("LEGGE 3 novembre 2026, n. 160", "", ALTA),
    ("DECRETO-LEGGE 31 ottobre 2026, n. 158", "", ALTA),
    ("DECRETO LEGISLATIVO 30 ottobre 2026, n. 155", "", ALTA),
    ("TESTO COORDINATO DEL DECRETO-LEGGE 1 ottobre 2026, n. 140", "", ALTA),
    ("DECRETO DEL PRESIDENTE DELLA REPUBBLICA 10 ottobre 2026, n. 150", "Regolamento recante norme sul processo", ALTA),
    ("DECRETO DEL PRESIDENTE DELLA REPUBBLICA 2 ottobre 2026", "Scioglimento del consiglio comunale di Alfa.", SERVIZIO),
    ("MINISTERO DELLA GIUSTIZIA - DECRETO 29 ottobre 2026", "", ALTA),
    ("MINISTERO DELL'AGRICOLTURA, DELLA SOVRANITA' ALIMENTARE E DELLE FORESTE - DECRETO 2 novembre 2026", "", UTILE),
    ("DELIBERA DEL CONSIGLIO DEI MINISTRI 28 ottobre 2026", "", UTILE),
    ("AGENZIA ITALIANA DEL FARMACO - COMUNICATO", "Autorizzazione all'immissione in commercio", SERVIZIO),
    ("AGENZIA ITALIANA DEL FARMACO - DETERMINA 30 ottobre 2026", "", SERVIZIO),
    ("MINISTERO DELL'ECONOMIA E DELLE FINANZE - COMUNICATO", "Cambi di riferimento", SERVIZIO),
    ("PRESIDENZA DEL CONSIGLIO DEI MINISTRI - DIPARTIMENTO PER LE POLITICHE IN FAVORE DELLE PERSONE CON DISABILITA' - COMUNICATO", "", SERVIZIO),
])
def test_rilevanza_gazzetta_da_emittente_e_tipo_dell_atto(titolo, sintesi, livello):
    assert rilevanza("gu_serie_generale", fonti.NORMA, titolo, sintesi).livello == livello


def test_emittente_e_tipo_dal_titolo_ufficiale_del_sommario():
    assert emittente_e_tipo("AGENZIA ITALIANA DEL FARMACO - COMUNICATO") == ("AGENZIA ITALIANA DEL FARMACO", "COMUNICATO")
    assert emittente_e_tipo("LEGGE 3 novembre 2026, n. 160") == ("", "LEGGE")


def test_rilevanza_delle_altre_fonti():
    assert rilevanza("eurlex_gu_l", fonti.NORMA, "Regolamento di esecuzione (UE) 2026/2496 della Commissione").livello == SERVIZIO
    assert rilevanza("eurlex_gu_l", fonti.NORMA, "Direttiva (UE) 2026/12 del Parlamento europeo e del Consiglio").livello == ALTA
    assert rilevanza("eurlex_gu_l", fonti.NORMA, "Raccomandazione (UE) 2026/2394 della Commissione").livello == UTILE
    assert rilevanza("entrate_prassi", fonti.PRASSI, "Interpello: Trattamento di emolumenti").livello == ALTA
    assert rilevanza("entrate_prassi", fonti.PRASSI, "Attuazione delle disposizioni in materia di servizi digitali").livello == UTILE
    assert rilevanza("cassazione", fonti.PRONUNCIA, "Sentenza n. 28375 del 03/11/2026").livello == ALTA
    assert rilevanza("gu_corte_costituzionale", fonti.NOTIZIA, "n. 22 RICORSO PER LEGITTIMITA' COSTITUZIONALE").livello == UTILE
    assert rilevanza("pst_giustizia", fonti.AVVISO_PCT, "Nuovi schemi XSD").livello == ALTA
    assert rilevanza("inps_circolari", fonti.PRASSI, "Circolare numero 110").livello == ALTA
    assert rilevanza("inps_messaggi", fonti.PRASSI, "Messaggio numero 3601").livello == UTILE


def _archivio(tmp_path: Path) -> ArchivioNotiziario:
    archivio = ArchivioNotiziario(tmp_path / "notiziario.sqlite")
    gu = fonti.fonte("gu_serie_generale")
    archivio.salva([
        notizia(gu, titolo="AGENZIA ITALIANA DEL FARMACO - COMUNICATO", url="https://www.gazzettaufficiale.it/eli/id/1",
                data="2026-11-07", descrizione="Autorizzazione all'immissione in commercio del medicinale Alfa."),
        notizia(gu, titolo="DECRETO-LEGGE 31 ottobre 2026, n. 158", url="https://www.gazzettaufficiale.it/eli/id/2",
                data="2026-10-31", descrizione="Modifiche all'articolo 1, comma 121, della legge 13 luglio 2015, n. 107."),
        notizia(gu, titolo="MINISTERO DELL'AGRICOLTURA - DECRETO 2 novembre 2026", url="https://www.gazzettaufficiale.it/eli/id/3",
                data="2026-11-06", descrizione="Conferma dell'incarico al Consorzio di tutela."),
    ])
    return archivio


def test_vista_ordina_per_rilevanza_e_nasconde_i_comunicati_di_servizio(tmp_path: Path):
    archivio = _archivio(tmp_path)

    def _vista(**argomenti):
        return vista.costruisci_vista(archivio, interazioni={}, fascicoli=[], filtri=vista.filtri_richiesti(argomenti), oggi=date(2026, 11, 8))

    normale = _vista()
    assert [voce["title"][:13] for voce in normale["items"]] == ["DECRETO-LEGGE", "MINISTERO DEL"]
    assert normale["items"][0]["relevanceLabel"] == "Rilevanza alta"
    assert normale["serviceCount"] == 1 and normale["total"] == 2
    con_servizio = _vista(servizio="1")
    assert con_servizio["total"] == 3
    assert con_servizio["items"][-1]["relevanceLabel"] == "Comunicato di servizio"


def test_citazioni_con_articolo_e_comma_e_leggi_regionali_escluse():
    testo = (
        "Visto l'art. 1, comma 121, della legge 13 luglio 2015, n. 107, e il D.Lgs. 165/2001; "
        "ai sensi della legge regionale n. 5 del 2010 e ancora della L. 107/2015."
    )
    assert citazioni_atti(testo) == [("legge:107:2015", "art. 1 c. 121"), ("dlgs:165:2001", "")]


def test_riepilogo_del_fascicolo_dagli_esiti_dei_documenti():
    riepilogo = riepilogo_fascicolo([
        ("Ricorso.pdf", esito_documento("art. 1, comma 121, della legge 13 luglio 2015, n. 107; D.Lgs. 165/2001")),
        ("Sentenza.pdf", esito_documento("D.Lgs. 165/2001 e l. 107/2015")),
    ])
    assert riepilogo["atti"][0] == {"chiave": "dlgs:165:2001", "articolo": "", "documento": "Ricorso.pdf", "documenti": 2}
    assert riepilogo["atti"][1]["articolo"] == "art. 1 c. 121"


def test_pertinenza_dalle_norme_citate_negli_atti_con_il_motivo():
    indice = costruisci_indice(
        [{"id": "F1", "etichetta": "RG 771/2025 - Rossi c. MIUR", "titolo": "Rossi c. MIUR", "oggetto": "222050 - Retribuzione",
          "tipo": "LAVORO", "area_pratica": "", "codice_oggetto_pst": "222050"}],
        {"F1": [{"chiave": "legge:107:2015", "articolo": "art. 1 c. 121", "documento": "Ricorso.pdf"}]},
    )
    lista, totale = pertinenza({"titolo": "DECRETO-LEGGE 31 ottobre 2026, n. 158", "sintesi": "",
                                "atti": ["legge:107:2015"], "materia": ""}, indice)
    assert totale == 1
    assert lista[0]["motivo"] == "Il fascicolo RG 771/2025 cita l'art. 1 c. 121 L. 107/2015 (documento «Ricorso.pdf»)"


_SHA = "a" * 64


def test_lettore_norme_citate_censito_e_incrementale(tmp_path: Path, monkeypatch):
    assert LETTORI[LETTORE]["etichetta"] == "Norme citate negli atti"
    assert versione_lettore(LETTORE) == VERSIONE
    registro = RegistroLetture(tmp_path / "registro.sqlite")
    oggetti = [
        Oggetto(tipo="documento", oggetto_id="D1", nome="Ricorso.pdf", sha256=_SHA),
        Oggetto(tipo="documento", oggetto_id="D2", nome="Scansione.pdf", sha256="b" * 64),
    ]
    registro.registra_inventario("studio", "F1", oggetti, tipi=("documento",))
    letti: list[str] = []

    def _testi(fascicolo):
        letti.append(fascicolo.id)
        return {"D1": "Visto l'art. 1, comma 121, della legge 13 luglio 2015, n. 107.", "D2": ""}

    monkeypatch.setattr("web.services.archivio_letture_runtime.testi_indice_archivio", _testi)
    fascicolo = SimpleNamespace(id="F1")

    primo = aggiorna_norme_citate(fascicolo, registro, "studio")
    assert primo == {"letti": 1, "senza_testo": 0, "in_attesa_testo": 1}
    atti = atti_per_fascicolo(registro, "studio")
    assert atti == {"F1": [{"chiave": "legge:107:2015", "articolo": "art. 1 c. 121", "documento": "Ricorso.pdf", "documenti": 1}]}

    # il secondo documento resta in attesa del testo; il primo non si rilegge
    secondo = aggiorna_norme_citate(fascicolo, registro, "studio")
    assert secondo["letti"] == 0 and secondo["in_attesa_testo"] == 1
    assert atti_dai_riepiloghi(registro.righe_fascicoli("studio", lettore=LETTORE))["F1"][0]["chiave"] == "legge:107:2015"


def test_atto_citato_in_quasi_tutti_i_fascicoli_conta_solo_con_lo_stesso_articolo():
    fascicoli = [
        {"id": f"F{i}", "etichetta": f"RG {i}/2025 - Parte {i}", "titolo": f"Parte {i}", "oggetto": "", "tipo": "LAVORO"}
        for i in range(25)
    ]
    # la procura di ogni fascicolo richiama la mediazione (art. 4 c. 3 D.Lgs. 28/2010): clausola di modulo
    atti = {f"F{i}": [{"chiave": "dlgs:28:2010", "articolo": "art. 4 c. 3", "documento": "Procura.pdf"}] for i in range(25)}
    indice = costruisci_indice(fascicoli, atti)
    assert "dlgs:28:2010" in indice.diffusi
    generica = {"titolo": "La competenza territoriale nella mediazione", "sintesi": "D.Lgs. 28/2010",
                "atti": ["dlgs:28:2010"], "materia": ""}
    assert pertinenza(generica, indice) == ([], 0)
    altro_comma = {"titolo": "Competenza territoriale", "sintesi": "art. 4, comma 1, del D.Lgs. 28/2010",
                   "atti": ["dlgs:28:2010"], "materia": ""}
    assert pertinenza(altro_comma, indice) == ([], 0)
    stesso_articolo = {"titolo": "Informativa sulla mediazione", "sintesi": "art. 4, comma 3, del D.Lgs. 28/2010",
                       "atti": ["dlgs:28:2010"], "materia": ""}
    assert pertinenza(stesso_articolo, indice)[1] == 25
