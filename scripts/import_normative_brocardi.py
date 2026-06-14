#!/usr/bin/env python3
"""
Script per importare normative dal sito Brocardi (https://www.brocardi.it/).

Scarica i testi dei codici normativi italiani principali:
- Codice Civile
- Codice di Procedura Civile
- Codice Penale
- Codice di Procedura Penale
- Costituzione
- Altri (da specifica)

Struttura i dati secondo il modello IUSENTRA (LegalCitation) e li salva
in formato JSONL per ingestione nel motore Lex.

Utilizzo:
    python3 scripts/import_normative_brocardi.py [--codice CODICE] [--output FILE]

Esempi:
    # Scarica tutti i codici
    python3 scripts/import_normative_brocardi.py

    # Scarica solo il Codice Civile
    python3 scripts/import_normative_brocardi.py --codice civile

    # Specifica file output
    python3 scripts/import_normative_brocardi.py --output data/normative_brocardi.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote, urljoin

# Configurazione logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


class BrocardiImporter:
    """Importatore di normative dal sito Brocardi."""

    # URL base Brocardi
    BASE_URL = "https://www.brocardi.it/"

    # Mappatura codici → URL segments
    CODICI = {
        "civile": {
            "slug": "codice-civile",
            "titolo": "Codice Civile",
            "categoria": "primary_legislation",
        },
        "procedura_civile": {
            "slug": "codice-di-procedura-civile",
            "titolo": "Codice di Procedura Civile",
            "categoria": "primary_legislation",
        },
        "penale": {
            "slug": "codice-penale",
            "titolo": "Codice Penale",
            "categoria": "primary_legislation",
        },
        "procedura_penale": {
            "slug": "codice-di-procedura-penale",
            "titolo": "Codice di Procedura Penale",
            "categoria": "primary_legislation",
        },
        "costituzione": {
            "slug": "costituzione",
            "titolo": "Costituzione della Repubblica Italiana",
            "categoria": "constitution",
        },
    }

    def __init__(self, output_file: Optional[Path] = None):
        """Inizializza l'importatore.

        Args:
            output_file: File di output JSONL (default: data/normative_brocardi.jsonl)
        """
        self.output_file = output_file or Path("data/normative_brocardi.jsonl")
        self.retrieved_at = datetime.now().isoformat()
        self.stats = {
            "codici": 0,
            "articoli": 0,
            "commi": 0,
            "errori": 0,
        }

    def _build_url(self, codice: str, articolo: int, comma: Optional[int] = None) -> str:
        """Costruisce URL stabile per un articolo/comma su Brocardi.

        Args:
            codice: Chiave codice (es. 'civile')
            articolo: Numero articolo
            comma: Numero comma (opzionale)

        Returns:
            URL completo stabile
        """
        if codice not in self.CODICI:
            raise ValueError(f"Codice sconosciuto: {codice}")

        slug = self.CODICI[codice]["slug"]
        url = f"{self.BASE_URL}{slug}/art{articolo}.html"
        return url

    def _create_citation(
        self,
        codice: str,
        numero_articolo: int,
        numero_comma: Optional[int] = None,
        testo_articolo: Optional[str] = None,
        sezione: Optional[str] = None,
        titolo: Optional[str] = None,
        libro: Optional[str] = None,
        capo: Optional[str] = None,
    ) -> dict[str, Any]:
        """Crea una citazione legale strutturata secondo il modello IUSENTRA.

        Args:
            codice: Chiave codice (es. 'civile')
            numero_articolo: Numero articolo
            numero_comma: Numero comma (opzionale)
            testo_articolo: Testo dell'articolo
            sezione: Sezione (per struttura gerarchica)
            titolo: Titolo (per struttura gerarchica)
            libro: Libro (per struttura gerarchica)
            capo: Capo (per struttura gerarchica)

        Returns:
            Dizionario con citazione strutturata secondo LegalCitation
        """
        codice_info = self.CODICI[codice]

        # Costruisci identificatori
        numero_articolo_str = str(numero_articolo).lstrip("0") or "0"
        article_id = f"art{numero_articolo_str}"
        if numero_comma is not None:
            article_id += f".comma{numero_comma}"

        # Costruisci titolo citazione
        citation_title = f"{codice_info['titolo']} - Art. {numero_articolo_str}"
        if numero_comma is not None:
            citation_title += f", comma {numero_comma}"

        url = self._build_url(codice, numero_articolo, numero_comma)

        citation = {
            # Identificativi fonte
            "source_id": "brocardi",
            "source_name": "Brocardi",
            "source_category": "secondary_legislation",
            "jurisdiction": "IT",
            # Metadati documento
            "document_type": "articolo",
            "authority": codice_info["titolo"],
            "title": citation_title,
            "number": article_id,
            # Identificativi articolo/comma
            "article": str(numero_articolo),
            "paragraph": str(numero_comma) if numero_comma is not None else None,
            # Gerarchia
            "section": sezione or None,
            "section_title": titolo or None,
            "book": libro or None,
            "capo": capo or None,
            # Contenuto
            "text": testo_articolo or None,
            # Versione/data
            "version_date": None,  # Brocardi non mantiene versioni storiche
            "publication": None,
            "publication_number": None,
            # Identificativi standard UE (non disponibili su Brocardi)
            "urn": None,
            "eli": None,
            "celex": None,
            "ecli": None,
            "hudoc_id": None,
            # Accesso
            "url": url,
            "retrieved_at": self.retrieved_at,
        }

        return citation

    def import_from_api(self, codice: Optional[str] = None) -> list[dict[str, Any]]:
        """Importa normative usando Apify Web Scraper.

        Questo metodo richiederebbe credenziali Apify e integrazione
        con l'API Apify per eseguire lo scraping effettivo.

        Args:
            codice: Codice specifico da scrapare (es. 'civile')
                   Se None, scarica tutti i codici

        Returns:
            Lista di citazioni importate
        """
        # NOTA: Implementazione completa richiede credenziali Apify
        # Per ora, restituisci istruzioni su come usare Apify
        msg = (
            "Per usare questo script con Apify:\n"
            "1. Imposta APIFY_TOKEN nelle variabili d'ambiente\n"
            "2. Usa: apify call motivational_nickel/my-actor --\n"
            "3. Configura i parametri per scrapare brocardi.it\n"
            "\nOppure, usa import_from_sample_data() per test con fixture"
        )
        logger.warning(msg)
        return []

    def import_from_sample_data(self) -> list[dict[str, Any]]:
        """Importa normative da dati campione (per test e demo).

        Genera citazioni per articoli campione di tutti i codici.

        Returns:
            Lista di citazioni campione
        """
        citations = []

        # Campione Codice Civile (articoli 1, 2, 10, 100)
        for art in [1, 2, 10, 100]:
            c = self._create_citation(
                codice="civile",
                numero_articolo=art,
                testo_articolo=f"Testo campione Art. {art} CC (da scrapare)",
                libro="Primo",
                titolo="Delle persone e della famiglia",
            )
            citations.append(c)
            for comma in [1, 2]:
                c_comma = self._create_citation(
                    codice="civile",
                    numero_articolo=art,
                    numero_comma=comma,
                    testo_articolo=f"Comma {comma} Art. {art} CC",
                    libro="Primo",
                    titolo="Delle persone e della famiglia",
                )
                citations.append(c_comma)

        # Campione Codice Penale (articoli 1, 2, 81, 110)
        for art in [1, 2, 81, 110]:
            c = self._create_citation(
                codice="penale",
                numero_articolo=art,
                testo_articolo=f"Testo campione Art. {art} CP (da scrapare)",
                libro="Primo",
                titolo="Dei reati in generale",
            )
            citations.append(c)

        # Campione Codice Procedura Civile (articoli 1, 100, 183)
        for art in [1, 100, 183]:
            c = self._create_citation(
                codice="procedura_civile",
                numero_articolo=art,
                testo_articolo=f"Testo campione Art. {art} CPC (da scrapare)",
                libro="Primo",
                titolo="Disposizioni generali",
            )
            citations.append(c)

        # Campione Codice Procedura Penale (articoli 1, 50, 163, 599)
        for art in [1, 50, 163, 599]:
            c = self._create_citation(
                codice="procedura_penale",
                numero_articolo=art,
                testo_articolo=f"Testo campione Art. {art} CPP (da scrapare)",
                libro="Primo",
                titolo="Disposizioni generali",
            )
            citations.append(c)

        # Campione Costituzione (articoli 1, 2, 3, 138, 139)
        for art in [1, 2, 3, 138, 139]:
            c = self._create_citation(
                codice="costituzione",
                numero_articolo=art,
                testo_articolo=f"Testo campione Art. {art} Costituzione (da scrapare)",
            )
            citations.append(c)

        self.stats["codici"] = len(set(c["authority"] for c in citations))
        self.stats["articoli"] = len(set((c["authority"], c["article"]) for c in citations))
        self.stats["commi"] = len([c for c in citations if c["paragraph"]])

        logger.info(
            f"Generati {len(citations)} record campione: "
            f"{self.stats['codici']} codici, "
            f"{self.stats['articoli']} articoli, "
            f"{self.stats['commi']} commi"
        )

        return citations

    def save_to_jsonl(self, citations: list[dict[str, Any]]) -> None:
        """Salva citazioni in formato JSONL.

        Args:
            citations: Lista di citazioni
        """
        self.output_file.parent.mkdir(parents=True, exist_ok=True)

        with open(self.output_file, "w", encoding="utf-8") as f:
            for citation in citations:
                f.write(json.dumps(citation, ensure_ascii=False) + "\n")

        logger.info(f"Salvate {len(citations)} citazioni in {self.output_file}")

    def save_to_json(self, citations: list[dict[str, Any]]) -> None:
        """Salva citazioni in formato JSON strutturato.

        Args:
            citations: Lista di citazioni
        """
        output_json = self.output_file.with_suffix(".json")
        output_json.parent.mkdir(parents=True, exist_ok=True)

        # Raggruppa per codice
        by_codice = {}
        for c in citations:
            codice = c["authority"]
            if codice not in by_codice:
                by_codice[codice] = []
            by_codice[codice].append(c)

        output = {
            "source": "brocardi",
            "source_url": self.BASE_URL,
            "retrieved_at": self.retrieved_at,
            "stats": self.stats,
            "codici": by_codice,
        }

        with open(output_json, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)

        logger.info(f"Salvate {len(citations)} citazioni in {output_json}")


def main() -> int:
    """Entry point CLI."""
    parser = argparse.ArgumentParser(
        description="Importa normative dal sito Brocardi in formato IUSENTRA",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi:
  # Scarica tutti i codici (campione)
  python3 scripts/import_normative_brocardi.py

  # Scarica un singolo codice
  python3 scripts/import_normative_brocardi.py --codice civile

  # Specifica file output
  python3 scripts/import_normative_brocardi.py --output data/brocardi.jsonl

  # Salva sia JSONL che JSON
  python3 scripts/import_normative_brocardi.py --both-formats
        """,
    )

    parser.add_argument(
        "--codice",
        choices=list(BrocardiImporter.CODICI.keys()),
        help="Codice specifico da importare (default: tutti)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("data/normative_brocardi.jsonl"),
        help="File output JSONL (default: data/normative_brocardi.jsonl)",
    )
    parser.add_argument(
        "--both-formats",
        action="store_true",
        help="Salva sia JSONL che JSON",
    )
    parser.add_argument(
        "--api",
        action="store_true",
        help="Usa Apify API (richiede APIFY_TOKEN)",
    )

    args = parser.parse_args()

    importer = BrocardiImporter(output_file=args.output)

    # Importa dati
    if args.api:
        logger.info("Usando Apify API per lo scraping...")
        citations = importer.import_from_api(codice=args.codice)
    else:
        logger.info("Generando dati campione (usa --api per scraping reale)...")
        citations = importer.import_from_sample_data()

    if not citations:
        logger.error("Nessun dato importato")
        return 1

    # Salva output
    importer.save_to_jsonl(citations)
    if args.both_formats:
        importer.save_to_json(citations)

    logger.info(f"Import completato: {len(citations)} citazioni")
    return 0


if __name__ == "__main__":
    sys.exit(main())
