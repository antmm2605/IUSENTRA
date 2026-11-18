"""I dati certi di una bozza: dalla Lettura del fascicolo, dal modello della causa e dalla scheda dello studio.

Nessun dato si deduce: l'ufficio, il ruolo, il giudice, le parti e le date sono quelli che la Lettura espone con
la loro fonte; quelli che mancano diventano segnaposti «[da completare: …]».
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from pct.fascicolo_lettura._testo import data_it, pulisci

from .modello import manca

_MINUSCOLE = {"di", "del", "della", "dello", "dei", "degli", "delle", "e", "in", "per", "a", "da", "al", "alla"}
_RE_AVVOCATURA = re.compile(r"avvocatura", re.IGNORECASE)


def ufficio_leggibile(nome: str) -> str:
    """«TRIBUNALE DI REGGIO DI CALABRIA» → «Tribunale di Reggio di Calabria»; i nomi già scritti restano."""
    nome = pulisci(nome)
    if not nome or not nome.isupper():
        return nome
    parole = nome.lower().split()
    return " ".join(p if i and p in _MINUSCOLE else p[:1].upper() + p[1:] for i, p in enumerate(parole))


def euro(valore: Decimal | float | None) -> str:
    if valore is None:
        return ""
    importo = Decimal(str(valore)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return "€ " + f"{importo:,.2f}".replace(",", "\x00").replace(".", ",").replace("\x00", ".")


def importo(testo: str) -> Decimal | None:
    """«2.400,00» → 2400.00; None se illeggibile."""
    pulito = pulisci(testo).replace("€", "").strip()
    if not re.fullmatch(r"\d{1,3}(?:\.\d{3})*(?:,\d{1,2})?|\d+(?:,\d{1,2})?", pulito):
        return None
    return Decimal(pulito.replace(".", "").replace(",", "."))


def percentuale(base: Decimal, aliquota: str) -> Decimal:
    return (base * Decimal(aliquota) / Decimal(100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


@dataclass
class Contesto:
    """Il fascicolo come lo vede chi scrive l'atto."""

    numero: str = ""
    titolo: str = ""
    ufficio: str = ""
    rg: str = ""
    giudice: str = ""
    sezione: str = ""
    tipo: str = ""
    cliente: str = ""
    controparte: str = ""
    difensori_controparte: list[str] = field(default_factory=list)
    avvocato: str = ""
    posizione: str = ""  # attiva | passiva | ""
    esecuzione: bool = False
    studio: dict[str, Any] = field(default_factory=dict)
    cliente_cf: str = ""

    @property
    def lavoro(self) -> bool:
        return self.tipo == "lavoro"

    @property
    def ufficio_o_manca(self) -> str:
        return self.ufficio or manca("ufficio giudiziario")

    @property
    def rg_o_manca(self) -> str:
        return self.rg or manca("numero di ruolo generale")

    @property
    def giudice_o_manca(self) -> str:
        return self.giudice or manca("giudice designato")

    @property
    def avvocato_o_manca(self) -> str:
        return self.avvocato or manca("nome del difensore")

    @property
    def controparte_o_manca(self) -> str:
        if self.controparte:
            return self.controparte
        accenno = self.controparte_nel_titolo
        return manca(f"controparte (nel titolo del fascicolo: «{accenno}»)" if accenno else "controparte")

    @property
    def controparte_nel_titolo(self) -> str:
        """La controparte come la scrive il titolo del fascicolo («Rossi c. MIM»): solo un'indicazione."""
        parti = re.split(r"\s+(?:c\.|contro|vs\.?|-)\s+", self.titolo, maxsplit=1, flags=re.IGNORECASE)
        return pulisci(parti[1]) if len(parti) == 2 else ""

    @property
    def controparte_e_avvocatura(self) -> bool:
        """La scheda indica come controparte l'Avvocatura dello Stato, che è il difensore, non la parte."""
        return bool(_RE_AVVOCATURA.search(self.controparte))

    @property
    def avvocatura(self) -> str:
        """L'Avvocatura dello Stato che difende l'amministrazione, se il fascicolo la indica (un solo nome)."""
        nomi = [n for n in self.difensori_controparte if _RE_AVVOCATURA.search(n)]
        if not nomi and _RE_AVVOCATURA.search(self.controparte):
            nomi = [self.controparte]
        normalizzati = {re.sub(r"\W+", " ", n.lower()).replace(" di stato ", " dello stato ").strip(): n for n in nomi}
        if len(normalizzati) != 1:
            return ""
        # Stesso ufficio scritto in due modi («Di Stato», «dello Stato»): si usa la denominazione dell'ufficio.
        nome = ufficio_leggibile(next(iter(normalizzati.values())))
        nome = re.sub(r"\b[Dd]i [Ss]tato\b", "dello Stato", nome)
        return re.sub(r"\bDello Stato\b", "dello Stato", nome)

    @property
    def pubblica_amministrazione(self) -> bool:
        return bool(self.avvocatura)

    @property
    def ruoli(self) -> tuple[str, str]:
        """(ruolo del cliente, ruolo della controparte) quando il rito e la posizione lo dicono con certezza."""
        if self.posizione == "attiva":
            if self.esecuzione:
                return "creditore procedente", "debitore esecutato"
            if self.lavoro:
                return "ricorrente", "resistente"
        if self.posizione == "passiva" and self.lavoro:
            return "resistente", "ricorrente"
        return "", ""

    @property
    def luogo(self) -> str:
        return pulisci(self.studio.get("citta")) or manca("luogo")

    def intestazione_ufficio(self) -> list[str]:
        righe = [f"# {self.ufficio_o_manca}"]
        if self.sezione:
            righe.append(f"## {self.sezione if self.sezione.lower().startswith('sezione') else 'Sezione ' + self.sezione}")
        elif self.lavoro:
            righe.append("## in funzione di Giudice del lavoro")
        righe.append(f"**R.G. n. {self.rg_o_manca}**")
        righe.append(f"*Giudice: {self.giudice_o_manca}*")
        return righe

    def parti(self) -> list[str]:
        ruolo_cliente, ruolo_controparte = self.ruoli
        cliente = self.cliente or manca("parte assistita")
        controparte = self.controparte_o_manca
        if self.controparte_e_avvocatura:
            accenno = self.controparte_nel_titolo
            controparte = manca("amministrazione convenuta" + (f" (nel titolo del fascicolo: «{accenno}»)" if accenno else ""))
        righe = [f"nell'interesse di **{cliente}**" + (f", {ruolo_cliente}" if ruolo_cliente else "")
                 + f", con il difensore {self.avvocato_o_manca}", "contro", f"**{controparte}**"
                 + (f", {ruolo_controparte}" if ruolo_controparte else "")]
        if self.avvocatura:
            righe[-1] += f", difesa dall'{self.avvocatura}"
        elif len(self.difensori_controparte) == 1:
            righe[-1] += f", con il difensore {self.difensori_controparte[0]}"
        return righe

    def firma(self) -> list[str]:
        return [f"{self.luogo}, {manca('data')}", self.avvocato_o_manca]


def _avvocato(intestazione: dict[str, Any], studio: dict[str, Any]) -> str:
    nome = pulisci(intestazione.get("avvocato")) or pulisci(studio.get("avvocato"))
    if not nome:
        return ""
    return nome if nome.lower().startswith("avv") else f"Avv. {nome}"


def contesto_della_lettura(lettura: dict[str, Any], *, studio: dict[str, Any] | None = None,
                           cliente_cf: str = "") -> Contesto:
    intestazione = lettura.get("intestazione") or {}
    ragionamento = lettura.get("ragionamento") or {}
    studio = dict(studio or {})
    parti = intestazione.get("parti") or {}
    difensori = [pulisci(n) for n in parti.get("difensore controparte") or [] if pulisci(n)]
    posizione_testo = pulisci(ragionamento.get("posizione")).lower()
    posizione = "attiva" if posizione_testo.startswith("il cliente agisce") else "passiva" if posizione_testo.startswith("il cliente resiste") else ""
    area = pulisci(intestazione.get("area")).lower()
    codice_oggetto = pulisci(intestazione.get("codice_oggetto_pst"))
    return Contesto(
        numero=pulisci(intestazione.get("numero")), titolo=pulisci(intestazione.get("titolo")),
        ufficio=ufficio_leggibile(intestazione.get("ufficio")),
        rg=pulisci(intestazione.get("rg")).removeprefix("RG ").removeprefix("R.G. "),
        giudice=pulisci(intestazione.get("giudice")), sezione=pulisci(intestazione.get("sezione")),
        tipo=pulisci(intestazione.get("tipo")).lower(), cliente=pulisci(intestazione.get("cliente")),
        controparte=pulisci(intestazione.get("controparte")), difensori_controparte=difensori,
        avvocato=_avvocato(intestazione, studio), posizione=posizione,
        esecuzione=area.startswith("esecuzion") or codice_oggetto.startswith("5"),
        studio=studio, cliente_cf=pulisci(cliente_cf),
    )


def udienza_sostituita(lettura: dict[str, Any], documento_id: str) -> str:
    """La data dell'udienza sostituita da note che lo stesso provvedimento fissa (una sola, altrimenti vuota)."""
    udienze = {u.get("data") for u in (lettura.get("ragionamento") or {}).get("udienze") or []
               if u.get("documento_id") == documento_id and "127-ter" in str(u.get("modalita") or "") and u.get("data")}
    return next(iter(udienze)) if len(udienze) == 1 else ""


def provvedimento(voce: dict[str, Any]) -> str:
    """«provvedimento del 04/11/2026 (2276942s.pdf)» dalla fonte letta della conclusione (senza articolo)."""
    letto = voce.get("letto") or {}
    data = data_it(letto.get("data"))
    nome = pulisci(letto.get("documento"))
    if data and nome:
        return f"provvedimento del {data} ({nome})"
    if data:
        return f"provvedimento del {data}"
    return f"provvedimento {manca('data del provvedimento')}" + (f" ({nome})" if nome else "")


__all__ = ["Contesto", "contesto_della_lettura", "euro", "importo", "percentuale", "provvedimento",
           "udienza_sostituita", "ufficio_leggibile"]
