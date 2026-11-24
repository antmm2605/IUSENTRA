"""Quale testo della norma si applica alla causa: vigente o anteriore alla riforma del d.lgs. 149/2022.

La decorrenza non si presume: si legge nella nota Normattiva del testo vigente («hanno effetto a decorrere dal 28
febbraio 2023 e si applicano ai procedimenti instaurati successivamente a tale data»). Si decide in automatico solo
quando la nota ha questa regola unica e la data di instaurazione del procedimento è certa; quando la nota prevede
decorrenze diverse (impugnazioni, cassazione, mediazione dal 30/06/2023) o la data manca, si mostrano le due versioni
e si dichiara il punto da verificare.

``testo_applicabile(chiave, data_instaurazione)`` è la funzione che l'harness di Lex può chiamare.
"""
from __future__ import annotations

import re
from datetime import date
from typing import Any

_MESI = {m: i for i, m in enumerate(("gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno", "luglio", "agosto",
                                     "settembre", "ottobre", "novembre", "dicembre"), 1)}
_REGOLA = re.compile(r"hanno effetto a decorrere dal (\d{1,2})° ?\s*(\w+) (\d{4}) e si applicano ai procedimenti instaurati "
                     r"successivamente a tale data", re.I)
_REGOLA_SEMPLICE = re.compile(r"hanno effetto a decorrere dal (\d{1,2}) (\w+) (\d{4}) e si applicano ai procedimenti "
                              r"instaurati successivamente a tale data", re.I)
_ALTRE_DECORRENZE = re.compile(r"\(con l'art\. 35, comma [2-9]\)|\(con l'art\. 41|si applicano alle impugnazioni|"
                               r"si applicano a decorrere dal|ha inoltre disposto", re.I)


def regola_decorrenza(nota_piu_recente: str) -> dict[str, Any]:
    """La regola letta nella nota: «instaurazione» con la data, oppure «differenziata»/«non letta»."""
    if not nota_piu_recente:
        return {"tipo": "non letta", "motivo": "nessuna nota di decorrenza del d.lgs. 149/2022 nel testo vigente"}
    m = _REGOLA_SEMPLICE.search(nota_piu_recente) or _REGOLA.search(nota_piu_recente)
    if m is None or _ALTRE_DECORRENZE.search(nota_piu_recente):
        return {"tipo": "differenziata", "motivo": "la nota prevede decorrenze diverse secondo la disposizione o "
                "l'impugnazione: la regola si sceglie sull'atto del fascicolo", "nota": nota_piu_recente}
    mese = _MESI.get(m.group(2).lower())
    if not mese:
        return {"tipo": "non letta", "motivo": "data della nota non leggibile", "nota": nota_piu_recente}
    return {"tipo": "instaurazione", "data": date(int(m.group(3)), mese, int(m.group(1))), "nota": nota_piu_recente}


def _data(valore: Any) -> date | None:
    if isinstance(valore, date):
        return valore
    try:
        return date.fromisoformat(str(valore)[:10]) if valore else None
    except ValueError:
        return None


def testo_applicabile(chiave: str, data_instaurazione: Any = None) -> dict[str, Any]:
    """Il testo da applicare alla causa instaurata in ``data_instaurazione`` (data o ISO), con il motivo.

    ``versione``: «vigente», «anteriore» oppure «entrambe» (decisione non automatica: si mostrano i due testi)."""
    from .consultazione import passaggio_norma, testo_anteriore

    vigente = passaggio_norma(chiave)
    anteriore = testo_anteriore(chiave)
    giorno = _data(data_instaurazione)
    base = {"chiave": chiave, "data_instaurazione": giorno.isoformat() if giorno else "", "testo_vigente": vigente}
    if anteriore is None:
        return {**base, "versione": "vigente", "testo_anteriore": None,
                "motivo": "norma senza testo anteriore registrato: non modificata dal d.lgs. 149/2022 fra quelle delle schede"}
    nota = (anteriore.get("decorrenza_letta") or [""])[-1]
    regola = regola_decorrenza(nota)
    base |= {"testo_anteriore": anteriore, "decorrenza": regola}
    if regola["tipo"] != "instaurazione":
        return {**base, "versione": "entrambe", "motivo": regola["motivo"] + "."}
    soglia = regola["data"]
    if giorno is None:
        return {**base, "versione": "entrambe",
                "motivo": f"data di instaurazione del procedimento non certa: per i procedimenti instaurati fino al "
                          f"{soglia:%d/%m/%Y} vale il testo anteriore, per quelli successivi il testo vigente."}
    if giorno > soglia:
        return {**base, "versione": "vigente", "motivo": f"procedimento instaurato il {giorno:%d/%m/%Y}, dopo il "
                                                          f"{soglia:%d/%m/%Y}: si applica il testo vigente (nota Normattiva)."}
    if anteriore["stato"] != "testo anteriore":
        return {**base, "versione": "anteriore",
                "motivo": f"procedimento instaurato il {giorno:%d/%m/%Y}, entro il {soglia:%d/%m/%Y}: l'articolo è stato "
                          f"introdotto dalla riforma e non si applica; vale la disciplina anteriore, da cercare nelle norme "
                          f"vigenti a quella data."}
    return {**base, "versione": "anteriore", "motivo": f"procedimento instaurato il {giorno:%d/%m/%Y}, entro il "
                                                        f"{soglia:%d/%m/%Y}: si applica il testo anteriore alla riforma."}


# ------------------------------------------------------------------ data di instaurazione dalle letture del fascicolo
# Campi dell'archivio delle letture che datano l'atto introduttivo: deposito del ricorso (riti a ricorso), notifica
# della citazione (rito ordinario), iscrizione a ruolo.
CAMPI_INSTAURAZIONE = ("data_deposito_ricorso", "data_notifica_citazione", "data_iscrizione_ruolo",
                       "data_deposito_atto_introduttivo")
VERIFICHE_CERTE = ("verificata", "corretta")


def data_instaurazione(fatti: list[Any]) -> dict[str, Any]:
    """La data di instaurazione dai fatti letti del fascicolo: certa solo se verificata (o corretta dall'avvocato) e
    unica; con date diverse o solo plausibili è incerta, e lo si dice."""
    candidati = [f for f in fatti if getattr(f, "campo", "") in CAMPI_INSTAURAZIONE
                 and getattr(f, "verifica", "") not in ("respinta", "ignorata")]
    certi = [f for f in candidati if getattr(f, "verifica", "") in VERIFICHE_CERTE and _data(getattr(f, "valore", ""))]
    valori = sorted({_data(f.valore) for f in certi})
    if len(valori) == 1:
        f = next(x for x in certi if _data(x.valore) == valori[0])
        return {"data": valori[0].isoformat(), "certa": True, "campo": f.campo,
                "motivo": f"{f.campo.replace('_', ' ')} letta nel fascicolo e verificata"}
    if len(valori) > 1:
        return {"data": "", "certa": False, "motivo": "date di instaurazione diverse fra i documenti letti: "
                + ", ".join(f"{d:%d/%m/%Y}" for d in valori)}
    if candidati:
        return {"data": "", "certa": False, "motivo": "data dell'atto introduttivo letta ma non ancora verificata"}
    return {"data": "", "certa": False, "motivo": "nessuna data dell'atto introduttivo fra le letture del fascicolo"}


def applicabilita_scheda(scheda: dict[str, Any], data: Any) -> dict[str, dict[str, str]]:
    """Per ogni norma della scheda con testo anteriore: quale versione si applica alla data e perché."""
    out = {}
    for f in scheda.get("fonti", []):
        if f.get("tipo") == "norma" and f.get("testo_anteriore"):
            r = testo_applicabile(f["chiave"], data)
            out[f["chiave"]] = {"versione": r["versione"], "motivo": r["motivo"]}
    return out
