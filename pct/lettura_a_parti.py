"""Lettura a parti per l'AI locale: nessun documento letto a metà.

Il modello locale ha un contesto fisso (`lex.settings.LexGenerationSettings.num_ctx`): oltre
quel limite Ollama taglia il prompt senza dirlo. Qui il testo si divide in parti contigue,
senza perdere caratteri, ciascuna entro il budget del contesto; ogni parte viene letta dal
modello e i risultati si uniscono nell'ordine, con la parte di provenienza. Se una parte
non si legge, l'esito lo dichiara («letto in parte», con le parti mancanti) invece di
presentare il documento come letto per intero.

Base: art. 3 D.M. 44/2011 e art. 20 CAD (integrità del documento informatico): ciò che si
afferma letto deve essere stato letto davvero.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Sequence

# Stima prudente per l'italiano: circa 3 caratteri per token (le stime a 4 sottostimano).
CARATTERI_PER_TOKEN = 3


def budget_caratteri(*, riserva_token: int = 0) -> int:
    """Caratteri che stanno nel contesto del modello, tolta la risposta e la parte fissa del prompt."""
    from lex.settings import lex_generation_settings

    impostazioni = lex_generation_settings()
    return max((impostazioni.input_budget_tokens - max(riserva_token, 0)) * CARATTERI_PER_TOKEN, 1200)


def sta_nel_contesto(testo: str, *, budget: int) -> bool:
    return len(str(testo or "")) <= budget


def dividi_senza_perdite(testo: str, *, massimo: int) -> list[str]:
    """Parti contigue entro `massimo` caratteri, su confini leggibili; unite ridanno il testo."""
    from lex.retrieval.chunking import bounded_text_chunks

    return list(bounded_text_chunks(str(testo or ""), max_chars=max(int(massimo), 1)))


def gruppi_entro_budget(blocchi: Sequence[str], *, budget: int, separatore: str = "\n\n---\n\n") -> list[str]:
    """Raggruppa blocchi contigui finché stanno nel budget; un blocco troppo grande si divide in parti."""
    gruppi: list[str] = []
    corrente = ""
    for blocco in blocchi:
        for pezzo in dividi_senza_perdite(blocco, massimo=budget) if len(blocco) > budget else [blocco]:
            candidato = f"{corrente}{separatore}{pezzo}" if corrente else pezzo
            if corrente and len(candidato) > budget:
                gruppi.append(corrente)
                corrente = pezzo
            else:
                corrente = candidato
    if corrente:
        gruppi.append(corrente)
    return gruppi


@dataclass
class EsitoLettura:
    risultati: list[str] = field(default_factory=list)
    totali: int = 0
    mancanti: list[int] = field(default_factory=list)
    errori: list[str] = field(default_factory=list)

    @property
    def completo(self) -> bool:
        return self.totali > 0 and not self.mancanti

    def nota(self) -> str:
        if self.totali <= 1 and not self.mancanti:
            return ""
        if not self.mancanti:
            return f"Contenuto letto per intero in {self.totali} parti."
        elenco = ", ".join(str(numero) for numero in self.mancanti)
        return (f"Contenuto letto in parte: {self.totali - len(self.mancanti)} parti su {self.totali}; "
                f"non lette le parti {elenco}.")


def leggi_a_parti(parti: Sequence[str], leggi: Callable[[str, int, int], str]) -> EsitoLettura:
    """Legge ogni parte con `leggi(parte, numero, totale)`; una parte che fallisce resta fra le mancanti."""
    esito = EsitoLettura(totali=len(parti))
    for numero, parte in enumerate(parti, start=1):
        try:
            risultato = str(leggi(parte, numero, len(parti)) or "").strip()
        except Exception as exc:  # una parte non letta non ferma le altre
            esito.mancanti.append(numero)
            esito.errori.append(f"parte {numero}: {type(exc).__name__}")
            continue
        esito.risultati.append(f"[Parte {numero} di {len(parti)}]\n{risultato}" if len(parti) > 1 else risultato)
    return esito


__all__ = [
    "CARATTERI_PER_TOKEN", "EsitoLettura", "budget_caratteri", "dividi_senza_perdite", "gruppi_entro_budget",
    "leggi_a_parti", "sta_nel_contesto",
]
