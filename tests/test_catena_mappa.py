"""La mappa della catena confrontata con il codice vero: nessun evento si ferma prima della fine della catena."""

from __future__ import annotations

import inspect

from pct.catena import mappa


def test_nessuna_lacuna_con_le_riaccensioni_attuali():
    assert mappa.lacune() == []


def test_le_lacune_fino_alla_2490_erano_lo_scadenziario_e_l_agenda_dopo_gli_eventi_non_documentali():
    """Prima del guardiano: scadenza, appuntamento, incasso, decisione, giorno e versione cambiavano il modello ma non
    riaccendevano l'allineamento dello scadenziario e dell'agenda (solo il ciclo delle letture lo faceva)."""
    prima = set(mappa.lacune(mappa.RIACCENSIONI_FINO_AL_2490))
    for evento in ("scadenza", "appuntamento", "parcella_incasso", "decisione_avvocato", "cambio_giorno", "voce_catalogo"):
        assert (evento, "allineamento_scadenziario") in prima
        assert (evento, "agenda_udienze") in prima
        assert (evento, "guardiano") in prima
    assert ("voce_catalogo", "archivio_fatti") in prima and ("voce_catalogo", "stato_fascicolo") in prima
    # Il documento e la PEC raggiungevano già tutto tranne il guardiano, che non esisteva.
    assert {a for e, a in prima if e == "documento"} == {"guardiano"}


def test_ogni_anello_ha_un_meccanismo_e_l_ordine_non_ha_cicli():
    for anello in mappa.ANELLI:
        assert anello.riacceso_da and set(anello.riacceso_da) <= set(mappa.MECCANISMI), anello.codice
        assert set(anello.legge) <= set(mappa.FONTI) | set(mappa.PER_CODICE), anello.codice
        assert anello.se_superato in {"in_aggiornamento", "calcolo_al_momento", "in_preparazione", "scrittura"}
    ordine = mappa.ordine_di_ricalcolo()
    assert ordine.index("modello_causa") < ordine.index("lettura") < ordine.index("allineamento_scadenziario")
    assert ordine.index("conto_economico") < ordine.index("quadro") and ordine.index("bozze_passi") < ordine.index("guardiano")


def test_ogni_fonte_e_contata_dall_impronta():
    """Il meccanismo «impronta» copre davvero tutte le fonti: tabelle con il fascicolo, tabelle senza fascicolo, file,
    giorno e versione (pct/pannelli_pronti/impronta.py, web/services/pannelli_pronti_fonti.py)."""
    from pct.pannelli_pronti import impronta, revisioni
    from web.services import pannelli_pronti_fonti as fonti

    assert set(mappa.MECCANISMI["impronta"].fonti) == set(mappa.FONTI)
    codice = inspect.getsource(impronta.componenti)
    assert '"giorno": giorno_roma(adesso)' in codice and '"versione": str(versione)' in codice
    assert {"appuntamenti", "parcella_incassi_proofs", "parcella_incassi_state"} <= set(fonti.TABELLE_STUDIO)
    assert "FATTURAZIONE_DB" in fonti.CHIAVI_FILE
    assert {"pec_fascicolo_links", "pec_legal_deadlines", "pec_legal_hearings"} <= set(fonti.TABELLE_PEC)
    # Scadenze, catalogo, fatti e decisioni hanno la colonna del fascicolo: i trigger per fascicolo li contano.
    assert revisioni.COLONNE_FASCICOLO == ("fascicolo_id", "id_fascicolo")
    assert not revisioni.esclusa("scadenze") and not revisioni.esclusa("document_catalog_assignments")
    assert not revisioni.esclusa("letture_fatti")


def test_le_versioni_delle_regole_cambiano_l_impronta_dei_pannelli_che_le_usano():
    from web.services.pannelli_pronti_catalogo import impronta_del_pannello

    codice = inspect.getsource(impronta_del_pannello)
    for versione in ("VERSIONE_LETTURA", "VERSIONE", "RESOLVER_VERSION"):
        assert versione in codice


def test_il_ciclo_delle_letture_riaccende_davvero_gli_anelli_che_la_mappa_gli_attribuisce():
    from web.blueprints import api_v1_react
    from web.services import archivio_letture_runtime

    leggi = inspect.getsource(archivio_letture_runtime)
    assert "_consegna_ai_presidi" in leggi and "_prepara_lettura" in leggi and "_registra_esiti_udienze" in leggi
    prepara = inspect.getsource(api_v1_react.prepara_lettura_in_cache)
    assert "conferma_termini_certi" in prepara and "riconcilia_adempimenti" in prepara
    assert "_guardiano_dopo_lettura" in prepara


def test_dopo_la_lettura_il_calcolatore_prepara_bozze_e_guardiano():
    from web.services import pannelli_pronti_calcolatore as calcolatore

    giro = inspect.getsource(calcolatore.giro)
    assert "_prepara_bozze(app, owner, voci)" in giro and "_guardiano(app, owner, voci)" in giro


def test_la_notte_comprende_il_guardiano_dopo_il_presidio_economico():
    from pct.scheduler_notturno.sequenza import passi_in_ordine

    lavori = [p.lavoro for _f, p in passi_in_ordine()]
    assert lavori.index("fascicoli_document_economic_presidio") < lavori.index("guardiano_catena_notturno")
    assert lavori.index("archivio_letture_automatico") < lavori.index("guardiano_catena_notturno")
    assert lavori.index("collaudo_catena") < lavori.index("guardiano_catena_notturno")


def test_i_pannelli_della_mappa_coincidono_con_il_catalogo_e_le_dipendenze():
    from web.services.pannelli_pronti_catalogo import PANNELLI

    per_nome = {p.nome: p for p in PANNELLI}
    assert set(per_nome["quadro"].dipende_da) == {"lettura", "conto-economico"}
    assert "lettura" in per_nome["conto-economico"].dipende_da
    assert set(mappa.PER_CODICE["quadro"].legge) >= {"lettura", "conto_economico"}
    assert "lettura" in mappa.PER_CODICE["conto_economico"].legge


def test_gli_anelli_in_aggiornamento_non_mostrano_il_dato_superato_come_attuale():
    """Lettura, Conto e Quadro serviti dal salvato superato portano il segnale «in aggiornamento»."""
    from web.services import pannelli_pronti_runtime as runtime

    codice = inspect.getsource(runtime._risposta_consultiva_salvata)
    assert '["aggiornamento_pendente"] = True' in codice and '["aggiornamentoPendente"] = True' in codice
    assert "quadro_precedente=True" in codice
    in_aggiornamento = {a.codice for a in mappa.ANELLI if a.se_superato == "in_aggiornamento"}
    assert in_aggiornamento == {"modello_causa", "lettura", "conto_economico", "quadro"}


def test_descrizione_leggibile():
    righe = mappa.descrizione()
    scadenziario = next(r for r in righe if r["codice"] == "allineamento_scadenziario")
    assert "Cambio del giorno" in scadenziario["eventi"] and "Parcella, fattura o incasso" in scadenziario["eventi"]
