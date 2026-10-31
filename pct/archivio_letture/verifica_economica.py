"""Prove economiche prodotte dai motori, mai riletture nei presìdi.

Il collaudo di una lettura non prova né il versamento né l'esenzione.
Cliente e RG devono risultare dal contenuto, non dal nome del file.
Le prove restano nel registro SQL comune, con documento e impronta.
"""
from __future__ import annotations

import json
import re
import unicodedata
from decimal import Decimal, InvalidOperation
from typing import Any

VERSIONE = "2026.10.13.economico.v8+autocertificazione-evento-contesto"


def _plain(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).casefold()
    return " ".join(re.sub(r"[^\w]+", " ", text).split())


def codice_fiscale_parte(testo: str, metadata: dict[str, Any]) -> dict[str, str]:
    from pct.pec_case_identity import client_tax_code_from_documents

    fascicolo = metadata.get("fascicolo")
    nome = str(getattr(fascicolo, "nome_cliente", "") or metadata.get("cliente") or "")
    profile = client_tax_code_from_documents({"cliente": nome}, [{"text": testo[:6000], "filename": "fonte_economica.pdf"}])
    declared = str(profile.get("codice_fiscale_cliente") or "").strip().upper()
    expected = str(metadata.get("codice_fiscale_cliente") or getattr(fascicolo, "codice_fiscale_cliente", "") or "").replace(" ", "").upper()
    if declared and not expected and getattr(fascicolo, "id_cliente", ""):
        from flask import has_app_context
        if has_app_context():
            try:
                from web.helpers import get_clienti
                cliente = get_clienti().get(str(fascicolo.id_cliente))
                expected = str(getattr(cliente, "codice_fiscale", "") or "").replace(" ", "").upper()
            except Exception:
                return {"codice": "cf_economico", "esito": "attenzione", "dettaglio": "Confronto anagrafico non disponibile: importi della fonte non attribuiti."}
    invalid = profile.get("codice_fiscale_cliente_stato") in {"letto_non_valido", "fonti_discordanti"}
    ok = not invalid and (not declared or bool(expected and declared == expected))
    return {"codice": "cf_economico", "esito": "ok" if ok else "attenzione",
            "dettaglio": "Codice fiscale della parte concordante o non dichiarato nella fonte." if ok else "Codice fiscale della parte non valido, discordante o privo di confronto anagrafico."}


def identita(testo: str, metadata: dict[str, Any]) -> list[dict[str, Any]]:
    from .estrazione_ruolo import estrai_ruoli

    fascicolo = metadata.get("fascicolo")
    cliente = str(getattr(fascicolo, "nome_cliente", "") or metadata.get("cliente") or "").strip()
    tokens = _plain(cliente).split()
    plain = " " + _plain(testo) + " "
    cliente_ok = len(tokens) >= 2 and (
        " " + " ".join(tokens) + " " in plain
        or " " + " ".join(reversed(tokens)) + " " in plain
    )
    numero = str(getattr(fascicolo, "numero_rg", "") or metadata.get("numero_rg") or "").strip()
    anno = str(getattr(fascicolo, "anno_rg", "") or metadata.get("anno_rg") or "").strip()
    if "/" in numero:
        numero, anno_da_numero = numero.split("/", 1)
        anno = anno or anno_da_numero
    rg = f"{int(numero)}/{anno}" if numero.isdigit() and anno.isdigit() else ""
    letture_rg = [f for f in estrai_ruoli(testo, origine="nativo") if f.campo == "numero_ruolo"]
    citati = []
    diretti = []
    for fatto in letture_rg:
        # Una lista esplicita di sentenze e uffici nel corpo dell'atto è una
        # citazione, non un'intestazione RG della pratica. La prova si conserva.
        prima = testo[max(0, fatto.posizione - 240):fatto.posizione]
        elenco_precedenti = fatto.posizione > 1800 and (
            len(re.findall(r"\bsentenz[ae]\b|\bsent\.", prima, re.I)) >= 2
            and len(re.findall(r"\btribunale\b|\bcorte\b", prima, re.I)) >= 2
        )
        (citati if elenco_precedenti else diretti).append(fatto)
    ruoli = {f.valore for f in diretti}
    rg_ok = bool(rg and ruoli == {rg})
    dettaglio_rg = "RG del fascicolo presente senza conflitti." if rg_ok else (
        "RG rilevati nel contenuto: " + ", ".join(sorted(ruoli)) + "; RG del fascicolo " + (rg or "non disponibile") + " non confermato."
        if ruoli else "Numero e anno RG della pratica non presenti nel contenuto."
    )
    if citati:
        dettaglio_rg += " RG citati nell'elenco dei precedenti: " + ", ".join(sorted({f.valore for f in citati})) + "; non usati per attribuire il pagamento."

    from pct.pec_case_identity import document_case_identity_evidence

    office_identity = document_case_identity_evidence(testo, fascicolo) if fascicolo is not None else {}
    office_ok = bool(office_identity.get("office_match")) and not office_identity.get("conflicts")

    return [
        codice_fiscale_parte(testo, metadata),
        {"codice": "ufficio_economico", "esito": "ok" if office_ok else "attenzione",
         "dettaglio": "Ufficio giudiziario della fonte concordante con il fascicolo." if office_ok else "Ufficio giudiziario della fonte non confermato per il fascicolo.",
         "conflitto": bool(office_identity.get("conflicts"))},
        {"codice": "cliente_economico", "esito": "ok" if cliente_ok else "attenzione",
         "dettaglio": "Cliente del fascicolo presente nel documento." if cliente_ok else "Nome e cognome del cliente non confermati nel contenuto."},
        {"codice": "rg_economico", "esito": "ok" if rg_ok else "attenzione",
         "dettaglio": dettaglio_rg,
         "riferimenti_citati": [{"rg": f.valore, "contesto": f.contesto} for f in citati]},
    ]


def identita_ricevuta_prima_del_ruolo(prove: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Ricevuta telematica pagata prima dell'iscrizione a ruolo: RG e ufficio non possono comparire.

    La RT (schema PagamentiTelematiciGiustizia) del contributo per l'atto introduttivo si paga prima del
    deposito, quando il numero di ruolo non esiste ancora, e indica come beneficiario il Ministero. Se la
    ricevuta non cita alcun ruolo né un ufficio in contrasto e vi compaiono il cliente o il suo codice
    fiscale, RG e ufficio si considerano riscontrati. L'uso dello stesso IUV in un altro fascicolo resta
    segnalato dal registro dei pagamenti (`pct.pagamenti_giustizia_registro`).
    """
    per_codice = {p.get("codice"): p for p in prove}
    rg, ufficio = per_codice.get("rg_economico", {}), per_codice.get("ufficio_economico", {})
    persona_ok = per_codice.get("cliente_economico", {}).get("esito") == "ok" or (
        per_codice.get("cf_economico", {}).get("esito") == "ok" and "concordante" in str(per_codice.get("cf_economico", {}).get("dettaglio")))
    senza_ruolo = rg.get("esito") != "ok" and str(rg.get("dettaglio") or "").startswith("Numero e anno RG della pratica non presenti")
    if not (persona_ok and senza_ruolo) or ufficio.get("conflitto"):
        return prove
    motivo = "Versamento anteriore all'iscrizione a ruolo: la ricevuta non può riportare RG e ufficio; cliente riscontrato."
    aggiornate = []
    for prova in prove:
        if prova.get("codice") == "rg_economico" or (prova.get("codice") == "ufficio_economico" and ufficio.get("esito") != "ok"):
            prova = {**prova, "esito": "ok", "dettaglio": motivo}
        aggiornate.append(prova)
    return aggiornate


def ricevuta_xml(testo: str) -> tuple[bool, dict[str, Any]]:
    """RT: esito reale e quota CU; totale misto CU/bollo mai attribuito al CU."""
    from pct.contributo_quote import quote_della_ricevuta
    from pct.pagamenti_giustizia import parse_rt

    if not str(testo).lstrip().startswith("<"):
        return False, {}
    if not re.search(r"<\s*(?:[\w.-]+:)?RT(?:\s|>)", str(testo)):
        return False, {}
    raw = str(testo).encode("utf-8")
    ricevuta = parse_rt(raw)
    if ricevuta is None:
        return True, {"errore": "XML non riconosciuto come ricevuta telematica valida."}
    quote = quote_della_ricevuta(raw, ricevuta.importo_totale)
    if quote.errore:
        return True, {"errore": quote.errore}
    return True, {
        "importo": float(quote.contributo), "status": "pagato" if ricevuta.pagamento_eseguito else "non_eseguito",
        "esito_codice": ricevuta.esito_codice, "iuv": ricevuta.iuv, "iur": ricevuta.iur,
        "data": ricevuta.data_esito_pagamento or ricevuta.data_ricevuta,
        "titolo": "Quota contributo unificato nella ricevuta telematica",
        "natura": "ricevuta_telematica_pagopa_contributo_unificato",
    }


def prova_ricevuta(dati: dict[str, Any]) -> dict[str, str]:
    completa = dati.get("status") == "pagato" and bool(dati.get("iuv") and dati.get("data"))
    dettaglio = dati.get("errore") or (
        "Ricevuta con esito positivo, data e IUV." if completa
        else "Pagamento non eseguito oppure data o IUV assenti nella ricevuta."
    )
    return {"codice": "ricevuta_economica", "esito": "ok" if completa else "attenzione", "dettaglio": str(dettaglio)}


def prova_dichiarazione(testo: str, *, secondario: str = "") -> dict[str, str]:
    """Distingue l'autocertificazione effettiva dal rinvio nell'atto introduttivo."""
    compatto = " ".join(str(testo or "").split())
    effettiva = bool(re.search(r"(?:autocertificazione|dichiarazione\s+sostitutiva).{0,120}reddit", compatto, re.I))
    effettiva = effettiva and bool(re.search(r"\bdichiara\b.{0,180}\breddito\b", compatto, re.I))
    # La scheda del registro attesta uno stato del procedimento. Non è una
    # verifica del reddito: non si deduce l'esenzione dalla sola intestazione
    # di un atto, dal nome del file o da una citazione normativa.
    scheda_registro = not effettiva and all(re.search(pattern, compatto, re.I) for pattern in (
        r"\bruolo\s+generale\s+n\.?",
        r"\biscritto\s+il\s*:",
        r"\bruolo\s+sezionale\s+n\.?",
        r"\battori\s*/\s*ricorrenti\s*/\s*appellanti\s*:",
        r"\bresistenti\s*/\s*ingiunti\s*/\s*appellati\s*:",
        r"\bcontributo\s+unificato\s*:\s*esente\b",
    )) and not re.search(r"\bnon\s+esente\b|esenzione\s+non\s+(?:ammessa|riconosciuta)", compatto, re.I)
    # Le cifre compilate fra i puntini del modulo restano cifre letterali:
    # nessuna sostituzione OCR di lettere e nessun anno cercato fuori dal campo.
    separatori = r"[\s.:…_·]*"
    schema_anno = re.compile(r"(?:relativamente\s+all.anno|periodo\s+(?:di\s+)?imposta(?:\s+anno)?)" + separatori +
        r"(2" + separatori + r"0" + separatori + r"\d" + separatori + r"\d)(?!\d)", re.I)
    anni: dict[str, tuple[str, str]] = {}
    for origine, contenuto in (("testo principale", compatto), ("seconda lettura dello stesso documento", " ".join(secondario.split()))):
        if origine.startswith("seconda") and not effettiva:
            continue
        for match in schema_anno.finditer(contenuto):
            anno = "".join(re.findall(r"\d", match.group(1)))
            anni.setdefault(anno, (origine, match.group(0)))
    unico = next(iter(anni.values())) if len(anni) == 1 else ("", "")
    limite = re.search(r"non\s+(?:è\s+superiore\s+a|supera(?:\s+(?:l.importo\s+)?di)?)\s*(?:euro|€)\s*([\d.,]+)", compatto, re.I)
    dati = {
        "versione": VERSIONE, "tipo": "autocertificazione" if effettiva else "attestazione_registro" if scheda_registro else "richiamo_nell_atto",
        "anno_reddito": next(iter(anni)) if len(anni) == 1 else "",
        "origine_anno": unico[0], "prova_anno": unico[1], "anni_discordanti": len(anni) > 1,
        "limite_dichiarato": limite.group(1) if limite else "",
        "esenzione_dichiarata": bool(effettiva and limite),
        "requisiti_verificati": False, "esenzione_attestata_registro": bool(scheda_registro),
        "motivo": (
            "Il registro indica contributo unificato esente; occorre il riscontro congiunto del procedimento."
            if scheda_registro else
            "Autocertificazione reddituale: riscontrare il dichiarante e il collegamento della fonte al fascicolo."
            if effettiva else
            "L'atto richiama l'esenzione; il richiamo non sostituisce l'autocertificazione reddituale."
        ),
    }
    return {"codice": "dichiarazione_economica", "esito": "attenzione", "dettaglio": json.dumps(dati, ensure_ascii=False)}


def identita_autocertificazione(testo: str, metadata: dict[str, Any]) -> list[dict[str, Any]]:
    """Dichiarante nel contenuto, procedimento dal collegamento SQL della fonte.

    Questa prova riguarda solo una dichiarazione effettiva di esenzione.
    Non autorizza l'attribuzione di sentenze o ricevute senza identità congiunta.
    """
    fascicolo = metadata.get("fascicolo")
    document_id = str(metadata.get("documento_id") or "")
    sha = str(metadata.get("document_hash_sha256") or "")
    documents = getattr(fascicolo, "documenti", ()) or ()
    linked = [doc for doc in documents if str(getattr(doc, "id", "")) == document_id]
    proof = identita(testo, metadata)
    client_ok = all(next((p.get("esito") for p in proof if p.get("codice") == code), "") == "ok"
                    for code in ("cliente_economico", "cf_economico"))
    numero = str(getattr(fascicolo, "numero_rg", "") or "")
    anno = str(getattr(fascicolo, "anno_rg", "") or "")
    if "/" in numero:
        numero, embedded_year = numero.split("/", 1)
        anno = anno or embedded_year
    office = str(getattr(fascicolo, "tribunale", "") or "").strip()
    linked_ok = bool(getattr(fascicolo, "id", "") and document_id and len(sha) == 64
                     and len(linked) == 1 and str(getattr(linked[0], "hash_sha256", "")) == sha
                     and numero.isdigit() and anno.isdigit() and office)
    # Un riferimento presente e discordante resta un conflitto: il contesto
    # SQL integra solo dati non previsti nel modulo, mai dati incompatibili.
    from .estrazione_ruolo import estrai_ruoli
    roles = {f.valore for f in estrai_ruoli(testo, origine="nativo") if f.campo == "numero_ruolo"}
    expected = f"{int(numero)}/{anno}" if numero.isdigit() and anno.isdigit() else ""
    conflict = bool(roles and roles != {expected})
    from pct.pec_case_identity import document_case_identity_evidence
    evidence = document_case_identity_evidence(testo, fascicolo) if fascicolo is not None else {}
    conflict = conflict or bool(evidence.get("conflicts"))
    ok = linked_ok and client_ok and not conflict
    return [p for p in proof if p["codice"] in {"cliente_economico", "cf_economico"}] + [{
        "codice": "contesto_autocertificazione", "esito": "ok" if ok else "attenzione",
        "dettaglio": "Dichiarante concordante; fonte originale collegata al fascicolo SQL con impronta verificata."
        if ok else "Dichiarante o collegamento della fonte al fascicolo non dimostrati, oppure riferimenti discordanti.",
        "fascicolo_id": str(getattr(fascicolo, "id", "") or ""), "documento_id": document_id,
        "sha256": sha, "rg": expected, "ufficio": office,
    }]
