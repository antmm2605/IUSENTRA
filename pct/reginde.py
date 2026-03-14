"""
Ricerca indirizzi PEC su ReGINde (Registro Generale degli Indirizzi Elettronici)
e ricerca uffici giudiziari nel Registro Ministero della Giustizia.
"""

import requests
from typing import Optional
from dataclasses import dataclass


@dataclass
class UfficioGiudiziario:
    """Rappresenta un ufficio giudiziario con il suo indirizzo PEC."""

    codice: str
    nome: str
    distretto: str
    pec: str
    tipo: str  # TRIBUNALE | CORTE_APPELLO | CORTE_CASSAZIONE | PROCURA


@dataclass
class SoggettoReGINde:
    """Soggetto censito nel ReGINde."""

    codice_fiscale: str
    nominativo: str
    pec: str
    tipo: str  # AVVOCATO | NOTAIO | CTU | PERITO


# Indirizzi PEC uffici giudiziari principali (campione dati)
UFFICI_GIUDIZIARI = {
    "TRIBUNALE_MILANO": UfficioGiudiziario(
        codice="0580010",
        nome="Tribunale di Milano",
        distretto="Milano",
        pec="tribunale.civile.milano@giustizia.it",
        tipo="TRIBUNALE",
    ),
    "TRIBUNALE_ROMA": UfficioGiudiziario(
        codice="0620010",
        nome="Tribunale di Roma",
        distretto="Roma",
        pec="tribunale.civile.roma@giustizia.it",
        tipo="TRIBUNALE",
    ),
    "TRIBUNALE_NAPOLI": UfficioGiudiziario(
        codice="0590010",
        nome="Tribunale di Napoli",
        distretto="Napoli",
        pec="tribunale.civile.napoli@giustizia.it",
        tipo="TRIBUNALE",
    ),
    "TRIBUNALE_TORINO": UfficioGiudiziario(
        codice="0530010",
        nome="Tribunale di Torino",
        distretto="Torino",
        pec="tribunale.civile.torino@giustizia.it",
        tipo="TRIBUNALE",
    ),
}


class ClientReGINde:
    """
    Client per la ricerca nel ReGINde e nel registro uffici giudiziari.

    Il ReGINde è il registro pubblico che contiene gli indirizzi PEC
    di avvocati, notai, CTU e altri soggetti abilitati al PCT.
    """

    REGINDE_BASE_URL = "https://pst.giustizia.it/PST/it/pst_1_6.wp"

    def __init__(self, session: Optional[requests.Session] = None):
        self.session = session or requests.Session()
        self.session.headers.update({"User-Agent": "PCT-Client/1.0"})

    def cerca_avvocato_cf(self, codice_fiscale: str) -> Optional[SoggettoReGINde]:
        """
        Cerca un avvocato nel ReGINde per codice fiscale.

        Args:
            codice_fiscale: Codice fiscale dell'avvocato

        Returns:
            Soggetto trovato o None
        """
        # Integrazione con API ReGINde del Ministero della Giustizia
        # Nota: richiede autenticazione al PST
        try:
            params = {"cf": codice_fiscale, "tipo": "AVVOCATO"}
            resp = self.session.get(self.REGINDE_BASE_URL, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()
            if data.get("risultati"):
                r = data["risultati"][0]
                return SoggettoReGINde(
                    codice_fiscale=r["cf"],
                    nominativo=r["nominativo"],
                    pec=r["pec"],
                    tipo="AVVOCATO",
                )
        except (requests.RequestException, KeyError, ValueError):
            pass
        return None

    def cerca_ufficio_giudiziario(self, nome: str) -> Optional[UfficioGiudiziario]:
        """
        Cerca un ufficio giudiziario per nome.

        Args:
            nome: Nome del tribunale (es. "MILANO", "ROMA")

        Returns:
            Ufficio giudiziario trovato o None
        """
        chiave = f"TRIBUNALE_{nome.upper()}"
        return UFFICI_GIUDIZIARI.get(chiave)

    def ottieni_pec_ufficio(self, codice_ufficio: str) -> Optional[str]:
        """
        Restituisce l'indirizzo PEC di un ufficio giudiziario dato il codice.

        Args:
            codice_ufficio: Codice identificativo dell'ufficio

        Returns:
            Indirizzo PEC o None
        """
        for ufficio in UFFICI_GIUDIZIARI.values():
            if ufficio.codice == codice_ufficio:
                return ufficio.pec
        return None

    def elenca_uffici(self, distretto: Optional[str] = None) -> list:
        """
        Elenca gli uffici giudiziari disponibili.

        Args:
            distretto: Filtra per distretto (opzionale)

        Returns:
            Lista di uffici giudiziari
        """
        uffici = list(UFFICI_GIUDIZIARI.values())
        if distretto:
            uffici = [u for u in uffici if u.distretto.upper() == distretto.upper()]
        return uffici
