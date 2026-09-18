"""Il ciclo della lettura: si legge tutto una volta, poi ci si ferma e si aspetta.

Il funzionamento voluto, e l'unico che regge nel tempo:

1. i **due motori** — motore documenti e motore PEC — leggono tutti i fascicoli;
2. quello che leggono finisce nell'**archivio**, che registra ogni dato e
   **conferma** la lettura al motore;
3. a conferma avvenuta il ciclo **si ferma**: nessuno rilegge nulla;
4. il ciclo **si riattiva solo** quando arriva un documento nuovo, un documento
   del fascicolo cambia, oppure arriva una PEC nuova;
5. i motori scrivono, l'archivio conferma, e tutto si ferma di nuovo.

Il punto delicato è il quarto: **il ciclo non deve spezzarsi mai**. Se un
evento non arriva, se una lettura fallisce, se il registro non si apre per un
giro, il fascicolo non può restare fuori dal ciclo per sempre. Per questo lo
stato del ciclo è scritto nell'archivio (`letture_fascicoli`, per motore) e ha
tre forme sole: **fermo** (tutto letto e confermato, nulla da fare), **da
leggere** (un evento lo ha risvegliato, oppure non è mai stato letto),
**in errore** (l'ultimo giro non è riuscito: si riprova, e nel frattempo si
vede). Una riconciliazione periodica ricontrolla anche i fascicoli fermi, così
un evento perso non li lascia indietro.

Base normativa della tracciabilità: art. 3 D.M. 44/2011 e art. 20 CAD.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable

# Gli stati del ciclo, in italiano, come li vede l'avvocato.
FERMO = "fermo"
DA_LEGGERE = "da_leggere"
IN_ERRORE = "in_errore"
ETICHETTE: dict[str, str] = {
    FERMO: "tutto letto: il ciclo è fermo e riparte solo su un documento nuovo o una PEC nuova",
    DA_LEGGERE: "in attesa di lettura: i motori leggeranno al prossimo giro",
    IN_ERRORE: "l'ultimo giro non è riuscito: si riprova",
}
# Storico: il ricontrollo periodico riapriva i fascicoli fermi.
# Ora il controllo automatico resta fermo finché non cambia l'impronta viva
# dell'inventario; questa costante resta esportata solo per compatibilità.
RICONCILIAZIONE_ORE = 24
# Quanti giri si riprova un fascicolo in errore prima di dichiararlo tale nel pannello.
TENTATIVI_PRIMA_DI_DICHIARARE = 3


def _adesso() -> datetime:
    return datetime.now(timezone.utc)


def _quando(valore: Any) -> datetime | None:
    testo = str(valore or "").strip().replace("Z", "+00:00")
    if not testo:
        return None
    try:
        letto = datetime.fromisoformat(testo)
    except ValueError:
        return None
    return letto if letto.tzinfo else letto.replace(tzinfo=timezone.utc)


@dataclass(frozen=True, slots=True)
class StatoCiclo:
    """Dove sta il fascicolo nel ciclo, e perché."""

    stato: str
    motivo: str
    impronta: str = ""
    aggiornato_il: str = ""
    tentativi: int = 0

    @property
    def da_leggere(self) -> bool:
        return self.stato != FERMO

    @property
    def etichetta(self) -> str:
        return ETICHETTE.get(self.stato, self.stato)

    def to_dict(self) -> dict[str, Any]:
        return {
            "stato": self.stato, "etichetta": self.etichetta, "motivo": self.motivo,
            "impronta": self.impronta, "aggiornato_il": self.aggiornato_il, "tentativi": self.tentativi,
            "daLeggere": self.da_leggere,
        }


def stato_ciclo(
    riga: dict[str, Any] | None,
    *,
    versione_attesa: str,
    impronta_attesa: str = "",
    oggi: datetime | None = None,
    versione_compatibile: Callable[[str], bool] | None = None,
) -> StatoCiclo:
    """Lo stato del ciclo per un motore, dalla riga del registro.

    Nessuna riga significa «mai letto». Una versione diversa del motore riapre
    il ciclo solo se non è dichiarata compatibile con la lettura già registrata.
    Un'impronta diversa significa che il fascicolo è cambiato: documento o PEC
    nuovi/cambiati. A impronta invariata il ciclo resta fermo, senza scansioni
    periodiche massive.
    """
    if not riga:
        return StatoCiclo(DA_LEGGERE, "il fascicolo non è mai stato letto dai motori")
    stato_registrato = str(riga.get("stato") or "")
    versione = str(riga.get("versione_lettore") or "")
    impronta = str(riga.get("impronta") or "")
    aggiornato = str(riga.get("aggiornato_il") or "")
    tentativi = int(riga.get("tentativi") or 0)
    compatibile = bool(versione_compatibile and versione_compatibile(versione))
    if versione != versione_attesa and not compatibile:
        return StatoCiclo(DA_LEGGERE, "le regole del motore sono cambiate: si rilegge", impronta, aggiornato, tentativi)
    if stato_registrato == "errore":
        return StatoCiclo(IN_ERRORE, str((riga.get("esito") or {}).get("motivo") or "l'ultimo giro non è riuscito"), impronta, aggiornato, tentativi)
    if stato_registrato != "completa":
        return StatoCiclo(DA_LEGGERE, "la lettura precedente è rimasta parziale", impronta, aggiornato, tentativi)
    if impronta_attesa and impronta != impronta_attesa:
        return StatoCiclo(DA_LEGGERE, "il fascicolo è cambiato: documenti o PEC nuovi", impronta, aggiornato, tentativi)
    return StatoCiclo(FERMO, "tutto letto e confermato dall'archivio", impronta, aggiornato, tentativi)


__all__ = [
    "DA_LEGGERE", "ETICHETTE", "FERMO", "IN_ERRORE", "RICONCILIAZIONE_ORE",
    "TENTATIVI_PRIMA_DI_DICHIARARE", "StatoCiclo", "stato_ciclo",
]
