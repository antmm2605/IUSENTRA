"""Diagnosi e preparazione locale dei riquadri, prima della lettura dei dati.

Le sonde di orientamento localizzano il testo, non compilano l'anagrafica.
Le trasformazioni lavorano su copie e hanno una sequenza finita.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiquadroPreparato:
    immagine: object
    passaggi: tuple[str, ...]
    orientamento: int
    scala: float


def prepara_riquadro_identita(image) -> RiquadroPreparato:
    from PIL import Image
    from .geometria_identita import prepara_geometria_identita
    from .identita import _orientamento_riscontrato
    from .immagine import (
        diagnostica_zona_testo, passaggi_diagnosi_zona,
        prepara_zona_testo, scala_caratteri_zona,
    )

    geometry = prepara_geometria_identita(image)
    working = geometry.immagine
    steps = list(geometry.passaggi)
    try:
        angle = _orientamento_riscontrato(working)
        if angle:
            oriented = working.rotate(angle, expand=True)
            working.close()
            working = oriented
        steps.append(f'Analisi orientamento: {angle}°; originale invariato.')
        diagnosis = diagnostica_zona_testo(working)
        # Misura i caratteri prima dei trattamenti: il rumore accentuato non
        # può diventare una falsa misura che ordina ulteriore ingrandimento.
        try:
            scale = max(1.0, int(scala_caratteri_zona(working) * 4) / 4)
        except ImportError:
            scale = 1.0
            steps.append('Misura dei caratteri non disponibile: nessun ingrandimento arbitrario.')
        steps.append(f'Analisi luce e dettaglio: fondo {diagnosis.livello_sfondo}, '
                     f'escursione {diagnosis.escursione}, bordi {diagnosis.rapporto_bordi:.5f}.')
        for phase in passaggi_diagnosi_zona(diagnosis):
            before = diagnostica_zona_testo(working)
            candidate = prepara_zona_testo(working, phase)
            after = diagnostica_zona_testo(candidate.immagine)
            improved = (
                ((phase.scura or phase.illuminazione_irregolare)
                 and not after.scura and not after.illuminazione_irregolare)
                or ((phase.chiara or phase.basso_contrasto)
                    and after.escursione > before.escursione)
                or (phase.sfocata and after.rapporto_bordi > before.rapporto_bordi)
            ) and after.escursione > 0
            if improved:
                working.close()
                working = candidate.immagine
                steps.extend(candidate.passaggi)
            else:
                candidate.immagine.close()
                steps.append('Preparazione scartata: la misura dell’immagine non migliora.')
        if scale > 1.1:
            enlarged = working.resize((max(1, round(working.width * scale)),
                                       max(1, round(working.height * scale))), Image.Resampling.LANCZOS)
            working.close()
            working = enlarged
            steps.append(f'Ingrandimento misurato ×{scale:.2f} prima dell’OCR.')
        steps.append('Preparazione terminata; avvio OCR locale sui pixel preparati.')
        return RiquadroPreparato(working, tuple(steps), angle, scale)
    except Exception:
        working.close()
        raise
