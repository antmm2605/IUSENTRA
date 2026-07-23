"""Libreria prompt "LegalSkills Italia": 26 aree del diritto, prompt in più forme.

Catalogo versionato e read-only di prompt operativi per la prassi forense
italiana. Ogni voce dichiara la propria base normativa (principio delle
fonti certe); i prompt composti impongono sempre la revisione
dell'avvocato e vietano l'invenzione di norme o precedenti.
"""

from .composer import FORME, componi_testo, forme_public, titolo_prompt
from .library import CATALOG_DIR, LegalPromptLibrary, get_prompt_library
from .models import AreaPrompt, VocePrompt

__all__ = [
    "AreaPrompt",
    "CATALOG_DIR",
    "FORME",
    "LegalPromptLibrary",
    "VocePrompt",
    "componi_testo",
    "forme_public",
    "get_prompt_library",
    "titolo_prompt",
]
