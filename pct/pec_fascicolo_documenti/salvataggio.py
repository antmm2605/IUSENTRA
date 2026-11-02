"""Scrittura nel fascicolo dei file scelti dalla PEC, con la provenienza nel documento.

Ogni documento porta: la fonte (``PEC_CANCELLERIA`` per gli uffici giudiziari, ``PEC_FASCICOLO`` per le altre
PEC, ``PEC_NOTIFICA`` e ``PEC_AUDIT_NOTIFICATION_RECEIPT`` per notifica e ricevute), il nome originale,
l'impronta SHA-256, il Message-ID della PEC e la data di consegna in ora italiana (etichette tecniche
``iusentra:pec:<id>`` e ``iusentra:pec-data:<aaaa-mm-gg>``, nascoste nella UI ma lette per «da PEC del …»).
L'archivio dei fascicoli avvisa da solo il registro delle letture (``@documenti_cambiati``).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pct.pec_fascicolo_documenti.classificazione import NOTIFICA, RICEVUTA_NOTIFICA, Allegato

ETICHETTA_PEC = "iusentra:pec:"
ETICHETTA_DATA = "iusentra:pec-data:"
MARCATORE_RICEVUTA = "IUSENTRA_LEGAL_NOTIFICATION_RECEIPT:"
MARCATORE_DOCUMENTO = "IUSENTRA_PEC_FASCICOLO:"


@dataclass(frozen=True)
class Provenienza:
    message_id: str
    message_id_header: str
    mittente: str
    consegnata_il: str  # aaaa-mm-ggThh:mm, ora italiana
    da_ufficio: bool

    @property
    def giorno(self) -> str:
        return self.consegnata_il[:10]

    def etichette(self) -> list[str]:
        return [f"{ETICHETTA_PEC}{self.message_id}", *([f"{ETICHETTA_DATA}{self.giorno}"] if self.giorno else [])]

    def righe_nota(self, nome: str, impronta: str) -> list[str]:
        giorno = "/".join(reversed(self.giorno.split("-"))) if self.giorno else "data non leggibile"
        return [
            f"{MARCATORE_DOCUMENTO}{self.message_id}",
            f"Da PEC del {giorno} ({self.consegnata_il[11:16] or 'ora n.d.'}, ora italiana).",
            f"File originale: {nome}. Impronta SHA-256: {impronta}.",
            *([f"Message-ID: {self.message_id_header}"] if self.message_id_header else []),
        ]


def impronte_presenti(fascicolo: Any) -> dict[str, str]:
    """Impronta → id documento per tutti i documenti del fascicolo (anche quelli scaricati dall'avvocato)."""
    out: dict[str, str] = {}
    for doc in list(getattr(fascicolo, "documenti", []) or []):
        for attributo in ("hash_contenuto_sha256", "hash_sha256"):
            impronta = str(getattr(doc, attributo, "") or "").strip().lower()
            if impronta:
                out.setdefault(impronta, str(getattr(doc, "id", "") or ""))
    return out


def eml_presente(fascicolo: Any, message_id: str, impronta: str) -> str:
    """Il documento che conserva già l'.eml di questa PEC (stesso Message-ID interno o stessa impronta)."""
    for doc in list(getattr(fascicolo, "documenti", []) or []):
        stesso_messaggio = str(getattr(doc, "msg_id_portale", "") or "") == message_id and str(getattr(doc, "nome", "") or "").casefold().endswith(".eml")
        if stesso_messaggio or f"{MARCATORE_RICEVUTA}{message_id}" in str(getattr(doc, "note", "") or ""):
            return str(getattr(doc, "id", "") or "")
    return impronte_presenti(fascicolo).get(impronta.lower(), "")


def _tipo_allegato(nome: str, provenienza: Provenienza, oggetto: str) -> Any:
    from pct.fascicoli import TipoDocumento
    from pct.fascicolo_document_catalog import catalog_tipo_documento_per_nome
    from pct.pec_provvedimento_fascicolo import tipo_documento

    tipo = catalog_tipo_documento_per_nome(nome)
    if provenienza.da_ufficio and tipo in {TipoDocumento.ALLEGATO, TipoDocumento.ALTRO}:
        return tipo_documento("", f"{nome} {oggetto}")
    return tipo


def salva_allegato(manager: Any, fascicolo_id: str, allegato: Allegato, provenienza: Provenienza, *, oggetto: str, actor: str) -> Any:
    nota = provenienza.righe_nota(allegato.nome, allegato.sha256)
    etichette = ["pec", "da-pec", *provenienza.etichette()]
    if provenienza.da_ufficio:
        # Copia informativa: la copia da notificare e attestare si scarica dal Portale dei Servizi Telematici.
        nota.append("Copia informativa allegata alla comunicazione dell'ufficio: per notifica e attestazione di "
                    "conformità serve la copia scaricata dal Portale dei Servizi Telematici.")
        etichette.append("copia-informativa")
    return manager.aggiungi_documento(
        fascicolo_id, allegato.nome, _tipo_allegato(allegato.nome, provenienza, oggetto), allegato.contenuto,
        note="\n".join(nota), tags=etichette, data_documento=provenienza.giorno, caricato_da=actor,
        firmato=allegato.nome.casefold().endswith(".p7m"),
        fonte_documento="PEC_CANCELLERIA" if provenienza.da_ufficio else "PEC_FASCICOLO",
        nome_originale=allegato.nome, hash_contenuto_sha256=allegato.sha256,
        # Chiave per allegato: due atti della stessa PEC restano due documenti distinti.
        msg_id_portale=f"{provenienza.message_id}#{allegato.sha256[:16]}",
    )


def salva_eml(manager: Any, fascicolo_id: str, raw: bytes, impronta: str, provenienza: Provenienza, *, genere: str,
              nome: str, righe_ricevuta: list[str], actor: str, etichetta_ricevuta: str = "") -> Any:
    from pct.fascicoli import TipoDocumento

    nota = provenienza.righe_nota(nome, impronta)
    etichette = ["pec", "da-pec", *provenienza.etichette()]
    if genere == RICEVUTA_NOTIFICA:
        # Stesso marcatore della riconciliazione del presidio notifiche: se la ricevuta si abbina più tardi a
        # un presidio, il documento si riusa e diventa la prova del destinatario (nessun doppione).
        nota = [f"{MARCATORE_RICEVUTA}{provenienza.message_id}", *righe_ricevuta, *nota]
        etichette = ["notifica-legale", *([etichetta_ricevuta.casefold()] if etichetta_ricevuta else []), *etichette]
    return manager.aggiungi_documento(
        fascicolo_id, nome, TipoDocumento.NOTIFICA, raw, note="\n".join(nota), tags=etichette,
        data_documento=provenienza.giorno, caricato_da=actor,
        fonte_documento="PEC_AUDIT_NOTIFICATION_RECEIPT" if genere == RICEVUTA_NOTIFICA else "PEC_NOTIFICA",
        nome_originale=nome, nome_archivio=nome, hash_contenuto_sha256=impronta, msg_id_portale=provenienza.message_id,
    )


def nome_eml(oggetto: str, genere: str) -> str:
    import re

    base = re.sub(r'[<>:"/\\|?*\x00-\x1f]+', "_", " ".join(str(oggetto or "").split())).strip(" ._")[:200]
    if not base:
        base = "Notifica PEC" if genere == NOTIFICA else "Ricevuta notifica PEC"
    return base if base.casefold().endswith(".eml") else f"{base}.eml"


__all__ = [
    "ETICHETTA_DATA", "ETICHETTA_PEC", "MARCATORE_DOCUMENTO", "MARCATORE_RICEVUTA", "Provenienza", "eml_presente",
    "impronte_presenti", "nome_eml", "salva_allegato", "salva_eml",
]
