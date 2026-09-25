"""Processo penale telematico: il deposito tramite il Portale Deposito atti Penali (PDP).

Il PDP non ha un canale per programmi esterni: l'atto lo invia l'avvocato
dalla sua area riservata del PST (provvedimento DGSIA 11/07/2023 art. 4 e 7).
IUSENTRA prepara il deposito con il catalogo ufficiale degli atti, esegue in
anticipo i controlli del portale, registra ricevute e stati, importa gli
elenchi esportati dal PDP. Analisi completa:
``docs/specs/ministero/PDP_PORTALE_DEPOSITO_ATTI_PENALI_2026-09-25.md``.
"""

from . import calendario, catalogo, stati
from .archivio import ArchivioPenale
from .controlli import Richiesta, avviso_indagini_nei_titoli, controlla
from .controlli_file import FileDeposito

__all__ = [
    "ArchivioPenale", "FileDeposito", "Richiesta", "avviso_indagini_nei_titoli", "calendario", "catalogo",
    "controlla", "stati",
]
