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

VERSIONE = "2026.10.01.economico.v4+contesto-allegati-pec"


def _plain(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or "")).casefold()
    return " ".join(re.sub(r"[^\w]+", " ", text).split())


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

    return [
        {"codice": "cliente_economico", "esito": "ok" if cliente_ok else "attenzione",
         "dettaglio": "Cliente del fascicolo presente nel documento." if cliente_ok else "Nome e cognome del cliente non confermati nel contenuto."},
        {"codice": "rg_economico", "esito": "ok" if rg_ok else "attenzione",
         "dettaglio": dettaglio_rg,
         "riferimenti_citati": [{"rg": f.valore, "contesto": f.contesto} for f in citati]},
    ]


def ricevuta_xml(testo: str) -> tuple[bool, dict[str, Any]]:
    """RT: esito reale e quota CU; totale misto CU/bollo mai attribuito al CU."""
    from defusedxml import ElementTree
    from pct.pagamenti_giustizia import parse_rt

    if not str(testo).lstrip().startswith("<"):
        return False, {}
    if not re.search(r"<\s*(?:[\w.-]+:)?RT(?:\s|>)", str(testo)):
        return False, {}
    raw = str(testo).encode("utf-8")
    ricevuta = parse_rt(raw)
    if ricevuta is None:
        return True, {"errore": "XML non riconosciuto come ricevuta telematica valida."}
    root = ElementTree.fromstring(raw)
    quote_cu: list[Decimal] = []
    quote_tutte: list[Decimal] = []
    for nodo in root.iter():
        if nodo.tag.split("}")[-1] != "datiSingoloPagamento":
            continue
        campi = {el.tag.split("}")[-1]: str(el.text or "").strip() for el in nodo.iter()}
        try:
            importo = Decimal(campi.get("singoloImportoPagato", ""))
            if not importo.is_finite() or importo < 0:
                raise InvalidOperation
        except InvalidOperation:
            return True, {"errore": "Una quota della ricevuta non ha un importo valido."}
        quote_tutte.append(importo)
        causale = campi.get("causaleVersamento", "") + " " + campi.get("datiSpecificiRiscossione", "")
        if re.search(r"contributo\s+unificato", causale, re.I):
            quote_cu.append(importo)
    totale = Decimal(str(ricevuta.importo_totale))
    if not totale.is_finite() or totale < 0:
        return True, {"errore": "Il totale della ricevuta non è un importo valido."}
    if not quote_tutte or abs(sum(quote_tutte) - totale) > Decimal("0.01"):
        return True, {"errore": "Le quote della ricevuta non coincidono con il totale pagato."}
    if not quote_cu:
        return True, {"errore": "La ricevuta non identifica separatamente il contributo unificato."}
    return True, {
        "importo": float(sum(quote_cu)), "status": "pagato" if ricevuta.pagamento_eseguito else "non_eseguito",
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
    limite = re.search(r"non\s+(?:è\s+superiore\s+a|supera(?:\s+l.importo\s+di)?)\s*(?:euro|€)\s*([\d.,]+)", compatto, re.I)
    dati = {
        "versione": VERSIONE, "tipo": "autocertificazione" if effettiva else "richiamo_nell_atto",
        "anno_reddito": next(iter(anni)) if len(anni) == 1 else "",
        "origine_anno": unico[0], "prova_anno": unico[1], "anni_discordanti": len(anni) > 1,
        "limite_dichiarato": limite.group(1) if limite else "",
        "requisiti_verificati": False,
        "motivo": "Verifica la riferibilità alla pratica, l'ultima dichiarazione dei redditi e la sottoscrizione."
        if effettiva else "L'atto richiama l'esenzione; il richiamo non sostituisce l'autocertificazione reddituale.",
    }
    return {"codice": "dichiarazione_economica", "esito": "attenzione", "dettaglio": json.dumps(dati, ensure_ascii=False)}
