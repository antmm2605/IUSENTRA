"""Controlli automatici di un blocco d'atto (scritto da Lex o dal modello di redazione via API) rispetto al messaggio ricevuto.

Errori GRAVI (il blocco non passa):
- norma_fuori_fonti: articolo citato che non e' fra le Fonti del messaggio;
- numero_sbagliato: richiamo [n] attaccato a un articolo diverso da quello della Fonte n;
- richiamo_inesistente: [n] oltre il numero delle Fonti;
- data_inventata: data che non viene da scheda, note, scadenze o data di oggi;
- contro_il_cliente: domanda o formula a sfavore della parte assistita;
- dati_inventati: la scheda ha dati mancanti e il testo non ne segnala nessuno;
- lingua: ragionamento visibile o parti in inglese;
- vuoto: meno di 300 caratteri.
Avvisi (non bloccano): richiamo [n] mancante dopo un articolo che pero' e' nelle Fonti; assistito non nominato.
"""
from __future__ import annotations

import re

DATA = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")
ART = re.compile(r"\bart(?:t)?\.\s*(\d+(?:\s*-?\s*(?:terdecies|duodecies|undecies|quinquies|septies|novies|decies|quater|sexies|octies|bis|ter))?(?:\.\d+)?)", re.I)
RICH = re.compile(r"\[(\d{1,2})\]")
INGLESE = re.compile(r"\b(the|and|of the|which|should|must|however|therefore|request|court)\b", re.I)
ATTIVO = re.compile(r"ricorr|attor|oppon|reclam|appellant|istant|creditor|lavorator|contribuent|danneggiat|interessat|consumator|ricorrente|denunciant|querelant|persona offesa", re.I)
PASSIVO = re.compile(r"resistent|convenut|oppost|appellat|debitor|esecutat|ingiunt|imputat|indagat|condannat", re.I)
CONTRO_ATTIVO = re.compile(r"(rigettar[ei]|respinger[ei]|dichiarare inammissibile|dichiarare improcedibile)\s+(il|la|l')?\s*(presente\s+)?(ricorso|domanda|opposizione|reclamo|appello|istanza)|accertare\s+e?\s*(dichiarare\s+)?la\s+legittimit|dichiarare\s+legittim[oa]", re.I)
CONTRO_PASSIVO = re.compile(r"(accoglier[ei])\s+(il|la|l')?\s*(ricorso|domanda|opposizione)\s+(avversari|di controparte|proposta da)", re.I)
SIGLA = re.compile(r"^[^\n]{0,30}?(c\.\s?p\.\s?c|c\.\s?c\.|c\.\s?p\.\s?p|c\.\s?p\.(?!\s?[ac])|c\.\s?p\.\s?a|d\.\s?lgs|d\.\s?l\.|d\.\s?p\.\s?r|d\.\s?m\.|\bl\.\s|legge|ccii|cod\.|reg\.|regolamento \(|t\.u\.|disp\.\s?att|cost\.|costituzione|r\.d\.)", re.I)
ALTRUI = re.compile(r"^.{0,60}?(propost[oa] da|di controparte|avversari|dell[ae]? (resistente|ricorrente|controparte|appellat|reclamat|attore|convenut))", re.I | re.S)
SUFFISSI = "bis|ter|quater|quinquies|sexies|septies|octies|novies|decies|undecies|duodecies|terdecies"


def _atto_diverso(tra: str, fonte: dict) -> bool:
    """Fra articolo e [n] e' scritto un atto (n/anno) diverso da quello della Fonte n."""
    codici = {"cpc": r"c\.\s?p\.\s?c", "cc": r"c\.\s?c\.", "cpp": r"c\.\s?p\.\s?p", "cpa": r"c\.\s?p\.\s?a", "cp": r"c\.\s?p\.(?!\s?[cpa])"}
    sig = str(fonte.get("sigla", ""))
    usati = {k for k, rx in codici.items() if re.search(rx, tra, re.I)}
    della_fonte = {k for k, rx in codici.items() if re.search(rx, sig, re.I)}
    if usati and della_fonte and not (usati & della_fonte) and "disp" not in sig.lower():
        return True
    citato = re.findall(r"(?<![\d/])(\d{1,4})\s*/\s*(\d{4})(?!/)", re.sub(r"\b\d{1,2}/\d{1,2}/\d{4}\b", " ", tra))  # n/anno, non le date
    if not citato:
        return False
    rif = " ".join(str(fonte.get(k, "")) for k in ("sigla", "atto"))
    return not any(f"{a}/{b}" in rif.replace(" ", "") or f"{a}_{b}" in rif for a, b in citato)


def _richiamato_nel_testo(art: str, testo: str) -> bool:
    """L'articolo citato e' nominato nel testo della Fonte n (es. «impugnabile nelle forme dell'art. 617»)."""
    testo = re.sub(r"\barticol[oi]\s+", "art. ", testo, flags=re.I)
    numeri = {norm_art(m.group(1)) for m in ART.finditer(testo)}
    numeri |= {norm_art(x) for x in re.findall(r"(?:,|\be)\s+(\d+(?:-?(?:bis|ter|quater))?)\b", testo)}  # «articoli 392, 393 e 395»
    return art in numeri


def norm_art(a: str) -> str:
    return re.sub(r"[\s\-.]", "", a.lower())


def _date(t: str) -> set[str]:
    return {f"{int(g):02d}/{int(m):02d}/{a}" for g, m, a in DATA.findall(t)}


def ruolo(etichetta: str) -> str:
    if PASSIVO.search(etichetta or ""):
        return "passivo"
    if ATTIVO.search(etichetta or ""):
        return "attivo"
    return "?"


def controlla(testo: str, caso: dict, fatti: str = "") -> dict:
    gravi, avvisi = [], []
    t = testo or ""
    if len(t.strip()) < 300:
        gravi.append(("vuoto", f"{len(t.strip())} caratteri"))
    if "<think>" in t or "Thinking..." in t or len(INGLESE.findall(t)) >= 6:
        gravi.append(("lingua", "ragionamento visibile o testo in inglese"))
    fonti = {f["n"]: norm_art(f["articolo"]) for f in caso["fonti_ref"]}
    testi_fonti = {int(m.group(1)): m.group(2) for m in re.finditer(r"(?:^|\n\n)\[(\d+)\] (.*?)(?=\n\n\[\d+\] |\Z)", caso.get("fonti", ""), re.S)}
    articoli_fonti = set(fonti.values())
    for m in ART.finditer(t):
        art = norm_art(m.group(1))
        coda = t[m.end(): m.end() + 70]
        r = RICH.search(coda)
        legato = r is not None and r.start() < 60 and not ART.search(coda[: r.start()])
        if legato:
            n = int(r.group(1))
            if n not in fonti:
                gravi.append(("richiamo_inesistente", f"art. {m.group(1)} [{n}]"))
            elif fonti[n] != art and _richiamato_nel_testo(art, testi_fonti.get(n, "")):
                avvisi.append(("rinvio_dentro_fonte", f"art. {m.group(1)} richiamato nel testo della Fonte [{n}]"))
            elif fonti[n] != art or _atto_diverso(coda[: r.start()], caso["fonti_ref"][n - 1]):
                if fonti[n] != art and any(f == art for f in fonti.values()) and RICH.search(coda[r.end(): r.end() + 6]):
                    continue  # «art. X [1][2]»: l'articolo e' una delle Fonti richiamate insieme
                gravi.append(("numero_sbagliato", f"art. {m.group(1)} con [{n}] = art. {caso['fonti_ref'][n-1]['articolo']}"))
        elif art in articoli_fonti:
            avvisi.append(("manca_richiamo", f"art. {m.group(1)}"))
        elif not SIGLA.search(coda):
            avvisi.append(("rinvio_interno", f"art. {m.group(1)}"))  # clausola, punto o articolo senza fonte: non e' una norma citata
        else:
            # rinvii interni (clausole, punti) non sono norme: si scartano solo se preceduti da «del contratto»/«dello statuto»
            if re.search(r"(del|dello|della)\s+(contratto|statuto|regolamento condominiale|accordo|presente)", coda[:40], re.I):
                continue
            gravi.append(("norma_fuori_fonti", f"art. {m.group(1)} {coda[:25].strip()}"))
    for r in RICH.finditer(t):
        if int(r.group(1)) not in fonti and ("richiamo_inesistente", f"[{r.group(1)}]") not in gravi:
            gravi.append(("richiamo_inesistente", f"[{r.group(1)}]"))
    ammesse = _date(caso["scheda_risolta"]) | _date(fatti) | set(caso["scadenze"]) | {caso["oggi"]}
    for d in sorted(_date(t) - ammesse):
        gravi.append(("data_inventata", d))
    rr = ruolo(caso["assistito"]["ruolo"])
    if rr == "attivo":
        for m in CONTRO_ATTIVO.finditer(t):
            nome_cp = caso.get("controparte", {}).get("nome") or "@@"
            if "legittimit" not in m.group(0).lower() and "legittim" not in m.group(0).lower() and (
                    ALTRUI.search(t[m.end(): m.end() + 80]) or re.search(r"^.{0,30}?\b(di|da)\s+" + re.escape(nome_cp), t[m.end(): m.end() + 80], re.S)):
                continue  # chiede di respingere la domanda dell'altra parte: e' a favore del cliente
            gravi.append(("contro_il_cliente", m.group(0))); break
    if rr == "passivo" and CONTRO_PASSIVO.search(t):
        gravi.append(("contro_il_cliente", CONTRO_PASSIVO.search(t).group(0)))
    nome = caso["assistito"]["nome"]
    if nome and re.search(r"condann\w+\s+(il\s+sig\.?\s+|la\s+sig\.?ra\s+|la\s+|il\s+)?" + re.escape(nome), t, re.I) and rr != "passivo":
        gravi.append(("contro_il_cliente", f"condanna di {nome}"))
    if caso.get("dati_mancanti") and "[DATO MANCANTE" not in t:
        gravi.append(("dati_inventati", "la scheda ha dati mancanti ma il testo non ne segnala"))
    if nome and nome.split()[-1].lower() not in t.lower():
        avvisi.append(("assistito_non_nominato", nome))
    tipi = sorted({g[0] for g in gravi})
    return {"ok": not gravi, "gravi": gravi, "avvisi": avvisi, "tipi": tipi}
