"""Riunione dei doppioni già presenti in scadenziario e agenda (verifica di produzione del 31/10/2026).

Le regole di `pct.agenda_eventi_equivalenti` e del presidio delle scadenze impediscono i doppioni nuovi;
qui si riuniscono quelli già creati prima della correzione. Prudenza:

- si toccano solo le voci **automatiche** (create dall'archivio delle letture, dalla PEC, dall'udienza o
  dalla sentenza) ancora aperte e senza responsabile assegnato: ciò che l'avvocato ha inserito o
  modificato non si tocca;
- una voce doppia non si cancella: si annulla con la nota «Riunita a …», così resta la traccia;
- si conserva la voce più precisa (adempimento esplicito, termine perentorio, ora certa), a parità la più vecchia.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any, Iterable

from pct.agenda_eventi_equivalenti import ora_da_confermare

MARCATORI_AUTOMATICI = ("ARCHIVIO_FATTO:", "PEC_AUDIT:", "UDIENZA_DERIVATA:", "SENTENZA_327:", "DOC_IDENTITA:")


def _valore(oggetto: Any, nome: str) -> str:
    valore = getattr(oggetto, nome, "")
    return str(getattr(valore, "value", valore) or "")


def automatica(voce: Any) -> bool:
    testo = f"{_valore(voce, 'note')} {_valore(voce, 'external_uid')}"
    return any(marcatore in testo for marcatore in MARCATORI_AUTOMATICI) and not _valore(voce, "id_utente_responsabile")


def _adempimento(voce: Any) -> str:
    from pct.archivio_letture.identita_eventi import adempimento_da_testo

    return adempimento_da_testo(f"{_valore(voce, 'titolo')} {_valore(voce, 'descrizione')}")


def gruppi_scadenze_doppie(scadenze: Iterable[Any]) -> list[list[Any]]:
    """Scadenze automatiche aperte dello stesso fascicolo, giorno e adempimento (una generica si unisce a una sola specifica)."""
    per_giorno: dict[tuple[str, str], list[Any]] = defaultdict(list)
    for voce in scadenze:
        if _valore(voce, "stato") not in {"APERTO", "BOZZA"} or not automatica(voce) or not _valore(voce, "id_fascicolo"):
            continue
        per_giorno[(_valore(voce, "id_fascicolo"), _valore(voce, "data_scadenza")[:10])].append(voce)
    gruppi: list[list[Any]] = []
    for voci in per_giorno.values():
        per_adempimento: dict[str, list[Any]] = defaultdict(list)
        for voce in voci:
            per_adempimento[_adempimento(voce)].append(voce)
        generiche = per_adempimento.pop("", [])
        specifici = list(per_adempimento.values())
        if len(specifici) == 1:
            specifici[0].extend(generiche)
        elif not specifici:
            specifici = [generiche]
        gruppi.extend(gruppo for gruppo in specifici if len(gruppo) > 1)
    return gruppi


def _da_conservare_scadenza(gruppo: list[Any]) -> Any:
    from pct.archivio_letture.identita_eventi import adempimento_da_testo

    # Prima il termine perentorio, poi il titolo che dice l'adempimento («Deposito note scritte …»)
    # rispetto al generico «Termine del …», a parità la voce più vecchia.
    return sorted(gruppo, key=lambda v: (_valore(v, "tipo") != "TERMINE_PERENTORIO",
                                         not adempimento_da_testo(_valore(v, "titolo")),
                                         _valore(v, "creata_il"), _valore(v, "id")))[0]


def gruppi_udienze_doppie(appuntamenti: Iterable[Any]) -> list[list[Any]]:
    """Udienze automatiche programmate dello stesso fascicolo (o RG) e giorno, con ora uguale o da confermare."""
    from pct.agenda_eventi_equivalenti import _ruolo

    per_giorno: dict[tuple[str, str], list[Any]] = defaultdict(list)
    for voce in appuntamenti:
        if _valore(voce, "tipo") != "UDIENZA" or _valore(voce, "stato") in {"ANNULLATO", "COMPLETATO"} or not automatica(voce):
            continue
        chiave = _valore(voce, "id_fascicolo") or _ruolo(_valore(voce, "procedimento"))
        if chiave:
            per_giorno[(chiave, _valore(voce, "data_ora")[:10])].append(voce)
    gruppi: list[list[Any]] = []
    for voci in per_giorno.values():
        certe = {_valore(v, "data_ora")[11:16] for v in voci if not ora_da_confermare(v)}
        if len(voci) > 1 and len(certe) <= 1:
            gruppi.append(voci)
    return gruppi


def _da_conservare_udienza(gruppo: list[Any]) -> Any:
    return sorted(gruppo, key=lambda v: (ora_da_confermare(v), _valore(v, "creato_il"), _valore(v, "id")))[0]


def riunisci(scadenziario: Any, agenda: Any) -> dict[str, int]:
    """Annulla i doppioni automatici, conserva la voce più precisa e sposta i collegamenti all'udienza."""
    from pct.agenda import StatoAppuntamento
    from pct.scadenziario import StatoTermine

    esito = {"scadenze_riunite": 0, "udienze_riunite": 0}
    tutte = list(scadenziario.tutte(solo_aperte=False))
    for gruppo in gruppi_scadenze_doppie(tutte):
        tenuta = _da_conservare_scadenza(gruppo)
        for voce in gruppo:
            if voce is tenuta:
                continue
            scadenziario.aggiorna(voce.id, stato=StatoTermine.ANNULLATO.value,
                                  note=f"{_valore(voce, 'note')}\nRiunita a {tenuta.id}: stessa scadenza da un'altra fonte.".strip())
            esito["scadenze_riunite"] += 1
    if agenda is not None:
        for gruppo in gruppi_udienze_doppie(agenda.tutti()):
            tenuta = _da_conservare_udienza(gruppo)
            for voce in gruppo:
                if voce is tenuta:
                    continue
                agenda.modifica(voce.id, stato=StatoAppuntamento.ANNULLATO,
                                note=f"{_valore(voce, 'note')}\nRiunita a {tenuta.id}: stessa udienza da un'altra fonte.".strip())
                for scadenza in tutte:
                    if _valore(scadenza, "id_appuntamento") == voce.id:
                        scadenziario.aggiorna(scadenza.id, id_appuntamento=tenuta.id)
                esito["udienze_riunite"] += 1
    return esito


__all__ = ["MARCATORI_AUTOMATICI", "automatica", "gruppi_scadenze_doppie", "gruppi_udienze_doppie", "riunisci"]
