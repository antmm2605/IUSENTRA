"""Nessun fascicolo resta fermo nella coda delle letture (regola del registro delle letture).

Verifica del 03/11/2026: fascicoli «in coda» dal 21/09 e dal 13/10, con le verifiche dei presìdi
ferme al 13/10. Due cause: riaccodare un evento già in coda (a ogni apertura del fascicolo) lo
rimandava in fondo a una coda servita per data, e le verifiche dei presìdi partivano solo dal
pulsante «Aggiorna». Base: art. 3 D.M. 44/2011; art. 20 CAD. Nessun dato reale.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from pct.discordanze_letture_repository import RegistroDiscordanze
from pct.ora_italiana import ROME_TZ
from pct.registro_letture import RegistroLetture


def _registro(tmp_path):
    return RegistroLetture(tmp_path / "registro.db")


def _sposta_indietro(registro, fascicolo_id, giorni):
    quando = (datetime.now(timezone.utc) - timedelta(days=giorni)).strftime("%Y-%m-%dT%H:%M:%SZ")
    with registro.connection() as conn:
        conn.execute("UPDATE letture_eventi SET aggiornato_il=? WHERE fascicolo_id=?", (quando, fascicolo_id))


def test_riaccodare_un_evento_in_coda_non_lo_rimanda_in_fondo(tmp_path):
    registro = _registro(tmp_path)
    registro.accoda_evento("studio", "VECCHIO")
    _sposta_indietro(registro, "VECCHIO", 20)
    for numero in range(5):
        registro.accoda_evento("studio", f"ALTRO{numero}")
    # Il fascicolo vecchio viene aperto più volte: resta primo in coda.
    registro.accoda_evento("studio", "VECCHIO")
    registro.accoda_evento("studio", "VECCHIO", presidi=True)
    primi = [e["fascicolo_id"] for e in registro.eventi_da_riprendere("studio", limite=2)]
    assert primi[0] == "VECCHIO"
    assert registro.presidi_in_corso("studio", "VECCHIO")


def test_le_verifiche_dei_presidi_ripartono_solo_per_nuove_fonti_o_regole(tmp_path):
    from web.services.archivio_letture_runtime import accoda_verifiche_periodiche
    from web.services.fascicolo_lettura_verifiche import VERSIONE_VERIFICHE

    registro = _registro(tmp_path)
    discordanze = RegistroDiscordanze(registro)
    for fascicolo_id in ("MAI", "FERMO", "RECENTE", "IN_CODA"):
        registro.segna_fascicolo("studio", fascicolo_id, "motore_documenti", impronta="x", oggetti_totali=1, oggetti_letti=1,
                                 stato="completa", versione="v")
    vecchio = {"eseguita_il": "2026-10-13T12:55:00+02:00", "completata_il": "2026-10-13T12:57:00+02:00"}
    for fid in ("FERMO", "RECENTE"):
        discordanze.pubblica_esito("studio", fid, {
            **vecchio, "versione_verifiche": VERSIONE_VERIFICHE, "firma_fonti": discordanze.firma_fonti("studio", fid),
        })
    registro.segna_fascicolo("studio", "RECENTE", "motore_pec", impronta="nuova-pec", oggetti_totali=1, oggetti_letti=1,
                             stato="completa", versione="v")
    with registro.connection() as conn:
        conn.execute("UPDATE letture_verifiche_esiti SET aggiornato_il='2026-10-13T10:55:00+00:00' WHERE fascicolo_id='FERMO'")
    registro.accoda_evento("studio", "IN_CODA")
    # Di giorno nessun carico aggiuntivo.
    assert accoda_verifiche_periodiche(registro, "studio", ora=11) == 0
    assert accoda_verifiche_periodiche(registro, "studio", ora=2) == 2
    accodati = {e["fascicolo_id"] for e in registro.eventi_da_riprendere("studio", limite=10)}
    assert {"MAI", "RECENTE"} <= accodati and "FERMO" not in accodati
    assert registro.presidi_in_corso("studio", "RECENTE")
    # Già in coda: il giro dopo non li riaccoda.
    assert accoda_verifiche_periodiche(registro, "studio", ora=2) == 0


def test_giro_di_verifiche_interrotto_non_resta_in_corso_per_sempre():
    from web.services.fascicolo_lettura_verifiche import in_corso_vivo, verifiche_necessarie

    adesso = datetime.now(ROME_TZ)
    vivo = {"in_corso": True, "eseguita_il": (adesso - timedelta(minutes=5)).isoformat()}
    interrotto = {"in_corso": True, "eseguita_il": (adesso - timedelta(days=21)).isoformat()}
    assert in_corso_vivo(vivo) and not verifiche_necessarie(vivo)
    assert not in_corso_vivo(interrotto) and verifiche_necessarie(interrotto)


def test_la_coda_notturna_riprende_una_liquidazione_storica_una_volta(tmp_path):
    from pct.registro_letture import Oggetto
    from pct.registro_letture.fatti_repository import Fatto
    from web.services.archivio_letture_runtime import accoda_verifiche_periodiche
    from web.services.fascicolo_lettura_verifiche import VERSIONE_VERIFICHE

    registro = _registro(tmp_path)
    discordanze = RegistroDiscordanze(registro)
    for fid, valore in [("INCOMPLETA", "condanna;distrazione"), ("COMPLETA", "condanna;importo=258,00")]:
        documento = Oggetto("documento", fid + "-SENTENZA", sha256=fid.lower())
        registro.registra_inventario("studio", fid, [documento])
        registro.registra_fatti("studio", fid, documento, "documenti", [
            Fatto(categoria="evento", campo="spese_sentenza", valore=valore, verifica="verificata"),
        ])
        registro.segna_fascicolo("studio", fid, "motore_documenti", impronta="x", oggetti_totali=1,
                                 oggetti_letti=1, stato="completa", versione="v")
        discordanze.pubblica_esito("studio", fid, {
            "eseguita_il": "oggi", "completata_il": "oggi", "versione_verifiche": VERSIONE_VERIFICHE,
            "firma_fonti": discordanze.firma_fonti("studio", fid),
        })

    assert accoda_verifiche_periodiche(registro, "studio", ora=2) == 1
    assert [e["fascicolo_id"] for e in registro.eventi_da_riprendere("studio", limite=10)] == ["INCOMPLETA"]
    assert accoda_verifiche_periodiche(registro, "studio", ora=2) == 0
