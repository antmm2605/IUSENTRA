"""Prompt specializzati per modalita' operative."""

from __future__ import annotations


def prompt_for_mode(mode: str) -> str:
    clean_mode = " ".join(str(mode or "").split()).strip().lower()
    if clean_mode == "ricerca_giurisprudenza":
        return "Privilegia precedenti verificati, massime e principio di diritto."
    if clean_mode == "controllo_conformita":
        return "Evidenzia criticita', requisiti mancanti e passo successivo minimo."
    if clean_mode == "timeline_pratica":
        return "Ordina i fatti per sequenza temporale e separa eventi futuri da eventi gia' avvenuti."
    return "Rispondi in modo operativo, chiaro e ancorato alle fonti disponibili."
