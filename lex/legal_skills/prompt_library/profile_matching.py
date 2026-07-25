"""Adattamento della libreria prompt al profilo dello studio.

Traduce le aree di attività dichiarate nel ``PracticeProfile`` (testo
libero inserito dall'avvocato nel cold start Legal Skills) negli
``area_id`` del catalogo LegalSkills Italia, così da proporre per prime
le aree effettivamente praticate dallo studio.
"""

from __future__ import annotations

import unicodedata

# Parole chiave (minuscole, senza accenti) → area del catalogo.
# L'ordine di dichiarazione è irrilevante: conta la corrispondenza.
_SINONIMI_AREA: dict[str, tuple[str, ...]] = {
    "civile": ("civile", "contratti", "obbligazioni", "responsabilita civile", "risarcimento"),
    "penale": ("penale", "difesa penale"),
    "lavoro": ("lavoro", "giuslavoristico", "licenziament", "previdenza"),
    "famiglia": ("famiglia", "separazion", "divorz", "minori"),
    "successioni": ("succession", "eredita", "testament", "donazion"),
    "tributario": ("tributario", "fiscale", "tribut", "imposte"),
    "immobiliare": ("immobiliare", "real estate", "compravendit"),
    "amministrativo": ("amministrativo", "appalt", "tar", "pubblica amministrazione"),
    "privacy": ("privacy", "gdpr", "protezione dati", "dati personali"),
    "societario": ("societario", "commerciale", "societa", "impresa", "m&a"),
    "crisi_impresa": ("crisi", "fallimentare", "insolvenza", "concordat", "ristrutturazion"),
    "bancario": ("bancario", "banca", "finanziario", "mutui", "usura"),
    "assicurativo": ("assicurativo", "assicurazion", "sinistri", "polizze"),
    "consumatori": ("consumator", "consumo"),
    "condominio": ("condomini",),
    "locazioni": ("locazion", "affitt", "sfratt"),
    "recupero_crediti": ("recupero crediti", "esecuzion", "pignorament", "decreto ingiuntivo"),
    "circolazione_stradale": ("circolazione", "stradale", "infortunistica", "rc auto"),
    "responsabilita_medica": ("medica", "sanitaria", "malpractice", "sanitario"),
    "mediazione_adr": ("mediazione", "adr", "arbitrato", "negoziazione assistita"),
    "proprieta_intellettuale": ("proprieta intellettuale", "marchi", "brevetti", "diritto d'autore", "ip"),
    "nuove_tecnologie": ("tecnologie", "informatica", "digitale", "software", "e-commerce", "it"),
    "internazionale": ("internazionale", "unione europea", "cross-border"),
    "ambiente": ("ambiente", "ambientale"),
    "edilizia_urbanistica": ("edilizia", "urbanistica", "costruzioni"),
    "sportivo": ("sportivo", "sport"),
}


def _normalizza(testo: str) -> str:
    decomposto = unicodedata.normalize("NFKD", str(testo or "").lower())
    return " ".join("".join(ch for ch in decomposto if not unicodedata.combining(ch)).split())


def _corrisponde(chiave: str, testo: str, parole: list[str]) -> bool:
    """Le chiavi multi-parola cercano nel testo; le altre per parola intera.

    Il prefisso è ammesso solo per chiavi lunghe (radici come "licenziament"):
    le chiavi corte come "it" o "ip" esigono la parola esatta, altrimenti
    "diritto" attiverebbe l'area informatica.
    """
    if " " in chiave or "'" in chiave:
        return chiave in testo
    return any(parola == chiave or (len(chiave) >= 5 and parola.startswith(chiave)) for parola in parole)


def aree_preferite_da_profilo(practice_areas: list[str], aree_disponibili: set[str]) -> list[str]:
    """Restituisce gli area_id del catalogo che corrispondono al profilo studio.

    L'ordine segue quello di dichiarazione nel profilo; i termini che non
    trovano corrispondenza vengono ignorati senza errori (il profilo è
    testo libero).
    """
    preferite: list[str] = []
    for voce_profilo in practice_areas or []:
        testo = _normalizza(voce_profilo)
        if not testo:
            continue
        parole = testo.split()
        for area_id, chiavi in _SINONIMI_AREA.items():
            if area_id in preferite or area_id not in aree_disponibili:
                continue
            candidate = (area_id.replace("_", " "), *chiavi)
            if any(_corrisponde(chiave, testo, parole) for chiave in candidate):
                preferite.append(area_id)
    return preferite


__all__ = ["aree_preferite_da_profilo"]
