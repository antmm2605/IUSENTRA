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
# Nomi verificati sull'archivio delle letture (campione di 5 fascicoli dell'8080, 24/11/2026):
# - «data_deposito_ricorso» (categoria «metadato_fascicolo», pct/archivio_letture/date_campi_modello.py): è la data
#   dell'atto introduttivo nei riti a ricorso; certa quando verificata;
# - «deposito» (categoria «data», pct/archivio_letture/ancoraggio.py): data generica di un deposito; è dell'atto
#   introduttivo solo se il contesto lo dice («ricorso depositato in data», «iscritta a ruolo in data», «Nota
#   d'iscrizione a ruolo»), mai il deposito dell'originale notificato o della relata. «Tipologia: Atto principale» del
#   PolisWeb NON basta: è l'atto principale di ogni deposito, anche della memoria della controparte;
# - «data_notifica_citazione»: campo dell'anagrafica del fascicolo (pct/fascicoli.py), scritto dallo studio.
CAMPO_RICORSO = "data_deposito_ricorso"
VERIFICHE_CERTE = ("verificata", "corretta")
_INTRODUTTIVO = re.compile(r"ricorso\s+(?:telematico\s+)?depositato\s+in\s+data|"
                           r"iscritt[ao]\s+a\s+ruolo\s+in\s+data|nota\s+d.?iscrizione\s+a\s+ruolo", re.I)
_NON_INTRODUTTIVO = re.compile(r"originale\s+notificato|relata|note\s+scritte|contributo\s+unificato\s+richiesto", re.I)


def _e_introduttivo(f: Any) -> bool:
    if getattr(f, "campo", "") == CAMPO_RICORSO:
        return True
    contesto = str(getattr(f, "contesto", "") or "")
    return (getattr(f, "campo", "") == "deposito" and bool(_INTRODUTTIVO.search(contesto))
            and not _NON_INTRODUTTIVO.search(contesto))


def data_instaurazione(fatti: list[Any], fascicolo: Any = None) -> dict[str, Any]:
    """La data di instaurazione dai fatti letti del fascicolo: certa solo se verificata (o corretta dall'avvocato) e
    unica, oppure scritta dallo studio nell'anagrafica (data di notifica della citazione); con date diverse o solo
    plausibili è incerta, e lo si dice con la data letta."""
    candidati = [f for f in fatti if _e_introduttivo(f) and getattr(f, "verifica", "") not in ("respinta", "ignorata")
                 and _data(getattr(f, "valore", ""))]
    certi = [f for f in candidati if getattr(f, "verifica", "") in VERIFICHE_CERTE]
    valori = sorted({_data(f.valore) for f in certi})
    citazione = _data(getattr(fascicolo, "data_notifica_citazione", "")) if fascicolo is not None else None
    if citazione and not valori:
        return {"data": citazione.isoformat(), "certa": True, "campo": "data_notifica_citazione",
                "motivo": "data di notifica della citazione scritta nell'anagrafica del fascicolo"}
    if len(valori) == 1:
        f = next(x for x in certi if _data(x.valore) == valori[0])
        come = ("data di deposito del ricorso letta" if f.campo == CAMPO_RICORSO
                else "data di deposito dell'atto introduttivo letta")
        return {"data": valori[0].isoformat(), "certa": True, "campo": f.campo, "motivo": f"{come} nel fascicolo e verificata"}
    if len(valori) > 1:
        return {"data": "", "certa": False, "motivo": "date di instaurazione diverse fra i documenti letti: "
                + ", ".join(f"{d:%d/%m/%Y}" for d in valori)}
    letti = sorted({_data(f.valore) for f in candidati})
    if letti:
        return {"data": "", "certa": False, "data_letta": letti[0].isoformat(),
                "motivo": "deposito dell'atto introduttivo letto ma non ancora verificato: "
                          + ", ".join(f"{d:%d/%m/%Y}" for d in letti)}
    return {"data": "", "certa": False, "motivo": "nessuna data dell'atto introduttivo fra le letture del fascicolo"}


def applicabilita_scheda(scheda: dict[str, Any], data: Any) -> dict[str, dict[str, str]]:
    """Per ogni norma della scheda con testo anteriore: quale versione si applica alla data e perché."""
    out = {}
    for f in scheda.get("fonti", []):
        if f.get("tipo") == "norma" and f.get("testo_anteriore"):
            r = testo_applicabile(f["chiave"], data)
            out[f["chiave"]] = {"versione": r["versione"], "motivo": r["motivo"]}
    return out
