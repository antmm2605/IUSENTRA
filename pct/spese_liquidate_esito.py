"""Direzione del capo spese di una sentenza: chi è condannato, a favore di chi, per quale quota.

L'importo liquidato (`pct.spese_liquidate_lettura`) non basta per un credito dello studio:

- art. 91 c.p.c.: le spese le paga la parte soccombente. Se il condannato è il cliente, l'importo è un suo
  debito verso la controparte, non un compenso dello studio;
- art. 92 c.p.c.: con la compensazione parziale è dovuta solo la quota non compensata;
- art. 93 c.p.c.: con la distrazione la somma spetta al difensore antistatario;
- art. 133 D.P.R. 115/2002: se la parte vittoriosa è ammessa al patrocinio a spese dello Stato, il pagamento
  è disposto a favore dello Stato; il compenso del difensore si liquida con il decreto dell'art. 82.

Modulo puro, senza dipendenze dal dominio. Quando il dispositivo non permette di stabilire chi è condannato
la direzione resta «non determinata»: nessun credito automatico, la decisione spetta all'avvocato.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field

CONTROPARTE = "controparte"
CLIENTE = "cliente"
NON_DETERMINATO = "non_determinato"

PARTE = "parte"
ANTISTATARIO = "difensore_antistatario"
STATO = "stato"

_RUOLI = {
    "ricorrent": "ricorrente", "resistent": "resistente", "attor": "attore", "attric": "attore",
    "convenut": "convenuto", "appellant": "appellante", "appellat": "appellato", "opponent": "opponente",
    "oppost": "opposto", "reclamant": "reclamante", "reclamat": "reclamato", "intimat": "intimato",
    # Processo penale (artt. 74-89 e 541 c.p.p.): la parte civile ottiene la rifusione dall'imputato o dal
    # responsabile civile.
    "imputat": "imputato", "parte civile": "parte_civile", "responsabile civile": "responsabile_civile",
}
_OPPOSTI = {
    "ricorrente": {"resistente", "intimato", "convenuto"}, "resistente": {"ricorrente"},
    "attore": {"convenuto"}, "convenuto": {"attore", "ricorrente"}, "appellante": {"appellato"},
    "appellato": {"appellante"}, "opponente": {"opposto"}, "opposto": {"opponente"},
    "reclamante": {"reclamato"}, "reclamato": {"reclamante"}, "intimato": {"ricorrente"},
    "parte_civile": {"imputato", "responsabile_civile"}, "imputato": {"parte_civile"},
    "responsabile_civile": {"parte_civile"},
}
_DISPOSITIVO_RE = re.compile(r"\b(?:p\s*\.?\s*q\s*\.?\s*m\b|per\s+questi\s+motivi|definitivamente\s+pronunciando)", re.I)
_CONDANNA_RE = re.compile(
    r"\bcondann\w*\s+(?P<chi>.{0,120}?)\s*(?P<verbo>\bal(?:la|le)?\s+(?:pagamento|rifusione|rimborso|refusione|spese)|"
    r"\ba\s+(?:pagare|rifondere|rimborsare|refondere|tale\s+titolo)|\bliquidand\w*)(?P<oggetto>.{0,220})",
    re.I | re.S,
)
_PROMOSSA_RE = re.compile(r"\b(?:promoss[ao]|propost[ao]|instaurat[ao]|ad\s+istanza)\b(?:\s+da)?", re.I)
_CONTRO_RE = re.compile(r"\b(?:contro|nei\s+confronti\s+d[ie]|avverso)\b", re.I)
_ACCOGLIE_RE = re.compile(r"\baccogli\w*\b", re.I)
_RIGETTA_RE = re.compile(r"\b(?:rigett\w*|respin\w*|dichiara\s+inammissibil\w*)\b", re.I)
_GENERICHE = frozenset({"parte", "parti", "sig", "sigg", "signor", "signora", "stesso", "stessa", "medesimo", "medesima",
                        "entrambe", "entrambi", "tutte", "tutti", "solido", "solidale", "solidalmente", "tra", "loro"})
_AGISCE = {"ricorrente", "attore", "appellante", "opponente", "reclamante"}
_SPESE_RE = re.compile(r"\bspese\b|\bcompens[io]\b|\bonorar[io]\b", re.I)
_STATO_RE = re.compile(
    r"\bin\s+favore\s+dello\s+stato\b|\ba\s+favore\s+dello\s+stato\b|\berario\b|\bart\.?\s*133\b.{0,40}\b115\b", re.I | re.S
)
_ANTISTATARIO_RE = re.compile(r"\bantistatari[oa]\b|\bdistrazion\w*\b|\bdistratt\w*\b", re.I)
_FRAZIONI = {"meta": 0.5, "un terzo": 1 / 3, "due terzi": 2 / 3, "un quarto": 0.25, "tre quarti": 0.75}
_COMPENSAZIONE_RE = re.compile(
    r"\bcompens\w*\s+(?:(?:le\s+)?spese\s+(?:di\s+lite\s+)?)?(?:per|nella\s+misura\s+(?:di|del))\s+"
    r"(?:la\s+|un[ao]?\s+)?(?P<quota>meta|un\s+terzo|due\s+terzi|un\s+quarto|tre\s+quarti|\d{1,2}\s*%)",
    re.I,
)
_INTERO_RE = re.compile(r"\b(?:per\s+l'?\s*intero|per\s+intero|restante|residu[ao])\b", re.I)


@dataclass(slots=True)
class CapoSpese:
    condannato: str = NON_DETERMINATO
    beneficiario: str = PARTE
    quota_dovuta: float = 1.0
    quota_da_verificare: bool = False
    motivi: list[str] = field(default_factory=list)

    @property
    def credito_dello_studio(self) -> bool:
        """Solo la condanna della controparte, a favore della parte o del difensore, è un credito da registrare."""
        return self.condannato == CONTROPARTE and self.beneficiario in {PARTE, ANTISTATARIO}


def _piano(testo: str) -> str:
    grezzo = unicodedata.normalize("NFKD", str(testo or "")).casefold()
    grezzo = "".join(c for c in grezzo if unicodedata.category(c) != "Mn")
    return re.sub(r"\s+", " ", grezzo.replace("’", "'"))


def _parole(nome: str) -> list[str]:
    return [p for p in re.findall(r"[a-z]{3,}", _piano(nome))]


def _ruolo(testo: str) -> str:
    """Il ruolo scritto per primo: «ROSSI MARIO, parte civile. … l'imputato» è la parte civile."""
    trovati = [(m.start(), ruolo) for radice, ruolo in _RUOLI.items()
               for m in [re.search(rf"\b{radice}\w*", testo)] if m]
    return min(trovati)[1] if trovati else ""


def _ruolo_del_cliente(testo: str, nomi: list[list[str]]) -> str:
    """Il ruolo scritto accanto al nome del cliente nell'intestazione («ROSSI MARIO, ricorrente»)."""
    intestazione = testo[:6000]
    for parole in nomi:
        for trovato in re.finditer(re.escape(parole[0]), intestazione):
            # Il nome può essere scritto in un ordine qualsiasi («ROBERTA MONTAGNESE»): la finestra parte prima.
            vicino = intestazione[trovato.start(): trovato.start() + 160]
            if all(p in intestazione[max(0, trovato.start() - 40): trovato.start() + 160] for p in parole):
                ruolo = _ruolo(vicino[:160])
                if ruolo:
                    return ruolo
                # «causa promossa da ROSSI MARIO contro …»: chi promuove agisce, chi è convenuto resiste.
                prima = intestazione[max(0, trovato.start() - 60): trovato.start()]
                lati = [(m.start(), "ricorrente") for m in _PROMOSSA_RE.finditer(prima)]
                lati += [(m.start(), "resistente") for m in _CONTRO_RE.finditer(prima)]
                if lati:
                    return max(lati)[1]
    return ""


def _chi_e(chi: str, nomi: list[list[str]], ruolo_cliente: str) -> str:
    if any(parole and all(p in chi for p in parole) for parole in nomi):
        return CLIENTE
    ruolo = _ruolo(chi)
    if ruolo and ruolo_cliente:
        if ruolo == ruolo_cliente:
            return CLIENTE
        if ruolo in _OPPOSTI.get(ruolo_cliente, set()):
            return CONTROPARTE
    if not ruolo and nomi and re.search(r"\b(?:ministero|amministrazione|inps|inail|comune|regione|agenzia|"
                                         r"azienda|universita|istituto|ente|societa|s\.?p\.?a|s\.?r\.?l|banca|ufficio|erario)\b", chi):
        # Un ente nominato come condannato, quando il cliente è una persona riconosciuta: è la controparte.
        return CONTROPARTE
    parole = [p for p in re.findall(r"[a-z]{3,}", chi) if p not in _GENERICHE]
    if not ruolo and nomi and parole:
        # Una parte nominata che non è il cliente («condanna Alfa alle spese»): è la parte avversa.
        return CONTROPARTE
    return NON_DETERMINATO


def _dall_esito(dispositivo: str, ruolo_cliente: str) -> str:
    """Senza parte nominata paga il soccombente (art. 91 c.p.c.): accoglimento o rigetto e lato del cliente."""
    accoglie, rigetta = bool(_ACCOGLIE_RE.search(dispositivo)), bool(_RIGETTA_RE.search(dispositivo))
    if rigetta and not accoglie:
        # Rigetto: paga chi ha agito. Senza il ruolo del cliente non si può dire chi sia.
        if not ruolo_cliente:
            return NON_DETERMINATO
        return CLIENTE if ruolo_cliente in _AGISCE else CONTROPARTE
    if ruolo_cliente and ruolo_cliente not in _AGISCE and accoglie:
        return CLIENTE
    # Nessun rigetto: la condanna senza parte nominata segue l'accoglimento della domanda del cliente.
    return CONTROPARTE


def capo_spese(testo: str, nomi_cliente: list[str]) -> CapoSpese:
    """Legge dal dispositivo la direzione della condanna alle spese."""
    piano = _piano(testo)
    inizio = 0
    for trovato in _DISPOSITIVO_RE.finditer(piano):
        inizio = trovato.start()
    dispositivo = piano[inizio:] if inizio else piano[-4000:]
    nomi = [p for p in (_parole(n) for n in nomi_cliente) if len(p) >= 2]
    esito = CapoSpese()
    ruolo_cliente = _ruolo_del_cliente(piano, nomi)
    # Ogni capo del dispositivo si legge da solo: «condanna il Ministero a costituire la Carta…; condanna parte
    # resistente alla rifusione delle spese…» sono due capi diversi.
    capi = [capo for capo in re.split(r";|\s-\s|\n", dispositivo) if "condann" in capo]
    condanne = (trovata for capo in capi for trovata in _CONDANNA_RE.finditer(capo))
    for condanna in condanne:
        verbo = condanna.group("verbo")
        if not (_SPESE_RE.search(verbo) or verbo.lower().startswith("liquid") or "titolo" in verbo.lower()
                or _SPESE_RE.search(condanna.group("oggetto"))):
            continue
        chi = condanna.group("chi").strip()
        esito.condannato = _chi_e(chi, nomi, ruolo_cliente) if chi else _dall_esito(dispositivo, ruolo_cliente)
        esito.motivi.append(f"condanna alle spese: «{chi[:80]}»" if chi else
                            "condanna alle spese senza la parte nominata: lato dedotto dall'esito e dal ruolo del cliente")
        break
    else:
        if re.search(r"\bliquid\w*\b", dispositivo) and _ACCOGLIE_RE.search(dispositivo):
            # «accoglie il ricorso … e liquida in favore del procuratore antistatario»: la liquidazione segue
            # l'esito, come per la condanna senza parte nominata.
            esito.condannato = _dall_esito(dispositivo, ruolo_cliente)
            esito.motivi.append("condanna alle spese senza la parte nominata: lato dedotto dall'esito e dal ruolo del cliente")
        else:
            esito.motivi.append("nessuna condanna alle spese riconosciuta nel dispositivo")
    if _STATO_RE.search(dispositivo):
        esito.beneficiario = STATO
        esito.motivi.append("pagamento a favore dello Stato (art. 133 D.P.R. 115/2002)")
    elif _ANTISTATARIO_RE.search(dispositivo):
        esito.beneficiario = ANTISTATARIO
        esito.motivi.append("distrazione a favore del difensore antistatario (art. 93 c.p.c.)")
    compensazione = _COMPENSAZIONE_RE.search(dispositivo)
    if compensazione:
        quota = compensazione.group("quota").strip()
        compensata = float(quota.rstrip("% ")) / 100 if quota.endswith("%") else _FRAZIONI.get(re.sub(r"\s+", " ", quota), 0.0)
        if 0 < compensata < 1:
            if _INTERO_RE.search(dispositivo[compensazione.start():]) or _INTERO_RE.search(dispositivo[:compensazione.start()][-300:]):
                esito.quota_dovuta = round(1 - compensata, 4)
                esito.motivi.append(f"spese compensate per {quota}: dovuta la quota residua (art. 92 c.p.c.)")
            else:
                esito.quota_da_verificare = True
                esito.motivi.append(f"spese compensate per {quota}: verificare se l'importo è già la quota residua")
    return esito


__all__ = ["ANTISTATARIO", "CLIENTE", "CONTROPARTE", "NON_DETERMINATO", "PARTE", "STATO", "CapoSpese", "capo_spese"]
