"""Dalle parti lette negli atti alle parti del fascicolo: chi è già in anagrafica, chi manca.

Le parti arrivano dall'archivio delle letture (categoria «parte», vedi
`estrazione_parti`). Qui si decide, senza leggere nulla:

- **che soggetto è**: persona fisica, persona giuridica (partita IVA, forma
  societaria) o pubblica amministrazione (Ministeri, Agenzie, enti pubblici,
  Avvocatura dello Stato, art. 1 R.D. 1611/1933);
- **cognome e nome**: con un codice fiscale valido le prime sei lettere dicono
  quale parola è il cognome (D.M. 23/12/1976); senza, il nome resta come è
  scritto nell'atto, tutto nel cognome, per non invertire nulla;
- **se è già nel fascicolo o è il cliente**: stesso codice fiscale, o stesso
  nome normalizzato;
- **il ruolo processuale** nell'anagrafica dei soggetti.

Entra da sola in anagrafica solo la parte **certa**: lato riconosciuto dal
difensore dello studio o dal nome del cliente e fatto verificato (codice
fiscale valido o difensore della controparte letto nell'epigrafe). Le altre
restano proposte nel riquadro «Parti lette dagli atti».
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Iterable

RUOLI_CERTI = ("assistito", "controparte", "difensore_controparte")
RUOLI_LETTI = RUOLI_CERTI + ("testimone", "ctu", "parte")
ETICHETTE_RUOLO = {
    "assistito": "Assistito",
    "controparte": "Controparte",
    "difensore_controparte": "Difensore della controparte",
    "testimone": "Testimone",
    "ctu": "Consulente tecnico d'ufficio",
    "parte": "Parte (lato da confermare)",
}
# Il ruolo dell'anagrafica soggetti (pct.soggetti.RuoloSoggetto) per ogni ruolo letto.
RUOLO_SOGGETTO = {
    "assistito": "ASSISTITO",
    "controparte": "CONTROPARTE",
    "difensore_controparte": "DIFENSORE_CONTROPARTE",
    "testimone": "TESTIMONE",
    "ctu": "PERITO_CTU",
    "parte": "ALTRO",
}
_PA = re.compile(
    r"\b(?:ministero|ministro|agenzia|comune|regione|provincia|citt[aà]\s+metropolitana|inps|inail|istituto\s+nazionale|"
    r"ufficio\s+scolastico|azienda\s+sanitaria|asl|asp|universit[aà]|prefettura|questura|avvocatura|presidenza\s+del\s+consiglio|"
    r"amministrazione|autorit[aà])\b",
    re.IGNORECASE,
)
_SOCIETA = re.compile(r"\b(?:s\.?\s*r\.?\s*l\.?s?|s\.?\s*p\.?\s*a\.?|s\.?\s*a\.?\s*s\.?|s\.?\s*n\.?\s*c\.?|soc\.?\s*coop|societ[aà]|consorzio|fondazione|associazione|condominio)\b", re.IGNORECASE)


def semplice(testo: Any) -> str:
    base = unicodedata.normalize("NFKD", str(testo or "")).encode("ascii", "ignore").decode().casefold()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", base).split())


def _parole(testo: str) -> frozenset[str]:
    return frozenset(semplice(testo).split())


def stesso_nome(uno: Any, altro: Any) -> bool:
    """Stesse parole in qualsiasi ordine: «Rossi Mario» e «Mario Rossi» sono la stessa persona."""
    a, b = _parole(str(uno or "")), _parole(str(altro or ""))
    return bool(a) and a == b


def tipo_soggetto(nome: str, codice_fiscale: str = "", ruolo: str = "") -> str:
    """Il valore di pct.soggetti.TipoSoggetto per la parte letta."""
    if _PA.search(nome):
        return "PUBBLICA_AMMINISTRAZIONE"
    if _SOCIETA.search(nome) or re.fullmatch(r"\d{11}", str(codice_fiscale or "")):
        return "PERSONA_GIURIDICA"
    if ruolo in {"difensore_controparte", "ctu"}:
        return "PROFESSIONISTA"
    return "PERSONA_FISICA"


def cognome_e_nome(nome_letto: str, codice_fiscale: str = "") -> tuple[str, str]:
    """(cognome, nome): dal codice fiscale valido, altrimenti il nome resta com'è scritto."""
    from pct.codice_fiscale import _codice_nome

    parole = str(nome_letto or "").split()
    cf = re.sub(r"\s+", "", str(codice_fiscale or "")).upper()
    if len(parole) >= 2 and re.fullmatch(r"[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]", cf):
        for taglio in range(1, len(parole)):
            for cognome, nome in ((parole[:taglio], parole[taglio:]), (parole[taglio:], parole[:taglio])):
                if _codice_nome(" ".join(cognome)) == cf[:3] and _codice_nome(" ".join(nome), nome=True) == cf[3:6]:
                    return " ".join(cognome), " ".join(nome)
    return " ".join(parole), ""


@dataclass
class ParteDelFascicolo:
    """Una parte letta, aggregata su tutti i documenti che la nominano."""

    nome: str
    ruolo: str
    codice_fiscale: str = ""
    codice_fiscale_valido: bool = False
    difensore: str = ""
    posizione: str = ""
    verifica: str = "plausibile"
    fatti: list[str] = field(default_factory=list)
    oggetti: list[str] = field(default_factory=list)
    citazione: str = ""
    # calcolati confrontando con il fascicolo
    e_il_cliente: bool = False
    gia_presente: bool = False
    id_soggetto: str = ""

    @property
    def certa(self) -> bool:
        return self.ruolo in RUOLI_CERTI and self.verifica in {"verificata", "corretta"}

    def to_dict(self) -> dict[str, Any]:
        return {
            "nome": self.nome, "ruolo": self.ruolo, "ruoloLabel": ETICHETTE_RUOLO.get(self.ruolo, self.ruolo),
            "codiceFiscale": self.codice_fiscale, "codiceFiscaleValido": self.codice_fiscale_valido,
            "difensore": self.difensore, "posizione": self.posizione, "verifica": self.verifica,
            "certa": self.certa, "eIlCliente": self.e_il_cliente, "giaPresente": self.gia_presente,
            "idSoggetto": self.id_soggetto, "documenti": len(self.oggetti), "citazione": self.citazione[:240],
            "fatti": list(self.fatti), "tipoSoggetto": tipo_soggetto(self.nome, self.codice_fiscale, self.ruolo),
        }


def _dettaglio(fatto: Any, codice: str) -> str:
    for prova in list(getattr(fatto, "prove", []) or []):
        if str(prova.get("codice") or "") == codice:
            return str(prova.get("dettaglio") or "")
    return ""


def parti_lette(fatti: Iterable[Any]) -> list[ParteDelFascicolo]:
    """Le parti dell'archivio, una voce per persona e ruolo, la lettura più solida per prima."""
    voci: dict[tuple[str, str], ParteDelFascicolo] = {}
    for fatto in fatti:
        if str(getattr(fatto, "categoria", "")) != "parte":
            continue
        verifica = str(getattr(fatto, "verifica", "") or "")
        if verifica in {"respinta", "ignorata"}:
            continue
        ruolo = str(getattr(fatto, "campo", "") or "")
        nome = " ".join(str(getattr(fatto, "valore", "") or "").split())
        if ruolo not in RUOLI_LETTI or not nome:
            continue
        cf_grezzo = str(getattr(fatto, "valore_letto", "") or "")
        cf = cf_grezzo if re.fullmatch(r"[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]|\d{11}", cf_grezzo) else ""
        chiave = (" ".join(sorted(_parole(nome))), ruolo)
        voce = voci.get(chiave)
        if voce is None:
            voce = voci[chiave] = ParteDelFascicolo(nome=nome, ruolo=ruolo, citazione=str(getattr(fatto, "contesto", "") or ""))
        if cf and not voce.codice_fiscale:
            voce.codice_fiscale = cf
            voce.codice_fiscale_valido = "carattere di controllo valido" in _dettaglio(fatto, "codice_fiscale") or len(cf) == 11
        voce.difensore = voce.difensore or _dettaglio(fatto, "difensore")
        voce.posizione = voce.posizione or _dettaglio(fatto, "posizione")
        if verifica in {"verificata", "corretta"}:
            voce.verifica = verifica
        fatto_id = str(getattr(fatto, "id", "") or "")
        if fatto_id and fatto_id not in voce.fatti:
            voce.fatti.append(fatto_id)
        oggetto = str(getattr(fatto, "oggetto_id", "") or "")
        if oggetto and oggetto not in voce.oggetti:
            voce.oggetti.append(oggetto)
    # Una parte con il lato riconosciuto rende superflua la stessa persona letta «senza lato».
    certe = {" ".join(sorted(_parole(v.nome))) for v in voci.values() if v.ruolo != "parte"}
    elenco = [v for v in voci.values() if not (v.ruolo == "parte" and " ".join(sorted(_parole(v.nome))) in certe)]
    ordine = {ruolo: indice for indice, ruolo in enumerate(RUOLI_LETTI)}
    return sorted(elenco, key=lambda v: (ordine.get(v.ruolo, 9), 0 if v.certa else 1, v.nome))


def confronta_con_fascicolo(voci: list[ParteDelFascicolo], *, nome_cliente: str, parti_esistenti: Iterable[tuple[Any, Any]]) -> list[ParteDelFascicolo]:
    """Segna chi è il cliente e chi è già fra le parti del fascicolo (stesso codice fiscale o stesso nome)."""
    esistenti = list(parti_esistenti)
    for voce in voci:
        voce.e_il_cliente = voce.ruolo in {"assistito", "parte"} and stesso_nome(voce.nome, nome_cliente)
        for parte, soggetto in esistenti:
            cf = str(getattr(soggetto, "codice_fiscale", "") or getattr(soggetto, "partita_iva", "") or "").upper()
            if (voce.codice_fiscale and cf == voce.codice_fiscale) or stesso_nome(voce.nome, getattr(soggetto, "nome_completo", "")):
                voce.gia_presente = True
                voce.id_soggetto = str(getattr(soggetto, "id", "") or "")
                break
    return voci


__all__ = [
    "ETICHETTE_RUOLO", "RUOLI_CERTI", "RUOLI_LETTI", "RUOLO_SOGGETTO", "ParteDelFascicolo",
    "cognome_e_nome", "confronta_con_fascicolo", "parti_lette", "semplice", "stesso_nome", "tipo_soggetto",
]
