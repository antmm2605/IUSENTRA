"""Registro attività in forma leggibile per l'avvocato.

Gli eventi del registro (art. 30 GDPR, tracciabilità delle operazioni; art. 20 CAD per
l'integrità dei documenti) sono scritti dai moduli con codici tecnici: azione
`dominio.verbo`, esito `OK`/`SUCCESSO`/`DENIED`, dettagli in JSON. Qui si traducono per la
pagina «Registro attività» senza cambiare quanto è registrato:

- l'esito si riconduce ai tre valori del registro (OK, NEGATO, ERRORE), così i conteggi
  della pagina comprendono anche gli eventi scritti con sinonimi;
- l'azione e il tipo di risorsa diventano un'etichetta italiana;
- i dettagli JSON diventano «Nome: valore · …» prima del taglio a lunghezza fissa, così
  un JSON lungo non arriva mai alla pagina spezzato e illeggibile.
"""

from __future__ import annotations

import json
import re
from typing import Any

_ESITI = {
    "OK": "OK",
    "SUCCESSO": "OK",
    "SUCCESS": "OK",
    "COMPLETATO": "OK",
    "NEGATO": "NEGATO",
    "DENIED": "NEGATO",
    "FORBIDDEN": "NEGATO",
    "ERRORE": "ERRORE",
    "ERROR": "ERRORE",
    "FALLITO": "ERRORE",
    "FAILED": "ERRORE",
}

_AZIONI = {
    "auth.login": "Accesso al gestionale",
    "auth.logout": "Uscita dal gestionale",
    "email.sincronizzata": "Casella di posta sincronizzata",
    "email_ordinaria.sincronizzata": "Email ordinaria sincronizzata",
    "notifiche_legali.anteprima_relata": "Anteprima della relata di notifica",
    "fascicoli.documento.visualizza": "Documento del fascicolo aperto",
    "fascicoli.documento.visualizza.mobile": "Documento del fascicolo aperto da telefono",
    "fascicoli.documento.carica": "Documento caricato nel fascicolo",
    "fascicoli.documento.firma_esistente_verificata": "Firma del documento verificata",
    "fascicoli.deposito.selezione_riallineata": "Selezione del deposito riallineata",
    "fascicolo.giudice_da_fonte": "Giudice del fascicolo letto dal provvedimento",
    "termini.revisione": "Termine processuale revisionato",
    "termini.adozione": "Termini processuali adottati",
    "impostazioni.studio.aggiorna": "Dati dello studio aggiornati",
    "impostazioni.fatturazione.aggiorna": "Impostazioni di fatturazione aggiornate",
    "impostazioni.firma.aggiorna": "Firma digitale dello studio aggiornata",
    "impostazioni.firma_certificato.aggiorna": "Certificato di firma aggiornato",
    "impostazioni.deposito_telematico_role.aggiorna": "Ruolo per il deposito telematico aggiornato",
    "local_signer.diagnostica_salvata": "Diagnostica Local Signer salvata",
    "fatturazione.crea": "Documento economico creato",
    "fatturazione.stato": "Stato del documento economico cambiato",
    "fatturazione.dettaglio": "Documento economico consultato",
    "fatturazione.preparazione_incassi": "Incassi preparati",
    "pagamenti.esporta_selezione": "Pagamenti esportati",
    "scadenziario.esporta_pdf": "Scadenziario esportato in PDF",
    "udienza.avvio": "Preparazione udienza avviata",
    "udienza.passo": "Passaggio della preparazione udienza",
    "udienza.adozione": "Preparazione udienza adottata",
    "supporto_remoto.richiedi_sessione": "Assistenza remota richiesta",
    "policy_denied.tenant_isolation": "Accesso negato: dati di un altro studio",
    "policy_denied.backend_security": "Accesso negato: parametri riservati",
    "policy_denied.legal_skills": "Accesso negato: permesso mancante",
    "policy_denied.lex_learning": "Accesso negato: permesso Lex mancante",
}

_DOMINI = {
    "auth": "Accesso",
    "email": "Posta",
    "email_ordinaria": "Email ordinaria",
    "fascicolo": "Fascicolo",
    "fascicoli": "Fascicoli",
    "notifiche_legali": "Notifiche legali",
    "termini": "Termini",
    "impostazioni": "Impostazioni",
    "fatturazione": "Fatturazione",
    "pagamenti": "Pagamenti",
    "scadenziario": "Scadenziario",
    "agenda": "Agenda",
    "timesheet": "Timesheet",
    "udienza": "Udienza",
    "ctu": "CTU",
    "prima_nota": "Prima nota",
    "utenti": "Utenti",
    "backup": "Backup",
    "local_signer": "Local Signer",
    "supporto_remoto": "Assistenza remota",
    "policy_denied": "Accesso negato",
}

_RISORSE = {
    "fascicolo": "Fascicolo",
    "notifica_legale": "Notifica legale",
    "config_studio": "Impostazioni studio",
    "parcella": "Documento economico",
    "pagamento": "Pagamento",
    "scadenza": "Scadenza",
    "scadenze": "Scadenze",
    "appuntamento": "Appuntamento",
    "appuntamenti": "Agenda",
    "termini": "Termini",
    "preparazione_udienza": "Preparazione udienza",
    "local_signer": "Local Signer",
    "supporto_remoto": "Assistenza remota",
    "prima_nota": "Prima nota",
    "timesheet": "Timesheet",
    "fatturazione": "Fatturazione",
    "ctu": "CTU",
    "api": "Servizio",
    "permission": "Permesso",
    "utente": "Utente",
}

# Chiavi inglesi scritte dagli strumenti di migrazione e adozione SQL (03/11/2026, ADM-05 riverifica).
_CHIAVI = {
    "source": "Origine",
    "source_sha256": "Impronta dell'origine",
    "source_records": "Record di origine",
    "sha256": "Impronta SHA-256",
    "inserted": "Inseriti",
    "added": "Aggiunti",
    "backup_reference": "Copia di sicurezza",
    "backup_sha256": "Impronta della copia",
    "version": "Versione",
    "tenant": "Studio",
    "sql_records": "Record SQL",
    "revision": "Revisione",
    "prepared_at": "Preparato il",
    "historical_differences": "Differenze storiche",
    "before": "Prima",
    "after": "Dopo",
    "effects": "Effetti",
    "financial_rilevazione": "Rilevazione economica",
    "prima_nota_records": "Record di prima nota",
}

_DATA_ISO = re.compile(r"^(\d{4})-(\d{2})-(\d{2})(?:[T ](\d{2}):(\d{2}))?")
_LIMITE = 600


def _parole(codice: str) -> str:
    testo = re.sub(r"[_\-]+", " ", codice).strip()
    return testo[:1].upper() + testo[1:] if testo else ""


def _chiave(codice: Any) -> str:
    grezzo = str(codice)
    return _CHIAVI.get(grezzo.strip().lower(), _parole(grezzo))


def esito_registro(valore: Any) -> str:
    """OK, NEGATO o ERRORE; un esito sconosciuto resta com'è (in maiuscolo)."""
    grezzo = str(valore or "OK").strip().upper() or "OK"
    return _ESITI.get(grezzo, grezzo)


def etichetta_azione(codice: Any) -> str:
    grezzo = str(codice or "").strip()
    if not grezzo:
        return "Azione non indicata"
    if grezzo in _AZIONI:
        return _AZIONI[grezzo]
    dominio, _, resto = grezzo.partition(".")
    if not resto:
        return _parole(grezzo)
    nome_dominio = _DOMINI.get(dominio, _parole(dominio))
    resto_testo = _parole(resto.replace(".", " "))
    return f"{nome_dominio} · {resto_testo[:1].lower()}{resto_testo[1:]}"


def etichetta_risorsa(codice: Any) -> str:
    grezzo = str(codice or "").strip()
    if not grezzo:
        return ""
    return _RISORSE.get(grezzo, _parole(grezzo))


def _valore(valore: Any, profondita: int = 0) -> str:
    if valore is None or valore == "":
        return "—"
    if isinstance(valore, bool):
        return "sì" if valore else "no"
    if isinstance(valore, (int, float)):
        return f"{valore:,}".replace(",", ".") if isinstance(valore, int) else str(valore).replace(".", ",")
    if isinstance(valore, str):
        m = _DATA_ISO.match(valore)
        if m and len(valore) <= 32:
            data = f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
            return f"{data} {m.group(4)}:{m.group(5)}" if m.group(4) else data
        return valore
    if isinstance(valore, list):
        testo = ", ".join(_valore(v, profondita + 1) for v in valore[:5])
        return testo + (", …" if len(valore) > 5 else "")
    if isinstance(valore, dict):
        if profondita >= 2:
            return "…"
        coppie = ((_chiave(k), _valore(v, profondita + 1)) for k, v in list(valore.items())[:6])
        # Un valore annidato oltre la profondità leggibile diventa «…»: la voce non dice nulla e si omette.
        return " · ".join(f"{k}: {v}" for k, v in coppie if not re.fullmatch(r"[…,\s]+", v))
    return str(valore)


def testo_dettagli(dettagli: Any, limite: int = _LIMITE) -> str:
    """Dettagli dell'evento in testo leggibile, tagliato senza lasciare JSON a metà."""
    grezzo = str(dettagli or "").strip()
    if grezzo.startswith(("{", "[")):
        try:
            grezzo = _valore(json.loads(grezzo))
        except ValueError:
            pass
    if len(grezzo) > limite:
        return grezzo[:limite].rstrip() + "…"
    return grezzo


__all__ = ["esito_registro", "etichetta_azione", "etichetta_risorsa", "testo_dettagli"]
