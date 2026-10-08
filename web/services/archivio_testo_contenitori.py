"""Lettura dei formati fisici per i due motori dell'archivio, fuori dalle GET.

Riusa estrazione ZIP protetta, lettore CAdES e OCR locali. Nessuna lettura
binaria approssimativa viene usata come prova del contenuto.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from pathlib import Path
import hashlib

@dataclass
class TestoContenitore:
    testo: str = ""
    origine: str = "nativo"
    errori: list[str] = field(default_factory=list)
    componenti: list[dict] = field(default_factory=list)
    esito: str = "testo"
    motivo: str = ""


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
    if head.startswith(b"PK") and ext not in {".docx", ".xlsx", ".pptx", ".odt", ".ods", ".odp"}:
        from legal_document_ingestion.archive_extractor import extract_zip_bytes
        from legal_document_ingestion.zip_safety import ZipSafetyConfig
        from legal_document_ingestion.mime_detector import SUPPORTED_EXTENSIONS
        # Firma separata ammessa soltanto in questo lettore e ispezionata come
        # CMS qui sotto. Gli stessi limiti di sicurezza ZIP restano attivi.
        config = ZipSafetyConfig(allowed_extensions=SUPPORTED_EXTENSIONS | {".p7s"})
        result = extract_zip_bytes(data, filename=nome, parent_document_id="lettura", root_document_id="lettura", config=config)
        testi, errori, origini, componenti = [], [str(x.get("reason") or "Elemento ZIP non leggibile.") for x in result.blocked], [], []
        for file in result.files:
            if file.is_archive or file.security_status != "validated":
                continue
            letto = estrai_contenuto(file.data, file.original_filename, profondita=profondita+1)
            if letto.testo:
                testi.append("[" + file.extraction_path_virtuale + "]\n" + letto.testo)
                origini.append(letto.origine)
            if letto.componenti:
                for child in letto.componenti:
                    componenti.append({**child, 'path':file.extraction_path_virtuale+'/'+child['path'],
                                       'parent_sha256':child.get('parent_sha256') or hashlib.sha256(file.data).hexdigest(),
                                       'root_container_sha256':hashlib.sha256(data).hexdigest()})
            else:
                componenti.append({'path':file.extraction_path_virtuale, 'name':file.original_filename,
                                   'sha256':hashlib.sha256(file.data).hexdigest(), 'parent_sha256':hashlib.sha256(data).hexdigest(),
                                   'testo':letto.testo, 'errori':letto.errori,
                                   'esito':letto.esito, 'motivo':letto.motivo})
            errori.extend(letto.errori)
        soltanto_vuoti = bool(componenti) and not errori and all(c.get('esito') == 'senza_testo' for c in componenti)
        return TestoContenitore("\n\n".join(testi), "ocr" if "ocr" in origini else "nativo", errori, componenti,
                               esito="senza_testo" if soltanto_vuoti else "testo",
                               motivo="Archivio contenente soltanto allegati TXT senza contenuto documentale." if soltanto_vuoti else "")
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
        from legal_document_ingestion.zip_safety import ZipSafetyConfig, is_path_traversal, normalize_virtual_path
        from pct.document_intelligence.extraction import _email_part_bytes
        import mimetypes

        limits = ZipSafetyConfig()
        email_sha = hashlib.sha256(data).hexdigest()
        body_text = f"Tipo contenuto: messaggio email\nMittente: {message.get('From', '')}\nOggetto: {message.get('Subject', '')}\n\n{testo}"
        components = [{'path':'corpo-email', 'name':nome, 'sha256':email_sha, 'parent_sha256':email_sha,
                       'testo':body_text, 'errori':[], 'esito':'testo', 'motivo':''}]
        texts, errors, origins, total = [body_text], [], [], 0
        for index, part in enumerate(message.iter_attachments(), 1):
            if index > limits.max_files:
                errors.append('Numero di allegati email oltre il limite di lettura sicura.')
                break
            payload = _email_part_bytes(part)
            total += len(payload)
            if len(payload) > limits.max_single_file_bytes or total > limits.max_total_uncompressed_bytes:
                errors.append('Dimensione degli allegati email oltre il limite di lettura sicura.')
                continue
            suffix = mimetypes.guess_extension(part.get_content_type()) or '.bin'
            name = part.get_filename() or f'allegato-{index}{suffix}'
            if is_path_traversal(name) or '\x00' in name:
                errors.append('Percorso dell’allegato email non sicuro.')
                continue
            name = normalize_virtual_path(name)
            child = estrai_contenuto(payload, name, profondita=profondita+1)
            path = f'allegato-{index}/{name}'
            if child.testo:
                texts.append(f'[{path}]\n{child.testo}')
                origins.append(child.origine)
            if child.componenti:
                components.extend({**c, 'path':path+'/'+c['path'],
                                   'parent_sha256':c.get('parent_sha256') or hashlib.sha256(payload).hexdigest(),
                                   'root_container_sha256':email_sha} for c in child.componenti)
            else:
                components.append({'path':path, 'name':name, 'sha256':hashlib.sha256(payload).hexdigest(),
                                   'parent_sha256':email_sha, 'testo':child.testo, 'errori':child.errori,
                                   'esito':child.esito, 'motivo':child.motivo})
            errors.extend(child.errori)
        return TestoContenitore('\n\n'.join(texts), 'ocr' if 'ocr' in origins else 'nativo', errors, components)
    if ext in {".doc", ".docx", ".txt", ".rtf", ".html", ".htm", ".msg", ".xlsx", ".xls", ".png", ".jpg", ".jpeg", ".tif", ".tiff", ".bmp", ".gif", ".webp", ".csv", ".json", ".odt", ".ods", ".odp", ".pptx"}:
        from pct.document_intelligence.extraction import extract_text_from_document
        result = extract_text_from_document(data, nome, ext.lstrip("."))
        # Solo un TXT fisicamente composto da spazi/fine riga è un esito
        # negativo conclusivo. Un estrattore che restituisce testo vuoto per
        # un documento strutturato o binario continua a segnalare l'errore.
        if ext == ".txt" and result.ok and not data.strip(b" \t\r\n\v\f"):
            return TestoContenitore(esito="senza_testo", motivo="Allegato TXT composto soltanto da spazi o fine riga; nessun contenuto documentale da interpretare.")
        if result.ok and result.text.strip() and ".binary" not in result.extraction_engine:
            return TestoContenitore(result.text)
        return TestoContenitore(errori=[result.error_message or "Il formato richiede un lettore strutturato disponibile; nessun testo binario approssimativo viene usato come prova."])
    return TestoContenitore(errori=["Formato del contenuto non riconosciuto dal lettore."])
