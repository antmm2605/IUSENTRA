"""Identità testuale esatta degli atti, prodotta solo dai motori di lettura."""
from __future__ import annotations

import hashlib
import json
import re

from pct.registro_letture.fatti_repository import Fatto

VERSIONE_COPIE_ATTI = '2026.10.01.copie-atti-v3'
_ENFASI_TESTO_ESTRATTO = re.compile(r"(?<![\w*])(\*{1,2})([^\s*](?:[^*\n]*[^\s*])?)\1(?![\w*])")
_TIMBRO_FIRMA_E_PUBBLICAZIONE = re.compile(
    r"\s+firmato da: [\w '.-]{2,100} emesso da: [\w '.&/-]{2,130} serial#:\s*[0-9a-f]{8,64}"
    r"(?:\s+sentenza n\.\s*(?P<numero>\d+/\d{4}) pubbl\. il \d{1,2}/\d{1,2}/\d{4}"
    r"\s+r\.g\. n\.\s*\d+/\d{4}(?:\s+sentenza a verbale \(art\. 127[ -]ter c\.p\.c\.\) del \d{1,2}/\d{1,2}/\d{4})?(?=\s|$)|$)"
)


def identita_dispositivo_sentenza(testo: str) -> tuple[str, str]:
    """Impronta del dispositivo e numero ufficiale dall'intestazione o dal timbro."""
    from pct.percorso_pratica.esito import dispositivo
    from pct.ragionamento.testo import semplice
    from pct.termine_lungo_sentenza import numero_sentenza

    contenuto = dispositivo(testo)
    if len(contenuto.split()) < 30 or len(contenuto) >= 5900:
        return "", ""
    normalizzato = semplice(_ENFASI_TESTO_ESTRATTO.sub(r"\2", contenuto))
    numeri = {numero_sentenza(testo[:1300])}
    numeri.update(timbro["numero"] for timbro in _TIMBRO_FIRMA_E_PUBBLICAZIONE.finditer(normalizzato))
    numeri.difference_update(("", None))
    if len(numeri) > 1:
        return "", ""
    normalizzato = " ".join(_TIMBRO_FIRMA_E_PUBBLICAZIONE.sub(" ", normalizzato).split()).rstrip(" .:;,")
    return hashlib.sha256(normalizzato.encode("utf-8")).hexdigest(), next(iter(numeri), "")


def messaggio_strutturato(testo: str) -> bool:
    head = str(testo or '')[:2000]
    # L'estrattore MIME nativo conserva un'intestazione esplicita prima del
    # corpo decodificato. Non è una citazione contenuta in un atto PDF.
    if re.match(r'\s*Tipo contenuto:\s*messaggio email\s*\nMittente:[^\n]+\nOggetto:', head, re.I):
        return True
    if not re.match(r'\s*(?:MIME-Version|From|Return-Path|Delivered-To|Oggetto)\s*:', head, re.I):
        return False
    # Il formulario può appiattire le righe dell'intestazione. Si richiedono
    # comunque il primo campo di una busta e almeno tre campi distinti.
    mime = sum(bool(re.search(rf'(?im)(?:^|\s){campo}\s*:', head))
               for campo in ('MIME-Version', 'From', 'To', 'Subject'))
    esportato = all(re.search(rf'(?im)(?:^|\s){campo}\s*:', head)
                    for campo in ('Oggetto', 'Mittente', 'Destinatari'))
    return mime >= 3 or esportato


def fatto_identita(testo: str, *, origine: str, nome: str) -> Fatto | None:
    # Nessuna somiglianza, rimozione di cifre o ricostruzione OCR: si confronta
    # l'intero testo, con la sola normalizzazione degli spazi di impaginazione.
    if not nome.casefold().endswith('.pdf') or messaggio_strutturato(testo):
        return None
    normalizzato = ' '.join(str(testo or '').split())
    if len(normalizzato) < 500:
        return None
    digest = hashlib.sha256(normalizzato.encode('utf-8')).hexdigest()
    return Fatto(categoria='evento', campo='impronta_testo_atto', valore=digest,
                 origine=origine, verifica='verificata', confidenza=1.0,
                 etichetta='Identità testuale dell’atto',
                 contesto='Intero testo identico, normalizzati soltanto gli spazi.',
                 prove=[{'codice':'identita_testuale_esatta', 'esito':'ok',
                         'versione':VERSIONE_COPIE_ATTI, 'caratteri':len(normalizzato)}])


def riunisci_obblighi(obblighi: list[dict], identita: dict[str, str]) -> list[dict]:
    """Una proposta con tutte le fonti, solo se contenuto e contesto coincidono."""
    gruppi: dict[str, dict] = {}
    esito = []
    for item in obblighi:
        oid = str(item['documentoId'])
        impronta = identita.get(oid, '')
        # Le decisioni e i calcoli differenti non vengono fusi né sovrascritti.
        contesto = {k:item.get(k) for k in ('regola','stato','motivo','scadenza','natura',
                    'formula','destinatari','contesto_verificato','eventi_documento')}
        # Le fonti dell'evento possono avere id diversi: in quel caso resta
        # necessaria una correlazione documentata, non basta la data uguale.
        chiave = json.dumps([impronta, contesto], sort_keys=True, ensure_ascii=False)
        fonte = {'documentoId':oid, 'documento':item['documento'],
                 'chiave':item['chiave'], 'impronta_testo':impronta}
        if impronta and chiave in gruppi:
            gruppi[chiave]['fonti_documentali'].append(fonte)
            continue
        copia = dict(item, fonti_documentali=[fonte])
        if impronta:
            contesto_hash = hashlib.sha256(json.dumps(contesto, sort_keys=True, ensure_ascii=False).encode()).hexdigest()[:16]
            copia['chiave'] = f"{item['regola']}:atto:{impronta}:{contesto_hash}"
        esito.append(copia)
        if impronta:
            gruppi[chiave] = copia
    return esito
