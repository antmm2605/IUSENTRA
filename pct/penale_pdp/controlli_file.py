"""Controlli sui singoli file di un deposito PDP.

Base: provvedimento DGSIA 11/07/2023 art. 5 (formati, A4, testo nativo,
niente password, 50 MB per file e 500 MB per deposito, PAdES o CAdES con
almeno una firma del depositante) e manuale PDP (nome file e oggetto al
massimo 100 caratteri; controlli formali eseguiti dal portale all'invio).
"""

from __future__ import annotations

import hashlib
import io
from dataclasses import dataclass, field
from typing import Any

MB = 1024 * 1024
LIMITE_FILE = 50 * MB
LIMITE_DEPOSITO = 500 * MB
LIMITE_NOME = 100
ESTENSIONI_ALLEGATI = frozenset({
    "pdf", "p7m", "jpg", "jpeg", "gif", "tiff", "tif", "mp4", "m4v", "mov", "webm", "mkv", "mpg", "mpeg", "avi",
    "mp3", "m4a", "aac", "ogg", "flac", "wav", "aiff", "aif", "wma", "raw", "rtf", "txt", "xml", "eml", "msg",
    "zip", "rar", "arj", "tar",
})
FIRMATI = frozenset({"principale", "contestuale"})


@dataclass
class Esito:
    codice: str
    livello: str  # errore | avviso | ok | info
    messaggio: str
    file: str = ""

    def to_dict(self) -> dict[str, str]:
        return {"codice": self.codice, "livello": self.livello, "messaggio": self.messaggio, "file": self.file}


@dataclass
class FileDeposito:
    ruolo: str  # principale | contestuale | abilitante | allegato
    nome: str
    dati: bytes
    oggetto: str = ""
    documento_id: str = ""
    tipo_atto: str = ""
    esiti: list[Esito] = field(default_factory=list)
    firmatari: list[dict[str, Any]] = field(default_factory=list)

    @property
    def estensione(self) -> str:
        return self.nome.rsplit(".", 1)[-1].casefold() if "." in self.nome else ""

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.dati).hexdigest()


def _contenuto_pdf(file: FileDeposito) -> bytes:
    if file.dati[:5] == b"%PDF-":
        return file.dati
    try:
        from pct.firma import estrai_contenuto_cades

        interno = estrai_contenuto_cades(file.dati) or b""
        return interno if interno[:5] == b"%PDF-" else b""
    except Exception:
        return b""


def _controlla_pdf(file: FileDeposito, pdf: bytes) -> None:
    if not pdf:
        file.esiti.append(Esito("NON_PDF", "errore", "Il PDP accetta come atto solo un PDF (o un PDF firmato .p7m).", file.nome))
        return
    try:
        from pypdf import PdfReader

        lettore = PdfReader(io.BytesIO(pdf))
        if lettore.is_encrypted:
            file.esiti.append(Esito("PASSWORD", "errore", "Il PDF è protetto da password: il PDP lo rifiuta (art. 5 co. 3).", file.nome))
            return
        pagine = list(lettore.pages)
    except Exception:
        file.esiti.append(Esito("PDF_ILLEGGIBILE", "errore", "Il PDF non si apre: rigeneralo prima del deposito.", file.nome))
        return
    if not pagine:
        file.esiti.append(Esito("PDF_VUOTO", "errore", "Il PDF non ha pagine.", file.nome))
        return
    fuori_a4 = [
        i + 1 for i, pagina in enumerate(pagine[:50])
        if not (560 <= min(float(pagina.mediabox.width), float(pagina.mediabox.height)) <= 610
                and 780 <= max(float(pagina.mediabox.width), float(pagina.mediabox.height)) <= 860)
    ]
    if fuori_a4:
        file.esiti.append(Esito("NON_A4", "avviso", f"Pagine non in formato A4 ({', '.join(map(str, fuori_a4[:5]))}): l'atto deve essere A4 (art. 5 co. 1).", file.nome))
    if file.ruolo in FIRMATI:
        testo = "".join((p.extract_text() or "") for p in pagine[:3]).strip()
        if len(testo) < 40:
            file.esiti.append(Esito("SCANSIONE", "avviso", "L'atto sembra una scansione: il PDP chiede un PDF nativo, non immagini (art. 5 co. 1 lett. b).", file.nome))


def _verifica_disponibile() -> bool:
    """La verifica crittografica usa pyHanko (requirements/pades.txt, installato nell'immagine di produzione)."""
    try:
        import pyhanko.sign.validation.generic_cms  # noqa: F401
    except Exception:
        return False
    return True


def _controlla_firma(file: FileDeposito, cf_avvocato: str, avvocatura_stato: bool) -> None:
    from pct.document_signature_state import cades_crittograficamente_valida
    from pct.firma import analizza_firma_documento, busta_cades_valida

    cades = busta_cades_valida(file.dati)
    firmatari = analizza_firma_documento(file.dati, file.nome)
    file.firmatari = [
        {"nome": f.get("intestatario", ""), "codiceFiscale": f.get("codice_fiscale", ""), "formato": f.get("formato", ""),
         "scaduto": bool(f.get("scaduto")), "validoAl": f.get("valido_al", "")}
        for f in firmatari
    ]
    if not firmatari:
        file.esiti.append(Esito("FIRMA_ASSENTE", "errore", "Manca la firma digitale PAdES o CAdES: il PDP rifiuta l'atto.", file.nome))
        return
    if not _verifica_disponibile():
        integra = None
        file.esiti.append(Esito("FIRMA_NON_VERIFICATA", "avviso",
                                "Verifica crittografica non disponibile su questo server: la eseguirà il PDP all'invio.", file.nome))
    else:
        integra = cades_crittograficamente_valida(file.dati) if cades else any(
            f.get("content_digest_verified") and f.get("cryptographic_signature_verified") for f in firmatari
        )
    if integra is False:
        file.esiti.append(Esito("FIRMA_NON_VALIDA", "errore", "La firma non è integra: il documento è stato modificato dopo la firma.", file.nome))
    if all(f.get("scaduto") for f in firmatari):
        file.esiti.append(Esito("CERTIFICATO_SCADUTO", "errore", "Il certificato di firma è scaduto.", file.nome))
    codici = {str(f.get("codice_fiscale") or "").upper() for f in firmatari} - {""}
    if avvocatura_stato:
        file.esiti.append(Esito("FIRMA_ADS", "info", "Avvocatura dello Stato: ammessa la firma di altro avvocato dello Stato (art. 5 co. 7).", file.nome))
    elif not cf_avvocato:
        file.esiti.append(Esito("CF_AVVOCATO_ASSENTE", "avviso", "Codice fiscale dell'avvocato non configurato (Impostazioni → Firma digitale): non posso verificare che la firma sia sua.", file.nome))
    elif cf_avvocato.upper() not in codici:
        file.esiti.append(Esito("FIRMATARIO_DIVERSO", "errore",
                                "Nessuna firma è dell'avvocato che deposita: il PDP richiede almeno la sua (art. 5 co. 7).", file.nome))
    if integra and not any(e.livello == "errore" for e in file.esiti):
        formato = "CAdES" if cades else "PAdES"
        file.esiti.append(Esito("FIRMA_OK", "ok", f"Firma {formato} integra"
                                + (f" di {file.firmatari[0]['nome']}" if file.firmatari and file.firmatari[0]["nome"] else "") + ".", file.nome))


def controlla_file(file: FileDeposito, *, cf_avvocato: str = "", avvocatura_stato: bool = False) -> FileDeposito:
    """Esegue sul file i controlli che il PDP e il provvedimento DGSIA prevedono per il suo ruolo."""
    if len(file.nome) > LIMITE_NOME:
        file.esiti.append(Esito("NOME_LUNGO", "errore", f"Il nome del file supera {LIMITE_NOME} caratteri: il PDP lo rifiuta.", file.nome))
    if len(file.dati) > LIMITE_FILE:
        file.esiti.append(Esito("FILE_GRANDE", "errore", "Il file supera 50 MB (art. 5 co. 6).", file.nome))
    if not file.dati:
        file.esiti.append(Esito("FILE_VUOTO", "errore", "Il file è vuoto.", file.nome))
        return file
    if file.ruolo in {"abilitante", "allegato"}:
        oggetto = (file.oggetto or "").strip()
        if not oggetto:
            file.esiti.append(Esito("OGGETTO_MANCANTE", "errore", "Scrivi l'oggetto: il PDP lo chiede per atti abilitanti e allegati.", file.nome))
        elif len(oggetto) > LIMITE_NOME:
            file.esiti.append(Esito("OGGETTO_LUNGO", "errore", f"L'oggetto supera {LIMITE_NOME} caratteri.", file.nome))
    if file.ruolo == "allegato":
        if file.estensione not in ESTENSIONI_ALLEGATI:
            file.esiti.append(Esito("FORMATO_ALLEGATO", "errore", f"Formato .{file.estensione or '?'} non ammesso dal PDP per gli allegati.", file.nome))
        elif file.estensione == "pdf":
            _controlla_pdf(file, _contenuto_pdf(file))
        return file
    _controlla_pdf(file, _contenuto_pdf(file))
    if file.ruolo in FIRMATI:
        _controlla_firma(file, cf_avvocato, avvocatura_stato)
    return file


__all__ = ["ESTENSIONI_ALLEGATI", "Esito", "FileDeposito", "LIMITE_DEPOSITO", "LIMITE_FILE", "LIMITE_NOME", "controlla_file"]
