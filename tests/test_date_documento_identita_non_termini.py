"""Fascicolo 9A681FDF (10/11/2026): la «Scadenza» della carta d'identità cartacea, scansionata in coda al
ricorso, diventava «Termine del 03/07/2026 — data fissata dal provvedimento», due volte (atto notificato e
deposito dello stesso ricorso). Testi anonimizzati, con l'OCR sporco della scansione reale.

La carta scade nel giorno e mese di nascita del titolare (art. 7, c. 1, D.L. 5/2012): per questo la data
coincideva con il compleanno della ricorrente, ma l'anno 2026 era scritto sul documento, non proiettato.
"""
from pct.archivio_letture.ancoraggio import brano, esclusione_data_salvata
from pct.archivio_letture.deduplica import fatti_canonici
from pct.archivio_letture.estrazione_date import estrai_date
from pct.registro_letture.fatti_repository import Fatto

CARTA_OCR = ("Impronta a del dito IL FUNZIÓNARIO INCARICATO indice sinistro Bianchi Mario NE DID Scadenza 03-07-2026 "
             "REWVBLICA IALANA Diritti 5,50 COMVNE DI ROCCAVERDE CARTA D'IDENTITA N°AX0000000 AX0")
CARTA_IN_EPIGRAFE = ("La sig.ra Anna Rossi, identificata con carta d'identità n. CA00000AA rilasciata dal Comune di "
                     "Roccaverde, scadenza 12/05/2027, residente in Roccaverde.")
NASCITE = (
    "La Prof.ssa Anna Rossi, c.f. RSSNNA82L43H224X, nata il 03/07/1982 a Roccaverde e residente in via Roma 1",
    "Anna Rossi, nata a Reggio di Calabria (RC) in data 03/07/2026, residente in Roccaverde",
    "Paolo Bianchi, nato a San Giovanni in Fiore (CS) il 10/12/2026, residente in Cosenza",
    "Data di nascita: 03/07/2026",
)


def _termini(testo: str, origine: str = "ocr") -> list:
    return [f for f in estrai_date(testo, origine=origine) if f.campo in {"termine", "udienza", "costituzione"}]


def test_la_scadenza_della_carta_d_identita_non_e_un_termine():
    assert _termini(CARTA_OCR) == []
    assert _termini(CARTA_IN_EPIGRAFE, "nativo") == []


def test_una_data_di_nascita_non_e_mai_un_termine():
    for testo in NASCITE:
        assert _termini(testo, "nativo") == [], testo


def test_i_termini_veri_restano_anche_vicino_a_un_documento_d_identita():
    testo = "Il giudice assegna termine fino al 03/07/2026 per il deposito di note. Si allega carta d'identità."
    assert [f.campo for f in _termini(testo, "nativo")] == ["termine"]
    assert [f.campo for f in _termini("Il giudice fissa l'udienza del 12/05/2027 ore 9.30.", "nativo")] == ["udienza"]


def test_riconvalida_del_fatto_gia_registrato_dal_brano_salvato():
    """Il brano salvato nell'archivio basta a respingere il fatto con la riconvalida."""
    inizio = CARTA_OCR.index("03-07-2026")
    motivo = esclusione_data_salvata(brano(CARTA_OCR, inizio, inizio + 10), "2026-07-03")
    assert "documento di identità" in motivo and "non termine processuale" in motivo


def _termine(oggetto_id: str, contesto: str, posizione: int) -> Fatto:
    return Fatto(categoria="data", campo="termine", valore="2026-03-20", valore_letto="20/03/2026",
                 etichetta="Termine del 20/03/2026", contesto=contesto, posizione=posizione, origine="ocr",
                 confidenza=1.0, verifica="verificata", prove=[], motore="documenti", tipo="documento",
                 oggetto_id=oggetto_id, sha256=oggetto_id * 8, id=f"fat_{oggetto_id}", fascicolo_id="FASC0001")


def test_lo_stesso_brano_in_due_copie_dello_stesso_atto_e_un_fatto_solo_con_due_fonti():
    brano_atto = "Il giudice assegna alle parti termine fino al 20/03/2026 per il deposito di note scritte ai sensi"
    canonici = fatti_canonici([_termine("NOTIFICA1", brano_atto, 4600), _termine("DEPOSITO2", brano_atto, 27561)])
    assert len(canonici) == 1
    fonti = next(p for p in canonici[0].prove if p.get("codice") == "fonti_unite")["fonti"]
    assert {f["oggetto_id"] for f in fonti} == {"NOTIFICA1", "DEPOSITO2"}


def test_due_termini_diversi_nello_stesso_giorno_restano_distinti():
    a = _termine("ATTO1", "Il giudice assegna alla parte ricorrente termine fino al 20/03/2026 per la notifica del ricorso", 10)
    b = _termine("ATTO2", "Il giudice assegna alla parte resistente termine fino al 20/03/2026 per il deposito della memoria", 10)
    assert len(fatti_canonici([a, b])) == 2


def test_la_riconvalida_respinge_il_termine_gia_registrato_e_lascia_traccia(tmp_path):
    """Il fatto reale (verificato, «Scadenza» a 1 carattere) si respinge da solo, con il motivo."""
    from pct.registro_letture import Oggetto, RegistroLetture

    registro = RegistroLetture(tmp_path / "intelligence" / "registro_letture.db")
    oggetto = Oggetto(tipo="documento", oggetto_id="d1", nome="ricorso.pdf", sha256="a" * 64, sha256_archivio="e" * 64, dimensione=10)
    registro.registra_inventario("studio-prova", "F1", [oggetto])
    inizio = CARTA_OCR.index("03-07-2026")
    registro.registra_fatti("studio-prova", "F1", oggetto, "documenti", [
        Fatto(categoria="data", campo="termine", valore="2026-07-03", valore_letto="03-07-2026", etichetta="Termine del 03/07/2026",
              contesto=brano(CARTA_OCR, inizio, inizio + 10), verifica="verificata"),
        Fatto(categoria="data", campo="termine", valore="2026-03-20", valore_letto="20/03/2026", etichetta="Termine del 20/03/2026",
              contesto="Il giudice assegna termine fino al 20/03/2026 per il deposito di note.", verifica="verificata"),
    ])
    respinti = registro.riconvalida_fatti("studio-prova", "F1")
    assert [f.valore_letto for f in respinti] == ["03-07-2026"]
    assert any(p.get("codice") == "riconvalida" and "documento di identità" in p.get("dettaglio", "") for p in respinti[0].prove)
    assert [f.valore_letto for f in registro.fatti("studio-prova", "F1")] == ["20/03/2026"]


def test_dopo_nato_a_un_verbo_del_processo_non_fa_della_notifica_una_nascita():
    testo = "La ricorrente nata a Roma ha proposto ricorso notificato il 03/07/2026 al Ministero."
    assert [f.campo for f in estrai_date(testo, origine="nativo")] == ["notifica"]


def test_il_presidio_mostra_il_termine_una_volta_con_le_due_fonti():
    from datetime import date

    from pct.archivio_letture.presidi import udienze_e_termini

    brano_atto = "Il giudice assegna alle parti termine fino al 20/03/2026 per il deposito di note scritte ai sensi"
    azioni = udienze_e_termini(fatti_canonici([_termine("NOTIFICA1", brano_atto, 4600), _termine("DEPOSITO2", brano_atto, 27561)]),
                               oggi=date(2026, 11, 10))
    assert len(azioni) == 1 and set(azioni[0]["documentIds"]) == {"NOTIFICA1", "DEPOSITO2"}
