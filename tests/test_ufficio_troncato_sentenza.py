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


# --- Riammissione del fatto già registrato (21/11/2026) ---------------------------------------------------------
# 0d7262bb correggeva le letture nuove e l'esclusione del documento, ma il fatto di ruolo restava «respinto»
# nell'archivio: la Lettura (sentenza_pertinente) e il modello della causa continuavano a non vedere la sentenza.

def test_il_ruolo_respinto_per_l_ufficio_tagliato_torna_verificato():
    from pct.archivio_letture.riammissione_ruolo import respinto_da_regola_superata, ruoli_da_riammettere

    fatto = _ruolo()
    assert respinto_da_regola_superata(fatto) == "TRIBUNALE DI REGGIO DI CALABRIA"
    [nuovo] = ruoli_da_riammettere([fatto], numero_rg="161", anno_rg="2026")
    assert nuovo.verifica == "verificata" and fatto.verifica == "respinta"  # l'originale non cambia
    codici = {(p["codice"], p["esito"]) for p in nuovo.prove}
    assert ("concordanza", "ok") in codici and ("riconvalida", "ok") in codici
    assert ("ufficio_giudiziario", "respinta") not in codici
    # Ruolo diverso da quello del fascicolo: torna plausibile, non verificato.
    [altro_ruolo] = ruoli_da_riammettere([_ruolo()], numero_rg="99", anno_rg="2026")
    assert altro_ruolo.verifica == "plausibile"


def test_non_si_riammette_un_ufficio_davvero_diverso_ne_una_decisione_dell_avvocato():
    from pct.archivio_letture.riammissione_ruolo import ruoli_da_riammettere

    palmi = _ruolo(contesto="RG n. 161/2026 TRIBUNALE DI PALMI")
    palmi.prove[0]["dettaglio"] = "il documento indica TRIBUNALE DI PALMI, diverso dall'ufficio del fascicolo TRIBUNALE DI REGGIO DI CALABRIA"
    avvocato = _ruolo()
    avvocato.prove.append({"codice": "decisione_avvocato", "esito": "respinta", "dettaglio": "respinto dall'avvocato"})
    altra_ragione = _ruolo()
    altra_ragione.prove.append({"codice": "forma", "esito": "respinta", "dettaglio": "lettere al posto delle cifre"})
    assert ruoli_da_riammettere([palmi, avvocato, altra_ragione], numero_rg="161", anno_rg="2026") == []


def test_riammissione_nel_registro_delle_letture(tmp_path):
    from pct.registro_letture import Oggetto, RegistroLetture

    registro = RegistroLetture(tmp_path / "letture.sqlite")
    oggetto = Oggetto(tipo="documento", oggetto_id="2657592E", sha256="a" * 64)
    registro.registra_fatti("studio", "9A681FDF", oggetto, "documenti", [_ruolo(oggetto="2657592E")], versione="v1")
    [riammesso] = registro.riammetti_ruoli("studio", "9A681FDF", numero_rg="161", anno_rg="2026")
    [salvato] = [f for f in registro.fatti("studio", "9A681FDF", verifiche=None) if f.categoria == "ruolo"]
    assert salvato.verifica == "verificata" and salvato.id == riammesso.id
    assert any(p.get("codice") == "riconvalida" for p in salvato.prove)
    # Una seconda passata non trova più nulla da riammettere.
    assert registro.riammetti_ruoli("studio", "9A681FDF", numero_rg="161", anno_rg="2026") == []


def test_la_lettura_riconosce_la_sentenza_della_causa_dopo_la_riammissione():
    from pct.archivio_letture.riammissione_ruolo import ruoli_da_riammettere
    from pct.fascicolo_lettura.documenti import documenti

    [ruolo] = ruoli_da_riammettere([_ruolo(oggetto="2657592E")], numero_rg="161", anno_rg="2026")
    fonte = {"oggetto_id": "2657592E", "categoria": "ruolo", "campo": "numero_ruolo", "valore": ruolo.valore,
             "verifica": ruolo.verifica, "posizione": ruolo.posizione}
    elenco = [{"id": "2657592E", "nome": "Sentenza (originale notificato).pdf", "data_documento": "2026-05-31"}]
    catalogo = [{"document_id": "2657592E", "document_label": "Sentenza", "document_section": "provvedimenti",
                 "document_nature": "provvedimento", "status": "catalogued"}]
    letti = documenti(elenco, catalogo, rg="161/2026", fonti=[fonte])
    assert letti["sentenza"] and letti["sentenza"]["id"] == "2657592E"
    respinta = {**fonte, "verifica": "respinta"}
    assert documenti(elenco, catalogo, rg="161/2026", fonti=[respinta])["sentenza"] is None
