"""Checkpoint della prima costruzione Normattiva; nessun secondo embedder."""
from __future__ import annotations


def prepara(conn, meta, *, righe, ids):
    if "prima_costruzione" not in meta:
        if righe:
            raise ValueError("La prima costruzione richiede un indice nuovo e separato")
        upper, total = conn.execute("SELECT COALESCE(MAX(id),0),COUNT(*) FROM normative_chunks").fetchone()
        meta["prima_costruzione"] = {"ultimo_id": 0, "massimo_id": int(upper),
                                    "totale_iniziale": int(total), "completa": False}
    state = meta["prima_costruzione"]
    if any(int(value) < 0 for value in (state["ultimo_id"], state["massimo_id"], state["totale_iniziale"])):
        raise ValueError("Checkpoint della prima costruzione non valido")
    # Le code riparate dal costruttore nativo sono autorevoli: non saltare
    # righe il cui vettore è stato perso durante un'interruzione.
    state["ultimo_id"] = max((int(value) for value in ids if value >= 0), default=0)
    if state["ultimo_id"] > state["massimo_id"]:
        raise ValueError("Righe estranee al perimetro della prima costruzione")
    return state


def conferma_lotto(meta, lotto):
    meta["prima_costruzione"]["ultimo_id"] = max(voce[0] for voce in lotto)


def concludi(conn, meta, *, interrotto):
    state = meta["prima_costruzione"]
    pending = conn.execute("SELECT 1 FROM normative_chunks WHERE id>? AND id<=? LIMIT 1",
                           (state["ultimo_id"], state["massimo_id"])).fetchone()
    state["completa"] = not interrotto and pending is None
    # La costruzione iniziale non certifica modifiche concorrenti già passate.
    # Una riconvalida nativa finale resta necessaria prima della promozione.
    meta["riconvalida_finale_richiesta"] = True


def disponibile(meta):
    state = meta.get("prima_costruzione")
    return state is None or (state.get("completa") is True and meta.get("riconvalida_finale_richiesta") is False)
