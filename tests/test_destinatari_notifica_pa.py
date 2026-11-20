"""Effetti della notifica della sentenza alla P.A. secondo chi l'ha ricevuta (Avvocatura o amministrazione)."""

from pct.destinatari_notifica_pa import AMMINISTRAZIONE, AVVOCATURA, ruolo_destinatario, voci_relata
from pct.ragionamento import ragiona
from tests.test_ragionamento_casi_collaudo_versione_8080 import (
    LAVORO, RICORSO_161, SENTENZA, _consegna, _notifica, conclusione, fonti,
)

BLOCCO = """
1) - AVVOCATURA DISTRETTUALE DI STATO DI REGGIO CALABRIA C.F: 92006980806 (difensore di MIM) mediante inoltro
all'indirizzo pec: ads.rc@mailcert.avvocaturastato.it estratto dal pubblico elenco: RegInde;
2) - MIM- USR REGGIO CALABRIA C.F: 80007410808 mediante inoltro all'indirizzo pec: usprc.contenzioso@postacert.istruzione.it estratto dal pubblico elenco: IPA;
3) - MINISTERO DELL'ISTRUZIONE E DEL MERITO C.F: 80185250588 mediante inoltro all'indirizzo pec:
dgosv@postacert.istruzione.it estratto dal pubblico elenco: IPA;
4) - UFFICIO SCOLASTICO REGIONALE - REGGIO CALABRIA C.F: 80185250588 mediante inoltro all'indirizzo pec: usprc@postacert.istruzione.it estratto dal pubblico elenco: RegInde;
"""
AVV = {"indirizzo": "ads.rc@mailcert.avvocaturastato.it", "ruolo": AVVOCATURA}
MIM = {"indirizzo": "dgosv@postacert.istruzione.it", "ruolo": AMMINISTRAZIONE}


def test_ruoli_dei_quattro_destinatari_della_relata_carbone():
    voci = voci_relata(BLOCCO)
    ruoli = {indirizzo: ruolo_destinatario(indirizzo, voce) for indirizzo, voce in voci.items()}
    assert ruoli == {"ads.rc@mailcert.avvocaturastato.it": AVVOCATURA, "usprc.contenzioso@postacert.istruzione.it": AMMINISTRAZIONE,
                     "dgosv@postacert.istruzione.it": AMMINISTRAZIONE, "usprc@postacert.istruzione.it": AMMINISTRAZIONE}


def _causa(destinatari):
    documenti = [RICORSO_161, SENTENZA, _notifica("N2", "Sen1234", "20/04/2026", "Sentenza.PDF", "Sentenza"),
                 _consegna("K2", "Sen1234", "20/04/2026")]
    prova = {"data": "2026-04-20", "riferimento": "prova", "titolo_esecutivo": "verificato", "destinatari": destinatari}
    return ragiona(fonti({**LAVORO, "numero_rg": "161"}, documenti, consegne_verificate={"SEN": prova}))


def test_avvocatura_e_amministrazione_consegnate_entrambi_gli_effetti():
    causa = _causa([AVV, MIM])
    assert conclusione(causa, "notifica_sentenza").stato == "fatto"
    assert conclusione(causa, "termine_impugnazione").termine.scadenza == "2026-05-20"
    assert conclusione(causa, "esecuzione_pa").termine.scadenza == "2026-08-18"


def test_solo_avvocatura_termine_breve_ma_non_120_giorni():
    causa = _causa([AVV])
    assert conclusione(causa, "termine_impugnazione").termine.scadenza == "2026-05-20"
    pa = conclusione(causa, "esecuzione_pa")
    assert pa.stato == "dubbio" and pa.termine is None and "amministrazione debitrice" in pa.prova_o_motivo


def test_solo_amministrazione_120_giorni_ma_non_termine_breve():
    causa = _causa([MIM])
    notifica = conclusione(causa, "notifica_sentenza")
    assert notifica.stato == "dubbio" and "procuratore costituito" in notifica.prova_o_motivo
    assert "pubblicazione" in conclusione(causa, "termine_impugnazione").termine.evento_decorrenza
    assert not any(c.codice == "giudicato" for c in causa.conclusioni)
    assert conclusione(causa, "esecuzione_pa").termine.scadenza == "2026-08-18"


def test_prova_senza_ruoli_resta_come_prima():
    documenti = [RICORSO_161, SENTENZA]
    prova = {"data": "2026-04-20", "riferimento": "prova", "titolo_esecutivo": "verificato"}
    causa = ragiona(fonti({**LAVORO, "numero_rg": "161"}, documenti, consegne_verificate={"SEN": prova}))
    assert conclusione(causa, "esecuzione_pa").termine.scadenza == "2026-08-18"
