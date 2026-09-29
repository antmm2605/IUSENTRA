"""Formati dei file per la conservazione (Linee guida AgID sul documento informatico, Allegato 2).

L'Allegato 2 elenca i formati idonei alla conservazione (aperti, documentati, diffusi). Qui si
riconosce il formato dall'estensione e si dice se è fra quelli dell'Allegato 2; un formato non
idoneo non blocca il pacchetto ma va segnalato, perché il conservatore può rifiutarlo o chiedere
la conversione (es. un .doc in PDF/A prima del versamento).
"""

from __future__ import annotations

from pathlib import PurePath

# estensione → (nome del formato, tipo MIME, idoneo secondo l'Allegato 2)
FORMATI: dict[str, tuple[str, str, bool]] = {
    "pdf": ("PDF / PDF/A", "application/pdf", True),
    "p7m": ("CAdES (busta di firma)", "application/pkcs7-mime", True),
    "tsd": ("TimeStampedData (RFC 5544)", "application/timestamped-data", True),
    "m7m": ("CAdES con marca temporale", "application/pkcs7-mime", True),
    "xml": ("XML", "application/xml", True),
    "txt": ("Testo semplice", "text/plain", True),
    "csv": ("CSV", "text/csv", True),
    "html": ("HTML", "text/html", True),
    "htm": ("HTML", "text/html", True),
    "eml": ("Messaggio di posta (RFC 5322)", "message/rfc822", True),
    "jpg": ("JPEG", "image/jpeg", True),
    "jpeg": ("JPEG", "image/jpeg", True),
    "png": ("PNG", "image/png", True),
    "tif": ("TIFF", "image/tiff", True),
    "tiff": ("TIFF", "image/tiff", True),
    "odt": ("OpenDocument testo", "application/vnd.oasis.opendocument.text", True),
    "ods": ("OpenDocument foglio di calcolo", "application/vnd.oasis.opendocument.spreadsheet", True),
    "odp": ("OpenDocument presentazione", "application/vnd.oasis.opendocument.presentation", True),
    "docx": ("Office Open XML testo", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", True),
    "xlsx": ("Office Open XML foglio di calcolo", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", True),
    "pptx": ("Office Open XML presentazione", "application/vnd.openxmlformats-officedocument.presentationml.presentation", True),
    "mp3": ("MP3", "audio/mpeg", True),
    "mp4": ("MPEG-4", "video/mp4", True),
    "doc": ("Word 97-2003", "application/msword", False),
    "xls": ("Excel 97-2003", "application/vnd.ms-excel", False),
    "rtf": ("RTF", "application/rtf", False),
    "zip": ("Archivio ZIP", "application/zip", False),
    "rar": ("Archivio RAR", "application/vnd.rar", False),
    "msg": ("Messaggio Outlook", "application/vnd.ms-outlook", False),
}


def formato_file(nome: str) -> dict[str, object]:
    """Formato del file; per le buste .p7m si guarda anche il formato del documento firmato."""

    suffissi = [s.lower().lstrip(".") for s in PurePath(str(nome or "")).suffixes]
    estensione = suffissi[-1] if suffissi else ""
    etichetta, mime, idoneo = FORMATI.get(estensione, (estensione.upper() or "Sconosciuto", "application/octet-stream", False))
    interno = ""
    if estensione in {"p7m", "m7m", "tsd"} and len(suffissi) >= 2:
        interno = suffissi[-2]
        idoneo = idoneo and FORMATI.get(interno, ("", "", False))[2]
    nota = "" if idoneo else ("Formato non compreso nell'Allegato 2 delle Linee guida AgID: valuta la conversione in PDF/A "
                              "prima del versamento o concorda il formato con il conservatore.")
    return {"estensione": estensione, "formato": etichetta + (f" ({interno.upper()} firmato)" if interno else ""),
            "mime": mime, "idoneo": idoneo, "nota": nota}


__all__ = ["FORMATI", "formato_file"]
