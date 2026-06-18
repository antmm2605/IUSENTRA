"""PDF helpers for fascicolo signature and attestazione routes."""

from __future__ import annotations

import io


def attestazione_conformita_pdf(data_raw: bytes, testo: str) -> bytes:
    """Append or stamp a visible attestazione di conformità on a PDF payload."""
    try:
        from pyhanko.pdf_utils.incremental_writer import IncrementalPdfFileWriter
        from pyhanko.pdf_utils.reader import PdfFileReader
        from pyhanko.stamp import TextStamp, TextStampStyle

        buf_in = io.BytesIO(data_raw)
        PdfFileReader(buf_in)
        writer = IncrementalPdfFileWriter(buf_in)
        style = TextStampStyle(stamp_text=testo, background_opacity=0.85)
        stamp = TextStamp(
            writer=writer,
            style=style,
            dest_page=0,
            x=20,
            y=20,
            width=350,
            height=65,
        )
        stamp.apply()

        buf_out = io.BytesIO()
        writer.write(buf_out)
        buf_out.seek(0)
        return buf_out.read()
    except Exception:
        import reportlab.lib.pagesizes as pagesizes
        from reportlab.pdfgen import canvas as rlcanvas

        buf_att = io.BytesIO()
        canvas = rlcanvas.Canvas(buf_att, pagesize=pagesizes.A4)
        canvas.setFont("Helvetica-Bold", 11)
        canvas.drawString(50, 780, "ATTESTAZIONE DI CONFORMITÀ")
        canvas.setFont("Helvetica", 10)
        for index, riga in enumerate(testo.split("\n")):
            canvas.drawString(50, 760 - index * 18, riga)
        canvas.save()
        buf_att.seek(0)
        try:
            return data_raw + buf_att.read()
        except Exception:
            return data_raw
