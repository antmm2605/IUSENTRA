"""Regressione Carbone (9A681FDF, 21/11/2026): la sentenza esclusa dalla Lettura per un ufficio letto tagliato.

Il contesto salvato del numero di ruolo finiva con «TRIBUNALE DI REGGIO CALAB» (parola tagliata); il fascicolo dice
«TRIBUNALE DI REGGIO DI CALABRIA». Il collaudo lo dava per un altro ufficio, il fatto veniva respinto e la sentenza
(con la sua copia notificata) finiva tra i documenti di «ufficio incompatibile»: fuori dal ragionamento, quindi niente
notifica provata, termine breve, giudicato e precetto anche con i casi del registro delle notifiche presenti.
"""

from pct.archivio_letture.collaudo import ruolo_compatibile_con_ufficio
from pct.archivio_letture.pertinenza_documentale import documenti_ufficio_incompatibile
from pct.registro_letture.fatti_repository import Fatto

CONTESTO = "Sentenza n. 679/2026 pubbl. il 17/04/2026 RG n. 161/2026 Sentenza a verbale TRIBUNALE DI REGGIO CALAB"


def _ruolo(contesto=CONTESTO, ufficio_fascicolo="TRIBUNALE DI REGGIO DI CALABRIA", oggetto="SEN"):
    return Fatto(
        categoria="ruolo", campo="numero_ruolo", valore="161/2026", contesto=contesto, posizione=42,
        verifica="respinta", tipo="documento", oggetto_id=oggetto,
        prove=[{"codice": "ufficio_giudiziario", "esito": "respinta",
                "dettaglio": "il documento indica TRIBUNALE DI REGGIO CALAB, diverso dall'ufficio "
                             f"del fascicolo {ufficio_fascicolo}"}],
    )


def test_ufficio_tagliato_a_meta_parola_e_lo_stesso_ufficio():
    fatto = _ruolo()
    assert ruolo_compatibile_con_ufficio(fatto, "TRIBUNALE DI REGGIO DI CALABRIA")
    assert ruolo_compatibile_con_ufficio(fatto, "Tribunale di Reggio Calabria")
    assert not ruolo_compatibile_con_ufficio(fatto, "TRIBUNALE DI PALMI")
    # Senza taglio una parola diversa resta un altro ufficio.
    intero = _ruolo(contesto="TRIBUNALE DI ROMA, RG n. 161/2026")
    assert not ruolo_compatibile_con_ufficio(intero, "TRIBUNALE DI ROMAGNANO")


def test_esclusione_registrata_si_riconvalida_con_la_regola_di_oggi():
    # Lo stato salvato nel registro delle letture di Carbone: fatto respinto dal collaudo precedente.
    assert documenti_ufficio_incompatibile([_ruolo(oggetto="18B9FEA6"), _ruolo(oggetto="2657592E")]) == set()
    # Un ufficio davvero diverso resta escluso.
    altro = _ruolo(contesto="RG n. 161/2026 TRIBUNALE DI PALMI", ufficio_fascicolo="TRIBUNALE DI REGGIO DI CALABRIA")
    altro.prove[0]["dettaglio"] = "il documento indica TRIBUNALE DI PALMI, diverso dall'ufficio del fascicolo TRIBUNALE DI REGGIO DI CALABRIA"
    assert documenti_ufficio_incompatibile([altro]) == {"SEN"}
