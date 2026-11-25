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
# Campi del lettore (pct/archivio_letture/date_campi_modello.py, CAMPI_INSTAURAZIONE; branch lettore-iscrizione):
# - «data_deposito_ricorso» e «data_iscrizione_ruolo»: atto introduttivo nei riti a ricorso (deposito, poi iscrizione);
# - «data_notifica_citazione»: atto introduttivo nei riti a citazione (anche nell'anagrafica del fascicolo, scritta
#   dallo studio: pct/fascicoli.py);
# - «deposito» (categoria «data», generico): vale solo con il contesto dell'atto introduttivo («ricorso depositato in
#   data», «iscritta a ruolo in data», «Nota d'iscrizione a ruolo»), mai l'originale notificato o la relata;
#   «Tipologia: Atto principale» del PolisWeb non basta (vale anche per la memoria della controparte);
# - «numero_ruolo» («N/AAAA»): l'anno dell'iscrizione a ruolo, usato solo come regola di riserva (vedi sotto).
CAMPO_RICORSO = "data_deposito_ricorso"
CAMPO_ISCRIZIONE = "data_iscrizione_ruolo"
CAMPO_CITAZIONE = "data_notifica_citazione"
VERIFICHE_CERTE = ("verificata", "corretta")
SOGLIA_RIFORMA = date(2023, 2, 28)
_INTRODUTTIVO = re.compile(r"ricorso\s+(?:telematico\s+)?depositato\s+in\s+data|"
                           r"iscritt[ao]\s+a\s+ruolo\s+in\s+data|nota\s+d.?iscrizione\s+a\s+ruolo", re.I)
_NON_INTRODUTTIVO = re.compile(r"originale\s+notificato|relata|note\s+scritte|contributo\s+unificato\s+richiesto", re.I)
_ETICHETTE = {CAMPO_RICORSO: "data di deposito del ricorso", CAMPO_ISCRIZIONE: "data di iscrizione a ruolo",
              CAMPO_CITAZIONE: "data di notifica della citazione", "deposito": "data di deposito dell'atto introduttivo"}


def _e_introduttivo(f: Any) -> bool:
    campo = getattr(f, "campo", "")
    if campo in (CAMPO_RICORSO, CAMPO_ISCRIZIONE, CAMPO_CITAZIONE):
        return True
    contesto = str(getattr(f, "contesto", "") or "")
    return campo == "deposito" and bool(_INTRODUTTIVO.search(contesto)) and not _NON_INTRODUTTIVO.search(contesto)


def _anni_ruolo(fatti: list[Any]) -> set[int]:
    anni = set()
    for f in fatti:
        if getattr(f, "campo", "") == "numero_ruolo" and getattr(f, "verifica", "") in VERIFICHE_CERTE:
            m = re.search(r"/(\d{4})\b", str(getattr(f, "valore", "")))
            if m:
                anni.add(int(m.group(1)))
    return anni


def periodo_da_ruolo(anni: set[int]) -> dict[str, Any] | None:
    """L'anno del numero di ruolo: ≥ 2024 basta per «instaurato dopo il 28/02/2023», ≤ 2022 per «prima»; il 2023 resta
    ambiguo (il 28/02 cade nell'anno). Numeri di ruolo verificati con anni discordanti: nessuna conclusione."""
    if not anni:
        return None
    if all(a >= 2024 for a in anni):
        return {"periodo": "dopo", "motivo": f"numero di ruolo del {max(anni)}: iscrizione a ruolo successiva al 28/02/2023"}
    if all(a <= 2022 for a in anni):
        return {"periodo": "prima", "motivo": f"numero di ruolo del {min(anni)}: iscrizione a ruolo anteriore al 28/02/2023"}
    return {"periodo": "", "motivo": "numero di ruolo del 2023 (o anni discordanti): l'anno da solo non dice se prima o dopo il 28/02/2023"}


def data_instaurazione(fatti: list[Any], fascicolo: Any = None) -> dict[str, Any]:
    """La data di instaurazione del procedimento dalle letture del fascicolo, con il motivo.

    Priorità: citazione → data di notifica (fatto verificato o anagrafica del fascicolo); ricorso → data di deposito,
    poi di iscrizione a ruolo; poi il deposito generico con il contesto dell'atto introduttivo. Certa solo se verificata
    (o corretta dall'avvocato) e unica nel suo livello. Senza data certa, l'anno del numero di ruolo può bastare a dire
    «prima» o «dopo» il 28/02/2023 («periodo»)."""
    validi = [f for f in fatti if _e_introduttivo(f) and getattr(f, "verifica", "") not in ("respinta", "ignorata")
              and _data(getattr(f, "valore", ""))]
    certi = [f for f in validi if getattr(f, "verifica", "") in VERIFICHE_CERTE]
    anagrafica = _data(getattr(fascicolo, CAMPO_CITAZIONE, "")) if fascicolo is not None else None
    livelli = ((CAMPO_CITAZIONE,), (CAMPO_RICORSO,), (CAMPO_ISCRIZIONE,), ("deposito",))
    for campi in livelli:
        valori = sorted({_data(f.valore) for f in certi if f.campo in campi})
        if campi == (CAMPO_CITAZIONE,) and anagrafica and not valori:
            return {"data": anagrafica.isoformat(), "certa": True, "campo": CAMPO_CITAZIONE,
                    "motivo": "data di notifica della citazione scritta nell'anagrafica del fascicolo"}
        if len(valori) == 1:
            return {"data": valori[0].isoformat(), "certa": True, "campo": campi[0],
                    "motivo": f"{_ETICHETTE[campi[0]]} letta nel fascicolo e verificata"}
        if len(valori) > 1:
            return _con_ruolo(fatti, {"data": "", "certa": False, "motivo": f"{_ETICHETTE[campi[0]]}: date diverse fra i "
                                      "documenti letti: " + ", ".join(f"{d:%d/%m/%Y}" for d in valori)})
    letti = sorted({_data(f.valore) for f in validi})
    if letti:
        return _con_ruolo(fatti, {"data": "", "certa": False, "data_letta": letti[0].isoformat(),
                                  "motivo": "data dell'atto introduttivo letta ma non ancora verificata: "
                                            + ", ".join(f"{d:%d/%m/%Y}" for d in letti)})
    return _con_ruolo(fatti, {"data": "", "certa": False, "motivo": "nessuna data dell'atto introduttivo fra le letture del fascicolo"})


def _con_ruolo(fatti: list[Any], esito: dict[str, Any]) -> dict[str, Any]:
    ruolo = periodo_da_ruolo(_anni_ruolo(fatti))
    if ruolo is None:
        return esito
    esito = dict(esito, periodo=ruolo["periodo"])
    esito["motivo"] += "; " + ruolo["motivo"]
    return esito


def data_per_testo(esito: dict[str, Any]) -> date | None:
    """La data da usare per scegliere il testo: quella certa, oppure un giorno sicuramente dalla parte giusta del
    28/02/2023 quando lo dice l'anno del numero di ruolo; altrimenti nessuna (si mostrano le due versioni)."""
    if esito.get("certa") and esito.get("data"):
        return _data(esito["data"])
    if esito.get("periodo") == "dopo":
        return date(2024, 1, 1)
    if esito.get("periodo") == "prima":
        return date(2022, 12, 31)
    return None


def applicabilita_scheda(scheda: dict[str, Any], esito: Any) -> dict[str, dict[str, str]]:
    """Per ogni norma della scheda con testo anteriore: quale versione si applica e perché. ``esito`` è il risultato di
    ``data_instaurazione`` (o una data)."""
    if not isinstance(esito, dict):
        esito = {"data": str(esito or ""), "certa": bool(esito)}
    giorno = data_per_testo(esito)
    dal_ruolo = giorno is not None and not esito.get("certa")
    out = {}
    for f in scheda.get("fonti", []):
        if f.get("tipo") == "norma" and f.get("testo_anteriore"):
            r = testo_applicabile(f["chiave"], giorno)
            motivo = r["motivo"]
            if dal_ruolo and r["versione"] != "entrambe":
                motivo = (f"{esito['motivo'].split('; ')[-1]}: si applica il testo "
                          f"{'vigente' if r['versione'] == 'vigente' else 'anteriore alla riforma'} (nota Normattiva).")
            out[f["chiave"]] = {"versione": r["versione"], "motivo": motivo}
    return out
