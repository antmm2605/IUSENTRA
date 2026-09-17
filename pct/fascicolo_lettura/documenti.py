"""I documenti del fascicolo come li ha catalogati il contenuto.

La lettura non conta file: conta atti, provvedimenti, comunicazioni e prove,
e dice quali documenti chiave ci sono — l'atto introduttivo, l'ultimo
provvedimento, l'ultima comunicazione — e quali mancano o restano da
verificare. È il catalogo dal contenuto a dirlo, non il nome del file.
"""

from __future__ import annotations

from typing import Any

from ._testo import data_it, pulisci

SEZIONI = ("identita", "atti", "provvedimenti", "comunicazioni", "notifiche", "procure", "pagamenti", "contratti", "allegati", "da-verificare")
ETICHETTE_SEZIONE = {
    "identita": "Documenti d’identità",
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


def documenti(elenco: list[dict[str, Any]], catalogo: list[dict[str, Any]], *, rg: str = "", fonti: list[dict[str, Any]] | None = None) -> dict[str, Any]:
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
            "data_evento": "",
            "data_it": data_it(_data(documento)),
            "firmato": bool(documento.get("firmato")),
            # Letto dal presidio documentale: testo indicizzato o record Document AI indicizzato.
            "indicizzato": bool(documento.get("lex_read")) or bool(voce.get("indexed")),
            # Censito dal portale ma non scaricato: il presidio non può leggerlo finché non è nel fascicolo.
            "da_acquisire": bool(documento.get("da_acquisire")),
            "deposito": pulisci(documento.get("id_deposito_pct")),
        })
    for documento in letti:
        prove = [f for f in (fonti or []) if f.get("oggetto_id") == documento["id"]]
        nature = [f for f in prove if f.get("campo") == "natura_documentale" and f.get("verifica") in {"verificata", "corretta"}]
        natura = nature[0].get("valore") if nature else ""
        if natura == "procura":
            documento.update(natura="procura", etichetta="Procura alle liti", sezione="procure")
        elif natura == "precedente_giurisprudenziale":
            documento.update(natura=natura, etichetta="Precedente giurisprudenziale", sezione="allegati", data_evento="")
        ruoli = sorted((f for f in prove if f.get("categoria") == "ruolo"), key=lambda f: f.get("posizione", 0))
        # È il ruolo dell'intestazione a identificare la causa, non una citazione
        # nel corpo né l'etichetta «Sentenza» di un allegato di giurisprudenza.
        documento["sentenza_pertinente"] = bool(ruoli and ruoli[0].get("valore") == rg and ruoli[0].get("verifica") in {"verificata", "corretta"})
        date_evento = [f for f in prove if f.get("campo") == "provvedimento" and f.get("verifica") in {"verificata", "corretta"}]
        if date_evento and documento["sezione"] == "provvedimenti" and documento["sentenza_pertinente"]:
            documento["data_evento"] = str(sorted(date_evento, key=lambda f: f.get("posizione", 0))[0]["valore"])[:10]
        if documento["etichetta"].lower().startswith("sentenza") and not documento["sentenza_pertinente"]:
            documento["data_evento"] = ""
        if documento["sentenza_pertinente"]:
            date = sorted((f for f in prove if f.get("campo") == "provvedimento" and f.get("verifica") in {"verificata", "corretta"}), key=lambda f: f.get("posizione", 0))
            # Una data di caricamento non è la data della sentenza.
            documento["data"] = str(date[0]["valore"])[:10] if date else ""
            documento["data_it"] = data_it(documento["data"])
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
        "catalogati": sum(1 for voce in letti if voce["stato_catalogo"] in {"catalogued", "proposed", "confirmed"}),
        "proposti": sum(1 for voce in letti if voce["stato_catalogo"] == "proposed"),
        "automatici": sum(1 for voce in letti if voce["stato_catalogo"] == "catalogued"),
        "confermati": sum(1 for voce in letti if voce["stato_catalogo"] == "confirmed"),
        "da_verificare": [voce for voce in letti if voce["sezione"] == "da-verificare"],
        "non_indicizzati": [voce for voce in letti if not voce["indicizzato"] and not voce["da_acquisire"]],
        "da_acquisire": [voce for voce in letti if voce["da_acquisire"]],
        "atto_introduttivo": primo({"atto_principale"}),
        "ultimo_atto_di_parte": ultimo(sezione="atti"),
        "ultimo_provvedimento": ultimo(sezione="provvedimenti"),
        "ultima_comunicazione": ultimo(sezione="comunicazioni"),
        "procura": ultimo({"procura"}),
        "sentenza": next((voce for voce in reversed(letti) if voce["etichetta"].lower().startswith("sentenza") and voce["sentenza_pertinente"]), None),
        "sentenze": [voce for voce in letti if voce["etichetta"].lower().startswith("sentenza") and voce["sentenza_pertinente"]],
    }


__all__ = ["ETICHETTE_SEZIONE", "SEZIONI", "documenti"]
