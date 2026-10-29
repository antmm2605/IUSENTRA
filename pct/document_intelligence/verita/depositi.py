"""Le etichette certe dei depositi registrati nel fascicolo.

Ogni deposito (`EsitoDepositoPCT`) conserva il tipo atto della busta, i documenti inclusi, il nome dell'atto
principale e, per i depositi letti dal portale, i metadati ufficiali di ogni file (classificazione e tipo atto).
I metadati del portale stanno nel deposito, non sempre nel documento: il collegamento file → riga del portale usa
il resolver condiviso del fascicolo (`GestioneFascicoli._trova_documento_portale_correlato`), non una copia.

- Deposito letto dal portale: ogni file collegato riceve l'etichetta dichiarata nel deposito
  (`portale.etichetta_dal_portale`), solo per atti principali e provvedimenti.
- Deposito inviato dallo studio: il tipo atto è quello dichiarato nel `DatiAtto.xml` della busta (D.M. 44/2011,
  art. 12; Specifiche tecniche DGSIA). Vale solo per l'atto principale, riconosciuto dal nome registrato nel
  deposito; gli allegati non ricevono etichetta.
"""

from __future__ import annotations

from collections import Counter
from types import SimpleNamespace
from typing import Any

from .modello import LIVELLO_DEPOSITO, EtichettaCerta
from .portale import _normalizza, etichetta_dal_portale

FONTE_DEPOSITO_STUDIO = "deposito_telematico_studio"

# Tipo atto della busta inviata dallo studio (`EsitoDepositoPCT.tipo_atto`, normalizzato) → voce del catalogo.
TIPI_DEPOSITO_STUDIO: dict[str, tuple[str, str]] = {
    "ricorso per decreto ingiuntivo": ("Ricorso per decreto ingiuntivo", "atti"),
    "ricorso decreto ingiuntivo": ("Ricorso per decreto ingiuntivo", "atti"),
    "atto di citazione": ("Atto di citazione", "atti"),
    "citazione": ("Atto di citazione", "atti"),
    "comparsa di costituzione e risposta": ("Comparsa di costituzione e risposta", "atti"),
    "comparsa di risposta": ("Comparsa di costituzione e risposta", "atti"),
    "comparsa conclusionale": ("Comparsa conclusionale", "atti"),
    "note di trattazione scritta": ("Note di trattazione scritta", "atti"),
    "note scritte": ("Note di trattazione scritta", "atti"),
    "memoria integrativa": ("Memoria integrativa ex art. 171-ter c.p.c.", "atti"),
    "precisazione delle conclusioni": ("Precisazione delle conclusioni", "atti"),
    "ricorso in materia di lavoro": ("Ricorso in materia di lavoro (art. 414 c.p.c.)", "atti"),
}


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split()).strip()


def _documenti_del_deposito(fascicolo: Any, deposito: Any) -> list[Any]:
    ids = {_testo(i) for i in list(getattr(deposito, "documenti_ids", []) or [])}
    dep_id = _testo(getattr(deposito, "id", ""))
    return [d for d in list(getattr(fascicolo, "documenti", []) or [])
            if not getattr(d, "eliminato_il", "") and (_testo(getattr(d, "id", "")) in ids
                                                         or (dep_id and _testo(getattr(d, "id_deposito_pct", "")) == dep_id))]


def etichette_dai_depositi(fascicolo: Any) -> dict[str, Any]:
    """Etichette certe dei depositi del fascicolo, con i tipi atto non ancora in tabella e i conteggi."""
    from pct.fascicoli import GestioneFascicoli, _documento_portale_payload

    fascicolo_id = _testo(getattr(fascicolo, "id", ""))
    etichette: dict[str, EtichettaCerta] = {}
    non_mappati: Counter[str] = Counter()
    conteggi: Counter[str] = Counter()
    for deposito in list(getattr(fascicolo, "depositi_pct", []) or []):
        documenti = _documenti_del_deposito(fascicolo, deposito)
        if list(getattr(deposito, "documenti_portale", []) or []):
            conteggi["depositi_portale"] += 1
            for documento in documenti:
                riga = GestioneFascicoli._trova_documento_portale_correlato(documento, deposito)
                if riga is None:
                    conteggi["file_portale_senza_riga"] += 1
                    continue
                metadati = _documento_portale_payload(deposito, riga)
                vista = SimpleNamespace(id=_testo(getattr(documento, "id", "")), hash_sha256=getattr(documento, "hash_sha256", ""),
                                        **metadati)
                etichetta = etichetta_dal_portale(vista, fascicolo_id=fascicolo_id)
                classificazione = _testo(metadati.get("classificazione_portale")).upper()
                if etichetta:
                    etichette.setdefault(etichetta.document_id, etichetta)
                elif classificazione in {"ATTO", "PROVVEDIMENTO"}:
                    non_mappati[f"portale {classificazione}: {_normalizza(metadati.get('tipo_atto_portale'))}"] += 1
            continue
        conteggi["depositi_studio"] += 1
        principale = _testo(getattr(deposito, "nome_atto_principale", "")).casefold()
        atti = [d for d in documenti if principale and principale in {_testo(getattr(d, "nome", "")).casefold(),
                                                                      _testo(getattr(d, "nome_originale", "")).casefold()}]
        tipo = _normalizza(getattr(deposito, "tipo_atto", ""))
        if len(atti) != 1 or not tipo:
            conteggi["depositi_studio_senza_atto_principale"] += 1
            continue
        voce = TIPI_DEPOSITO_STUDIO.get(tipo)
        if voce is None:
            non_mappati[f"studio: {tipo}"] += 1
            continue
        documento = atti[0]
        etichette.setdefault(_testo(getattr(documento, "id", "")), EtichettaCerta(
            fascicolo_id=fascicolo_id, document_id=_testo(getattr(documento, "id", "")), etichetta=voce[0], sezione=voce[1],
            livello=LIVELLO_DEPOSITO, fonte=FONTE_DEPOSITO_STUDIO, dettaglio=f"DatiAtto: {tipo}",
            sha256=_testo(getattr(documento, "hash_sha256", "")),
        ))
    return {"etichette": list(etichette.values()), "non_mappati": dict(non_mappati), "conteggi": dict(conteggi)}


__all__ = ["FONTE_DEPOSITO_STUDIO", "TIPI_DEPOSITO_STUDIO", "etichette_dai_depositi"]
