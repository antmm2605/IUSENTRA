"""Processo amministrativo telematico: il deposito dal Formweb del Portale dell'Avvocato.

Dal 1° febbraio 2026 il canale ordinario del PAT è il Formweb del nuovo SIGA
(Portale dell'Avvocato, accesso SPID/CIE/CNS); la PEC con i moduli XFA resta
residuale. Il portale non ha un canale per programmi esterni: IUSENTRA prepara
dati, parti (foglio Excel ufficiale), file con nomi accettati dal portale e la
scheda da seguire nell'ordine del Formweb; dopo «Genera riepilogo» confronta le
impronte del riepilogo con i file del fascicolo. L'invio resta all'avvocato.
Base normativa: art. 136 c.p.a.; d.P.C.M. 40/2016; regole tecnico-operative
d.P.C.S. 2025; avviso Segretariato generale 28/01/2026 (priorità Formweb).
Analisi: ``docs/specs/ministero/PAT_FORMWEB_PORTALE_AVVOCATO_2026-09-25.md``.
"""

from . import catalogo, contributo, excel_parti, parti, regole, riepilogo, scheda
from .archivio import ArchivioPat

__all__ = ["ArchivioPat", "catalogo", "contributo", "excel_parti", "parti", "regole", "riepilogo", "scheda"]
