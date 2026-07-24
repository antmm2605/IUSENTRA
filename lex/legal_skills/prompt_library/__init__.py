"""Libreria prompt "LegalSkills Italia": 26 aree del diritto, prompt in più forme.

Catalogo versionato e read-only di prompt operativi per la prassi forense
italiana. Ogni voce dichiara la propria base normativa (principio delle
fonti certe); i prompt composti impongono sempre la revisione
dell'avvocato e vietano l'invenzione di norme o precedenti.
"""

from .case_context import ContestoFascicolo
from .composer import FORME, componi_testo, forme_public, titolo_prompt
from .library import CATALOG_DIR, LegalPromptLibrary, get_prompt_library
from .models import AreaPrompt, VocePrompt
from .pathway_progress import PathwayProgressStore
from .pathways import PATHWAYS_DIR, PassoPercorso, PathwayCatalog, Percorso, get_pathway_catalog
from .profile_matching import aree_preferite_da_profilo
from .reference_watch import estrai_estremi, revisioni_da_normative, voci_da_rivedere
from .runner import PROMPT_PACK_ID, prepara_esecuzione_prompt

__all__ = [
    "AreaPrompt",
    "CATALOG_DIR",
    "ContestoFascicolo",
    "FORME",
    "LegalPromptLibrary",
    "PATHWAYS_DIR",
    "PROMPT_PACK_ID",
    "PassoPercorso",
    "PathwayCatalog",
    "PathwayProgressStore",
    "Percorso",
    "VocePrompt",
    "aree_preferite_da_profilo",
    "estrai_estremi",
    "get_pathway_catalog",
    "prepara_esecuzione_prompt",
    "revisioni_da_normative",
    "voci_da_rivedere",
    "componi_testo",
    "forme_public",
    "get_prompt_library",
    "titolo_prompt",
]
