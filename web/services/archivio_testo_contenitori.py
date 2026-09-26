"""Lettura dei formati fisici per i due motori dell'archivio, fuori dalle GET.

Riusa estrazione ZIP protetta, lettore CAdES e OCR locali. Nessuna lettura
binaria approssimativa viene usata come prova del contenuto.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path

@dataclass
class TestoContenitore:
    testo: str = ""
    origine: str = "nativo"
    errori: list[str] = field(default_factory=list)


def estrai_contenuto(data: bytes, nome: str, *, profondita: int = 0) -> TestoContenitore:
    if not data:
        return TestoContenitore(errori=["File senza contenuto disponibile nell’archivio."])
    if profondita > 4:
        return TestoContenitore(errori=["Contenitori annidati oltre il limite di lettura sicura."])
    head = data[:256].lstrip()
    ext = Path(nome).suffix.lower()
    if head.startswith(b"%PDF"):
        from legal_ocr.motore.testo import testo_da_pdf
        try:
            pagine = testo_da_pdf(data, max_pagine=0)
            if not pagine:
                return TestoContenitore(errori=["PDF incompleto o privo di pagine: occorre recuperare la copia integrale dalla fonte originale."])
            # Testo e tabelle: ogni tabella disegnata segue la sua pagina come blocco.
            testi, primo = [], 1
            for pagina in pagine:
                if pagina.testo.strip():
                    testi.append(pagina.testo_con_tabelle(primo=primo))
                    primo += len(pagina.tabelle)
            testo = "\n\n".join(testi)
            errori = [str(a) for p in pagine if not p.testo.strip() for a in p.avvisi]
            return TestoContenitore(testo, "ocr" if any(p.origine == "ocr" for p in pagine) else "nativo", errori)
        except Exception:
            return TestoContenitore(errori=["Lettura del PDF non riuscita; il file richiede recupero automatico."])
    if head.startswith((b"<?xml", b"<")) and (ext in {".xml", ".p7m"} or head.startswith(b"<?xml")):
        from defusedxml import ElementTree
        try:
            ElementTree.fromstring(data)
            for encoding in ("utf-8-sig", "utf-16", "cp1252"):
                try:
                    return TestoContenitore(data.decode(encoding))
                except UnicodeDecodeError:
                    continue
        except Exception:
            return TestoContenitore(errori=["XML non leggibile o non sicuro."])
    if head.startswith(b"PK") and ext != ".docx":
        from legal_document_ingestion.archive_extractor import extract_zip_bytes
        from legal_document_ingestion.zip_safety import ZipSafetyConfig
        from legal_document_ingestion.mime_detector import SUPPORTED_EXTENSIONS
        # Firma separata ammessa soltanto in questo lettore e ispezionata come
        # CMS qui sotto. Gli stessi limiti di sicurezza ZIP restano attivi.
        config = ZipSafetyConfig(allowed_extensions=SUPPORTED_EXTENSIONS | {".p7s"})
        result = extract_zip_bytes(data, filename=nome, parent_document_id="lettura", root_document_id="lettura", config=config)
        testi, errori, origini = [], [str(x.get("reason") or "Elemento ZIP non leggibile.") for x in result.blocked], []
        for file in result.files:
            if file.is_archive or file.security_status != "validated":
                continue
            letto = estrai_contenuto(file.data, file.original_filename, profondita=profondita+1)
            if letto.testo:
                testi.append("[" + file.extraction_path_virtuale + "]\n" + letto.testo)
                origini.append(letto.origine)
            errori.extend(letto.errori)
        return TestoContenitore("\n\n".join(testi), "ocr" if "ocr" in origini else "nativo", errori)
    if ext in {".p7s", ".enc"}:
        from asn1crypto.cms import ContentInfo
        try:
            cms = ContentInfo.load(data, strict=True)
            tipo = cms["content_type"].native
            if tipo == "signed_data" and cms["content"]["encap_content_info"]["content"].native is None:
                # Leggere la struttura non certifica validità, titolare o
                # contenuto firmato; nessun fatto legale nasce da questo testo.
                return TestoContenitore("Componente tecnico: firma CMS separata, senza testo autonomo. Validità crittografica non verificata da questa lettura.")
            if tipo == "enveloped_data":
                cms["content"]["encrypted_content_info"]["content_encryption_algorithm"].native
                return TestoContenitore("Componente tecnico: busta CMS cifrata. Contenuto riservato al destinatario; atti e ricevute hanno fonti separate.")
        except (ValueError, TypeError, KeyError):
            pass
        return TestoContenitore(errori=["Componente CMS non leggibile: struttura tecnica non riconosciuta."])
    if data.startswith(b"0") or ext in {".p7m", ".pm7"}:
        from pct.firme_cades import inspect_signed_document_bytes
        try:
            signed = inspect_signed_document_bytes(source_name=nome, data=data)
            if signed.payload_bytes and signed.payload_bytes != data:
                return estrai_contenuto(signed.payload_bytes, signed.status.payload_name or nome.removesuffix(".p7m"), profondita=profondita+1)
        except Exception:
            pass
        return TestoContenitore(errori=["Contenuto della busta firmata non estraibile; nessuna verifica della firma è dedotta dal nome."])
    if ext == ".eml" or b"From:" in head or b"MIME-Version:" in head:
        from email import policy
        from email.parser import BytesParser
        message = BytesParser(policy=policy.default).parsebytes(data)
        if not message.get("From") or not message.get("Subject"):
            return TestoContenitore(errori=["Messaggio email privo di intestazioni leggibili."])
        body = message.get_body(preferencelist=("plain", "html"))
        testo = str(body.get_content()) if body else ""
        if body is not None and body.get_content_type() == "text/html":
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(testo, "html.parser")
            for node in soup(["script", "style"]): node.decompose()
            testo = soup.get_text(" ", strip=True)
        return TestoContenitore(f"Tipo contenuto: messaggio email\nMittente: {message.get('From', '')}\nOggetto: {message.get('Subject', '')}\n\n{testo}")
    if ext in {".doc", ".docx", ".txt", ".rtf"}:
        from pct.document_intelligence.extraction import extract_text_from_document
        result = extract_text_from_document(data, nome, ext.lstrip("."))
        if result.ok and result.text.strip():
            return TestoContenitore(result.text)
    return TestoContenitore(errori=["Formato del contenuto non riconosciuto dal lettore."])
