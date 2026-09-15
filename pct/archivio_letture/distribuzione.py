"""La distribuzione: l'archivio dice a ogni presidio che cosa gli spetta.

Questa è la seconda gamba della catena. La prima porta i fatti nell'archivio;
qui l'archivio li **distribuisce**: per ogni presidio attivo sa quali categorie
e quali campi gli servono, gli offre solo i fatti che non ha ancora preso, e
quando il presidio conferma di averli scritti smette di offrirglieli.

Il registro dei presìdi qui sotto è la dichiarazione di chi consuma che cosa.
Un presidio nuovo si censisce aggiungendo una riga: senza riga non riceve
nulla, e questo è voluto — nessun dato raggiunge una superficie che non lo ha
dichiarato.

Nessun fatto viene consegnato se non è utile: si consegnano i fatti
`verificata` e `corretta` (il software li ha riscontrati, o l'avvocato li ha
corretti). I `plausibile` restano nel riquadro delle conferme finché l'avvocato
non decide: consegnarli sarebbe scrivere nello scadenziario un dato che nessuno
ha confermato.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

# I verdetti che autorizzano la consegna: il software li ha riscontrati, oppure
# l'avvocato li ha corretti. Un «plausibile» non si consegna: si chiede.
VERIFICHE_CONSEGNABILI = frozenset({"verificata", "corretta"})


@dataclass(frozen=True, slots=True)
class Presidio:
    """Un presidio che riceve fatti dall'archivio, con ciò che dichiara di usare.

    `modo` distingue due nature diverse, e la distinzione conta:

    - **scrive**: il presidio ha un proprio registro e ci scrive una riga nuova
      (una scadenza nello scadenziario, un appuntamento in agenda). Qui la
      consegna è un atto: l'archivio dà il fatto una volta sola, il presidio
      scrive e conferma con il riferimento della riga creata, e da quel momento
      non gli viene più riproposto. Senza questa contabilità nascerebbero
      doppioni a ogni giro.
    - **consulta**: il presidio non ha un registro proprio, mostra ciò che
      l'archivio contiene (presidio economico, documentale, notifiche, dati del
      fascicolo). Qui non c'è nulla da consegnare e nulla da duplicare: si
      legge l'archivio quando serve.
    """

    nome: str
    etichetta: str
    versione: str
    categorie: frozenset[str]
    campi: frozenset[str] = frozenset()
    descrizione: str = ""
    modo: str = "consulta"

    @property
    def scrive(self) -> bool:
        return self.modo == "scrive"

    def gli_serve(self, fatto: Any) -> bool:
        if str(getattr(fatto, "categoria", "")) not in self.categorie:
            return False
        if self.campi and str(getattr(fatto, "campo", "")) not in self.campi:
            return False
        return str(getattr(fatto, "verifica", "")) in VERIFICHE_CONSEGNABILI


# I presìdi censiti e ciò che ciascuno prende dall'archivio.
PRESIDI: tuple[Presidio, ...] = (
    Presidio(
        "scadenziario", "Scadenziario", "2026.09.16.v1",
        categorie=frozenset({"data"}), campi=frozenset({"termine", "costituzione"}),
        descrizione="i termini letti diventano scadenze da confermare",
        modo="scrive",
    ),
    Presidio(
        "agenda", "Agenda", "2026.09.16.v1",
        categorie=frozenset({"data"}), campi=frozenset({"udienza"}),
        descrizione="le udienze lette diventano appuntamenti",
        modo="scrive",
    ),
    Presidio(
        "presidio_notifiche", "Presidio notifiche", "2026.09.16.v1",
        categorie=frozenset({"prova_notifica"}),
        descrizione="relate, ricevute e atti notificati riconosciuti nel contenuto",
    ),
    Presidio(
        "presidio_economico", "Presidio economico", "2026.09.16.v1",
        categorie=frozenset({"importo"}),
        descrizione="contributo unificato, compenso liquidato, spese ed esborsi",
    ),
    Presidio(
        "intestazione_fascicolo", "Dati del fascicolo", "2026.09.16.v1",
        categorie=frozenset({"ruolo"}),
        descrizione="il numero di ruolo letto in un provvedimento",
    ),
    Presidio(
        "cronologia", "Lettura del fascicolo", "2026.09.16.v1",
        categorie=frozenset({"evento"}),
        descrizione="gli eventi processuali comunicati dalle PEC entrano in cronologia",
    ),
    Presidio(
        "presidio_documentale", "Presidio documentale", "2026.09.16.v1",
        categorie=frozenset({"data"}), campi=frozenset({"udienza", "termine", "costituzione", "provvedimento", "notifica"}),
        descrizione="udienze, termini e date dei provvedimenti nella regia del fascicolo",
    ),
)
PRESIDI_PER_NOME: dict[str, Presidio] = {presidio.nome: presidio for presidio in PRESIDI}


def presidio(nome: str) -> Presidio | None:
    return PRESIDI_PER_NOME.get(str(nome or "").strip())


def fatti_per_presidio(fatti: Iterable[Any], nome: str) -> list[Any]:
    """I fatti che quel presidio dichiara di usare, fra quelli dati."""
    voce = presidio(nome)
    if voce is None:
        return []
    return [fatto for fatto in fatti if voce.gli_serve(fatto)]


PRESIDI_CHE_SCRIVONO: tuple[Presidio, ...] = tuple(voce for voce in PRESIDI if voce.scrive)


def distribuzione_attesa(fatti: Iterable[Any]) -> dict[str, list[Any]]:
    """Per ogni presidio censito, i fatti che gli spettano."""
    elenco = list(fatti)
    return {voce.nome: [fatto for fatto in elenco if voce.gli_serve(fatto)] for voce in PRESIDI}


def categorie_senza_presidio(fatti: Iterable[Any]) -> dict[str, int]:
    """Le categorie prodotte dai motori che nessun presidio dichiara di usare.

    Serve a vedere subito uno spreco: un motore che legge un dato che non
    raggiunge nessuna superficie sta lavorando per niente.
    """
    coperte = {categoria for voce in PRESIDI for categoria in voce.categorie}
    senza: dict[str, int] = {}
    for fatto in fatti:
        categoria = str(getattr(fatto, "categoria", ""))
        if categoria and categoria not in coperte:
            senza[categoria] = senza.get(categoria, 0) + 1
    return senza


__all__ = [
    "PRESIDI", "PRESIDI_CHE_SCRIVONO", "PRESIDI_PER_NOME", "Presidio", "VERIFICHE_CONSEGNABILI",
    "categorie_senza_presidio", "distribuzione_attesa", "fatti_per_presidio", "presidio",
]
