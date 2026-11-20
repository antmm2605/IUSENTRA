"""Le parti e il valore della causa letti negli atti: chi è la controparte, chi la difende, quanto vale la causa.

- **Controparte e difensore.** L'atto introduttivo dello studio nomina la parte convenuta («contro MINISTERO
  DELL'ISTRUZIONE E DEL MERITO, in persona del Ministro pro tempore…, difeso per legge dall'Avvocatura
  Distrettuale dello Stato…»). L'Avvocatura dello Stato rappresenta e difende le Amministrazioni dello Stato
  (art. 1 R.D. 1611/1933): è il difensore, non la parte. Se in anagrafica la controparte è un'Avvocatura (o manca),
  la controparte è la parte nominata nell'atto e l'Avvocatura diventa il suo difensore; una controparte registrata
  che è davvero una parte resta com'è (decisione dello studio).
- **Valore.** Il valore si determina dalla domanda (artt. 10 e 14 c.p.c.) e, ai fini del contributo unificato, deve
  risultare da apposita dichiarazione nelle conclusioni dell'atto introduttivo (art. 14, comma 2, D.P.R. 115/2002);
  senza dichiarazione il processo si presume del valore più alto (art. 13, comma 6, D.P.R. 115/2002). Si legge la
  dichiarazione (importo o indeterminabilità) solo quando l'atto la scrive come valore della causa: «carta di valore
  pari a € 500 annui» non è una dichiarazione di valore.

Modulo puro, sul testo degli atti già letti: nessuna lettura di file.
"""

from __future__ import annotations

import re
from typing import Any, Iterable

from .modello import Atto
from .testo import pulito

_AVVOCATURA = re.compile(r"\bavvocatura\b", re.I)
_DIFENSORE_REGISTRATO = re.compile(r"\bavvocatura\b|^\s*avv(?:\.|ocat[oa])\b|\bstudio\s+legale\b", re.I)
_CONTRO = re.compile(
    r"\b(?i:contro|nei\s+confronti\s+d(?:i|el|ella|ello|egli|elle|ell['’]))\s+(?i:il\s+|la\s+|lo\s+|l['’]\s*)?"
    r"(?P<nome>[A-ZÀ-Ü][^,;()\n]{2,140}?)\s*(?i:,|\(|\s+in\s+persona|\s+c\.\s*f\.|\s+con\s+sede|\s+rappresentat|\s+difes|\s+p\.\s*iva)",
)
_DIFESO_DA = re.compile(
    r"\b(?:rappresentat[oaie]\s+e\s+)?difes[oaie]\s+(?:per\s+legge\s+|ex\s+lege\s+|ope\s+legis\s+)?(?:dall['’]\s*|dalla\s+|dal\s+)"
    r"(?P<nome>Avvocatura[^,;()\n]{3,90}?)\s*(?:,|\(|;|\.|\s+c\.\s*f\.|\s+presso|\s+con\s+sede|\s+domiciliat)", re.I)
_NUMERO = r"(?:[0-9]{1,3}(?:\.[0-9]{3})+|[0-9]+)(?:,[0-9]{1,2})?"
_OGGETTO_VALORE = (r"valore\s+(?:della\s+(?:presente\s+)?(?:causa|controversia|lite|procedura|domanda)|"
                   r"del\s+(?:presente\s+)?(?:giudizio|procedimento|ricorso))")
_VALORE_IMPORTO = re.compile(
    _OGGETTO_VALORE + r"\s*,?\s*(?:ai\s+fini[^.;€]{0,70}?)?\s*(?:è|e['’]|risulta|ammonta|corrisponde)?\s*(?:di|pari\s+a|a|:|=)?\s*"
    r"(?:€|euro|eur\.?)\s*(?P<importo>" + _NUMERO + r")(?![\d.,]*\d)", re.I)
_VALORE_INDETERMINABILE = re.compile(
    _OGGETTO_VALORE + r"[^.;]{0,50}?\bindetermina(?:bile|to)\b|"
    r"\b(?:causa|controversia|procedimento|giudizio|procedura)\s+(?:è\s+)?di\s+valore\s+indetermina(?:bile|to)\b", re.I)
_RAPPRESENTANTE = re.compile(r"(?:il\s+)?(?:ministro|legale\s+rappresentante|presidente|sindaco|direttore|dirigente)\b", re.I)
_MINUSCOLE = {"di", "del", "della", "dello", "dei", "degli", "delle", "e", "ed", "per", "in", "a", "al", "alla", "dell", "da", "dal", "dalla"}


def _nome_proprio(testo: str) -> str:
    """«MINISTERO DELL'ISTRUZIONE E DEL MERITO» → «Ministero dell'Istruzione e del Merito»; un nome già scritto bene resta."""
    nome = pulito(testo).strip(" .:-")
    if not nome or not nome.isupper():
        return nome
    parole = []
    for indice, parola in enumerate(nome.split()):
        pezzi = re.split(r"(['’])", parola.lower())
        pezzi = [p if p in {"'", "’"} or (indice and p in _MINUSCOLE) else p[:1].upper() + p[1:] for p in pezzi]
        parole.append("".join(pezzi))
    return " ".join(parole)


def _introduttivo(atti: Iterable[Atto], posizione: str) -> Atto | None:
    candidati = [a for a in atti if a.appartenenza == "causa" and a.natura == "atto_principale" and a.testo]
    nostri = [a for a in candidati if a.dello_studio]
    scelti = nostri if posizione == "attiva" and nostri else candidati if posizione != "attiva" else []
    return min(scelti, key=lambda a: (a.data or "9999", a.nome)) if scelti else None


def dichiarazione_di_valore(testo: str) -> dict[str, Any] | None:
    """La dichiarazione di valore dell'atto (l'ultima, quella delle conclusioni), o None se l'atto non la scrive."""
    testo = " ".join(str(testo or "").split())
    voci = [(m.start(), {"tipo": "importo", "importo": float(m.group("importo").replace(".", "").replace(",", ".")),
                         "brano": testo[m.start():m.end()]}) for m in _VALORE_IMPORTO.finditer(testo)]
    voci += [(m.start(), {"tipo": "indeterminabile", "brano": testo[m.start():m.end()]}) for m in _VALORE_INDETERMINABILE.finditer(testo)]
    return max(voci, key=lambda voce: voce[0])[1] if voci else None


def parti_della_causa(atti: Iterable[Atto], posizione: str, fascicolo: dict[str, Any]) -> dict[str, Any]:
    atti = list(atti)
    registrata = pulito(fascicolo.get("controparte"))
    difensore_registrato = pulito(fascicolo.get("avvocato_controparte"))
    esito: dict[str, Any] = {"controparte": registrata, "difensore_controparte": difensore_registrato,
                             "fonte_controparte": "anagrafica del fascicolo" if registrata else ""}
    atto = _introduttivo(atti, posizione)
    # Il testo estratto porta i segni dell'impaginazione («***MINISTERO…*»): non fanno parte del nome.
    testa = " ".join(re.sub(r"[*_#]+", "", (atto.testo if atto else "")[:8000]).split())
    trovato = _CONTRO.search(testa) if atto and posizione == "attiva" else None
    nome = _nome_proprio(trovato.group("nome")) if trovato else ""
    if nome and (_AVVOCATURA.search(nome) or _RAPPRESENTANTE.match(nome)):
        nome = ""  # l'atto nomina il difensore o chi rappresenta la parte («Ministro pro tempore»), non la parte
    if nome and (not registrata or _DIFENSORE_REGISTRATO.search(registrata)):
        difeso = _DIFESO_DA.search(testa[trovato.end():trovato.end() + 900]) if trovato else None
        difensore = _nome_proprio(difeso.group("nome")) if difeso else ""
        if not difensore and registrata and _AVVOCATURA.search(registrata):
            difensore = registrata
        esito.update(controparte=nome, difensore_controparte=difensore or difensore_registrato,
                     fonte_controparte=f"atto introduttivo «{atto.nome}»",
                     norma_difensore="art. 1 R.D. 1611/1933" if difensore and _AVVOCATURA.search(difensore) else "")
        if registrata and registrata != nome:
            esito["controparte_registrata"] = registrata
    try:
        valore = float(fascicolo.get("valore_causa") or 0)
    except (TypeError, ValueError):
        valore = 0.0
    if valore > 0:
        fonte = fascicolo.get("fonte_valore_causa") or {}
        esito["valore"] = {"tipo": "importo", "importo": valore,
                           "fonte": "nota di iscrizione a ruolo" if isinstance(fonte, dict) and fonte else "anagrafica del fascicolo"}
    elif atto:
        dichiarata = dichiarazione_di_valore(atto.testo)
        esito["valore"] = ({**dichiarata, "fonte": f"atto introduttivo «{atto.nome}»", "documento_id": atto.id,
                            "norma": "art. 14, comma 2, D.P.R. 115/2002; art. 14 c.p.c."} if dichiarata else
                           {"tipo": "non_dichiarato", "fonte": f"atto introduttivo «{atto.nome}»", "documento_id": atto.id,
                            "norma": "art. 14, comma 2, e art. 13, comma 6, D.P.R. 115/2002"})
    return esito


def etichetta_valore(valore: dict[str, Any] | None) -> str:
    """Il testo della testata: «Valore € 2.400,00», «Valore indeterminabile», «Valore non dichiarato nell'atto introduttivo»."""
    if not valore:
        return ""
    if valore.get("tipo") == "importo":
        importo = f"{float(valore['importo']):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        return f"Valore € {importo}"
    if valore.get("tipo") == "indeterminabile":
        return "Valore indeterminabile (dichiarato nell'atto introduttivo)"
    return "Valore non dichiarato nell'atto introduttivo (art. 14, comma 2, D.P.R. 115/2002)"


__all__ = ["dichiarazione_di_valore", "etichetta_valore", "parti_della_causa"]
