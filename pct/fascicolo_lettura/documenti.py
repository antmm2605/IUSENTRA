"""I documenti del fascicolo come li ha catalogati il contenuto.

La lettura non conta file: conta atti, provvedimenti, comunicazioni e prove,
e dice quali documenti chiave ci sono — l'atto introduttivo, l'ultimo
provvedimento, l'ultima comunicazione — e quali mancano o restano da
verificare. È il catalogo dal contenuto a dirlo, non il nome del file.
"""

from __future__ import annotations

from typing import Any

from ._testo import data_it, pulisci

SEZIONI = ("atti", "provvedimenti", "comunicazioni", "notifiche", "procure", "pagamenti", "contratti", "allegati", "da-verificare")
ETICHETTE_SEZIONE = {
    "atti": "atti di parte",
    "provvedimenti": "provvedimenti e verbali",
    "comunicazioni": "comunicazioni e ricevute",
    "notifiche": "prove di notifica",
    "procure": "procure e incarichi",
    "pagamenti": "pagamenti e contributo unificato",
    "contratti": "contratti",
    "allegati": "allegati e prove",
    "da-verificare": "da verificare",
}


def _data(documento: dict[str, Any]) -> str:
    return pulisci(documento.get("data_documento") or documento.get("data_caricamento"))[:10]


def documenti(elenco: list[dict[str, Any]], catalogo: list[dict[str, Any]]) -> dict[str, Any]:
    per_documento = {pulisci(voce.get("document_id")): voce for voce in catalogo}
    letti: list[dict[str, Any]] = []
    for documento in elenco:
        identificativo = pulisci(documento.get("id"))
        voce = per_documento.get(identificativo) or {}
        stato = pulisci(voce.get("status"))
        sezione = pulisci(voce.get("document_section")) or ("da-verificare" if not voce else "allegati")
        if stato == "review_required":
            sezione = "da-verificare"
        letti.append({
            "id": identificativo,
            "nome": pulisci(documento.get("nome")),
            "etichetta": pulisci(voce.get("document_label")) or pulisci(documento.get("tipo")).replace("_", " ").title() or "Documento",
            "natura": pulisci(voce.get("document_nature")),
            "sezione": sezione,
            "stato_catalogo": stato or "non_catalogato",
            "confidenza": int(voce.get("confidence") or 0),
            "data": _data(documento),
            "data_it": data_it(_data(documento)),
            "firmato": bool(documento.get("firmato")),
            # Letto dal presidio documentale: testo indicizzato o record Document AI indicizzato.
            "indicizzato": bool(documento.get("lex_read")) or bool(voce.get("indexed")),
            # Censito dal portale ma non scaricato: il presidio non può leggerlo finché non è nel fascicolo.
            "da_acquisire": bool(documento.get("da_acquisire")),
            "deposito": pulisci(documento.get("id_deposito_pct")),
        })
    letti.sort(key=lambda voce: voce["data"])
    conteggi = {sezione: sum(1 for voce in letti if voce["sezione"] == sezione) for sezione in SEZIONI}
    conteggi = {chiave: valore for chiave, valore in conteggi.items() if valore}

    def ultimo(natura: set[str] | None = None, sezione: str | None = None) -> dict[str, Any] | None:
        candidati = [
            voce for voce in letti
            if (natura is None or voce["natura"] in natura) and (sezione is None or voce["sezione"] == sezione)
        ]
        return candidati[-1] if candidati else None

    def primo(natura: set[str]) -> dict[str, Any] | None:
        candidati = [voce for voce in letti if voce["natura"] in natura]
        return candidati[0] if candidati else None

    return {
        "tutti": letti,
        "totale": len(letti),
        "conteggi": conteggi,
        "catalogati": sum(1 for voce in letti if voce["stato_catalogo"] in {"proposed", "confirmed"}),
        "confermati": sum(1 for voce in letti if voce["stato_catalogo"] == "confirmed"),
        "da_verificare": [voce for voce in letti if voce["sezione"] == "da-verificare"],
        "non_indicizzati": [voce for voce in letti if not voce["indicizzato"] and not voce["da_acquisire"]],
        "da_acquisire": [voce for voce in letti if voce["da_acquisire"]],
        "atto_introduttivo": primo({"atto_principale"}),
        "ultimo_atto_di_parte": ultimo(sezione="atti"),
        "ultimo_provvedimento": ultimo(sezione="provvedimenti"),
        "ultima_comunicazione": ultimo(sezione="comunicazioni"),
        "procura": ultimo({"procura"}),
        "sentenza": ultimo({"provvedimento"}) if any(voce["etichetta"].lower().startswith("sentenza") for voce in letti) else None,
        "sentenze": [voce for voce in letti if voce["etichetta"].lower().startswith("sentenza")],
    }


__all__ = ["ETICHETTE_SEZIONE", "SEZIONI", "documenti"]
