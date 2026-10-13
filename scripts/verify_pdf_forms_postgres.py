"""Prova sintetica PDF/SQL in uno schema PostgreSQL temporaneo isolato.

Segue il profilo locale di collaudo già usato dalle verifiche PostgreSQL.
Non legge o modifica tabelle degli studi, documenti o registri audit esistenti.
"""
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from uuid import uuid4

import fitz
import psycopg2
from psycopg2 import sql
from psycopg2.extensions import make_dsn

from pct.fascicoli import GestioneFascicoli, TipoDocumento, TipoFascicolo
from pct.mediazione_documenti import contiene_modulo_pdf
from pct.storage_postgres import PostgresStudioDB
from web.services.pdf_overlay_editor import apply_pdf_overlays


def main():
    schema = "iusentra_pdf_forms_test_" + uuid4().hex
    dsn = make_dsn(host=os.getenv("AUDIT_POSTGRES_HOST", "audit-postgres"),
                   dbname=os.getenv("AUDIT_POSTGRES_DB", "iusentra_audit"),
                   user=os.getenv("AUDIT_POSTGRES_USER", "iusentra_audit"),
                   password=os.environ["AUDIT_POSTGRES_PASSWORD"], connect_timeout=10)
    admin = psycopg2.connect(dsn)
    admin.autocommit = True
    created, backend = False, None
    try:
        with admin.cursor() as cursor:
            cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        created = True
        backend = PostgresStudioDB(make_dsn(dsn, options="-csearch_path=" + schema))
        with TemporaryDirectory(prefix="iusentra-pdf-forms-test-") as folder:
            root = Path(folder)
            args = {"db_path": str(root / "unused.json"), "documents_dir": str(root / "documents"),
                    "archive_dir": str(root / "archive"), "studio_db": backend}
            manager = GestioneFascicoli(**args)
            case = manager.nuovo("Collaudo PDF isolato", TipoFascicolo.CIVILE)
            with fitz.open() as pdf:
                page = pdf.new_page()
                widget = fitz.Widget()
                widget.field_name = "controllo"
                widget.field_type = fitz.PDF_WIDGET_TYPE_TEXT
                widget.rect = fitz.Rect(40, 100, 300, 130)
                page.add_widget(widget)
                original = pdf.tobytes()
            assert contiene_modulo_pdf(original)
            document = manager.aggiungi_documento(case.id, "Modulo.pdf", TipoDocumento.ALLEGATO, original)
            repeated = manager.aggiungi_documento(case.id, "Modulo.pdf", TipoDocumento.ALLEGATO, original)
            assert repeated.id == document.id
            modified, count = apply_pdf_overlays(original, [{"type": "form", "values": {"controllo": "Attività verificata"}}])
            assert count == 1
            manager.sostituisci_documento(case.id, document.id, "Modulo.pdf", modified, caricato_da="collaudo")
            reloaded = GestioneFascicoli(**args).get(case.id)
            assert len(reloaded.documenti) == 1
            current = reloaded.documenti[0]
            assert len(current.versioni) == 1
            assert (root / "documents" / current.versioni[0].percorso).read_bytes() == original
            with fitz.open(root / "documents" / current.percorso) as pdf:
                assert next(pdf[0].widgets()).field_value == "Attività verificata"
            print("PostgreSQL: persistenza, deduplicazione, versione originale e campo compilato verificati nello schema isolato.")
    finally:
        if backend is not None:
            backend.raw_conn.close()
        if created:
            with admin.cursor() as cursor:
                cursor.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
        admin.close()


if __name__ == "__main__":
    main()
