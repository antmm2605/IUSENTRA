"""Motore parametrico per notifiche PEC L. 53/1994 e comunicazioni cliente.

Il modulo separa tre percorsi che non devono essere confusi:

- notifica legale alla controparte, con relata separata e prova PEC;
- deposito della prova della notifica nel fascicolo;
- comunicazione informativa al cliente, senza relata.
"""

from __future__ import annotations

import base64
import hashlib
import io
import json
import re
import tempfile
from copy import deepcopy
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from pct.studio_address import compose_studio_address


LEGAL_NOTIFICATION_SUBJECT = "notificazione ai sensi della legge n. 53 del 1994"
LEGAL_NOTIFICATION_OPERATION = "notifica_pec_l53"
LEGAL_NOTIFICATION_SEND_OPERATION = "invio_pec_l53"
CLIENT_COMMUNICATION_OPERATION = "comunicazione_cliente_non_notifica"
UNEP_NOTIFICATION_OPERATION = "notifica_unep"
NON_PEC_NOTIFICATION_OPERATION = "notifica_non_pec"
TEMPLATE_CATALOG_PATH = Path(__file__).with_name("data") / "notifiche_legali_templates.json"
CLIENT_COMMUNICATION_CATALOG_PATH = Path(__file__).with_name("data") / "comunicazioni_cliente_templates.json"
ATTESTAZIONE_CONFORMITA_TEMPLATE_PATH = (
    Path(__file__).with_name("data") / "templates" / "attestazione_conformita.docx"
)
ROME_TZ = ZoneInfo("Europe/Rome")
SHA256_HEX_RE = re.compile(r"^[a-fA-F0-9]{64}$")
RG_PAIR_RE = re.compile(
    r"\b(?:R\.?\s*G\.?|RG|REGISTRO\s+GENERALE)?\s*(?:N\.?|NR\.?)?\s*[:\-]?\s*0*(\d{1,8})\s*/\s*(\d{4})\b",
    re.IGNORECASE,
)

PUBLIC_PEC_REGISTERS: dict[str, str] = {
    "reginde": "ReGIndE",
    "ini_pec": "INI-PEC",
    "registro_imprese": "Registro Imprese",
    "registro_ppaa": "Registro PP.AA. / PST",
    "inad": "INAD",
    "anpr": "ANPR",
    "altro_pubblico_elenco": "Altro pubblico elenco ammesso",
}

LEGAL_RECIPIENT_ROLES = {
    "controparte",
    "difensore",
    "pa",
    "impresa",
    "professionista",
    "terzo",
}

CLIENT_RECIPIENT_ROLES = {"cliente", "assistito"}

UNEP_NOTIFICATION_TYPES: dict[str, str] = {
    "mani": "A mani",
    "posta": "A mezzo posta",
    "estero": "All'estero",
    "telematica": "Telematica",
}

NON_PEC_NOTIFICATION_TYPES: dict[str, str] = {
    "raccomandata": "Raccomandata",
    "ufficiale_giudiziario": "Ufficiale giudiziario",
    "mani": "Consegna a mani",
    "estero": "Notifica all'estero",
    "altro": "Altro canale non PEC",
}

RECIPIENT_NOTIFICATION_DIRECTIVES: dict[str, dict[str, Any]] = {
    "controparte": {
        "label": "Controparte personalmente",
        "allowed_registers": ("inad", "ini_pec", "registro_imprese", "registro_ppaa", "altro_pubblico_elenco"),
        "template_id": "relata_pec_a_controparte_personalmente",
        "required_fields": (),
        "note": "Usa questo caso quando la notifica è diretta alla parte presso domicilio digitale da pubblico elenco.",
    },
    "difensore": {
        "label": "Difensore costituito",
        "allowed_registers": ("reginde", "ini_pec", "altro_pubblico_elenco"),
        "template_id": "relata_pec_a_difensore_costituito",
        "required_fields": ("destinatario.parte_rappresentata",),
        "note": "Da usare quando la controparte è assistita da difensore costituito e la notifica va al procuratore.",
    },
    "impresa": {
        "label": "Impresa o società",
        "allowed_registers": ("registro_imprese", "ini_pec", "altro_pubblico_elenco"),
        "template_id": "relata_pec_a_impresa_societa",
        "required_fields": ("destinatario.codice_fiscale_piva",),
        "note": "La PEC deve provenire da Registro Imprese o altro pubblico elenco ammesso.",
    },
    "professionista": {
        "label": "Professionista",
        "allowed_registers": ("ini_pec", "reginde", "altro_pubblico_elenco"),
        "template_id": "relata_pec_a_professionista_inipec",
        "required_fields": (),
        "note": "Per avvocati e professionisti verifica l'elenco pubblico coerente con la qualifica.",
    },
    "pa": {
        "label": "Pubblica amministrazione",
        "allowed_registers": ("registro_ppaa", "altro_pubblico_elenco"),
        "template_id": "relata_pec_a_pubblica_amministrazione",
        "required_fields": (),
        "note": "La PEC deve essere tratta dal registro pubblico delle PP.AA. o da fonte pubblica ammessa.",
    },
    "terzo": {
        "label": "Terzo destinatario",
        "allowed_registers": ("reginde", "ini_pec", "registro_imprese", "registro_ppaa", "inad", "altro_pubblico_elenco"),
        "template_id": "relata_pec_base_l53",
        "required_fields": (),
        "note": "Caso residuale: richiede revisione professionale del ruolo prima dell'invio.",
    },
}

NOTIFICATION_CASE_DIRECTIVES: dict[str, dict[str, Any]] = {
    "ordinaria": {
        "label": "Notifica ordinaria a mezzo PEC",
        "template_id": "relata_pec_base_l53",
        "required_fields": (),
        "proceeding_required": False,
        "note": "Atto o documento notificato con oggetto L. 53 e relata separata.",
    },
    "in_corso_di_causa": {
        "label": "Notifica in corso di causa",
        "template_id": "relata_pec_in_corso_di_causa",
        "required_fields": ("procedimento.ufficio", "procedimento.numero_rg", "procedimento.anno_rg"),
        "proceeding_required": True,
        "note": "Richiede riferimenti del procedimento pendente.",
    },
    "provvedimento_giudice": {
        "label": "Provvedimento del giudice",
        "template_id": "relata_provvedimento_giudice",
        "required_fields": ("procedimento.ufficio", "procedimento.numero_rg", "procedimento.anno_rg", "provvedimento.data"),
        "proceeding_required": True,
        "note": "Per provvedimenti comunicati o estratti dal fascicolo informatico.",
    },
    "sentenza_termine_breve": {
        "label": "Sentenza o termine breve",
        "template_id": "relata_sentenza_attestazione_conformita",
        "required_fields": (
            "avvocato.full_name",
            "avvocato.codice_fiscale",
            "avvocato.foro",
            "procedimento.ufficio",
            "procedimento.sezione",
            "procedimento.numero_rg",
            "procedimento.anno_rg",
            "provvedimento.tipo",
            "provvedimento.data_deposito",
        ),
        "proceeding_required": True,
        "note": "Per la notifica finalizzata alla decorrenza dei termini di impugnazione.",
    },
    "decreto_ingiuntivo": {
        "label": "Decreto ingiuntivo",
        "template_id": "relata_decreto_ingiuntivo",
        "required_fields": ("procedimento.ufficio", "procedimento.numero_rg", "procedimento.anno_rg"),
        "proceeding_required": True,
        "note": "Per decreto ingiuntivo e documenti collegati.",
    },
    "titolo_esecutivo_precetto": {
        "label": "Titolo esecutivo e precetto",
        "template_id": "relata_titolo_esecutivo_precetto",
        "required_fields": ("esecuzione.debitore",),
        "proceeding_required": False,
        "note": "Per titolo, formula esecutiva e precetto.",
    },
    "atto_stragiudiziale": {
        "label": "Atto stragiudiziale",
        "template_id": "relata_atto_stragiudiziale",
        "required_fields": (),
        "proceeding_required": False,
        "note": "Per atti non collegati a un procedimento pendente.",
    },
    "rinnovo_notifica": {
        "label": "Rinnovo notificazione",
        "template_id": "relata_rinnovo_notifica",
        "required_fields": ("provvedimento_rinnovo.data",),
        "proceeding_required": True,
        "note": "Per rinnovo ordinato o necessario dopo esito non valido.",
    },
    "integrazione_contraddittorio": {
        "label": "Integrazione del contraddittorio",
        "template_id": "relata_integrazione_contraddittorio",
        "required_fields": ("procedimento.ufficio", "procedimento.numero_rg", "procedimento.anno_rg"),
        "proceeding_required": True,
        "note": "Per integrazione nei confronti di litisconsorti o parti necessarie.",
    },
    "chiamata_terzo": {
        "label": "Chiamata del terzo",
        "template_id": "relata_chiamata_terzo",
        "required_fields": ("procedimento.ufficio", "procedimento.numero_rg", "procedimento.anno_rg"),
        "proceeding_required": True,
        "note": "Per citazione o chiamata del terzo autorizzata o prevista.",
    },
    "riassunzione": {
        "label": "Riassunzione",
        "template_id": "relata_riassunzione",
        "required_fields": ("riassunzione.causa", "procedimento.ufficio", "procedimento.numero_rg", "procedimento.anno_rg"),
        "proceeding_required": True,
        "note": "Per riassunzione dopo interruzione, sospensione o altra causa.",
    },
    "appello_impugnazione": {
        "label": "Appello o impugnazione",
        "template_id": "relata_appello_impugnazione",
        "required_fields": ("procedimento.ufficio", "provvedimento.tipo", "provvedimento.data"),
        "proceeding_required": True,
        "note": "Per atti di impugnazione.",
    },
    "reclamo_cautelare": {
        "label": "Reclamo cautelare",
        "template_id": "relata_reclamo_cautelare",
        "required_fields": ("procedimento.ufficio", "provvedimento.data"),
        "proceeding_required": True,
        "note": "Per reclamo contro provvedimenti cautelari.",
    },
    "sfratto_convalida": {
        "label": "Sfratto e convalida",
        "template_id": "relata_sfratto_convalida",
        "required_fields": ("sfratto.immobile_indirizzo",),
        "proceeding_required": False,
        "note": "Per intimazione di sfratto e citazione per convalida.",
    },
    "pignoramento_presso_terzi": {
        "label": "Pignoramento presso terzi",
        "template_id": "relata_pignoramento_presso_terzi",
        "required_fields": ("esecuzione.debitore", "esecuzione.terzo_pignorato"),
        "proceeding_required": False,
        "note": "Per notifiche esecutive verso debitore e terzo pignorato.",
    },
    "intervento_esecuzione": {
        "label": "Intervento in esecuzione",
        "template_id": "relata_intervento_esecuzione",
        "required_fields": ("esecuzione.debitore",),
        "proceeding_required": True,
        "note": "Per intervento del creditore in procedura esecutiva.",
    },
    "opposizione_decreto_ingiuntivo": {
        "label": "Opposizione a decreto ingiuntivo",
        "template_id": "relata_opposizione_decreto_ingiuntivo",
        "required_fields": ("procedimento.ufficio", "provvedimento.numero", "provvedimento.anno"),
        "proceeding_required": True,
        "note": "Per opposizione a decreto ingiuntivo.",
    },
    "opposizione_esecutiva": {
        "label": "Opposizione esecutiva",
        "template_id": "relata_opposizione_esecutiva",
        "required_fields": ("procedimento.ufficio", "esecuzione.debitore"),
        "proceeding_required": True,
        "note": "Per opposizioni all'esecuzione o agli atti esecutivi.",
    },
    "famiglia_persone_minori": {
        "label": "Famiglia, persone e minori",
        "template_id": "relata_famiglia_persone_minori",
        "required_fields": ("procedimento.ufficio",),
        "proceeding_required": True,
        "note": "Per procedimenti di famiglia, persone e minori.",
    },
    "provvedimento_urgente": {
        "label": "Provvedimento urgente o cautelare",
        "template_id": "relata_provvedimento_urgente",
        "required_fields": ("procedimento.ufficio", "provvedimento.data"),
        "proceeding_required": True,
        "note": "Per provvedimenti cautelari o urgenti.",
    },
    "accordo_transazione_stragiudiziale": {
        "label": "Accordo o transazione stragiudiziale",
        "template_id": "relata_accordo_transazione_stragiudiziale",
        "required_fields": (),
        "proceeding_required": False,
        "note": "Per accordi, transazioni o atti negoziali da notificare.",
    },
}

LEGAL_NOTIFICATION_SOURCE_REFERENCES: tuple[dict[str, str], ...] = (
    {
        "id": "l53_art3bis",
        "label": "L. 21 gennaio 1994, n. 53, art. 3-bis",
        "rule": "Notifica a mezzo PEC, oggetto obbligatorio, relata, pubblico elenco e dati essenziali della relazione.",
    },
    {
        "id": "l53_art3ter",
        "label": "L. 21 gennaio 1994, n. 53, art. 3-ter",
        "rule": "Obbligo di notifica telematica quando ricorrono i presupposti e area web PST nei casi di mancata notifica imputabile al destinatario.",
    },
    {
        "id": "dl179_art16ter",
        "label": "D.L. 18 ottobre 2012, n. 179, art. 16-ter",
        "rule": "Individuazione dei pubblici elenchi utilizzabili per notificazioni e comunicazioni.",
    },
    {
        "id": "dl179_art16decies",
        "label": "D.L. 18 ottobre 2012, n. 179, art. 16-decies",
        "rule": "Potere di attestazione di conformità delle copie informatiche estratte dal fascicolo informatico e dai registri telematici.",
    },
    {
        "id": "dl179_art16septies",
        "label": "D.L. 18 ottobre 2012, n. 179, art. 16-septies",
        "rule": "Regole temporali delle notifiche telematiche, lette con Corte cost. 75/2019.",
    },
    {
        "id": "corte_cost_75_2019",
        "label": "Corte costituzionale, sentenza 75/2019",
        "rule": "La notifica PEC tra le 21:00 e le 24:00 si perfeziona per il notificante alla generazione della RAC, restando la tutela oraria per il destinatario.",
    },
    {
        "id": "dpr68_art6_8",
        "label": "D.P.R. 11 febbraio 2005, n. 68, artt. 6 e 8",
        "rule": "Ricevuta di accettazione, ricevuta di avvenuta consegna e avviso di mancata consegna PEC.",
    },
    {
        "id": "dm44_art18",
        "label": "D.M. 21 febbraio 2011, n. 44, art. 18",
        "rule": "Notificazioni per via telematica eseguite dagli avvocati e ricevuta completa.",
    },
    {
        "id": "pst_xsd_unep_2024",
        "label": "PST, XSD UNEP 06/11/2024 e messa in esercizio 18/11/2024",
        "rule": "Canale telematico autonomo per depositi presso gli Uffici NEP, distinto dal deposito PCT civile e dalla notifica PEC L. 53.",
    },
    {
        "id": "cpc_137_149",
        "label": "Artt. 137-149 c.p.c.",
        "rule": "Regole generali sulle notificazioni eseguite dall'ufficiale giudiziario e sui canali non PEC.",
    },
    {
        "id": "cpc_149",
        "label": "Art. 149 c.p.c.",
        "rule": "Notificazione a mezzo del servizio postale con prova della spedizione e della ricezione.",
    },
    {
        "id": "dgsia_2024_art21",
        "label": "Specifiche tecniche DGSIA 7 agosto 2024, art. 21",
        "rule": "Comunicazioni e notificazioni provenienti dall'ufficio giudiziario, Comunicazione.xml e ricevute conservate nel fascicolo informatico.",
    },
    {
        "id": "dgsia_2024_art22",
        "label": "Specifiche tecniche DGSIA 7 agosto 2024, art. 22",
        "rule": "Avviso di disponibilità, URL sicuro e area download quando la comunicazione/notificazione dell'ufficio contiene categorie particolari di dati personali.",
    },
    {
        "id": "dgsia_2024_art25",
        "label": "Specifiche tecniche DGSIA 7 agosto 2024, art. 25",
        "rule": "Rilascio delle copie di atti e documenti via PEC o avviso di disponibilità con prelievo tramite servizi PST.",
    },
    {
        "id": "dgsia_2024_art26",
        "label": "Specifiche tecniche DGSIA 7 agosto 2024, art. 26",
        "rule": "Notificazioni per via telematica eseguite dagli avvocati, formato degli atti, ricevute e inserimento dei riferimenti nel deposito.",
    },
    {
        "id": "dgsia_2024_art27",
        "label": "Specifiche tecniche DGSIA 7 agosto 2024, art. 27",
        "rule": "Attestazione di conformità su documento informatico separato e inserimento degli elementi nella relazione di notificazione quando la copia è destinata alla notifica.",
    },
    {
        "id": "specifiche_19bis_storico",
        "label": "Specifiche tecniche PCT 2014, art. 19-bis (storico)",
        "rule": "Riferimento storico sostituito dalle specifiche DGSIA 2024 per atti notificati, ricevute e deposito prova.",
    },
    {
        "id": "disp_att_cpp_56bis",
        "label": "Art. 56-bis disp. att. c.p.p.",
        "rule": "Nel penale la relazione di notificazione del difensore è documento informatico separato, sottoscritto con firma digitale o altra firma elettronica qualificata.",
    },
    {
        "id": "disp_att_cpc_196undecies",
        "label": "Art. 196-undecies disp. att. c.p.c.",
        "rule": "Modalità dell'attestazione di conformità, anche su documento informatico separato secondo le specifiche tecniche DGSIA.",
    },
    {
        "id": "cpc_170",
        "label": "Art. 170 c.p.c.",
        "rule": "Dopo la costituzione in giudizio le notificazioni e comunicazioni si fanno al procuratore costituito, salvo diversa disposizione.",
    },
    {
        "id": "cpc_285",
        "label": "Art. 285 c.p.c.",
        "rule": "Modo di notificazione della sentenza ai fini processuali.",
    },
    {
        "id": "cpc_325",
        "label": "Art. 325 c.p.c.",
        "rule": "Termini brevi per le impugnazioni.",
    },
    {
        "id": "cpc_326",
        "label": "Art. 326 c.p.c.",
        "rule": "Decorrenza dei termini brevi dalla notificazione della sentenza.",
    },
    {
        "id": "cpc_330",
        "label": "Art. 330 c.p.c.",
        "rule": "Luogo della notificazione dell'impugnazione secondo difensore, domicilio eletto o residenza dichiarata.",
    },
    {
        "id": "cpc_480",
        "label": "Art. 480 c.p.c.",
        "rule": "Precetto e destinatario del titolo esecutivo prima dell'esecuzione.",
    },
    {
        "id": "cpc_543",
        "label": "Art. 543 c.p.c.",
        "rule": "Pignoramento presso terzi da notificare al terzo e al debitore.",
    },
    {
        "id": "cpc_643",
        "label": "Art. 643 c.p.c.",
        "rule": "Notificazione del decreto ingiuntivo al debitore/ingiunto.",
    },
)

LEGAL_NOTIFICATION_SOURCE_BY_ID = {item["id"]: item for item in LEGAL_NOTIFICATION_SOURCE_REFERENCES}


def _legal_source_rows(*ids: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for source_id in ids:
        row = LEGAL_NOTIFICATION_SOURCE_BY_ID.get(source_id)
        if row:
            rows.append(dict(row))
    return rows


ROLE_DIRECTIVE_LEGAL_SOURCES: dict[str, tuple[str, ...]] = {
    "controparte": ("l53_art3bis", "l53_art3ter", "dl179_art16ter", "dgsia_2024_art26"),
    "difensore": ("l53_art3bis", "l53_art3ter", "dl179_art16ter", "cpc_170", "dgsia_2024_art26"),
    "impresa": ("l53_art3bis", "l53_art3ter", "dl179_art16ter", "dgsia_2024_art26"),
    "professionista": ("l53_art3bis", "l53_art3ter", "dl179_art16ter", "dgsia_2024_art26"),
    "pa": ("l53_art3bis", "l53_art3ter", "dl179_art16ter", "dgsia_2024_art26"),
    "terzo": ("l53_art3bis", "l53_art3ter", "dl179_art16ter", "dgsia_2024_art26"),
}

CASE_DIRECTIVE_LEGAL_SOURCES: dict[str, tuple[str, ...]] = {
    "ordinaria": ("l53_art3bis", "l53_art3ter", "dm44_art18", "dgsia_2024_art26"),
    "in_corso_di_causa": ("l53_art3bis", "l53_art3ter", "dm44_art18", "cpc_170", "dgsia_2024_art26"),
    "provvedimento_giudice": (
        "l53_art3bis",
        "l53_art3ter",
        "dm44_art18",
        "dgsia_2024_art21",
        "dgsia_2024_art22",
        "dgsia_2024_art25",
        "dgsia_2024_art26",
        "dgsia_2024_art27",
    ),
    "sentenza_termine_breve": (
        "l53_art3bis",
        "l53_art3ter",
        "dl179_art16decies",
        "dm44_art18",
        "cpc_170",
        "cpc_285",
        "cpc_325",
        "cpc_326",
        "cpc_330",
        "dgsia_2024_art26",
        "dgsia_2024_art27",
        "disp_att_cpc_196undecies",
    ),
    "decreto_ingiuntivo": ("l53_art3bis", "l53_art3ter", "dm44_art18", "cpc_643", "dgsia_2024_art26"),
    "titolo_esecutivo_precetto": ("l53_art3bis", "l53_art3ter", "dm44_art18", "cpc_480", "dgsia_2024_art26"),
    "atto_stragiudiziale": ("l53_art3bis", "l53_art3ter", "dl179_art16ter", "dgsia_2024_art26"),
    "rinnovo_notifica": ("l53_art3bis", "l53_art3ter", "dm44_art18", "dgsia_2024_art26"),
    "integrazione_contraddittorio": ("l53_art3bis", "l53_art3ter", "dm44_art18", "cpc_170", "dgsia_2024_art26"),
    "chiamata_terzo": ("l53_art3bis", "l53_art3ter", "dm44_art18", "dgsia_2024_art26"),
    "riassunzione": ("l53_art3bis", "l53_art3ter", "dm44_art18", "cpc_170", "dgsia_2024_art26"),
    "appello_impugnazione": ("l53_art3bis", "l53_art3ter", "dm44_art18", "cpc_330", "dgsia_2024_art26"),
    "reclamo_cautelare": ("l53_art3bis", "l53_art3ter", "dm44_art18", "dgsia_2024_art26"),
    "sfratto_convalida": ("l53_art3bis", "l53_art3ter", "dm44_art18", "dgsia_2024_art26"),
    "pignoramento_presso_terzi": ("l53_art3bis", "l53_art3ter", "dm44_art18", "cpc_543", "dgsia_2024_art26"),
    "intervento_esecuzione": ("l53_art3bis", "l53_art3ter", "dm44_art18", "dgsia_2024_art26"),
    "opposizione_decreto_ingiuntivo": ("l53_art3bis", "l53_art3ter", "dm44_art18", "cpc_643", "dgsia_2024_art26"),
    "opposizione_esecutiva": ("l53_art3bis", "l53_art3ter", "dm44_art18", "dgsia_2024_art26"),
    "famiglia_persone_minori": ("l53_art3bis", "l53_art3ter", "dm44_art18", "cpc_170", "dgsia_2024_art26"),
    "provvedimento_urgente": ("l53_art3bis", "l53_art3ter", "dm44_art18", "dgsia_2024_art26"),
    "accordo_transazione_stragiudiziale": ("l53_art3bis", "l53_art3ter", "dl179_art16ter", "dgsia_2024_art26"),
}

CASE_ALLOWED_RECIPIENT_ROLES: dict[str, tuple[str, ...]] = {
    "ordinaria": ("controparte", "difensore", "pa", "impresa", "professionista", "terzo"),
    "in_corso_di_causa": ("controparte", "difensore", "pa", "impresa", "professionista", "terzo"),
    "provvedimento_giudice": ("controparte", "difensore", "pa", "impresa", "professionista", "terzo"),
    "sentenza_termine_breve": ("difensore", "controparte", "impresa", "professionista", "pa"),
    "decreto_ingiuntivo": ("controparte", "impresa", "professionista", "pa"),
    "titolo_esecutivo_precetto": ("controparte", "impresa", "professionista", "pa"),
    "atto_stragiudiziale": ("controparte", "pa", "impresa", "professionista", "terzo"),
    "rinnovo_notifica": ("controparte", "difensore", "pa", "impresa", "professionista", "terzo"),
    "integrazione_contraddittorio": ("controparte", "difensore", "pa", "impresa", "professionista", "terzo"),
    "chiamata_terzo": ("terzo",),
    "riassunzione": ("controparte", "difensore", "pa", "impresa", "professionista", "terzo"),
    "appello_impugnazione": ("difensore", "controparte", "impresa", "professionista", "pa"),
    "reclamo_cautelare": ("controparte", "difensore", "pa", "impresa", "professionista", "terzo"),
    "sfratto_convalida": ("controparte", "impresa", "professionista"),
    "pignoramento_presso_terzi": ("controparte", "impresa", "professionista", "terzo"),
    "intervento_esecuzione": ("controparte", "impresa", "professionista", "terzo"),
    "opposizione_decreto_ingiuntivo": ("difensore", "controparte", "impresa", "professionista", "pa"),
    "opposizione_esecutiva": ("controparte", "difensore", "pa", "impresa", "professionista", "terzo"),
    "famiglia_persone_minori": ("controparte", "difensore", "pa", "terzo"),
    "provvedimento_urgente": ("controparte", "difensore", "pa", "impresa", "professionista", "terzo"),
    "accordo_transazione_stragiudiziale": ("controparte", "pa", "impresa", "professionista", "terzo"),
}

CASE_RECIPIENT_RULES: dict[str, str] = {
    "ordinaria": "Il destinatario viene dalla pratica o dall'atto da notificare; il cliente resta fuori dal percorso di notifica.",
    "in_corso_di_causa": "Usare il soggetto processuale della fase pendente: parte o difensore costituito se il rito e l'atto lo richiedono.",
    "provvedimento_giudice": "Il provvedimento comunicato dall'ufficio si notifica al soggetto cui la parte intende far produrre gli effetti processuali, verificando costituzione e domicilio digitale.",
    "sentenza_termine_breve": "Per far decorrere il termine breve verificare se la notifica va al difensore costituito o alla parte non costituita secondo il caso concreto.",
    "decreto_ingiuntivo": "Destinatario ordinario è il debitore/ingiunto o il soggetto obbligato risultante dalla pratica.",
    "titolo_esecutivo_precetto": "Destinatario è il debitore o soggetto obbligato indicato dal titolo e dal precetto.",
    "atto_stragiudiziale": "Destinatario è il soggetto cui l'atto negoziale o stragiudiziale è rivolto.",
    "rinnovo_notifica": "Ripetere il destinatario imposto dal provvedimento di rinnovo o dalla notifica non valida.",
    "integrazione_contraddittorio": "Notificare ai soggetti da integrare o alle parti necessarie indicate dal provvedimento o dal rito.",
    "chiamata_terzo": "La chiamata richiede il terzo indicato/autorizzato; non va indirizzata automaticamente alla controparte già presente.",
    "riassunzione": "Destinatari sono le parti del processo da riassumere secondo provvedimento, evento interruttivo o norma applicabile.",
    "appello_impugnazione": "Destinatario è la controparte dell'impugnazione; se costituita, verificare notifica al difensore.",
    "reclamo_cautelare": "Destinatari sono le parti o i soggetti incisi dal provvedimento cautelare secondo il rito concreto.",
    "sfratto_convalida": "Destinatario è l'intimato/conduttore o soggetto tenuto al rilascio/pagamento.",
    "pignoramento_presso_terzi": "Il flusso deve distinguere debitore e terzo pignorato: entrambi possono essere destinatari necessari della notifica.",
    "intervento_esecuzione": "Destinatari sono debitore, parti o terzi della procedura esecutiva secondo il provvedimento o l'atto.",
    "opposizione_decreto_ingiuntivo": "Destinatario è la parte opposta o il difensore se costituito nel procedimento pertinente.",
    "opposizione_esecutiva": "Destinatari sono le parti della procedura esecutiva e gli eventuali terzi coinvolti.",
    "famiglia_persone_minori": "Destinatari e cautele dipendono dal provvedimento e dalla posizione processuale; richiede verifica professionale.",
    "provvedimento_urgente": "Destinatari sono le parti o i soggetti incisi dal provvedimento urgente/cautelare.",
    "accordo_transazione_stragiudiziale": "Destinatario è il soggetto obbligato o aderente indicato nell'accordo o nella pratica.",
}

DOCUMENT_ORIGIN_LABELS: dict[str, str] = {
    "nativo_digitale": "documento nativo digitale",
    "firmato_digitalmente": "documento firmato digitalmente",
    "originale_informatico": "originale informatico",
    "duplicato_informatico": "duplicato informatico",
    "copia_fascicolo_informatico": "copia informatica estratta dal fascicolo",
    "comunicazione_cancelleria": "copia da comunicazione di cancelleria",
    "scansione_analogico": "copia per immagine da originale analogico",
}

PORTAL_DOCUMENT_SOURCES = {
    "PORTALE_TELEMATICO",
    "PST",
    "POLISWEB",
    "PDP",
    "PAT",
    "PTT",
    "SIGIT",
}

LEGAL_NOTIFICATION_AUTOMATION_STEPS: tuple[dict[str, str], ...] = (
    {
        "id": "precompilazione",
        "title": "Precompilazione da pratica e studio",
        "body": "IUSENTRA propone avvocato, assistito, procedimento, destinatario e documenti già presenti nel fascicolo.",
        "source": "L. 53/1994, art. 3-bis, commi 5 e 6",
    },
    {
        "id": "documento_ufficio",
        "title": "Documento rilasciato dall'ufficio",
        "body": "Quando la PEC dell'ufficio comunica un documento da notificare, il percorso controlla che quel documento sia gia' nei documenti e atti o chiede di collegarlo prima della relata.",
        "source": "Specifiche tecniche DGSIA 7 agosto 2024, artt. 21, 22 e 25",
    },
    {
        "id": "pubblici_elenchi",
        "title": "Verifica PEC su pubblico elenco",
        "body": "Il percorso registra fonte, data e ora della verifica dell'indirizzo PEC del mittente e del destinatario.",
        "source": "L. 53/1994, art. 3-bis, comma 1; D.L. 179/2012, art. 16-ter",
    },
    {
        "id": "allegati",
        "title": "Preparazione allegati",
        "body": "Sono ammessi più documenti; per ciascun file vengono riportati nome, origine, eventuale attestazione e impronta del file quando disponibile.",
        "source": "Specifiche tecniche DGSIA 7 agosto 2024, art. 26",
    },
    {
        "id": "relata",
        "title": "Relata separata e attestazioni",
        "body": "Il sistema genera la relata separata e le attestazioni richieste; l'avvocato rivede e firma digitalmente prima dell'invio.",
        "source": "L. 53/1994, art. 3-bis, commi 2 e 5",
    },
    {
        "id": "pec",
        "title": "PEC con oggetto obbligatorio",
        "body": "L'oggetto è fissato alla formula prevista e la ricevuta richiesta resta completa.",
        "source": "L. 53/1994, art. 3-bis, commi 3 e 4; D.M. 44/2011, art. 18, comma 6",
    },
    {
        "id": "prova",
        "title": "Pacchetto prova e deposito",
        "body": "Dopo l'invio si conservano PEC inviata, RAC e RdAC complete in originale digitale e si prepara l'indicizzazione per il deposito.",
        "source": "L. 53/1994, art. 9; Specifiche tecniche DGSIA 7 agosto 2024, art. 26, comma 5",
    },
)

LEGAL_NOTIFICATION_DEPOSIT_STEPS: tuple[dict[str, str], ...] = (
    {
        "id": "atti",
        "title": "Raccolta atti notificati",
        "body": "La prova può includere più atti o allegati notificati, con nome e impronta del file.",
        "source": "Specifiche tecniche DGSIA 7 agosto 2024, art. 26, comma 5",
    },
    {
        "id": "ricevute",
        "title": "Ricevute originali",
        "body": "Per ogni destinatario servono RAC e RdAC completa in formato originale digitale .eml o .msg.",
        "source": "L. 53/1994, art. 3-bis, comma 3; D.M. 44/2011, art. 18, comma 6",
    },
    {
        "id": "dati_atto",
        "title": "Indicizzazione ricevute",
        "body": "I riferimenti delle ricevute sono preparati per il riepilogo del deposito.",
        "source": "Specifiche tecniche DGSIA 7 agosto 2024, art. 26, comma 5",
    },
    {
        "id": "audit",
        "title": "Audit e controllo finale",
        "body": "Il pacchetto prova registra file, impronte e controlli prima del deposito.",
        "source": "L. 53/1994, art. 9",
    },
)

LEGAL_NOTIFICATION_ATTACHMENT_RULES: tuple[dict[str, str], ...] = (
    {
        "id": "atto_o_provvedimento",
        "label": "Atto, provvedimento o documento da notificare",
        "source": "Specifiche tecniche DGSIA 7 agosto 2024, art. 26",
        "rule": "Va allegato alla PEC in formato PDF/PDF-A o come documento informatico firmato ammesso, senza elementi attivi quando si tratta di copia.",
    },
    {
        "id": "relata_separata_firmata",
        "label": "Relata di notificazione separata e firmata",
        "source": "L. 53/1994, art. 3-bis, comma 5",
        "rule": "La relata deve essere un documento informatico separato e sottoscritto con firma digitale prima dell'invio.",
    },
    {
        "id": "procura",
        "label": "Procura alle liti, se non gia' in atti o se necessaria",
        "source": "D.M. 44/2011, art. 18, comma 5",
        "rule": "Se la procura non e' gia' in atti e serve per la notifica, va allegata come documento informatico separato.",
    },
    {
        "id": "attestazione_conformita",
        "label": "Attestazione di conformita', quando richiesta",
        "source": "L. 53/1994, art. 3-bis, comma 2; D.M. 44/2011, art. 18",
        "rule": "Per copie da fascicolo, comunicazioni di cancelleria o scansioni analogiche l'attestazione deve essere presente, normalmente nella relata.",
    },
    {
        "id": "ricevute_deposito",
        "label": "PEC inviata, RAC e RdAC completa per il deposito prova",
        "source": "L. 53/1994, art. 9; Specifiche tecniche DGSIA 7 agosto 2024, art. 26, comma 5",
        "rule": "Non sono allegati della PEC di notifica: si conservano dopo l'invio e si depositano come prova della notifica.",
    },
    {
        "id": "eml_ufficio",
        "label": "EML della PEC dell'ufficio che comunica il rilascio",
        "source": "Specifiche tecniche DGSIA 7 agosto 2024, artt. 21, 22 e 25",
        "rule": "Quando il trigger nasce dalla cancelleria, l'EML originale della PEC d'ufficio va conservato come evidenza del rilascio e del documento da scaricare.",
    },
)

DOCUMENT_ORIGIN_ALIASES: dict[str, str] = {
    "nativo": "nativo_digitale",
    "nativo_digitale": "nativo_digitale",
    "documento_nativo_digitale": "nativo_digitale",
    "firmato": "firmato_digitalmente",
    "firmato_digitalmente": "firmato_digitalmente",
    "documento_firmato": "firmato_digitalmente",
    "originale": "originale_informatico",
    "originale_informatico": "originale_informatico",
    "documento_originale_informatico": "originale_informatico",
    "duplicato": "duplicato_informatico",
    "duplicato_informatico": "duplicato_informatico",
    "copia_fascicolo": "copia_fascicolo_informatico",
    "copia_fascicolo_informatico": "copia_fascicolo_informatico",
    "fascicolo_informatico": "copia_fascicolo_informatico",
    "provvedimento_da_fascicolo": "copia_fascicolo_informatico",
    "comunicazione_cancelleria": "comunicazione_cancelleria",
    "cancelleria": "comunicazione_cancelleria",
    "scansione": "scansione_analogico",
    "scansione_analogico": "scansione_analogico",
    "copia_immagine": "scansione_analogico",
}

ORIGINS_REQUIRING_ATTESTATION = {
    "copia_fascicolo_informatico",
    "comunicazione_cancelleria",
    "scansione_analogico",
}

AVAILABLE_TEMPLATE_FIELDS: tuple[dict[str, str], ...] = (
    {"group": "Pratica", "label": "Codice pratica", "token": "{{ pratica.codice }}"},
    {"group": "Avvocato", "label": "Avvocato notificante", "token": "{{ avvocato.full_name }}"},
    {"group": "Avvocato", "label": "Codice fiscale avvocato", "token": "{{ avvocato.codice_fiscale }}"},
    {"group": "Avvocato", "label": "Foro", "token": "{{ avvocato.foro }}"},
    {"group": "Avvocato", "label": "PEC notificante", "token": "{{ avvocato.pec }}"},
    {"group": "Avvocato", "label": "Indirizzo studio", "token": "{{ avvocato.studio }}"},
    {"group": "Avvocato", "label": "Indirizzo completo studio", "token": "{{ avvocato.studio_completo }}"},
    {"group": "Avvocato", "label": "CAP studio", "token": "{{ avvocato.studio_cap }}"},
    {"group": "Avvocato", "label": "Città studio", "token": "{{ avvocato.studio_citta }}"},
    {"group": "Avvocato", "label": "Provincia studio", "token": "{{ avvocato.studio_provincia }}"},
    {"group": "Avvocato", "label": "Firma avvocato in calce", "token": "{{ avvocato.firma_in_calce }}"},
    {"group": "Avvocato", "label": "Dicitura firma digitale", "token": "{{ avvocato.firma_digitale_dicitura }}"},
    {"group": "Assistito", "label": "Parte assistita", "token": "{{ cliente.nome_denominazione }}"},
    {"group": "Assistito", "label": "C.F. / P. IVA assistito", "token": "{{ cliente.codice_fiscale_piva }}"},
    {"group": "Procedimento", "label": "Ufficio giudiziario", "token": "{{ procedimento.ufficio }}"},
    {"group": "Procedimento", "label": "Sezione", "token": "{{ procedimento.sezione }}"},
    {"group": "Procedimento", "label": "Numero RG", "token": "{{ procedimento.numero_rg }}"},
    {"group": "Procedimento", "label": "Anno RG", "token": "{{ procedimento.anno_rg }}"},
    {"group": "Procedimento", "label": "Blocco procedimento", "token": "{{ blocco_procedimento }}"},
    {"group": "Destinatario", "label": "Destinatario", "token": "{{ destinatario.nome_denominazione }}"},
    {"group": "Destinatario", "label": "C.F. / P. IVA destinatario", "token": "{{ destinatario.codice_fiscale_piva }}"},
    {"group": "Destinatario", "label": "PEC destinatario", "token": "{{ destinatario.pec }}"},
    {"group": "Destinatario", "label": "Fonte PEC", "token": "{{ destinatario.fonte_pec }}"},
    {"group": "Destinatario", "label": "Data verifica PEC", "token": "{{ destinatario.data_verifica_pec }}"},
    {"group": "Destinatario", "label": "Ora verifica PEC", "token": "{{ destinatario.ora_verifica_pec }}"},
    {"group": "Documenti", "label": "Elenco documenti", "token": "{{ documenti_righe }}"},
    {"group": "Documenti", "label": "Elenco documenti riservato", "token": "{{ documenti_righe_privacy }}"},
    {"group": "Documenti", "label": "Attestazione di conformità dell'avvocato", "token": "{{ attestazioni_testo }}"},
    {"group": "Notifica", "label": "Luogo relata", "token": "{{ notifica.luogo }}"},
    {"group": "Notifica", "label": "Data relata", "token": "{{ notifica.data }}"},
    {"group": "Notifica", "label": "Ora relata", "token": "{{ notifica.ora }}"},
    {"group": "Notifica", "label": "Oggetto PEC L. 53", "token": "{{ notifica.oggetto_pec }}"},
    {"group": "Provvedimento", "label": "Tipo provvedimento", "token": "{{ provvedimento.tipo }}"},
    {"group": "Provvedimento", "label": "Numero provvedimento", "token": "{{ provvedimento.numero }}"},
    {"group": "Provvedimento", "label": "Anno provvedimento", "token": "{{ provvedimento.anno }}"},
    {"group": "Provvedimento", "label": "Data provvedimento", "token": "{{ provvedimento.data }}"},
    {"group": "Provvedimento", "label": "Data deposito / pubblicazione", "token": "{{ provvedimento.data_deposito }}"},
)

_OPERATIONAL_TEMPLATE_FIELDS = {
    "documenti_righe": "Elenco documenti",
    "documenti_righe_privacy": "Elenco documenti riservato",
    "attestazioni_testo": "Attestazione di conformità dell'avvocato",
    "blocco_procedimento": "Blocco procedimento",
}
_OPTIONAL_OPERATIONAL_TEMPLATE_FIELDS = {
    "attestazioni_testo",
    "blocco_procedimento",
}
_FORBIDDEN_TEMPLATE_TOKEN_CHARS = set("[]()")

CLIENT_COMMUNICATION_FIELDS: tuple[dict[str, str], ...] = (
    {"label": "Cliente", "token": "{{ cliente.nome }}"},
    {"label": "Codice pratica", "token": "{{ pratica.codice }}"},
    {"label": "Ufficio", "token": "{{ procedimento.ufficio }}"},
    {"label": "Numero RG", "token": "{{ procedimento.numero_rg }}"},
    {"label": "Anno RG", "token": "{{ procedimento.anno_rg }}"},
    {"label": "Riferimento procedimento", "token": "{{ procedimento.riferimento }}"},
    {"label": "Documento", "token": "{{ documento.descrizione }}"},
    {"label": "Studio", "token": "{{ studio.nome }}"},
    {"label": "Prossimi passi", "token": "{{ prossimi_passi }}"},
)


@dataclass(frozen=True)
class LegalWorkflowResult:
    ok: bool
    blockers: list[str]
    warnings: list[str]
    subject: str = ""
    body: str = ""
    relata_text: str = ""
    next_actions: tuple[str, ...] = ()
    template_id: str = ""
    template_label: str = ""
    template_version: str = ""
    selected_blocks: tuple[str, ...] = ()
    checklist_text: str = ""
    log_json: dict[str, Any] | None = None
    output_plan: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "blockers": self.blockers,
            "warnings": self.warnings,
            "subject": self.subject,
            "body": self.body,
            "relataText": self.relata_text,
            "nextActions": list(self.next_actions),
            "templateId": self.template_id,
            "templateLabel": self.template_label,
            "templateVersion": self.template_version,
            "selectedBlocks": list(self.selected_blocks),
            "checklistText": self.checklist_text,
            "logJson": self.log_json or {},
            "outputPlan": self.output_plan or {},
        }


def text(value: Any, fallback: str = "") -> str:
    return " ".join(str(value if value is not None else fallback).split()).strip()


def multiline_text(value: Any, fallback: str = "") -> str:
    raw = str(value if value is not None else fallback).replace("\r\n", "\n").replace("\r", "\n").strip()
    return "\n".join(line.rstrip() for line in raw.split("\n"))


def boolish(value: Any) -> bool:
    return value is True or str(value or "").strip().lower() in {"1", "true", "si", "yes", "on"}


def normalise_role(value: Any) -> str:
    raw = text(value).lower().replace(" ", "_").replace("-", "_")
    if raw in {"pubblica_amministrazione", "amministrazione"}:
        return "pa"
    if raw in {"difensore_controparte", "avvocato_controparte"}:
        return "difensore"
    if raw in {"societa", "societa_impresa", "azienda"}:
        return "impresa"
    return raw


def is_legal_notification_subject(value: Any) -> bool:
    return LEGAL_NOTIFICATION_SUBJECT in text(value).lower()


def normalise_public_register(value: Any) -> str:
    raw = text(value).lower().replace("-", "_").replace(" ", "_").replace(".", "")
    aliases = {
        "reginde": "reginde",
        "re_g_ind_e": "reginde",
        "registro_generale_indirizzi_elettronici": "reginde",
        "registro_generale_indirizzi_elettronici_reginde": "reginde",
        "inipec": "ini_pec",
        "ini_pec": "ini_pec",
        "inipec_professionisti": "ini_pec",
        "ini_pec_professionisti": "ini_pec",
        "inipec_imprese": "ini_pec",
        "ini_pec_imprese": "ini_pec",
        "registro_imprese": "registro_imprese",
        "registroimprese": "registro_imprese",
        "imprese": "registro_imprese",
        "registro_ppaa": "registro_ppaa",
        "registro_pst": "registro_ppaa",
        "pst": "registro_ppaa",
        "ipa": "registro_ppaa",
        "indice_pubbliche_amministrazioni": "registro_ppaa",
        "inad": "inad",
        "anpr": "anpr",
        "altro": "altro_pubblico_elenco",
        "altro_pubblico_elenco": "altro_pubblico_elenco",
    }
    return aliases.get(raw, raw)


def register_label(value: Any) -> str:
    key = normalise_public_register(value)
    return PUBLIC_PEC_REGISTERS.get(key, text(value))


def _normalise_identity(value: Any) -> str:
    return re.sub(r"[^A-Z0-9]", "", text(value).upper())


def _pec_verification_matches(
    evidence: Any,
    *,
    expected_pec: Any,
    expected_cf: Any,
    expected_source: Any,
) -> bool:
    if not isinstance(evidence, dict) or not boolish(evidence.get("verified")):
        return False
    address = text(
        evidence.get("pec_attesa")
        or evidence.get("address")
        or evidence.get("pec")
    ).lower()
    expected_address = text(expected_pec).lower()
    if not expected_address or address != expected_address:
        return False
    evidence_cf = _normalise_identity(
        evidence.get("codice_fiscale")
        or evidence.get("taxCode")
        or evidence.get("codiceFiscale")
    )
    required_cf = _normalise_identity(expected_cf)
    if required_cf and evidence_cf != required_cf:
        return False
    source = normalise_public_register(evidence.get("source"))
    required_source = normalise_public_register(expected_source)
    if not source or source != required_source or source not in PUBLIC_PEC_REGISTERS:
        return False
    checked_at = text(
        evidence.get("verified_at")
        or evidence.get("verifiedAt")
        or evidence.get("checked_at")
        or evidence.get("checkedAt")
    )
    evidence_sha256 = text(evidence.get("evidence_sha256") or evidence.get("evidenceSha256"))
    evidence_body_b64 = text(evidence.get("evidence_body_b64") or evidence.get("evidenceBodyBase64"))
    if not checked_at or not SHA256_HEX_RE.fullmatch(evidence_sha256) or not evidence_body_b64:
        return False
    try:
        evidence_body = base64.b64decode(evidence_body_b64, validate=True)
    except (ValueError, TypeError):
        return False
    if not evidence_body or len(evidence_body) > 2_000_000:
        return False
    if hashlib.sha256(evidence_body).hexdigest() != evidence_sha256.lower():
        return False
    evidence_text = evidence_body.decode("utf-8", errors="ignore")
    if expected_address not in evidence_text.lower():
        return False
    if required_cf and required_cf not in _normalise_identity(evidence_text):
        return False
    return not bool(re.search(r"radiat|cancellat|sospes|cessat|revocat", evidence_text, re.IGNORECASE))


def _sender_pec_verified(payload: dict[str, Any], context: dict[str, Any]) -> bool:
    evidence = payload.get("verifica_pec_mittente") or payload.get("mittente_verifica_pec")
    if isinstance(evidence, dict):
        return _pec_verification_matches(
            evidence,
            expected_pec=context["avvocato"]["pec"],
            expected_cf=context["avvocato"]["codice_fiscale"],
            expected_source=_first(payload, "avvocato.fonte_pec", "fonte_pec_mittente"),
        )
    return False


def _recipient_rows(payload: dict[str, Any], context: dict[str, Any]) -> list[dict[str, Any]]:
    rows = payload.get("destinatari")
    if isinstance(rows, list) and rows:
        return [item for item in rows if isinstance(item, dict)]
    return [{
        "pec": context["destinatario"]["pec"],
        "codice_fiscale_piva": context["destinatario"].get("codice_fiscale_piva", ""),
        "fonte_pec": context["destinatario"]["fonte_pec_key"],
    }]


def _recipients_pec_verified(payload: dict[str, Any], context: dict[str, Any]) -> bool:
    evidences = payload.get("verifiche_pec_destinatari") or payload.get("destinatari_verifiche_pec")
    if isinstance(evidences, list):
        evidence_rows = [item for item in evidences if isinstance(item, dict)]
        recipients = _recipient_rows(payload, context)
        if not recipients or len(evidence_rows) < len(recipients):
            return False
        for recipient in recipients:
            if not any(_pec_verification_matches(
                evidence,
                expected_pec=recipient.get("pec") or recipient.get("indirizzo_pec"),
                expected_cf=(
                    recipient.get("codice_fiscale_piva")
                    or recipient.get("codice_fiscale")
                    or recipient.get("cf")
                ),
                expected_source=recipient.get("fonte_pec") or recipient.get("fonte"),
            ) for evidence in evidence_rows):
                return False
        return True
    return False


def normalise_unep_notification_type(value: Any) -> str:
    raw = text(value).lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "": "mani",
        "a_mani": "mani",
        "mani": "mani",
        "manuale": "mani",
        "posta": "posta",
        "postale": "posta",
        "a_mezzo_posta": "posta",
        "raccomandata": "posta",
        "estero": "estero",
        "internazionale": "estero",
        "telematica": "telematica",
        "pec": "telematica",
        "digitale": "telematica",
    }
    return aliases.get(raw, raw if raw in UNEP_NOTIFICATION_TYPES else "mani")


def normalise_non_pec_notification_type(value: Any) -> str:
    raw = text(value).lower().replace("-", "_").replace(" ", "_")
    aliases = {
        "": "raccomandata",
        "rac": "raccomandata",
        "raccomandata_ar": "raccomandata",
        "raccomandata_a_r": "raccomandata",
        "posta": "raccomandata",
        "unep": "ufficiale_giudiziario",
        "ug": "ufficiale_giudiziario",
        "ufficiale": "ufficiale_giudiziario",
        "ufficiale_giudiziario": "ufficiale_giudiziario",
        "mani": "mani",
        "a_mani": "mani",
        "consegna_mani": "mani",
        "estero": "estero",
        "internazionale": "estero",
        "altro": "altro",
    }
    return aliases.get(raw, raw if raw in NON_PEC_NOTIFICATION_TYPES else "raccomandata")


def notification_directive_matrix() -> dict[str, list[dict[str, Any]]]:
    """Return the governed matrix used by UI, tests and validation."""

    roles = []
    for key, directive in RECIPIENT_NOTIFICATION_DIRECTIVES.items():
        roles.append(
            {
                "value": key,
                "label": text(directive.get("label")),
                "allowedRegisters": list(directive.get("allowed_registers") or ()),
                "templateId": text(directive.get("template_id")),
                "requiredFields": list(directive.get("required_fields") or ()),
                "note": text(directive.get("note")),
                "legalBasis": _legal_source_rows(*ROLE_DIRECTIVE_LEGAL_SOURCES.get(key, ())),
            }
        )
    cases = []
    for key, directive in NOTIFICATION_CASE_DIRECTIVES.items():
        cases.append(
            {
                "value": key,
                "label": text(directive.get("label")),
                "templateId": text(directive.get("template_id")),
                "requiredFields": list(directive.get("required_fields") or ()),
                "proceedingRequired": bool(directive.get("proceeding_required")),
                "note": text(directive.get("note")),
                "allowedRecipientRoles": list(CASE_ALLOWED_RECIPIENT_ROLES.get(key, LEGAL_RECIPIENT_ROLES)),
                "recipientRule": text(CASE_RECIPIENT_RULES.get(key)),
                "legalBasis": _legal_source_rows(*CASE_DIRECTIVE_LEGAL_SOURCES.get(key, ())),
            }
        )
    return {"roles": roles, "cases": cases}


def _normalise_notification_case(value: Any) -> str:
    raw = text(value).lower().replace("-", "_").replace(" ", "_").replace("/", "_")
    aliases = {
        "": "ordinaria",
        "base": "ordinaria",
        "notifica_ordinaria": "ordinaria",
        "l53": "ordinaria",
        "l_53": "ordinaria",
        "corso_causa": "in_corso_di_causa",
        "procedimento": "in_corso_di_causa",
        "provvedimento": "provvedimento_giudice",
        "provvedimento_da_fascicolo": "provvedimento_giudice",
        "provvedimento_ufficio": "provvedimento_giudice",
        "termine_breve": "sentenza_termine_breve",
        "sentenza": "sentenza_termine_breve",
        "decreto": "decreto_ingiuntivo",
        "di": "decreto_ingiuntivo",
        "precetto": "titolo_esecutivo_precetto",
        "titolo_precetto": "titolo_esecutivo_precetto",
        "stragiudiziale": "atto_stragiudiziale",
        "rinnovo": "rinnovo_notifica",
        "integrazione": "integrazione_contraddittorio",
        "contraddittorio": "integrazione_contraddittorio",
        "chiamata": "chiamata_terzo",
        "terzo": "chiamata_terzo",
        "appello": "appello_impugnazione",
        "impugnazione": "appello_impugnazione",
        "reclamo": "reclamo_cautelare",
        "sfratto": "sfratto_convalida",
        "pignoramento": "pignoramento_presso_terzi",
        "opposizione_di": "opposizione_decreto_ingiuntivo",
        "opposizione_esecuzione": "opposizione_esecutiva",
        "famiglia": "famiglia_persone_minori",
        "minori": "famiglia_persone_minori",
        "urgente": "provvedimento_urgente",
        "cautelare": "provvedimento_urgente",
        "accordo": "accordo_transazione_stragiudiziale",
        "transazione": "accordo_transazione_stragiudiziale",
    }
    return aliases.get(raw, raw if raw in NOTIFICATION_CASE_DIRECTIVES else "ordinaria")


def _explicit_notification_case(payload: dict[str, Any]) -> str:
    return text(
        _first(
            payload,
            "notifica.caso",
            "notifica.tipo",
            "caso_notifica",
            "tipo_notifica",
            "scenario_notifica",
            "notifica_case",
        )
    )


def notification_case_from_payload(payload: dict[str, Any]) -> str:
    explicit = _explicit_notification_case(payload)
    if explicit:
        return _normalise_notification_case(explicit)
    if boolish(payload.get("rinnovo_notifica")):
        return "rinnovo_notifica"
    if boolish(payload.get("integrazione_contraddittorio")):
        return "integrazione_contraddittorio"
    if boolish(payload.get("chiamata_terzo")):
        return "chiamata_terzo"
    if boolish(payload.get("riassunzione")) or text(_first(payload, "riassunzione.causa", "riassunzione_causa")):
        return "riassunzione"
    return "in_corso_di_causa" if boolish(payload.get("procedimento_pendente")) or boolish(_deep_get(payload, "procedimento.presente")) else "ordinaria"


def resolve_legal_notification_directive(payload: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    context = context or _build_context(payload, template=select_relata_template(payload))
    role = normalise_role(_first(payload, "destinatario.tipo", "ruolo_destinatario")) or context["destinatario"]["tipo"]
    case_id = notification_case_from_payload(payload)
    role_directive = RECIPIENT_NOTIFICATION_DIRECTIVES.get(role, RECIPIENT_NOTIFICATION_DIRECTIVES["terzo"])
    case_directive = NOTIFICATION_CASE_DIRECTIVES.get(case_id, NOTIFICATION_CASE_DIRECTIVES["ordinaria"])
    required_fields = list(dict.fromkeys([*(role_directive.get("required_fields") or ()), *(case_directive.get("required_fields") or ())]))
    allowed_case_roles = list(CASE_ALLOWED_RECIPIENT_ROLES.get(case_id, tuple(LEGAL_RECIPIENT_ROLES)))
    return {
        "role": role,
        "roleLabel": text(role_directive.get("label")),
        "caseId": case_id,
        "caseLabel": text(case_directive.get("label")),
        "allowedRegisters": list(role_directive.get("allowed_registers") or ()),
        "allowedRecipientRoles": allowed_case_roles,
        "requiredFields": required_fields,
        "proceedingRequired": bool(case_directive.get("proceeding_required")),
        "recommendedTemplateId": text(case_directive.get("template_id")) or text(role_directive.get("template_id")),
        "roleTemplateId": text(role_directive.get("template_id")),
        "caseTemplateId": text(case_directive.get("template_id")),
        "recipientRule": text(CASE_RECIPIENT_RULES.get(case_id)),
        "roleLegalBasis": _legal_source_rows(*ROLE_DIRECTIVE_LEGAL_SOURCES.get(role, ())),
        "caseLegalBasis": _legal_source_rows(*CASE_DIRECTIVE_LEGAL_SOURCES.get(case_id, ())),
        "attachmentRules": [dict(item) for item in LEGAL_NOTIFICATION_ATTACHMENT_RULES],
        "notes": [text(role_directive.get("note")), text(case_directive.get("note"))],
    }


def _validate_notification_directive(
    payload: dict[str, Any],
    context: dict[str, Any],
    template: dict[str, Any],
    blockers: list[str],
    warnings: list[str],
) -> dict[str, Any]:
    directive = resolve_legal_notification_directive(payload, context)
    source_key = context["destinatario"]["fonte_pec_key"]
    role = directive["role"]
    if role in LEGAL_RECIPIENT_ROLES and source_key and source_key not in directive["allowedRegisters"]:
        allowed = ", ".join(register_label(item) for item in directive["allowedRegisters"])
        blockers.append(block("PEC_DESTINATARIO_REGISTRO_INCOERENTE", f"La fonte PEC selezionata non è coerente con {directive['roleLabel']}; usa {allowed}."))
    if role in LEGAL_RECIPIENT_ROLES and role not in directive["allowedRecipientRoles"]:
        allowed_roles = ", ".join(text(RECIPIENT_NOTIFICATION_DIRECTIVES.get(item, {}).get("label"), item) for item in directive["allowedRecipientRoles"])
        blockers.append(block(
            "DESTINATARIO_CASO_INCOERENTE",
            f"Per il caso '{directive['caseLabel']}' il ruolo '{directive['roleLabel']}' non è tra i destinatari governati; verifica la casistica e seleziona: {allowed_roles}.",
        ))
    for path in directive["requiredFields"]:
        if not text(_context_lookup(context, path)):
            blockers.append(f"Completa il campo richiesto per il caso '{directive['caseLabel']}': {_field_label(template, path)}.")
    if directive["proceedingRequired"]:
        context["procedimento"]["presente"] = True
        _validate_proceeding(context, blockers)
    compatibility = template.get("compatibility") or {}
    allowed_roles = set(compatibility.get("recipient_roles") or [])
    if allowed_roles and role and role not in allowed_roles:
        blockers.append(block("MODELLO_DESTINATARIO_INCOERENTE", f"Il modello scelto non è compatibile con il destinatario '{directive['roleLabel']}'."))
    allowed_origins = set(compatibility.get("document_origins") or [])
    if allowed_origins:
        for document in context["documenti"]:
            if document["origine"] not in allowed_origins:
                blockers.append(block("MODELLO_DOCUMENTO_INCOERENTE", f"Il modello scelto non è compatibile con l'origine del documento {document['index']}."))
    if role == "terzo":
        warnings.append("Caso terzo destinatario: verifica espressamente titolo della notifica, ruolo e pubblico elenco prima dell'invio.")
    if directive["caseId"] in {"famiglia_persone_minori", "provvedimento_giudice", "provvedimento_urgente"}:
        warnings.append(f"Verifica professionale richiesta: {directive['recipientRule']}")
    return directive


def normalise_document_origin(value: Any) -> str:
    raw = text(value).lower().replace("-", "_").replace(" ", "_")
    return DOCUMENT_ORIGIN_ALIASES.get(raw, raw)


def needs_attestazione(origin: Any) -> bool:
    return normalise_document_origin(origin) in ORIGINS_REQUIRING_ATTESTATION


def block(code: str, message: str) -> str:
    return f"{code}: {message}"


def _normalise_portal_match(value: Any) -> str:
    return re.sub(r"[^a-z0-9]+", "", text(value).lower())


def _portal_reference_keys_from_mapping(item: dict[str, Any]) -> set[str]:
    keys = {
        text(item.get("id_documento")),
        text(item.get("id_cat")),
        text(item.get("id_repeatto")),
        text(item.get("msg_id")),
    }
    return {key for key in keys if key}


def _portal_reference_keys_from_document(document: Any) -> set[str]:
    keys = {
        text(getattr(document, "id_documento_portale", "")),
        text(getattr(document, "id_cat_portale", "")),
        text(getattr(document, "id_repeatto_portale", "")),
        text(getattr(document, "msg_id_portale", "")),
    }
    return {key for key in keys if key}


def _portal_name_keys_from_document(document: Any) -> set[str]:
    return {
        key
        for key in (
            _normalise_portal_match(getattr(document, "nome", "")),
            _normalise_portal_match(getattr(document, "nome_originale", "")),
            _normalise_portal_match(getattr(document, "nome_portale", "")),
        )
        if key
    }


def _portal_item_notification_hint(item: dict[str, Any], deposit: Any) -> bool:
    haystack = " ".join(
        text(value).lower()
        for value in (
            item.get("nome"),
            item.get("tipo"),
            item.get("tipo_atto"),
            item.get("mittente"),
            getattr(deposit, "tipo_atto", ""),
            getattr(deposit, "servizio_portale", ""),
        )
    )
    return any(
        token in haystack
        for token in (
            "notifica",
            "notificare",
            "relata",
            "sentenza",
            "ordinanza",
            "decreto",
            "provvedimento",
            "comunicazione",
            "cancelleria",
        )
    )


def released_office_documents_from_portal(fascicolo: Any) -> list[dict[str, Any]]:
    """Return portal-released office documents not yet represented as local files."""

    local_refs = {
        key
        for document in getattr(fascicolo, "documenti", []) or []
        for key in _portal_reference_keys_from_document(document)
    }
    local_names = {
        key
        for document in getattr(fascicolo, "documenti", []) or []
        for key in _portal_name_keys_from_document(document)
    }
    releases: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    for deposit in getattr(fascicolo, "depositi_pct", []) or []:
        portal_documents = list(getattr(deposit, "documenti_portale", []) or [])
        if not portal_documents:
            continue
        all_linked = bool(getattr(deposit, "documenti_ids", []) or []) and len(getattr(deposit, "documenti_ids", []) or []) >= len(portal_documents)
        for item in portal_documents:
            if not isinstance(item, dict):
                continue
            if "disponibile" in item and not boolish(item.get("disponibile")):
                continue
            ref_keys = _portal_reference_keys_from_mapping(item)
            name_key = _normalise_portal_match(item.get("nome"))
            acquired = bool((ref_keys & local_refs) or (name_key and name_key in local_names) or all_linked)
            if acquired:
                continue
            external_deposit_id = text(getattr(deposit, "id_deposito_esterno", "")) or text(item.get("id_deposito"))
            document_id = text(item.get("id_documento") or item.get("id_cat") or item.get("id_repeatto") or item.get("msg_id") or item.get("nome"))
            unique_key = (external_deposit_id, document_id, text(item.get("nome")))
            if unique_key in seen:
                continue
            seen.add(unique_key)
            service = text(getattr(deposit, "servizio_portale", "")) or text(item.get("servizio"))
            source = text(getattr(deposit, "fonte_portale", "")) or text(getattr(deposit, "fonte", "")) or "PST"
            releases.append({
                "fascicoloId": text(getattr(fascicolo, "id", "")),
                "fascicoloNumero": text(getattr(fascicolo, "numero", "")),
                "fascicoloTitolo": text(getattr(fascicolo, "titolo", "")),
                "ufficio": text(getattr(fascicolo, "tribunale", "")),
                "numeroRg": text(getattr(fascicolo, "numero_rg", "")),
                "annoRg": text(getattr(fascicolo, "anno_rg", "")),
                "depositoId": text(getattr(deposit, "id", "")),
                "idDepositoEsterno": external_deposit_id,
                "documentoId": document_id,
                "nome": text(item.get("nome")),
                "tipo": text(item.get("tipo") or item.get("tipo_atto") or getattr(deposit, "tipo_atto", "")),
                "dataDeposito": text(item.get("data_deposito") or getattr(deposit, "timestamp", ""))[:10],
                "mittente": text(item.get("mittente") or getattr(deposit, "pec_destinatario", "")),
                "fontePortale": source,
                "servizioPortale": service,
                "riferimentoPortale": next(iter(ref_keys), document_id),
                "notificaRichiesta": _portal_item_notification_hint(item, deposit),
            })
    releases.sort(key=lambda item: (item.get("dataDeposito") or "", item.get("nome") or ""), reverse=True)
    return releases


_OFFICE_EMAIL_HINTS = (
    "cancelleria",
    "tribunale",
    "corte",
    "ufficio giudiziario",
    "giudice di pace",
    "giustiziacert",
    "giustiziapec",
    "pst.giustizia",
    "postacert.giustizia",
)
_OFFICE_DOCUMENT_HINTS = (
    "sentenza",
    "ordinanza",
    "decreto",
    "provvedimento",
    "verbale",
    "comunicazione",
    "avviso",
)
_NOTIFICATION_REQUEST_HINTS = ("notific", "relata", "termine breve")
_DOCUMENT_FILENAME_RE = re.compile(
    r"(?P<name>[A-Za-z0-9][A-Za-z0-9._()\-]{1,180}\.(?:pdf(?:\.p7m)?|p7m|docx?|rtf))",
    re.IGNORECASE,
)


def _mapping_or_attr(value: Any, *names: str) -> Any:
    for name in names:
        if isinstance(value, dict) and name in value:
            return value.get(name)
        if hasattr(value, name):
            return getattr(value, name)
    return ""


def _email_text(email_obj: Any) -> str:
    attachments = " ".join(
        text(_mapping_or_attr(item, "nome", "nome_file", "filename", "name"))
        for item in list(_mapping_or_attr(email_obj, "allegati") or [])
    )
    return " ".join(
        text(value)
        for value in (
            _mapping_or_attr(email_obj, "mittente", "from"),
            _mapping_or_attr(email_obj, "mittente_nome", "from_name"),
            _mapping_or_attr(email_obj, "oggetto", "subject"),
            _mapping_or_attr(email_obj, "corpo_testo", "text"),
            _mapping_or_attr(email_obj, "corpo_html", "html"),
            attachments,
        )
        if text(value)
    )


def _normalise_office_document_name(value: Any) -> str:
    raw = Path(text(value)).name.casefold()
    if raw.endswith(".pdf.p7m"):
        raw = raw[:-4]
    if raw.endswith(".p7m") and ".pdf" not in raw:
        raw = raw[:-4]
    return re.sub(r"[^a-z0-9]+", "", raw)


def _normalise_rg_number(value: Any) -> str:
    raw = re.sub(r"\D+", "", text(value))
    return raw.lstrip("0") or raw


def _rg_pairs_from_text(value: Any) -> set[tuple[str, str]]:
    return {(_normalise_rg_number(match.group(1)), match.group(2)) for match in RG_PAIR_RE.finditer(text(value))}


def _fascicolo_reference_tokens(fascicolo: Any) -> dict[str, str]:
    numero_rg = text(getattr(fascicolo, "numero_rg", ""))
    anno_rg = text(getattr(fascicolo, "anno_rg", ""))
    return {
        "id": text(getattr(fascicolo, "id", "")),
        "numero": text(getattr(fascicolo, "numero", "")),
        "titolo": text(getattr(fascicolo, "titolo", "")),
        "ufficio": text(getattr(fascicolo, "tribunale", "")),
        "numero_rg": numero_rg,
        "anno_rg": anno_rg,
        "rg": f"{numero_rg}/{anno_rg}" if numero_rg and anno_rg else "",
    }


def _email_matches_fascicolo(email_obj: Any, fascicolo: Any) -> bool:
    refs = _fascicolo_reference_tokens(fascicolo)
    explicit = text(
        _mapping_or_attr(
            email_obj,
            "id_fascicolo",
            "fascicolo_id",
            "case_id",
            "id_pratica",
            "pratica_id",
        )
    )
    if explicit and explicit == refs["id"]:
        return True
    haystack = _email_text(email_obj).casefold()
    compact = re.sub(r"\s+", "", haystack)
    if refs["rg"]:
        email_rg_pairs = _rg_pairs_from_text(haystack)
        if email_rg_pairs:
            return (_normalise_rg_number(refs["numero_rg"]), refs["anno_rg"]) in email_rg_pairs
        rg_compact = re.sub(r"\s+", "", refs["rg"].casefold())
        if rg_compact in compact:
            return True
    if refs["numero"] and refs["numero"].casefold() in haystack:
        return True
    titolo = refs["titolo"].casefold()
    ufficio = refs["ufficio"].casefold()
    return bool(titolo and ufficio and titolo in haystack and ufficio in haystack)


def _email_is_from_office(email_obj: Any) -> bool:
    haystack = _email_text(email_obj).casefold()
    return any(hint in haystack for hint in _OFFICE_EMAIL_HINTS)


def _email_requests_notification(email_obj: Any) -> bool:
    haystack = _email_text(email_obj).casefold()
    has_request = any(hint in haystack for hint in _NOTIFICATION_REQUEST_HINTS)
    has_document = any(hint in haystack for hint in _OFFICE_DOCUMENT_HINTS) or bool(_DOCUMENT_FILENAME_RE.search(haystack))
    return bool(has_request and has_document)


def _office_email_attachment_rows(email_obj: Any) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for index, item in enumerate(list(_mapping_or_attr(email_obj, "allegati") or [])):
        name = text(_mapping_or_attr(item, "nome", "nome_file", "filename", "name"))
        if not name:
            continue
        lower = name.casefold()
        if not lower.endswith((".pdf", ".pdf.p7m", ".p7m", ".doc", ".docx", ".rtf")):
            continue
        rows.append(
            {
                "name": name,
                "sha256": text(_mapping_or_attr(item, "sha256", "hash_sha256")),
                "mime": text(_mapping_or_attr(item, "mime", "content_type")),
                "index": str(index),
            }
        )
    return rows


def _office_document_names_from_email(email_obj: Any) -> list[dict[str, str]]:
    rows = _office_email_attachment_rows(email_obj)
    seen = {_normalise_office_document_name(row["name"]) for row in rows}
    haystack = _email_text(email_obj)
    for match in _DOCUMENT_FILENAME_RE.finditer(haystack):
        name = text(match.group("name"))
        key = _normalise_office_document_name(name)
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append({"name": name, "sha256": "", "mime": "", "index": str(len(rows))})
    if not rows and _email_requests_notification(email_obj):
        rows.append({"name": "Documento comunicato dalla cancelleria", "sha256": "", "mime": "", "index": "0"})
    return rows


def _office_portal_service_from_email(email_obj: Any) -> str:
    haystack = _email_text(email_obj).casefold()
    for label in ("PolisWeb", "PST", "PDP", "PAT", "PTT", "SIGIT"):
        if label.casefold() in haystack:
            return label
    if "portale" in haystack:
        return "Portale Servizi"
    return ""


def _office_portal_key_from_service(service: Any) -> str:
    raw = text(service).casefold()
    if "pdp" in raw or "penal" in raw:
        return "pdp"
    if "pat" in raw or "siga" in raw or "amministrativ" in raw:
        return "pat"
    if "ptt" in raw or "sigit" in raw or "tributar" in raw:
        return "ptt"
    return "pst"


def _office_document_acquisition_href(
    fascicolo: Any,
    *,
    document_name: str,
    email_id: str,
    service: str,
    sha256: str = "",
) -> str:
    params = {
        "id_fasc": text(getattr(fascicolo, "id", "")),
        "numero": text(getattr(fascicolo, "numero_rg", "")),
        "anno": text(getattr(fascicolo, "anno_rg", "")),
        "ufficio": text(getattr(fascicolo, "tribunale", "")),
        "focus": "documenti",
        "mode": "update_existing",
        "single_document": "1",
        "documento": document_name,
        "pec_id": email_id,
        "hash": sha256,
        "non_duplicare_documenti": "1",
        "fase_successiva": "relata_notifica",
    }
    query = urlencode({key: value for key, value in params.items() if text(value)})
    return f"/portali/{_office_portal_key_from_service(service)}/acquisizione?{query}"


def _local_office_document_lookup(fascicolo: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    by_name: dict[str, Any] = {}
    by_hash: dict[str, Any] = {}
    for document in getattr(fascicolo, "documenti", []) or []:
        for value in (
            getattr(document, "nome", ""),
            getattr(document, "nome_originale", ""),
            getattr(document, "nome_portale", ""),
            getattr(document, "percorso", ""),
        ):
            key = _normalise_office_document_name(value)
            if key:
                by_name.setdefault(key, document)
        sha = text(getattr(document, "hash_sha256", "")).lower()
        if sha:
            by_hash.setdefault(sha, document)
    return by_name, by_hash


def office_notification_evidence_from_pec(fascicolo: Any, emails: list[Any] | tuple[Any, ...] | None) -> list[dict[str, Any]]:
    """Return office-document notification evidence derived from PEC messages."""

    by_name, by_hash = _local_office_document_lookup(fascicolo)
    evidence: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    refs = _fascicolo_reference_tokens(fascicolo)
    for email_obj in list(emails or []):
        if not _email_matches_fascicolo(email_obj, fascicolo):
            continue
        if not _email_is_from_office(email_obj):
            continue
        if not _email_requests_notification(email_obj):
            continue
        email_id = text(_mapping_or_attr(email_obj, "id", "message_id", "uid_imap")) or text(_mapping_or_attr(email_obj, "message_id"))
        email_date = text(_mapping_or_attr(email_obj, "data", "ricevuta_il", "timestamp"))[:10]
        sender = text(_mapping_or_attr(email_obj, "mittente_nome")) or text(_mapping_or_attr(email_obj, "mittente"))
        eml_file = text(_mapping_or_attr(email_obj, "eml_file", "pec_eml_file", "file_eml"))
        eml_sha256 = text(_mapping_or_attr(email_obj, "eml_sha256", "pec_eml_sha256", "sha256_eml"))
        message_id = text(_mapping_or_attr(email_obj, "message_id"))
        service = _office_portal_service_from_email(email_obj)
        for row in _office_document_names_from_email(email_obj):
            name = text(row.get("name"))
            key = _normalise_office_document_name(name) or f"pec-{email_id}-{row.get('index')}"
            unique = (email_id, key)
            if unique in seen:
                continue
            seen.add(unique)
            sha = text(row.get("sha256")).lower()
            acquired_doc = by_hash.get(sha) if sha else None
            if acquired_doc is None:
                acquired_doc = by_name.get(key)
            document_id = text(getattr(acquired_doc, "id", ""))
            acquisition_href = _office_document_acquisition_href(
                fascicolo,
                document_name=name,
                email_id=email_id,
                service=service,
                sha256=sha,
            )
            evidence.append(
                {
                    "fascicoloId": refs["id"],
                    "fascicoloNumero": refs["numero"],
                    "fascicoloTitolo": refs["titolo"],
                    "ufficio": refs["ufficio"],
                    "numeroRg": refs["numero_rg"],
                    "annoRg": refs["anno_rg"],
                    "documentoId": f"pec:{email_id}:{row.get('index')}",
                    "documentoLocaleId": document_id,
                    "nome": name,
                    "tipo": "Documento comunicato dall'ufficio",
                    "dataDeposito": email_date,
                    "mittente": sender,
                    "fontePortale": "PEC cancelleria",
                    "servizioPortale": service,
                    "riferimentoPortale": text(_mapping_or_attr(email_obj, "message_id")) or email_id,
                    "fonteControllo": "pec_cancelleria",
                    "pecId": email_id,
                    "pecMessageId": message_id,
                    "pecEmlFile": eml_file,
                    "pecEmlSha256": eml_sha256,
                    "pecHref": f"/email/messaggio/{quote(email_id)}" if email_id else "/email/",
                    "acquisitionHref": acquisition_href,
                    "acquisitionActionLabel": "Scarica dal portale",
                    "singleDocumentAcquisition": True,
                    "notificaRichiesta": True,
                    "acquisito": bool(acquired_doc),
                    "hashSha256": sha,
                }
            )
    evidence.sort(key=lambda item: (item.get("dataDeposito") or "", item.get("nome") or ""), reverse=True)
    return evidence


def released_office_documents_from_pec(fascicolo: Any, emails: list[Any] | tuple[Any, ...] | None) -> list[dict[str, Any]]:
    """Return PEC-communicated office documents not yet represented in Documenti e atti."""

    return [item for item in office_notification_evidence_from_pec(fascicolo, emails) if not item.get("acquisito")]


def _document_attestation_declared(document: dict[str, Any], payload: dict[str, Any]) -> bool:
    return boolish(document.get("attestazione_presente")) or boolish(document.get("attestazione_conformita_presente")) or boolish(
        payload.get("attestazione_conformita_presente")
    ) or boolish(payload.get("attestazione_presente")) or boolish(payload.get("attestazione_multipla"))


def _document_attestation_text_present(document: dict[str, Any], payload: dict[str, Any]) -> bool:
    return bool(
        multiline_text(document.get("attestazione_conformita"))
        or multiline_text(payload.get("attestazione_conformita"))
        or multiline_text(payload.get("attestazione_multipla_testo"))
        or _document_attestation_declared(document, payload)
    )


@lru_cache(maxsize=1)
def load_template_catalog() -> dict[str, Any]:
    payload = json.loads(TEMPLATE_CATALOG_PATH.read_text(encoding="utf-8"))
    templates = payload.get("templates")
    if not isinstance(templates, list) or not templates:
        raise RuntimeError("Catalogo modelli notifiche legali non valido.")
    return payload


def template_catalog_version() -> str:
    return text(load_template_catalog().get("catalog_version"), "2026.05.12")


@lru_cache(maxsize=1)
def load_client_communication_catalog() -> dict[str, Any]:
    payload = json.loads(CLIENT_COMMUNICATION_CATALOG_PATH.read_text(encoding="utf-8"))
    templates = payload.get("templates")
    if not isinstance(templates, list) or not templates:
        raise RuntimeError("Catalogo modelli comunicazione cliente non valido.")
    return payload


def client_communication_templates_version() -> str:
    return text(load_client_communication_catalog().get("catalog_version"), "comunicazioni-cliente-1.0")


def list_notification_templates(*, kind: str | None = None) -> list[dict[str, Any]]:
    templates = load_template_catalog()["templates"]
    if kind is None:
        return list(templates)
    return [item for item in templates if item.get("kind") == kind]


def list_client_communication_templates() -> list[dict[str, Any]]:
    return list(load_client_communication_catalog()["templates"])


def get_client_communication_template(template_id: Any) -> dict[str, Any] | None:
    raw = text(template_id).lower().strip()
    if not raw:
        return None
    normalised = raw.replace(" ", "_").replace("-", "_")
    for template in list_client_communication_templates():
        if normalised == text(template.get("id")).lower():
            return template
    return None


def available_template_fields() -> list[dict[str, str]]:
    """Return the guided field tokens that can be inserted in custom models."""

    return [dict(item) for item in AVAILABLE_TEMPLATE_FIELDS]


def _token_name(raw_token: str) -> str:
    raw = raw_token.strip()
    if raw.startswith("{{") and raw.endswith("}}"):
        return raw[2:-2].strip()
    return ""


def _iter_template_tokens(content: str):
    index = 0
    while index < len(content):
        start = content.find("{{", index)
        if start < 0:
            break
        end = content.find("}}", start + 2)
        if end < 0:
            break
        yield content[start + 2:end].strip()
        index = end + 2


def _is_identifier_path(value: str) -> bool:
    if not value or value.startswith(".") or value.endswith("."):
        return False
    parts = [part for part in value.split(".") if part]
    return bool(parts) and all(part.replace("_", "a").isalnum() and not part[0].isdigit() for part in parts)


def _token_has_forbidden_chars(token: str) -> bool:
    return any(char in _FORBIDDEN_TEMPLATE_TOKEN_CHARS for char in token)


def _iter_simple_if_tokens(content: str):
    index = 0
    while index < len(content):
        start = content.find("{%", index)
        if start < 0:
            break
        end = content.find("%}", start + 2)
        if end < 0:
            break
        directive = content[start + 2:end].strip()
        if directive.startswith("if "):
            token = directive[3:].strip()
            if _is_identifier_path(token):
                yield token
        index = end + 2


def _allowed_custom_template_tokens() -> set[str]:
    tokens = {
        _token_name(item["token"])
        for item in AVAILABLE_TEMPLATE_FIELDS
        if _token_name(item["token"])
    }
    tokens.update(_OPERATIONAL_TEMPLATE_FIELDS)
    return tokens


def _custom_template_token_labels() -> dict[str, str]:
    labels = {
        _token_name(item["token"]): item["label"]
        for item in AVAILABLE_TEMPLATE_FIELDS
        if _token_name(item["token"])
    }
    labels.update(_OPERATIONAL_TEMPLATE_FIELDS)
    return labels


def validate_custom_template_body(body: Any) -> list[str]:
    """Validate a studio-authored relata model without allowing free Jinja."""

    content = multiline_text(body)
    blockers: list[str] = []
    if not content:
        blockers.append("Inserisci il testo del modello relata.")
        return blockers
    if "{%" in content or "%}" in content:
        blockers.append("I modelli personalizzati non possono contenere istruzioni Jinja.")
    if "{#" in content or "#}" in content:
        blockers.append("I modelli personalizzati non possono contenere commenti Jinja.")
    if content.count("{{") != content.count("}}"):
        blockers.append("Controlla le parentesi dei campi automatici del modello.")

    allowed_tokens = _allowed_custom_template_tokens()
    for token in _iter_template_tokens(content):
        if "|" in token:
            blockers.append(f"Il campo automatico {{{{ {token} }}}} contiene un filtro non consentito.")
            continue
        if _token_has_forbidden_chars(token):
            blockers.append(f"Il campo automatico {{{{ {token} }}}} contiene una chiamata o un accesso non consentito.")
            continue
        if "__" in token or token.startswith(".") or ".__" in token:
            blockers.append(f"Il campo automatico {{{{ {token} }}}} contiene un accesso riservato non consentito.")
            continue
        if token not in allowed_tokens:
            blockers.append(f"Campo automatico non consentito: {{{{ {token} }}}}.")
    return list(dict.fromkeys(blockers))


def normalise_custom_template(raw: dict[str, Any]) -> dict[str, Any]:
    template_id = text(raw.get("id") or raw.get("value"))
    body = multiline_text(
        raw.get("custom_body")
        or raw.get("body")
        or raw.get("previewText")
        or raw.get("preview_text")
        or raw.get("testo")
    )
    fields = raw.get("fields") if isinstance(raw.get("fields"), list) else []
    return {
        "id": template_id,
        "code": text(raw.get("code"), "PERS"),
        "kind": "relata",
        "label": text(raw.get("label") or raw.get("nome"), "Modello personalizzato"),
        "description": text(raw.get("description") or raw.get("descrizione"), "Modello relata personalizzato dallo studio."),
        "custom": True,
        "custom_body": body,
        "requires_proceeding": boolish(raw.get("requires_proceeding")),
        "privacy_description": boolish(raw.get("privacy_description")),
        "required_fields": raw.get("required_fields") if isinstance(raw.get("required_fields"), list) else [],
        "fields": [field for field in fields if isinstance(field, dict)],
        "purpose_lines": [],
        "created_at": text(raw.get("created_at")),
        "created_by": text(raw.get("created_by")),
    }


def template_preview_text(template: dict[str, Any]) -> str:
    """Build a readable model body for preview and customisation."""

    custom_body = multiline_text(template.get("custom_body"))
    if custom_body:
        return custom_body
    privacy = bool(template.get("privacy_description"))
    lines = [
        "RELAZIONE DI NOTIFICAZIONE A MEZZO POSTA ELETTRONICA CERTIFICATA",
        "ai sensi dell'art. 3-bis della Legge 21 gennaio 1994, n. 53",
        "",
        "Io sottoscritto Avv. {{ avvocato.full_name }},",
        "C.F. {{ avvocato.codice_fiscale }},",
        "iscritto all'Ordine degli Avvocati di {{ avvocato.foro }},",
        "con studio in {{ avvocato.studio_completo }},",
        "indirizzo PEC {{ avvocato.pec }},",
        "",
        "nella qualita' di difensore di {{ cliente.nome_denominazione }},",
        "C.F./P.IVA {{ cliente.codice_fiscale_piva }},",
        "giusta procura alle liti in atti, allegata o rilasciata su separato documento,",
        "",
        "NOTIFICO",
        "",
        "a {{ destinatario.nome_denominazione }},",
        "C.F./P.IVA {{ destinatario.codice_fiscale_piva }},",
        "all'indirizzo PEC {{ destinatario.pec }},",
        "estratto dal pubblico elenco {{ destinatario.fonte_pec }} in data {{ destinatario.data_verifica_pec }} alle ore {{ destinatario.ora_verifica_pec }},",
        "",
        "i seguenti documenti informatici allegati al presente messaggio PEC:",
        "",
        "{{ documenti_righe_privacy }}" if privacy else "{{ documenti_righe }}",
        "",
        "{{ blocco_procedimento }}",
    ]
    purpose_lines = [multiline_text(line) for line in (template.get("purpose_lines") or []) if multiline_text(line)]
    if purpose_lines:
        lines.extend(["", *purpose_lines])
    lines.extend([
        "",
        "{{ attestazioni_testo }}",
        "",
        "{{ notifica.luogo }}, {{ notifica.data }} alle ore {{ notifica.ora }}",
        "",
        "{{ avvocato.firma_in_calce }}",
        "{{ avvocato.firma_digitale_dicitura }}",
    ])
    return "\n".join(lines).strip()


def _template_by_id() -> dict[str, dict[str, Any]]:
    index: dict[str, dict[str, Any]] = {}
    for template in list_notification_templates():
        template_id = text(template.get("id"))
        if template_id:
            index[template_id] = template
        code = text(template.get("code"))
        if code:
            index[code.lower()] = template
        for alias in template.get("aliases") or []:
            index[text(alias).lower()] = template
    return index


def get_notification_template(template_id: Any) -> dict[str, Any] | None:
    raw = text(template_id).lower().strip()
    if not raw:
        return None
    normalised = raw.replace(" ", "_").replace("-", "_")
    if normalised.startswith("relata_pec_a_societa"):
        normalised = "relata_pec_a_impresa_societa"
    if normalised == "relata_a_societa_impresa":
        normalised = "relata_pec_a_impresa_societa"
    return _template_by_id().get(normalised) or _template_by_id().get(raw)


def _deep_get(payload: Any, path: str) -> Any:
    current = payload
    for part in path.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
            continue
        return None
    return current


def _template_fields(payload: dict[str, Any]) -> dict[str, Any]:
    raw = payload.get("template_fields") or payload.get("campi_modello")
    return raw if isinstance(raw, dict) else {}


def _first(payload: dict[str, Any], *paths: str, fallback: Any = "") -> Any:
    extras = _template_fields(payload)
    for path in paths:
        value = _deep_get(payload, path)
        if text(value):
            return value
        snake = path.replace(".", "_")
        for source in (payload, extras):
            if isinstance(source, dict) and text(source.get(snake)):
                return source.get(snake)
            if isinstance(source, dict) and text(source.get(path)):
                return source.get(path)
    return fallback


def _first_bool(payload: dict[str, Any], *paths: str, fallback: bool = False) -> bool:
    for path in paths:
        value = _deep_get(payload, path)
        if value is not None and text(value) != "":
            return boolish(value)
        snake = path.replace(".", "_")
        if snake in payload:
            return boolish(payload.get(snake))
    return fallback


def _format_italian_date(value: Any, fallback: str = "") -> str:
    raw = text(value, fallback)
    if not raw:
        return ""
    date_part = raw.split("T", 1)[0].rsplit(" ", 1)[0]
    for pattern in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(date_part, pattern).strftime("%d/%m/%Y")
        except ValueError:
            continue
    return raw


def _split_datetime(value: Any) -> tuple[str, str]:
    raw = text(value)
    if "T" in raw:
        date, hour = raw.split("T", 1)
        return _format_italian_date(date), hour[:5]
    if " " in raw:
        date, hour = raw.rsplit(" ", 1)
        return _format_italian_date(date), hour[:5]
    return _format_italian_date(raw), ""


def _latest_verified_pec_timestamp(payload: dict[str, Any]) -> str:
    evidences: list[dict[str, Any]] = []
    sender = payload.get("verifica_pec_mittente") or payload.get("mittente_verifica_pec")
    if isinstance(sender, dict):
        evidences.append(sender)
    recipients = payload.get("verifiche_pec_destinatari") or payload.get("destinatari_verifiche_pec")
    if isinstance(recipients, list):
        evidences.extend(item for item in recipients if isinstance(item, dict))
    timestamps = [
        text(
            item.get("verified_at")
            or item.get("verifiedAt")
            or item.get("checked_at")
            or item.get("checkedAt")
        )
        for item in evidences
        if boolish(item.get("verified"))
    ]
    return max((item for item in timestamps if item), default="")


def _format_italian_time(value: Any, fallback: str = "") -> str:
    raw = text(value, fallback).strip()
    if not raw:
        return ""
    match = re.fullmatch(r"(\d{1,2}):(\d{2})(?::\d{2})?", raw)
    if not match:
        return raw
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        return raw
    return f"{hour:02d}:{minute:02d}"


def _normalise_lawyer_name(value: Any) -> str:
    clean = text(value)
    while True:
        stripped = re.sub(r"^(?:avv\.?|avvocato|avvocata)\s+", "", clean, flags=re.IGNORECASE).strip()
        if stripped == clean:
            return clean
        clean = stripped


def _documents(payload: dict[str, Any]) -> list[dict[str, Any]]:
    raw = payload.get("documenti")
    if isinstance(raw, list):
        source = [item for item in raw if isinstance(item, dict)]
    else:
        source = []
    if not source:
        single = {
            "nome_file": payload.get("nome_file") or payload.get("atto_file"),
            "descrizione": payload.get("descrizione_documento") or payload.get("atto_descrizione"),
            "descrizione_breve_privacy": payload.get("descrizione_breve_privacy"),
            "origine": payload.get("origine_documento") or payload.get("origine"),
            "hash_sha256": payload.get("hash_sha256"),
            "data_documento": payload.get("data_documento") or payload.get("dataDocumento"),
            "data_comunicazione_cancelleria": payload.get("data_comunicazione_cancelleria"),
            "attestazione_conformita": payload.get("attestazione_conformita"),
            "attestazione_conformita_presente": payload.get("attestazione_conformita_presente"),
            "fonte_documento": payload.get("fonte_documento"),
            "riferimento_portale": payload.get("riferimento_portale"),
            "servizio_portale": payload.get("servizio_portale"),
            "documento_ufficio": payload.get("documento_ufficio"),
            "notifica_richiesta": payload.get("notifica_richiesta"),
            "acquisito_da_portale": payload.get("acquisito_da_portale"),
            "data_rilascio_portale": payload.get("data_rilascio_portale"),
            "firma_digitale_richiesta": payload.get("firma_digitale_richiesta"),
            "firma_richiesta": payload.get("firma_richiesta"),
            "requires_signature": payload.get("requires_signature"),
            "requiresSignature": payload.get("requiresSignature"),
            "firmato_digitalmente": payload.get("firmato_digitalmente"),
        }
        if any(text(value) for value in single.values()):
            source = [single]

    documents: list[dict[str, Any]] = []
    for index, item in enumerate(source, start=1):
        origin = normalise_document_origin(item.get("origine"))
        description = text(item.get("descrizione"))
        privacy_description = text(item.get("descrizione_breve_privacy"), description)
        source_name = text(item.get("fonte_documento") or item.get("fonte") or item.get("source"))
        portal_service = text(item.get("servizio_portale") or item.get("portale") or item.get("portal"))
        portal_reference = text(
            item.get("riferimento_portale")
            or item.get("riferimentoPortale")
            or item.get("id_documento_portale")
            or item.get("idDocumentoPortale")
        )
        portal_source = source_name.upper() in PORTAL_DOCUMENT_SOURCES or portal_service.upper() in PORTAL_DOCUMENT_SOURCES
        acquired_from_portal = boolish(item.get("acquisito_da_portale") or item.get("acquisitoDaPortale")) or bool(portal_reference or portal_source)
        notification_required = boolish(item.get("notifica_richiesta") or item.get("notificaRichiesta"))
        signature_required = boolish(
            item.get("firma_digitale_richiesta")
            or item.get("firma_richiesta")
            or item.get("requires_signature")
            or item.get("requiresSignature")
        )
        digitally_signed = boolish(item.get("firmato_digitalmente") or item.get("digitallySigned"))
        office_document = (
            boolish(item.get("documento_ufficio") or item.get("documentoUfficio"))
            or origin == "comunicazione_cancelleria"
            or (origin == "copia_fascicolo_informatico" and notification_required)
        )
        documents.append({
            "index": index,
            "nome_file": text(item.get("nome_file") or item.get("file")),
            "descrizione": description,
            "descrizione_breve_privacy": privacy_description,
            "origine": origin,
            "origine_label": DOCUMENT_ORIGIN_LABELS.get(origin, text(item.get("origine"))),
            "necessita_attestazione": boolish(item.get("necessita_attestazione")) or origin in ORIGINS_REQUIRING_ATTESTATION,
            "hash_sha256": text(item.get("hash_sha256")),
            "data_documento": _format_italian_date(item.get("data_documento") or item.get("dataDocumento")),
            "fonte_documento": source_name,
            "riferimento_portale": portal_reference,
            "servizio_portale": portal_service,
            "documento_ufficio": office_document,
            "notifica_richiesta": notification_required,
            "acquisito_da_portale": acquired_from_portal,
            "data_rilascio_portale": _format_italian_date(item.get("data_rilascio_portale") or item.get("dataRilascioPortale")),
            "firma_digitale_richiesta": signature_required,
            "firma_richiesta": signature_required,
            "requires_signature": signature_required,
            "requiresSignature": signature_required,
            "firmato_digitalmente": digitally_signed,
            "attestazione_conformita": multiline_text(item.get("attestazione_conformita")),
            "attestazione_conformita_presente": boolish(item.get("attestazione_conformita_presente") or item.get("attestazione_presente")),
            "data_comunicazione_cancelleria": _format_italian_date(
                item.get("data_comunicazione_cancelleria"),
                text(payload.get("data_comunicazione_cancelleria")),
            ),
        })
    return documents


def _office_document_acquisition_state(payload: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    documents = context["documenti"]
    office_documents = [
        document
        for document in documents
        if document["documento_ufficio"]
        and (
            document["acquisito_da_portale"]
            or document["riferimento_portale"]
            or text(document["fonte_documento"]).upper() in PORTAL_DOCUMENT_SOURCES
            or document["origine"] == "comunicazione_cancelleria"
        )
    ]
    release_detected = (
        boolish(payload.get("documento_ufficio_rilasciato"))
        or boolish(payload.get("documentoUfficioRilasciato"))
        or boolish(payload.get("pec_ufficio_rilascio"))
        or boolish(_deep_get(payload, "pec_ufficio.rilascio_documento"))
        or any(document["notifica_richiesta"] and document["documento_ufficio"] for document in documents)
    )
    acquisition_required = release_detected or boolish(payload.get("acquisizione_portale_richiesta")) or boolish(
        payload.get("acquisizionePortaleRichiesta")
    )
    acquired = (
        boolish(payload.get("documento_ufficio_acquisito"))
        or boolish(payload.get("documentoUfficioAcquisito"))
        or boolish(payload.get("acquisizione_portale_completata"))
        or boolish(payload.get("acquisizionePortaleCompletata"))
        or bool(office_documents)
    )
    return {
        "releaseDetected": bool(release_detected),
        "acquisitionRequired": bool(acquisition_required),
        "acquired": bool(acquired),
        "blocking": bool(acquisition_required and not acquired),
        "documentsCount": len(office_documents),
        "documents": [
            {
                "name": document["nome_file"],
                "description": document["descrizione"],
                "source": document["fonte_documento"],
                "portal": document["servizio_portale"],
                "reference": document["riferimento_portale"],
                "releasedAt": document["data_rilascio_portale"],
                "notificationRequired": bool(document["notifica_richiesta"]),
            }
            for document in office_documents
        ],
    }


def _office_pec_eml_state(payload: dict[str, Any]) -> dict[str, Any]:
    release_detected = (
        boolish(payload.get("documento_ufficio_rilasciato"))
        or boolish(payload.get("documentoUfficioRilasciato"))
        or boolish(payload.get("pec_ufficio_rilascio"))
        or boolish(_deep_get(payload, "pec_ufficio.rilascio_documento"))
        or boolish(_deep_get(payload, "documento_ufficio.pec_rilascio"))
    )
    eml_file = text(
        _first(
            payload,
            "pec_ufficio.eml_file",
            "pec_ufficio.file_eml",
            "pec_ufficio_eml",
            "pec_ufficio_eml_file",
            "eml_pec_ufficio",
        )
    )
    eml_sha256 = text(_first(payload, "pec_ufficio.sha256", "pec_ufficio_eml_sha256", "eml_pec_ufficio_sha256"))
    message_id = text(_first(payload, "pec_ufficio.message_id", "pec_ufficio_message_id", "message_id_pec_ufficio"))
    return {
        "required": release_detected,
        "present": not release_detected or bool(eml_file or message_id),
        "emlFile": eml_file,
        "sha256": eml_sha256,
        "messageId": message_id,
    }


def _has_procura_document(documents: list[dict[str, Any]]) -> bool:
    for document in documents:
        haystack = f"{document['nome_file']} {document['descrizione']}".lower()
        if "procura" in haystack:
            return True
    return False


def build_notification_attachment_manifest(
    payload: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    context = context or _build_context(payload, template=select_relata_template(payload))
    documents = context["documenti"]
    attestation_required = any(document["necessita_attestazione"] for document in documents)
    procura_required = boolish(_first(payload, "procura_necessaria", "procura.necessaria", fallback=False))
    procura_in_atti = boolish(_first(payload, "procura_in_atti", "procura.in_atti", fallback=False))
    procura_attached = _has_procura_document(documents) or boolish(_first(payload, "procura_allegata", "procura.allegata", fallback=False))
    return [
        {
            "id": "atto_o_provvedimento",
            "label": "Atto, provvedimento o documento da notificare",
            "phase": "pec_notifica",
            "required": True,
            "present": bool(documents),
            "detail": f"{len(documents)} documento/i selezionati.",
            "source": "Specifiche tecniche DGSIA 7 agosto 2024, artt. 21, 22 e 25",
        },
        {
            "id": "relata_separata_firmata",
            "label": "Relata separata firmata digitalmente",
            "phase": "pec_notifica",
            "required": True,
            "present": boolish(_first(payload, "notifica.relata_documento_separato", "relata_documento_separato"))
            and boolish(_first(payload, "notifica.relata_firmata", "relata_firmata")),
            "detail": "Documento informatico separato, firmato prima dell'invio.",
            "source": "L. 53/1994, art. 3-bis, comma 5",
        },
        {
            "id": "procura",
            "label": "Procura alle liti",
            "phase": "pec_notifica",
            "required": procura_required and not procura_in_atti,
            "present": (not procura_required) or procura_in_atti or procura_attached,
            "detail": "Da allegare se necessaria e non gia' presente in atti.",
            "source": "D.M. 44/2011, art. 18, comma 5",
        },
        {
            "id": "attestazione_conformita",
            "label": "Attestazione di conformita'",
            "phase": "pec_notifica",
            "required": attestation_required,
            "present": not attestation_required
            or all(_document_attestation_text_present(document, payload) for document in documents if document["necessita_attestazione"]),
            "detail": "Richiesta per copie da fascicolo, cancelleria o scansioni analogiche.",
            "source": "L. 53/1994, art. 3-bis, comma 2",
        },
        {
            "id": "eml_ufficio",
            "label": "EML PEC ufficio che comunica il rilascio",
            "phase": "evidenza_pre_notifica",
            **_office_pec_eml_state(payload),
            "detail": "Serve a certificare il trigger PEC e il documento comunicato dall'ufficio.",
            "source": "Specifiche tecniche DGSIA 7 agosto 2024, artt. 21, 22 e 25",
        },
        {
            "id": "ricevute_deposito",
            "label": "PEC inviata, RAC e RdAC completa",
            "phase": "deposito_prova",
            "required": False,
            "present": boolish(payload.get("ricevuta_completa")),
            "detail": "Si generano dopo l'invio e non vanno allegati alla PEC di notifica.",
            "source": "L. 53/1994, art. 9; Specifiche tecniche DGSIA 7 agosto 2024, art. 26, comma 5",
        },
    ]


def _delivery_recipients_from_payload(payload: dict[str, Any], context: dict[str, Any]) -> list[dict[str, Any]]:
    raw_recipients = payload.get("destinatari")
    rows: list[dict[str, Any]] = []
    if isinstance(raw_recipients, list) and raw_recipients:
        for index, item in enumerate(raw_recipients, start=1):
            row = item if isinstance(item, dict) else {}
            name = text(row.get("nome") or row.get("name") or row.get("destinatario_nome"))
            pec = text(row.get("pec") or row.get("email") or row.get("destinatario_pec"))
            role = normalise_role(row.get("ruolo") or row.get("role") or row.get("ruolo_destinatario") or context["destinatario"]["tipo"])
            rows.append(
                {
                    "index": index,
                    "name": name,
                    "pec": pec,
                    "role": role,
                    "source": text(row.get("fonte_pec") or row.get("source") or row.get("fontePec") or context["destinatario"]["fonte_pec_key"]),
                    "parteRappresentata": text(row.get("parte_rappresentata") or row.get("parteRappresentata")),
                }
            )
    if not rows:
        rows.append(
            {
                "index": 1,
                "name": context["destinatario"]["nome_denominazione"],
                "pec": context["destinatario"]["pec"],
                "role": context["destinatario"]["tipo"],
                "source": context["destinatario"]["fonte_pec_key"],
                "parteRappresentata": context["destinatario"]["parte_rappresentata"],
            }
        )
    return rows


def _document_is_signed(document: dict[str, Any]) -> bool:
    name = text(document.get("nome_file")).lower()
    origin = text(document.get("origine")).lower()
    return name.endswith((".p7m", ".sig")) or origin == "firmato_digitalmente" or boolish(document.get("firmato_digitalmente"))


def _document_signature_required(document: dict[str, Any]) -> bool:
    return boolish(
        document.get("firma_digitale_richiesta")
        or document.get("firma_richiesta")
        or document.get("requires_signature")
        or document.get("requiresSignature")
    )


def _parse_notification_datetime(value: Any) -> datetime | None:
    raw = text(value)
    if not raw:
        return None
    for pattern in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%dT%H:%M", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%d/%m/%Y %H:%M"):
        try:
            return datetime.strptime(raw[:19] if "T" in raw and len(raw) >= 19 else raw, pattern)
        except ValueError:
            continue
    return None


def build_notification_timing_plan(payload: dict[str, Any]) -> dict[str, Any]:
    """Apply the PEC notification timing rules without hiding the lawyer review."""

    raw_send_at = text(
        _first(
            payload,
            "notifica.invio_programmato",
            "notifica.data_ora_invio",
            "invio_programmato",
            "data_ora_invio_pec",
            "pec_send_at",
        )
    )
    planned_at = _parse_notification_datetime(raw_send_at)
    if planned_at is None:
        return {
            "plannedAt": raw_send_at,
            "ready": True,
            "status": "da_pianificare",
            "senderEffect": "La RAC determinerà il perfezionamento per il notificante.",
            "recipientEffect": "La RdAC determinerà il perfezionamento per il destinatario, con verifica della fascia oraria.",
            "warning": "",
            "legalBasis": _legal_source_rows("l53_art3bis", "dl179_art16septies", "corte_cost_75_2019", "dpr68_art6_8"),
        }

    hour = planned_at.hour
    if 0 <= hour < 7:
        return {
            "plannedAt": planned_at.strftime("%d/%m/%Y %H:%M:%S"),
            "ready": False,
            "status": "fuori_fascia_destinatario",
            "senderEffect": "Verifica professionale richiesta prima dell'invio.",
            "recipientEffect": "La fascia 00:00-06:59 resta da evitare nel workflow automatico.",
            "warning": "Invio bloccato: pianifica dalle 07:00 oppure conferma manuale fuori automatismo.",
            "legalBasis": _legal_source_rows("l53_art3bis", "dl179_art16septies", "corte_cost_75_2019", "dpr68_art6_8"),
        }
    if 21 <= hour <= 23:
        return {
            "plannedAt": planned_at.strftime("%d/%m/%Y %H:%M:%S"),
            "ready": True,
            "status": "fascia_serale_con_scissione",
            "senderEffect": "Per il notificante vale il momento di generazione della RAC.",
            "recipientEffect": "Per il destinatario resta il differimento alle ore 07:00 del giorno successivo.",
            "warning": "Fascia serale: il software mostra la scissione degli effetti prima della conferma dell'avvocato.",
            "legalBasis": _legal_source_rows("l53_art3bis", "dl179_art16septies", "corte_cost_75_2019", "dpr68_art6_8"),
        }
    return {
        "plannedAt": planned_at.strftime("%d/%m/%Y %H:%M:%S"),
        "ready": True,
        "status": "fascia_ordinaria",
        "senderEffect": "Per il notificante vale il momento di generazione della RAC.",
        "recipientEffect": "Per il destinatario vale il momento di generazione della RdAC.",
        "warning": "",
        "legalBasis": _legal_source_rows("l53_art3bis", "dpr68_art6_8"),
    }


def build_notification_signature_plan(
    payload: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Select the documents that must enter the signature queue before PEC send."""

    context = context or _build_context(payload, template=select_relata_template(payload))
    signature_format = text(_first(payload, "notifica.firma_tipo", "firma_tipo", fallback="CAdES")).upper()
    signed_relata = "relata_notifica_firmata.pdf" if signature_format == "PADES" else "relata_notifica.pdf.p7m"
    required: list[dict[str, Any]] = [
        {
            "id": "relata_notifica",
            "label": "Relata di notificazione",
            "sourceFile": "relata_notifica.pdf",
            "signedFile": signed_relata,
            "required": True,
            "phase": "prima_invio_pec",
            "format": signature_format,
            "signer": context["avvocato"]["full_name"],
            "source": "L. 53/1994, art. 3-bis, comma 5; art. 56-bis disp. att. c.p.p. per il flusso penale",
            "reason": "La normativa richiede la relazione di notificazione su documento informatico separato, sottoscritta dall'avvocato prima dell'invio PEC.",
            "automaticSelection": True,
        }
    ]
    already_signed: list[dict[str, str]] = []
    not_to_sign: list[dict[str, str]] = []
    for document in context["documenti"]:
        name = document["nome_file"]
        if _document_signature_required(document) and not _document_is_signed(document):
            required.append(
                {
                    "id": f"documento_{document['index']}",
                    "label": document["descrizione"] or "Documento da notificare",
                    "sourceFile": name,
                    "signedFile": f"{name}.p7m" if not name.lower().endswith(".p7m") else name,
                    "required": True,
                    "phase": "prima_invio_pec",
                    "format": "CAdES",
                    "signer": context["avvocato"]["full_name"],
                    "source": "Specifiche tecniche DGSIA 7 agosto 2024, artt. 16 e 26; regole dell'atto processuale applicabili al documento",
                    "reason": "Il documento è marcato come atto da sottoscrivere autonomamente prima della notifica.",
                    "automaticSelection": True,
                }
            )
        elif _document_is_signed(document):
            already_signed.append({"filename": name, "reason": "Documento già firmato digitalmente o già in formato firmato."})
        else:
            not_to_sign.append(
                {
                    "filename": name,
                    "reason": "Resta allegato alla PEC come documento notificato; se è copia o provvedimento acquisito, l'eventuale attestazione è nella relata firmata.",
                }
            )
    checks = [
        _check_row(
            id="relata_da_firmare",
            label="Relata selezionata per firma",
            source="L. 53/1994, art. 3-bis, comma 5",
            passed=any(item["id"] == "relata_notifica" for item in required),
            detail=f"Documento da firmare: relata_notifica.pdf -> {signed_relata}.",
        ),
        _check_row(
            id="relata_firmata",
            label="Relata firmata prima dell'invio",
            source="L. 53/1994, art. 3-bis, comma 5",
            passed=boolish(_first(payload, "notifica.relata_firmata", "relata_firmata")),
            detail="Il workflow considera inviabile la PEC solo dopo la firma digitale della relata.",
        ),
    ]
    return {
        "mode": "local_signer",
        "legalBasis": _legal_source_rows(
            "l53_art3bis",
            "disp_att_cpp_56bis",
            "disp_att_cpc_196undecies",
            "dm44_art18",
            "dgsia_2024_art26",
            "dgsia_2024_art27",
        ),
        "requiredBeforeSend": required,
        "alreadySigned": already_signed,
        "notToSign": not_to_sign,
        "checks": checks,
        "ready": all(item["status"] == "superato" for item in checks),
        "localSignerRequired": True,
    }


def build_notification_send_plan(
    payload: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
    body: str = "",
) -> dict[str, Any]:
    """Return the controlled PEC-send plan after relata generation."""

    context = context or _build_context(payload, template=select_relata_template(payload))
    recipients = _delivery_recipients_from_payload(payload, context)
    attachment_manifest = build_notification_attachment_manifest(payload, context=context)
    signature_plan = build_notification_signature_plan(payload, context=context)
    timing_plan = build_notification_timing_plan(payload)
    signed_relata = text(
        next(
            (item.get("signedFile") for item in signature_plan.get("requiredBeforeSend", []) if item.get("id") == "relata_notifica"),
            "relata_notifica.pdf.p7m",
        )
    )
    documents = context["documenti"]
    pec_attachments = [
        {
            "id": "relata_firmata",
            "label": "Relata firmata digitalmente",
            "filename": text(payload.get("relata_firmata_file") or payload.get("relata_firmata_nome"), signed_relata),
            "required": True,
            "phase": "pec_notifica",
            "source": "L. 53/1994, art. 3-bis",
        }
    ]
    for document in documents:
        pec_attachments.append(
            {
                "id": f"documento_{document['index']}",
                "label": document["descrizione"] or "Documento da notificare",
                "filename": document["nome_file"],
                "sha256": document["hash_sha256"],
                "required": True,
                "phase": "pec_notifica",
                "source": "D.M. 44/2011, art. 18",
            }
        )
    if any(item.get("id") == "procura" and item.get("required") for item in attachment_manifest):
        pec_attachments.append(
            {
                "id": "procura",
                "label": "Procura alle liti",
                "filename": text(payload.get("procura_file") or payload.get("procura_nome")),
                "required": True,
                "phase": "pec_notifica",
                "source": "D.M. 44/2011, art. 18",
            }
        )

    checks = [
        _check_row(
            id="destinatari_pec",
            label="Destinatari PEC",
            source="D.L. 179/2012, art. 16-ter",
            passed=bool(recipients) and all(item["pec"] for item in recipients),
            detail="Ogni destinatario della notifica deve avere PEC tratta da pubblico elenco.",
        ),
        _check_row(
            id="pec_distinte",
            label="PEC distinte per destinatario",
            source="Prassi operativa prudente L. 53/1994",
            passed=True,
            detail="Il sistema prepara un messaggio separato per ciascun destinatario, evitando commistioni tra destinatari.",
        ),
        _check_row(
            id="allegati_pec",
            label="Allegati PEC di notifica",
            source="L. 53/1994, art. 3-bis; D.M. 44/2011, art. 18",
            passed=bool(documents)
            and all(item.get("filename") for item in pec_attachments if item.get("required"))
            and boolish(_first(payload, "notifica.relata_firmata", "relata_firmata")),
            detail="La PEC contiene relata firmata e documenti da notificare; RAC/RdAC si raccolgono dopo l'invio.",
        ),
        _check_row(
            id="orario_notifica",
            label="Orario notifica PEC",
            source="D.L. 179/2012, art. 16-septies; Corte cost. 75/2019; D.P.R. 68/2005",
            passed=bool(timing_plan.get("ready")),
            detail=text(timing_plan.get("warning") or timing_plan.get("recipientEffect")),
        ),
        _check_row(
            id="approvazione_avvocato",
            label="Conferma dell'avvocato",
            source="Controllo operativo IUSENTRA",
            passed=boolish(payload.get("approvazione_avvocato")),
            detail="Nessun invio parte senza conferma professionale finale.",
        ),
    ]
    return {
        "mode": "pec_l53_controllata",
        "subject": LEGAL_NOTIFICATION_SUBJECT,
        "body": body,
        "recipients": recipients,
        "messagesCount": len(recipients),
        "separatePecRequired": True,
        "attachments": pec_attachments,
        "attachmentManifest": attachment_manifest,
        "signaturePlan": signature_plan,
        "timingPlan": timing_plan,
        "sendChecks": checks,
        "postSendEvidenceRequired": [
            "PEC inviata in originale digitale .eml o .msg",
            "RAC per ogni destinatario",
            "RdAC completa per ogni destinatario",
            "Riferimenti ricevute per il deposito prova",
        ],
        "ready": all(item["status"] == "superato" for item in checks),
    }


def _build_context(payload: dict[str, Any], *, template: dict[str, Any] | None = None) -> dict[str, Any]:
    data_verifica, ora_verifica = _split_datetime(_latest_verified_pec_timestamp(payload))
    studio_cap = text(_first(payload, "avvocato.studio_cap", "studio_cap", fallback=""))
    studio_citta = text(_first(payload, "avvocato.studio_citta", "studio_citta", fallback=""))
    studio_provincia = text(_first(payload, "avvocato.studio_provincia", "studio_provincia", fallback="")).upper()
    studio_indirizzo = text(_first(payload, "avvocato.studio", "studio_indirizzo", fallback=""))
    studio_completo = compose_studio_address(
        indirizzo=studio_indirizzo,
        cap=studio_cap,
        city=studio_citta,
        province=studio_provincia,
        cap_label=True,
    )
    notifica_data = _format_italian_date(_first(payload, "notifica.data", "data_relata"))
    notifica_ora = _format_italian_time(_first(payload, "notifica.ora", "ora_relata"))
    luogo_studio = " ".join(part for part in (studio_citta, f"({studio_provincia})" if studio_provincia else "") if part)
    notifica_luogo = text(_first(payload, "notifica.luogo", "luogo", fallback=luogo_studio))
    role = normalise_role(_first(payload, "destinatario.tipo", "ruolo_destinatario"))
    source_key = normalise_public_register(_first(payload, "destinatario.fonte_pec", "fonte_pec_destinatario"))
    documents = _documents(payload)
    case_id = notification_case_from_payload(payload)
    avvocato_nome = _normalise_lawyer_name(_first(payload, "avvocato.nome", "avvocato_nome"))
    avvocato_cognome = text(_first(payload, "avvocato.cognome", "avvocato_cognome"))
    avvocato_full = _normalise_lawyer_name(text(" ".join(part for part in (avvocato_nome, avvocato_cognome) if part), avvocato_nome))
    firma_in_calce = text(
        _first(
            payload,
            "avvocato.firma_in_calce",
            "avvocato_firma_in_calce",
            "firma_avvocato",
            fallback=f"Avv. {avvocato_full}" if avvocato_full else "",
        )
    )
    firma_digitale_dicitura = text(
        _first(
            payload,
            "avvocato.firma_digitale_dicitura",
            "firma_digitale_dicitura",
            fallback="Firmato digitalmente",
        )
    )
    provvedimento_tipo = text(
        _first(
            payload,
            "provvedimento.tipo",
            "provvedimento_tipo",
            fallback="Sentenza" if case_id == "sentenza_termine_breve" else "",
        )
    )

    context = {
        "catalog_version": template_catalog_version(),
        "template": template or {},
        "pratica": {
            "codice": text(_first(payload, "pratica.codice", "pratica_codice")),
        },
        "avvocato": {
            "nome": avvocato_nome,
            "cognome": avvocato_cognome,
            "full_name": avvocato_full,
            "codice_fiscale": text(_first(payload, "avvocato.codice_fiscale", "avvocato_cf")),
            "foro": text(_first(payload, "avvocato.foro", "avvocato_foro")),
            "pec": text(_first(payload, "avvocato.pec", "mittente_pec")),
            "studio": studio_indirizzo,
            "studio_completo": studio_completo,
            "studio_cap": studio_cap,
            "studio_citta": studio_citta,
            "studio_provincia": studio_provincia,
            "fonte_pec": register_label(_first(payload, "avvocato.fonte_pec", "fonte_pec_mittente", fallback="reginde")),
            "firma_in_calce": firma_in_calce,
            "firma_digitale_dicitura": firma_digitale_dicitura,
        },
        "cliente": {
            "tipo": text(_first(payload, "cliente.tipo", "assistito_tipo")),
            "nome_denominazione": text(_first(payload, "cliente.nome_denominazione", "assistito_nome")),
            "codice_fiscale_piva": text(_first(payload, "cliente.codice_fiscale_piva", "assistito_cf")),
            "qualifica": text(_first(payload, "cliente.qualifica", "assistito_qualifica")),
        },
        "procedimento": {
            "presente": _first_bool(payload, "procedimento.presente", "procedimento_pendente", fallback=False),
            "ufficio": text(_first(payload, "procedimento.ufficio", "ufficio_giudiziario")),
            "sezione": text(_first(payload, "procedimento.sezione", "sezione")),
            "numero_rg": text(_first(payload, "procedimento.numero_rg", "numero_rg")),
            "anno_rg": text(_first(payload, "procedimento.anno_rg", "anno_rg")),
            "giudice": text(_first(payload, "procedimento.giudice", "giudice")),
            "tipo_procedimento": text(_first(payload, "procedimento.tipo_procedimento", "tipo_procedimento")),
        },
        "destinatario": {
            "tipo": role,
            "nome_denominazione": text(_first(payload, "destinatario.nome_denominazione", "destinatario_nome")),
            "codice_fiscale_piva": text(_first(payload, "destinatario.codice_fiscale_piva", "destinatario_cf", "destinatario_codice_fiscale_piva")),
            "pec": text(_first(payload, "destinatario.pec", "destinatario_pec")),
            "fonte_pec": PUBLIC_PEC_REGISTERS.get(source_key, text(_first(payload, "destinatario.fonte_pec", "fonte_pec_destinatario"))),
            "fonte_pec_key": source_key,
            "data_verifica_pec": data_verifica,
            "ora_verifica_pec": ora_verifica,
            "parte_rappresentata": text(_first(payload, "destinatario.parte_rappresentata", "destinatario_parte_rappresentata")),
            "qualifica": text(_first(payload, "destinatario.qualifica", "destinatario_qualifica")),
        },
        "documenti": documents,
        "notifica": {
            "tipo": text(_first(payload, "notifica.tipo", "tipo_notifica", fallback="pec_l53_1994")),
            "caso": case_id,
            "oggetto_pec": LEGAL_NOTIFICATION_SUBJECT,
            "luogo": notifica_luogo,
            "data": notifica_data,
            "ora": notifica_ora,
            "relata_firmata": boolish(_first(payload, "notifica.relata_firmata", "relata_firmata")),
            "firma_tipo": text(_first(payload, "notifica.firma_tipo", "firma_tipo", fallback="PAdES")),
            "ricevuta_tipo": "completa" if boolish(payload.get("ricevuta_completa")) else text(payload.get("ricevuta_tipo")),
            "esito": text(_first(payload, "notifica.esito", "esito")),
            "note": text(_first(payload, "notifica.note", "note")),
        },
        "provvedimento": {
            "tipo": provvedimento_tipo,
            "numero": text(_first(payload, "provvedimento.numero", "provvedimento_numero")),
            "anno": text(_first(payload, "provvedimento.anno", "provvedimento_anno")),
            "ufficio_origine": text(_first(payload, "provvedimento.ufficio_origine", "provvedimento_ufficio_origine")),
            "data": _format_italian_date(_first(payload, "provvedimento.data", "provvedimento_data")),
            "data_deposito": _format_italian_date(_first(payload, "provvedimento.data_deposito", "provvedimento_data_deposito")),
        },
        "notifica_precedente": {
            "data": _format_italian_date(_first(payload, "notifica_precedente.data", "notifica_precedente_data")),
            "esito": text(_first(payload, "notifica_precedente.esito", "notifica_precedente_esito")),
        },
        "provvedimento_rinnovo": {
            "presente": _first_bool(payload, "provvedimento_rinnovo.presente", "provvedimento_rinnovo_presente"),
            "data": _format_italian_date(_first(payload, "provvedimento_rinnovo.data", "provvedimento_rinnovo_data")),
            "nome_file": text(_first(payload, "provvedimento_rinnovo.nome_file", "provvedimento_rinnovo_nome_file")),
        },
        "riassunzione": {
            "causa": text(_first(payload, "riassunzione.causa", "riassunzione_causa")),
        },
        "sfratto": {
            "tipo_procedimento": text(_first(payload, "sfratto.tipo_procedimento", "sfratto_tipo_procedimento")),
            "immobile_indirizzo": text(_first(payload, "sfratto.immobile_indirizzo", "sfratto_immobile_indirizzo")),
        },
        "esecuzione": {
            "debitore": text(_first(payload, "esecuzione.debitore", "esecuzione_debitore")),
            "terzo_pignorato": text(_first(payload, "esecuzione.terzo_pignorato", "esecuzione_terzo_pignorato")),
        },
        "opposizione": {
            "tipo": text(_first(payload, "opposizione.tipo", "opposizione_tipo")),
        },
    }
    return context


def _context_lookup(context: dict[str, Any], path: str) -> Any:
    current: Any = context
    for part in path.split("."):
        if isinstance(current, dict):
            current = current.get(part)
        else:
            current = getattr(current, part, None)
        if current is None:
            return ""
    return current


def _field_label(template: dict[str, Any], path: str) -> str:
    snake = path.replace(".", "_")
    for field in template.get("fields") or []:
        if isinstance(field, dict) and field.get("name") in {path, snake}:
            return text(field.get("label"), snake.replace("_", " "))
    return snake.replace("_", " ")


def _render_lines(lines: list[str], context: dict[str, Any]) -> list[str]:
    rendered: list[str] = []
    for line in lines:
        value, _ = _render_restricted_template_body(_render_supported_if_blocks(line, context), context)
        value = value.strip()
        if value or line == "":
            rendered.append(value)
    return rendered


def select_relata_template(payload: dict[str, Any]) -> dict[str, Any]:
    explicit = (
        payload.get("template_id")
        or payload.get("modello_relata")
        or _deep_get(payload, "template.id")
        or _deep_get(payload, "notifica.template_id")
    )
    custom_template = payload.get("template_personalizzato")
    if isinstance(custom_template, dict):
        custom = normalise_custom_template(custom_template)
        custom_id = text(custom.get("id"))
        if custom_id and (not text(explicit) or text(explicit) == custom_id):
            return custom

    inline_custom_body = multiline_text(
        payload.get("template_personalizzato_testo")
        or payload.get("testo_modello_personalizzato")
        or payload.get("custom_template_body")
    )
    if inline_custom_body:
        inline_id = text(explicit, "relata_personalizzata")
        return normalise_custom_template({
            "id": inline_id,
            "code": "PERS",
            "label": payload.get("template_personalizzato_nome") or payload.get("nome_modello_personalizzato") or "Modello personalizzato",
            "description": payload.get("template_personalizzato_descrizione") or "Modello compilato dai dati IUSENTRA disponibili.",
            "custom_body": inline_custom_body,
            "requires_proceeding": payload.get("template_personalizzato_procedimento"),
        })

    template = get_notification_template(explicit)
    if template:
        return template

    role = normalise_role(_first(payload, "destinatario.tipo", "ruolo_destinatario"))
    documents = _documents(payload)
    origins = {document["origine"] for document in documents}
    case_id = notification_case_from_payload(payload)
    case_explicit = bool(_explicit_notification_case(payload))

    if role in {"cliente", "assistito"}:
        return get_notification_template("comunicazione_cliente_non_notifica") or list_notification_templates(kind="communication")[0]
    if case_id and case_id != "ordinaria":
        case_template = get_notification_template(text(NOTIFICATION_CASE_DIRECTIVES.get(case_id, {}).get("template_id")))
        if case_template:
            return case_template
    if not case_explicit:
        if boolish(payload.get("rinnovo_notifica")):
            return get_notification_template("relata_rinnovo_notifica") or get_notification_template("relata_pec_base_l53")
        if boolish(payload.get("integrazione_contraddittorio")):
            return get_notification_template("relata_integrazione_contraddittorio") or get_notification_template("relata_pec_base_l53")
        if boolish(payload.get("chiamata_terzo")):
            return get_notification_template("relata_chiamata_terzo") or get_notification_template("relata_pec_base_l53")
        if boolish(payload.get("riassunzione")) or text(_first(payload, "riassunzione.causa", "riassunzione_causa")):
            return get_notification_template("relata_riassunzione") or get_notification_template("relata_pec_base_l53")
    if role == "difensore":
        return get_notification_template("relata_pec_a_difensore_costituito") or get_notification_template("relata_pec_base_l53")
    if role == "impresa":
        return get_notification_template("relata_pec_a_impresa_societa") or get_notification_template("relata_pec_base_l53")
    if role == "pa":
        return get_notification_template("relata_pec_a_pubblica_amministrazione") or get_notification_template("relata_pec_base_l53")
    if role == "professionista":
        return get_notification_template("relata_pec_a_professionista_inipec") or get_notification_template("relata_pec_base_l53")
    if "comunicazione_cancelleria" in origins:
        return get_notification_template("relata_pec_provvedimento_da_fascicolo") or get_notification_template("relata_provvedimento_giudice")
    if "copia_fascicolo_informatico" in origins:
        return get_notification_template("relata_pec_con_attestazione_fascicolo") or get_notification_template("relata_provvedimento_giudice")
    if "scansione_analogico" in origins:
        return get_notification_template("relata_pec_con_attestazione_scansione_analogica") or get_notification_template("relata_pec_base_l53")
    if boolish(payload.get("procedimento_pendente")) or boolish(_deep_get(payload, "procedimento.presente")):
        return get_notification_template("relata_pec_in_corso_di_causa") or get_notification_template("relata_pec_base_l53")
    return get_notification_template("relata_pec_base_l53") or list_notification_templates(kind="relata")[0]


def _validate_required_context(template: dict[str, Any], context: dict[str, Any], blockers: list[str]) -> None:
    for path in template.get("required_fields") or []:
        if not text(_context_lookup(context, path)):
            blockers.append(f"Completa il campo richiesto per il modello: {_field_label(template, path)}.")


def _validate_proceeding(context: dict[str, Any], blockers: list[str]) -> None:
    for path, message in (
        ("procedimento.ufficio", "Per una notifica in corso di procedimento indica l'ufficio giudiziario."),
        ("procedimento.numero_rg", "Per una notifica in corso di procedimento indica il numero di ruolo."),
        ("procedimento.anno_rg", "Per una notifica in corso di procedimento indica l'anno di ruolo."),
    ):
        if not text(_context_lookup(context, path)):
            blockers.append(message)


def _sentence_case_label(value: Any, fallback: str = "Sentenza") -> str:
    raw = text(value, fallback)
    return raw[:1].upper() + raw[1:] if raw else fallback


def _rg_reference(proceeding: dict[str, Any]) -> str:
    number = text(proceeding.get("numero_rg"))
    year = text(proceeding.get("anno_rg"))
    if number and year:
        return f"{number}/{year}"
    return number or year


def _sentence_office_intro(office: str) -> str:
    clean = text(office)
    if not clean:
        return "dall'ufficio giudiziario indicato nel fascicolo"
    lower = clean.lower()
    if lower.startswith(("corte", "sezione")):
        return f"dalla {clean}"
    if lower.startswith(("ufficio", "autorità")):
        return f"dall'{clean}"
    return f"dal {clean}"


def _is_sentence_attestation_document(document: dict[str, Any], context: dict[str, Any]) -> bool:
    template = context.get("template") or {}
    haystack = " ".join(
        text(value).lower()
        for value in (
            context.get("notifica", {}).get("caso"),
            context.get("provvedimento", {}).get("tipo"),
            template.get("id"),
            template.get("label"),
            document.get("nome_file"),
            document.get("descrizione"),
        )
    )
    return "sentenza_termine_breve" in haystack or "sentenza" in haystack


def _sentence_attestation_text(document: dict[str, Any], context: dict[str, Any]) -> str:
    proceeding = context["procedimento"]
    provision = context["provvedimento"]
    office = text(provision.get("ufficio_origine") or proceeding.get("ufficio"))
    section = text(proceeding.get("sezione"))
    date_label = text(
        provision.get("data_deposito")
        or provision.get("data")
        or document.get("data_documento")
        or document.get("data_comunicazione_cancelleria")
    )
    section_part = f" Sez. {section}" if section else ""
    date_part = f" in data {date_label}" if date_label else ""
    rg = _rg_reference(proceeding)
    rg_part = f" R.G. n. {rg}" if rg else ""
    return (
        f"{_sentence_case_label(provision.get('tipo'))}, emessa {_sentence_office_intro(office)}"
        f"{section_part}{date_part} è conforme alla copia informatica presente nel fascicolo "
        f"informatico del relativo procedimento{rg_part} dal quale è estratta."
    )


def _document_attestation_text(document: dict[str, Any], context: dict[str, Any]) -> str:
    origin = document["origine"]
    name = document["nome_file"]
    description = document["descrizione"] or "documento indicato"
    proceeding = context["procedimento"]
    office = text(proceeding.get("ufficio"), "ufficio giudiziario indicato")
    rg = _rg_reference(proceeding)
    rg_part = f", R.G. n. {rg}" if rg else ""
    if origin in {"copia_fascicolo_informatico", "comunicazione_cancelleria"} and _is_sentence_attestation_document(document, context):
        return f"{name}: {_sentence_attestation_text(document, context)}"
    if origin == "copia_fascicolo_informatico":
        return (
            f"{name}, contenente {description}, copia informatica conforme al corrispondente "
            f"atto o provvedimento presente nel fascicolo informatico del procedimento {office}{rg_part}."
        )
    if origin == "comunicazione_cancelleria":
        date_part = f" del {document['data_comunicazione_cancelleria']}" if document["data_comunicazione_cancelleria"] else ""
        return (
            f"{name}, contenente {description}, copia informatica conforme al documento allegato "
            f"alla comunicazione telematica di cancelleria{date_part} relativa al procedimento{rg_part}."
        )
    if origin == "scansione_analogico":
        return (
            f"{name}, contenente {description}, copia informatica per immagine "
            "conforme all'originale analogico in possesso del sottoscritto difensore."
        )
    return ""


def _attestation_document_title_detail(
    document: dict[str, Any],
    context: dict[str, Any],
) -> tuple[str, str]:
    description = text(document.get("descrizione")).strip(" ,;:")
    filename = text(document.get("nome_file"))
    stem = Path(filename).name
    while Path(stem).suffix.lower() in {".p7m", ".pdf", ".doc", ".docx"}:
        stem = Path(stem).stem
    source = description or stem or "Documento"
    haystack = f"{description} {stem}".lower()
    known_titles = (
        ("decreto fissazione udienza", "Decreto fissazione udienza"),
        ("decreto", "Decreto"),
        ("sentenza", "Sentenza"),
        ("ordinanza", "Ordinanza"),
        ("provvedimento", "Provvedimento"),
        ("ricorso", "Ricorso"),
        ("procura", "Procura"),
        ("memoria", "Memoria"),
        ("verbale", "Verbale"),
        ("istanza", "Istanza"),
        ("atto di citazione", "Atto di citazione"),
    )
    title = next((label for token, label in known_titles if token in haystack), "")

    if title and source.lower().startswith(title.lower()):
        detail = source[len(title) :].strip(" ,;:-")
    elif "," in source:
        source_title, source_detail = source.split(",", 1)
        if not title:
            title = source_title.strip()
        detail = source_detail.strip(" ,;:")
    else:
        detail = "" if title else source
    title = title or source

    proceeding = context["procedimento"]
    document_date = _format_italian_date(
        document.get("data_documento") or document.get("data_comunicazione_cancelleria")
    )
    if title in {"Sentenza", "Ordinanza", "Provvedimento", "Decreto", "Decreto fissazione udienza"} and not detail:
        office = text(context["provvedimento"].get("ufficio_origine") or proceeding.get("ufficio"))
        section = text(proceeding.get("sezione"))
        date_label = _format_italian_date(
            context["provvedimento"].get("data_deposito")
            or context["provvedimento"].get("data")
            or document_date
        )
        participle = "emessa" if title in {"Sentenza", "Ordinanza"} else "emesso"
        detail = f"{participle} {_sentence_office_intro(office)}"
        if section:
            detail += f" Sez. {section}"
        if date_label:
            detail += f" in data {date_label}"
    elif title == "Procura" and detail.lower() in {"", "alle liti"}:
        detail = "mandato alle liti"
    elif title == "Ricorso":
        detail = detail or "atto introduttivo"
        if document_date and "depositat" not in detail.lower():
            detail += f", depositato in data {document_date}"
    elif not detail:
        detail = "documento allegato alla notificazione"

    if document["origine"] == "comunicazione_cancelleria" and document["data_comunicazione_cancelleria"]:
        communication_date = _format_italian_date(document["data_comunicazione_cancelleria"])
        if communication_date and communication_date not in detail:
            detail += f", allegato alla comunicazione di cancelleria del {communication_date}"
    return title.strip(), detail.strip(" ,;:")


def _attestation_conclusion(documents: list[dict[str, Any]], context: dict[str, Any]) -> str:
    origins = {document["origine"] for document in documents}
    proceeding = context["procedimento"]
    office = text(proceeding.get("ufficio"))
    section = text(proceeding.get("sezione"))
    rg = _rg_reference(proceeding)
    proceeding_parts = [office, f"Sez. {section}" if section else "", f"R.G. n. {rg}" if rg else ""]
    proceeding_label = ", ".join(part for part in proceeding_parts if part)
    singular = len(documents) == 1
    if origins == {"copia_fascicolo_informatico"}:
        rg_label = _rg_reference(proceeding)
        proceeding_reference = f" del relativo procedimento R.G. n. {rg_label}" if rg_label else ""
        return (
            f"{'è conforme alla copia informatica presente' if singular else 'sono conformi alle copie informatiche presenti'} "
            f"nel fascicolo informatico{proceeding_reference} "
            f"dal quale {'è estratta' if singular else 'sono estratte'}."
        )
    if origins == {"comunicazione_cancelleria"}:
        return (
            f"{'è conforme al documento allegato' if singular else 'sono conformi ai documenti allegati'} "
            f"{'alla comunicazione telematica' if singular else 'alle comunicazioni telematiche'} di cancelleria"
            f"{f' relative al procedimento {proceeding_label}' if proceeding_label else ''}."
        )
    if origins == {"scansione_analogico"}:
        return (
            f"{'è conforme all’originale analogico' if singular else 'sono conformi agli originali analogici'} "
            "in possesso del sottoscritto difensore."
        )
    return (
        f"{'è conforme alla rispettiva fonte indicata' if singular else 'sono conformi alle rispettive fonti indicate'}"
        f"{f' con riferimento al procedimento {proceeding_label}' if proceeding_label else ''}."
    )


def _attestation_document_rows(
    documents: list[dict[str, Any]],
    context: dict[str, Any],
) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for document in documents:
        title, detail = _attestation_document_title_detail(document, context)
        rows.append(
            {
                "title": title,
                "detail": detail,
                "text": f"{title}, {detail}" if detail else title,
            }
        )
    return rows


def _attestation_blocks(context: dict[str, Any]) -> list[str]:
    documents = [document for document in context["documenti"] if document["necessita_attestazione"]]
    if not documents:
        return []
    intro = (
        "Attesto, ai sensi della normativa vigente, che la seguente copia informatica:"
        if len(documents) == 1
        else "Attesto, ai sensi della normativa vigente, che le seguenti copie informatiche:"
    )
    items = [f"- {row['text']};" for row in _attestation_document_rows(documents, context)]
    return ["\n".join([intro, *items, _attestation_conclusion(documents, context)])]


def build_attestazione_conformita_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Prepara modello autocompilante per attestazione di conformità.

    Il testo segue la matrice salvata in docs/LEGAL_NOTIFICATIONS_AND_TELEMATIC_REGISTRY.md:
    se la copia informatica è destinata alla notifica, l'attestazione va riportata
    nella relata; questo modello serve come documento separato o anteprima di studio
    quando il flusso lo richiede.
    """

    context = _build_context(payload)
    attested_documents = [document for document in context["documenti"] if document["necessita_attestazione"]]
    documents = attested_documents
    sentence_documents = [document for document in documents if _is_sentence_attestation_document(document, context)]
    missing: list[str] = []
    if not context["avvocato"]["full_name"]:
        missing.append("avvocato.nome")
    if not context["avvocato"]["codice_fiscale"]:
        missing.append("avvocato.codice_fiscale")
    if not context["avvocato"]["foro"]:
        missing.append("avvocato.foro")
    if not context["procedimento"]["numero_rg"]:
        missing.append("procedimento.numero_rg")
    if not context["procedimento"]["anno_rg"]:
        missing.append("procedimento.anno_rg")
    if not documents:
        missing.append("documenti")
    if sentence_documents:
        for path in ("procedimento.ufficio", "procedimento.sezione"):
            if not text(_context_lookup(context, path)):
                missing.append(path)
        sentence_date = text(
            context["provvedimento"].get("data_deposito")
            or context["provvedimento"].get("data")
            or sentence_documents[0].get("data_documento")
            or sentence_documents[0].get("data_comunicazione_cancelleria")
        )
        if not sentence_date:
            missing.append("provvedimento.data_deposito")
    document_rows = _attestation_document_rows(documents, context)
    doc_lines: list[str] = []
    if not documents:
        conformity_text = ""
        copy_intro = "ai sensi di legge, che la copia informatica:"
    else:
        doc_lines.extend(f"- {row['text']};" for row in document_rows)
        conformity_text = _attestation_conclusion(documents, context)
        copy_intro = "ai sensi di legge, che le copie informatiche:" if len(documents) != 1 else "ai sensi di legge, che la copia informatica:"
    lines = [
        "ATTESTAZIONE DI CONFORMITÀ",
        "",
        (
            f"Il sottoscritto Avv. {context['avvocato']['full_name']} "
            f"C. F. {context['avvocato']['codice_fiscale']}, del Foro di {context['avvocato']['foro']},"
        ),
        "",
        "Attesta",
        "",
        copy_intro,
        *doc_lines,
        conformity_text,
        "",
        context["avvocato"]["firma_in_calce"],
        context["avvocato"]["firma_digitale_dicitura"],
    ]
    return {
        "schema": "iusentra.attestazione_conformita.v1",
        "ok": not missing,
        "missing_fields": list(dict.fromkeys(missing)),
        "title": "Attestazione di conformità",
        "text": "\n".join(line for line in lines if line is not None).strip() + "\n",
        "documenti": [
            {
                "nome_file": document["nome_file"],
                "descrizione": document["descrizione"],
                "origine": document["origine"],
                "origine_label": DOCUMENT_ORIGIN_LABELS.get(document["origine"], document["origine"]),
                "necessita_attestazione": bool(document["necessita_attestazione"]),
                "hash_sha256": document["hash_sha256"],
                "data_documento": document["data_documento"],
                "data_comunicazione_cancelleria": document["data_comunicazione_cancelleria"],
            }
            for document in documents
        ],
        "document_rows": document_rows,
        "copy_intro": copy_intro,
        "conformity_text": conformity_text,
        "campi_database": {
            "avvocato": context["avvocato"],
            "cliente": context["cliente"],
            "procedimento": context["procedimento"],
            "destinatario": context["destinatario"],
            "provvedimento": context["provvedimento"],
            "notifica": context["notifica"],
        },
        "normativa": [
            "art. 196-undecies disp. att. c.p.c.",
            "D.L. 179/2012, art. 16-decies",
            "L. 53/1994, art. 3-bis",
            "artt. 285, 325 e 326 c.p.c.",
            "Provvedimento DGSIA 7 agosto 2024, art. 27",
        ],
    }


def render_attestazione_conformita_text(payload: dict[str, Any]) -> str:
    return str(build_attestazione_conformita_payload(payload).get("text") or "")


def generate_attestazione_conformita_docx(
    payload: dict[str, Any],
    output_path: str | Path,
) -> dict[str, Any]:
    """Genera una sola attestazione usando impaginazione e stili del modello dello studio."""

    attestation = build_attestazione_conformita_payload(payload)
    try:
        from lxml import etree
        from zipfile import ZipFile
    except Exception as exc:  # pragma: no cover - dipendenza ambiente
        raise RuntimeError(f"Supporto DOCX non disponibile: {exc}") from exc

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if not ATTESTAZIONE_CONFORMITA_TEMPLATE_PATH.is_file():
        raise RuntimeError("Modello Word dell'attestazione di conformità non disponibile.")
    if output.resolve() == ATTESTAZIONE_CONFORMITA_TEMPLATE_PATH.resolve():
        raise RuntimeError("Il modello Word non può essere sovrascritto.")

    word_namespace = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"
    xml_namespace = "http://www.w3.org/XML/1998/namespace"
    namespaces = {"w": word_namespace}

    def qn(local_name: str) -> str:
        prefix, name = local_name.split(":", 1)
        if prefix != "w":
            raise RuntimeError(f"Namespace DOCX non riconosciuto: {prefix}")
        return f"{{{word_namespace}}}{name}"

    def paragraph_text(paragraph: Any) -> str:
        return "".join(paragraph.xpath(".//w:t/text()", namespaces=namespaces))

    def clear_paragraph(paragraph: Any) -> None:
        for child in list(paragraph):
            if child.tag != qn("w:pPr"):
                paragraph.remove(child)

    def run_from(prototype: Any, value: str) -> Any:
        run = deepcopy(prototype)
        for child in list(run):
            if child.tag != qn("w:rPr"):
                run.remove(child)
        for highlight in list(run.xpath("./w:rPr/w:highlight", namespaces=namespaces)):
            parent = highlight.getparent()
            if parent is not None:
                parent.remove(highlight)
        text_element = etree.Element(qn("w:t"))
        if value[:1].isspace() or value[-1:].isspace():
            text_element.set(f"{{{xml_namespace}}}space", "preserve")
        text_element.text = value
        run.append(text_element)
        return run

    with ZipFile(ATTESTAZIONE_CONFORMITA_TEMPLATE_PATH, "r") as source:
        infos = source.infolist()
        package = {info.filename: source.read(info.filename) for info in infos}

    document_xml_path = "word/document.xml"
    try:
        document_root = etree.fromstring(package[document_xml_path])
    except Exception as exc:
        raise RuntimeError("Il contenuto del modello Word non è leggibile.") from exc
    body = document_root.find(f".//{{{word_namespace}}}body")
    paragraphs = [] if body is None else body.findall(qn("w:p"))
    if len(paragraphs) != 12 or paragraph_text(paragraphs[0]).strip() != "ATTESTAZIONE DI CONFORMITÀ":
        raise RuntimeError("Struttura del modello Word dell'attestazione non riconosciuta.")

    lawyer = attestation["campi_database"]["avvocato"]
    intro_regular_run = paragraphs[1].xpath("./w:r", namespaces=namespaces)[0]
    intro_lawyer_run = paragraphs[1].xpath("./w:r[w:rPr/w:b and w:rPr/w:i]", namespaces=namespaces)[0]
    clear_paragraph(paragraphs[1])
    paragraphs[1].append(run_from(intro_regular_run, "Il sottoscritto "))
    paragraphs[1].append(run_from(intro_lawyer_run, f"Avv. {lawyer['full_name']}"))
    paragraphs[1].append(
        run_from(
            intro_regular_run,
            f" C. F. {lawyer['codice_fiscale']}, del Foro di {lawyer['foro']},",
        )
    )

    copy_intro_run = paragraphs[4].xpath("./w:r", namespaces=namespaces)[0]
    clear_paragraph(paragraphs[4])
    paragraphs[4].append(run_from(copy_intro_run, attestation["copy_intro"]))

    list_prototype = deepcopy(paragraphs[5])
    title_run_prototype = paragraphs[5].xpath("./w:r[w:rPr/w:b and w:rPr/w:u]", namespaces=namespaces)[0]
    detail_run_prototype = paragraphs[6].xpath("./w:r[not(w:rPr/w:b)]", namespaces=namespaces)[0]
    conclusion = paragraphs[8]
    for paragraph in paragraphs[5:8]:
        body.remove(paragraph)
    for row in attestation["document_rows"]:
        list_paragraph = deepcopy(list_prototype)
        clear_paragraph(list_paragraph)
        list_paragraph.append(run_from(title_run_prototype, row["title"]))
        detail = text(row.get("detail"))
        list_paragraph.append(run_from(detail_run_prototype, f", {detail};" if detail else ";"))
        conclusion.addprevious(list_paragraph)

    conclusion_run = conclusion.xpath("./w:r", namespaces=namespaces)[0]
    clear_paragraph(conclusion)
    conclusion.append(run_from(conclusion_run, attestation["conformity_text"]))

    signature_run = paragraphs[10].xpath("./w:r", namespaces=namespaces)[0]
    clear_paragraph(paragraphs[10])
    paragraphs[10].append(run_from(signature_run, lawyer["firma_in_calce"]))

    digital_signature_run = paragraphs[11].xpath("./w:r", namespaces=namespaces)[0]
    clear_paragraph(paragraphs[11])
    paragraphs[11].append(run_from(digital_signature_run, lawyer["firma_digitale_dicitura"]))

    for highlight in list(document_root.xpath(".//w:highlight", namespaces=namespaces)):
        parent = highlight.getparent()
        if parent is not None:
            parent.remove(highlight)
    package[document_xml_path] = etree.tostring(
        document_root,
        xml_declaration=True,
        encoding="UTF-8",
        standalone=True,
    )

    with ZipFile(output, "w") as destination:
        for info in infos:
            destination.writestr(info, package[info.filename])
    return {
        **attestation,
        "output_path": str(output),
        "template_path": str(ATTESTAZIONE_CONFORMITA_TEMPLATE_PATH),
    }


def _document_rows(context: dict[str, Any], *, privacy: bool = False) -> list[str]:
    rows: list[str] = []
    for document in context["documenti"]:
        description = document["descrizione_breve_privacy"] if privacy else document["descrizione"]
        rows.append(f"{document['index']}. {document['nome_file']} - {description}")
    return rows


def _rg_line(context: dict[str, Any]) -> str:
    number = text(context["procedimento"].get("numero_rg"))
    year = text(context["procedimento"].get("anno_rg"))
    if number and year:
        return f"R.G. n. {number}/{year}."
    if number:
        return f"R.G. n. {number}."
    if year:
        return f"Anno R.G. {year}."
    return ""


def _proceeding_lines(context: dict[str, Any]) -> list[str]:
    if not context["procedimento"]["presente"]:
        return []
    office = text(context["procedimento"].get("ufficio"))
    section = text(context["procedimento"].get("sezione"))
    rg = _rg_line(context)
    lines = ["La presente notificazione viene eseguita in relazione al procedimento"]
    lines.append(f"pendente innanzi a {office}," if office else "pendente innanzi all'ufficio giudiziario indicato negli atti,")
    if section:
        lines.append(f"Sezione {section},")
    if rg:
        lines.append(rg)
    return lines


def _proceeding_block(context: dict[str, Any]) -> str:
    return "\n".join(_proceeding_lines(context))


def _custom_render_context(context: dict[str, Any]) -> dict[str, Any]:
    return {
        **context,
        "documenti_righe": "\n".join(_document_rows(context, privacy=False)),
        "documenti_righe_privacy": "\n".join(_document_rows(context, privacy=True)),
        "blocco_procedimento": _proceeding_block(context),
        "attestazioni_testo": "\n\n".join(_attestation_blocks(context)),
    }


def _template_lookup_value(context: dict[str, Any], token: str) -> Any:
    render_context = _custom_render_context(context)
    if token in _OPERATIONAL_TEMPLATE_FIELDS:
        return context.get(token) if text(context.get(token)) else render_context.get(token)
    return _context_lookup(context, token)


def _render_supported_if_blocks(content: str, context: dict[str, Any]) -> str:
    output: list[str] = []
    index = 0
    while index < len(content):
        start = content.find("{%", index)
        if start < 0:
            output.append(content[index:])
            break
        directive_end = content.find("%}", start + 2)
        if directive_end < 0:
            output.append(content[index:])
            break
        directive = content[start + 2:directive_end].strip()
        if not directive.startswith("if "):
            output.append(content[index:start])
            index = directive_end + 2
            continue
        endif_start = content.find("{% endif %}", directive_end + 2)
        if endif_start < 0:
            output.append(content[index:start])
            index = directive_end + 2
            continue
        token = directive[3:].strip()
        output.append(content[index:start])
        if _is_identifier_path(token) and text(_template_lookup_value(context, token)):
            output.append(content[directive_end + 2:endif_start])
        index = endif_start + len("{% endif %}")
    return "".join(output)


def _render_restricted_template_body(
    body: str,
    context: dict[str, Any],
    *,
    placeholder_missing: bool = False,
) -> tuple[str, list[str]]:
    labels = _custom_template_token_labels()
    render_context = _custom_render_context(context)
    missing: list[str] = []

    def resolve_token(token: str) -> str:
        if _token_has_forbidden_chars(token) or "|" in token or "__" in token:
            return ""
        value = _template_lookup_value({**render_context, **context}, token)
        if not text(value):
            if token in _OPTIONAL_OPERATIONAL_TEMPLATE_FIELDS:
                return ""
            label = labels.get(token, token.replace(".", " ").replace("_", " "))
            if label not in missing:
                missing.append(label)
            return f"[dato mancante: {label}]" if placeholder_missing else ""
        return str(value)

    output: list[str] = []
    index = 0
    while index < len(body):
        start = body.find("{{", index)
        if start < 0:
            output.append(body[index:])
            break
        end = body.find("}}", start + 2)
        if end < 0:
            output.append(body[index:])
            break
        output.append(body[index:start])
        output.append(resolve_token(body[start + 2:end].strip()))
        index = end + 2
    return "".join(output).strip(), missing


def _assign_context_path(context: dict[str, Any], path: str, value: str) -> None:
    current: dict[str, Any] = context
    parts = [part for part in path.split(".") if part]
    for part in parts[:-1]:
        next_value = current.get(part)
        if not isinstance(next_value, dict):
            next_value = {}
            current[part] = next_value
        current = next_value
    if parts:
        current[parts[-1]] = value


def _standard_preview_tokens(body: str) -> set[str]:
    tokens = {token for token in _iter_template_tokens(body)}
    tokens.update(_iter_simple_if_tokens(body))
    return {
        token
        for token in tokens
        if token and "|" not in token and "__" not in token and not _token_has_forbidden_chars(token)
    }


def _render_standard_template_preview(
    body: str,
    context: dict[str, Any],
    template: dict[str, Any],
) -> tuple[str, list[str]]:
    labels = _custom_template_token_labels()
    preview_context = deepcopy(_custom_render_context(context))
    missing: list[str] = []
    for token in sorted(_standard_preview_tokens(body)):
        value = preview_context.get(token) if token in _OPERATIONAL_TEMPLATE_FIELDS else _context_lookup(preview_context, token)
        if text(value):
            continue
        if token in _OPTIONAL_OPERATIONAL_TEMPLATE_FIELDS:
            preview_context[token] = ""
            continue
        label = labels.get(token) or _field_label(template, token)
        if label not in missing:
            missing.append(label)
        placeholder = f"[dato mancante: {label}]"
        if token in _OPERATIONAL_TEMPLATE_FIELDS:
            preview_context[token] = placeholder
        else:
            _assign_context_path(preview_context, token, placeholder)
    rendered, _ = _render_restricted_template_body(
        _render_supported_if_blocks(body, preview_context),
        preview_context,
        placeholder_missing=True,
    )
    return rendered, missing


def preview_legal_relata(payload: dict[str, Any]) -> dict[str, Any]:
    """Render the selected model with current form data without final blocking checks."""

    template = select_relata_template(payload)
    body = template_preview_text(template)
    context = _build_context(payload, template=template)
    if multiline_text(template.get("custom_body")):
        blockers = validate_custom_template_body(body)
        if blockers:
            return {
                "ok": False,
                "previewText": "",
                "missingFields": [],
                "warnings": [],
                "blockers": blockers,
                "templateId": text(template.get("id")),
                "templateLabel": text(template.get("label")),
            }
        preview_text, missing = _render_restricted_template_body(body, context, placeholder_missing=True)
    else:
        preview_text, missing = _render_standard_template_preview(body, context, template)
    return {
        "ok": True,
        "previewText": preview_text,
        "missingFields": missing,
        "warnings": [f"Da completare nell'anteprima: {label}." for label in missing],
        "blockers": [],
        "templateId": text(template.get("id")),
        "templateLabel": text(template.get("label")),
    }


def _append_lawyer_addition(lines: list[str], payload: dict[str, Any]) -> None:
    addition = text(_first(payload, "notifica.note_integrative_relata", "note_integrative_relata", "integrazione_avvocato"))
    if addition:
        lines.extend(["", "INTEGRAZIONE DELL'AVVOCATO", "", addition])


def _validate_relata_override(
    override: str,
    canonical: str,
    context: dict[str, Any],
) -> list[str]:
    if not override:
        return []
    normalized_override = text(override).casefold()
    normalized_canonical = text(canonical).casefold()
    anchors = [
        "relazione di notificazione",
        context["avvocato"]["codice_fiscale"],
        context["avvocato"]["pec"],
        context["cliente"]["codice_fiscale_piva"],
        context["destinatario"]["pec"],
        context["destinatario"]["fonte_pec"],
        context["destinatario"]["data_verifica_pec"],
        context["destinatario"]["ora_verifica_pec"],
        context["notifica"]["data"],
        context["notifica"]["ora"],
        *(document.get("nome_file") for document in context["documenti"]),
    ]
    if context["procedimento"]["presente"]:
        anchors.extend([
            context["procedimento"]["ufficio"],
            context["procedimento"]["numero_rg"],
            context["procedimento"]["anno_rg"],
        ])
    if "attestazione di conform" in normalized_canonical:
        anchors.append("attestazione di conform")
    missing = [
        text(anchor)
        for anchor in anchors
        if text(anchor) and text(anchor).casefold() not in normalized_override
    ]
    if not missing:
        return []
    visible = ", ".join(dict.fromkeys(missing[:8]))
    return [block(
        "RELAZIONE_CONTENUTO_OBBLIGATORIO_REQUIRED",
        f"La bozza modificata non contiene tutti i dati obbligatori della relata: {visible}.",
    )]


def validate_legal_notification(
    payload: dict[str, Any],
    *,
    require_signed_relata: bool = True,
) -> LegalWorkflowResult:
    """Validate and prepare a controlled L. 53/1994 notification draft."""

    blockers: list[str] = []
    warnings: list[str] = []
    template = select_relata_template(payload)
    context = _build_context(payload, template=template)
    sender_pec_verified = _sender_pec_verified(payload, context)
    recipients_pec_verified = _recipients_pec_verified(payload, context)
    custom_body = multiline_text(template.get("custom_body"))
    if custom_body:
        blockers.extend(validate_custom_template_body(custom_body))
    role = context["destinatario"]["tipo"]
    documents = context["documenti"]
    office_acquisition = _office_document_acquisition_state(payload, context)
    attachment_manifest = build_notification_attachment_manifest(payload, context=context)
    subject = LEGAL_NOTIFICATION_SUBJECT
    subject_input = text(payload.get("oggetto_pec") or payload.get("subject") or _deep_get(payload, "notifica.oggetto_pec"))

    operation = text(payload.get("operazione") or _deep_get(payload, "notifica.operazione"))
    if operation not in {LEGAL_NOTIFICATION_OPERATION, LEGAL_NOTIFICATION_SEND_OPERATION}:
        blockers.append(block("OPERATION_REQUIRED", "Usa il percorso guidato di controllo o invio PEC L. 53/1994."))
    if not subject_input or subject_input.lower() != LEGAL_NOTIFICATION_SUBJECT:
        blockers.append(block("L53_SUBJECT_REQUIRED", "L'oggetto PEC deve essere esattamente: notificazione ai sensi della legge n. 53 del 1994."))
    if not role:
        blockers.append("Seleziona il ruolo del destinatario della notifica.")
    if role in CLIENT_RECIPIENT_ROLES:
        blockers.append(block("CLIENTE_NON_NOTIFICA", "Il cliente non va trattato come destinatario ordinario di una notifica: usa Comunicazione al cliente."))
    if role and role not in LEGAL_RECIPIENT_ROLES and role not in CLIENT_RECIPIENT_ROLES:
        warnings.append("Ruolo destinatario non ricondotto automaticamente: verifica che sia un soggetto notificabile.")
    directive = _validate_notification_directive(payload, context, template, blockers, warnings)

    required_paths = [
        ("avvocato.full_name", "Indica l'avvocato notificante."),
        ("avvocato.codice_fiscale", "Indica il codice fiscale dell'avvocato notificante."),
        ("avvocato.foro", "Indica l'Ordine o foro dell'avvocato."),
        ("avvocato.pec", "Indica la PEC del notificante."),
        ("cliente.nome_denominazione", "Indica la parte assistita."),
        ("cliente.codice_fiscale_piva", "Indica il codice fiscale o la partita IVA della parte assistita."),
        ("destinatario.nome_denominazione", "Indica il destinatario della notifica."),
        ("destinatario.pec", "Indica la PEC del destinatario."),
        ("notifica.luogo", "Indica il luogo della relata."),
        ("notifica.data", "Indica la data della relata."),
        ("notifica.ora", "Indica l'ora italiana della relata."),
    ]
    for path, message in required_paths:
        if not text(_context_lookup(context, path)):
            blockers.append(message)

    if normalise_public_register(_first(payload, "avvocato.fonte_pec", "fonte_pec_mittente")) not in PUBLIC_PEC_REGISTERS:
        blockers.append(block("PEC_MITTENTE_FONTE_REQUIRED", "La PEC del notificante deve risultare da un pubblico elenco."))
    if not sender_pec_verified:
        blockers.append(block("PEC_MITTENTE_VALIDATA_REQUIRED", "Il controllo automatico non ha verificato la PEC del notificante nel pubblico elenco."))

    source_key = context["destinatario"]["fonte_pec_key"]
    if source_key not in PUBLIC_PEC_REGISTERS:
        blockers.append(block("PEC_DESTINATARIO_FONTE_REQUIRED", "La PEC del destinatario deve avere una fonte da pubblico elenco."))
    if not context["destinatario"]["data_verifica_pec"] or not context["destinatario"]["ora_verifica_pec"]:
        blockers.append(block("PEC_DESTINATARIO_VERIFICA_REQUIRED", "Registra data e ora della verifica PEC del destinatario."))
    if not recipients_pec_verified:
        blockers.append(block("PEC_DESTINATARIO_PUBBLICO_ELENCO_REQUIRED", "Il controllo automatico non ha verificato la PEC del destinatario nel pubblico elenco indicato."))
    if not boolish(_first(payload, "notifica.relata_documento_separato", "relata_documento_separato")):
        blockers.append(block("RELATA_SEPARATA_REQUIRED", "La relata deve essere generata come documento separato."))
    if require_signed_relata and not boolish(_first(payload, "notifica.relata_firmata", "relata_firmata")):
        blockers.append(block("RELATA_FIRMATA_REQUIRED", "La relata deve essere firmata digitalmente."))
    if not boolish(payload.get("ricevuta_completa")) or text(payload.get("ricevuta_tipo")).lower() in {"breve", "sintetica", "assente"}:
        blockers.append(block("RICEVUTA_COMPLETA_REQUIRED", "La notifica PEC L. 53/1994 richiede ricevuta di avvenuta consegna completa."))
    if office_acquisition["blocking"]:
        blockers.append(block(
            "DOCUMENTO_UFFICIO_ACQUISIZIONE_REQUIRED",
            "La PEC dell'ufficio comunica un documento da notificare: collegalo ai documenti e atti prima di preparare la relata.",
        ))
    for attachment in attachment_manifest:
        if not attachment.get("required") or attachment.get("present"):
            continue
        if attachment.get("id") == "procura":
            blockers.append(block("PROCURA_ALLEGATO_REQUIRED", "La procura alle liti è necessaria e non risulta già in atti: allegala alla PEC di notifica."))
        elif attachment.get("id") == "eml_ufficio":
            blockers.append(block("PEC_UFFICIO_EML_REQUIRED", "Conserva l'EML originale della PEC dell'ufficio che comunica il provvedimento da notificare."))

    if not documents:
        blockers.append("Seleziona almeno un documento da notificare.")
    for document in documents:
        name = document["nome_file"]
        description = document["descrizione"]
        origin = document["origine"]
        if not name:
            blockers.append(f"Documento {document['index']}: indica il nome esatto del file.")
        if not description:
            blockers.append(f"Documento {document['index']}: indica una descrizione riconoscibile.")
        if origin and origin not in DOCUMENT_ORIGIN_LABELS:
            blockers.append(f"Documento {document['index']}: origine documento non riconosciuta.")
        if name and Path(name).suffix.lower() not in {".pdf", ".pdfa", ".p7m", ".eml", ".msg"}:
            blockers.append(f"Documento {document['index']}: per la notifica guidata usa PDF/PDF-A, file firmato, EML o MSG.")
        if document["necessita_attestazione"] and origin == "copia_fascicolo_informatico":
            _validate_proceeding(context, blockers)
        if document["necessita_attestazione"] and origin == "comunicazione_cancelleria":
            _validate_proceeding(context, blockers)
            if not document["data_comunicazione_cancelleria"]:
                blockers.append(f"Documento {document['index']}: indica la data della comunicazione di cancelleria.")
        if document["necessita_attestazione"] and not _document_attestation_text_present(document, payload):
            blockers.append(block("ATTESTAZIONE_REQUIRED", f"Documento {document['index']}: attestazione di conformità obbligatoria per l'origine indicata."))

    if context["procedimento"]["presente"] or template.get("requires_proceeding"):
        context["procedimento"]["presente"] = True
        _validate_proceeding(context, blockers)

    _validate_required_context(template, context, blockers)

    if boolish(payload.get("invio_finale")):
        if boolish(payload.get("destinatari_multipli")) and not boolish(payload.get("conferma_destinatari_multipli")):
            blockers.append("Per più destinatari nella stessa PEC serve una conferma esplicita.")
        if not boolish(payload.get("approvazione_avvocato")):
            blockers.append("L'invio richiede approvazione finale dell'avvocato.")

    relata_override_text = multiline_text(
        payload.get("relata_override_text")
        or payload.get("bozza_relata_testo")
        or payload.get("relata_text_override")
    )
    if relata_override_text and len(relata_override_text) > 30000:
        blockers.append("La bozza relata modificata è troppo lunga.")
    canonical_relata = render_relata(payload, template=template)
    blockers.extend(_validate_relata_override(relata_override_text, canonical_relata, context))

    blockers = list(dict.fromkeys(blockers))
    if blockers:
        return LegalWorkflowResult(
            ok=False,
            blockers=blockers,
            warnings=warnings,
            subject=subject,
            template_id=text(template.get("id")),
            template_label=text(template.get("label")),
            template_version=template_catalog_version(),
        )

    relata_text = f"{relata_override_text}\n" if relata_override_text else canonical_relata
    body = render_control_document("corpo_pec_standard", payload, template=template)
    checklist = render_control_document("checklist_pre_invio", payload, template=template)
    attestation_blocks = _attestation_blocks(_build_context(payload, template=template))
    selected_blocks = tuple(["procedimento"] if context["procedimento"]["presente"] else []) + tuple(
        f"attestazione:{document['origine']}" for document in context["documenti"] if document["necessita_attestazione"]
    )
    output_plan = build_output_plan(payload)
    output_plan["notificationDirective"] = directive
    output_plan["deliveryPlan"] = build_notification_send_plan(payload, context=context, body=body)
    return LegalWorkflowResult(
        ok=True,
        blockers=[],
        warnings=warnings,
        subject=subject,
        body=body,
        relata_text=relata_text,
        next_actions=(
            "Rivedi la bozza con l'avvocato responsabile.",
            "Esporta la relata in PDF/PDF-A e firmala digitalmente.",
            "Invia una PEC distinta per destinatario con ricevuta completa.",
            "Conserva messaggio inviato, RAC e RdAC in originale digitale.",
        ),
        template_id=text(template.get("id")),
        template_label=text(template.get("label")),
        template_version=template_catalog_version(),
        selected_blocks=selected_blocks,
        checklist_text=checklist,
        log_json=build_generation_log(payload, template=template, attestation_blocks=attestation_blocks),
        output_plan=output_plan,
    )


def render_relata(payload: dict[str, Any], *, template: dict[str, Any] | None = None) -> str:
    template = template or select_relata_template(payload)
    context = _build_context(payload, template=template)
    privacy = bool(template.get("privacy_description"))
    custom_body = multiline_text(template.get("custom_body"))
    if custom_body:
        if validate_custom_template_body(custom_body):
            return ""
        rendered, _missing = _render_restricted_template_body(custom_body, context)
        lines = [rendered] if rendered else []
        _append_lawyer_addition(lines, payload)
        return "\n\n".join(part for part in lines if text(part)).strip() + "\n"

    lines = [
        "RELAZIONE DI NOTIFICAZIONE A MEZZO POSTA ELETTRONICA CERTIFICATA",
        "ai sensi dell'art. 3-bis della Legge 21 gennaio 1994, n. 53",
        "",
        f"Io sottoscritto Avv. {context['avvocato']['full_name']},",
        f"C.F. {context['avvocato']['codice_fiscale']},",
        f"iscritto all'Ordine degli Avvocati di {context['avvocato']['foro']},",
        f"con studio in {context['avvocato']['studio_completo'] or 'indirizzo indicato negli atti di studio'},",
        f"indirizzo PEC {context['avvocato']['pec']},",
        "",
        f"nella qualita' di difensore di {context['cliente']['nome_denominazione']},",
        f"C.F./P.IVA {context['cliente']['codice_fiscale_piva']},",
    ]
    if context["cliente"]["qualifica"]:
        lines.append(f"{context['cliente']['qualifica']},")
    lines.extend([
        "giusta procura alle liti in atti, allegata o rilasciata su separato documento,",
        "",
        "NOTIFICO",
        "",
        f"a {context['destinatario']['nome_denominazione']},",
    ])
    if context["destinatario"]["codice_fiscale_piva"]:
        lines.append(f"C.F./P.IVA {context['destinatario']['codice_fiscale_piva']},")
    if context["destinatario"]["parte_rappresentata"]:
        lines.append(f"quale difensore di {context['destinatario']['parte_rappresentata']},")
    if context["destinatario"]["qualifica"]:
        lines.append(f"in qualita' di {context['destinatario']['qualifica']},")
    lines.extend([
        f"all'indirizzo PEC {context['destinatario']['pec']},",
        f"estratto dal pubblico elenco {context['destinatario']['fonte_pec']}",
        f" in data {context['destinatario']['data_verifica_pec']}"
        f"{(' alle ore ' + context['destinatario']['ora_verifica_pec']) if context['destinatario']['ora_verifica_pec'] else ''},",
        "",
        "i seguenti documenti informatici allegati al presente messaggio PEC:",
        "",
        *_document_rows(context, privacy=privacy),
    ])

    if context["procedimento"]["presente"] or template.get("requires_proceeding"):
        proceeding_lines = _proceeding_lines(context)
        if proceeding_lines:
            lines.extend(["", *proceeding_lines])

    purpose_lines = _render_lines(template.get("purpose_lines") or [], context)
    if purpose_lines:
        lines.extend(["", *purpose_lines])

    attestations = _attestation_blocks(context)
    manual_attestation = text(payload.get("attestazione_conformita"))
    if manual_attestation:
        if attestations:
            attestations[0] = f"{attestations[0]}\n\nPrecisazione dell'avvocato:\n{manual_attestation}"
        else:
            attestations.append(manual_attestation)
    if attestations:
        lines.extend(["", "ATTESTAZIONE DI CONFORMITÀ", ""])
        for block in attestations:
            lines.extend([block, ""])

    _append_lawyer_addition(lines, payload)

    lines.extend([
        f"{context['notifica']['luogo']}, {context['notifica']['data']}".strip(", "),
        "",
        context["avvocato"]["firma_in_calce"],
        context["avvocato"]["firma_digitale_dicitura"],
    ])
    return "\n".join(lines).strip() + "\n"


def render_control_document(template_id: str, payload: dict[str, Any], *, template: dict[str, Any] | None = None) -> str:
    control_template = get_notification_template(template_id)
    if not control_template:
        return ""
    context = _build_context(payload, template=template)
    return "\n".join(_render_lines(control_template.get("content_lines") or [], context)).strip()


def build_generation_log(
    payload: dict[str, Any],
    *,
    template: dict[str, Any] | None = None,
    attestation_blocks: list[str] | None = None,
) -> dict[str, Any]:
    template = template or select_relata_template(payload)
    context = _build_context(payload, template=template)
    return {
        "evento": "generazione_relata",
        "template_id": text(template.get("id")),
        "template_versione": template_catalog_version(),
        "data_generazione": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "utente_generatore": text(_first(payload, "utente.nome", "utente_generatore")),
        "avvocato_responsabile": context["avvocato"]["full_name"],
        "pratica": context["pratica"]["codice"],
        "procedimento": (
            f"{context['procedimento']['numero_rg']}/{context['procedimento']['anno_rg']}"
            if context["procedimento"]["numero_rg"] or context["procedimento"]["anno_rg"]
            else ""
        ),
        "destinatario": context["destinatario"]["nome_denominazione"],
        "pec_destinatario": context["destinatario"]["pec"],
        "fonte_pec": context["destinatario"]["fonte_pec"],
        "documenti": [
            {
                "nome_file": document["nome_file"],
                "descrizione": document["descrizione"],
                "origine": document["origine"],
                "hash_sha256": document["hash_sha256"],
                "attestazione": bool(document["necessita_attestazione"]),
            }
            for document in context["documenti"]
        ],
        "relata_firmata": boolish(_first(payload, "notifica.relata_firmata", "relata_firmata")),
        "firma_tipo": text(_first(payload, "notifica.firma_tipo", "firma_tipo", fallback="PAdES")),
        "oggetto_pec": LEGAL_NOTIFICATION_SUBJECT,
        "ricevuta_richiesta": "completa",
        "public_registry_checked": True,
        "attestazioni": attestation_blocks or [],
    }


def legal_notification_automation_payload() -> dict[str, list[dict[str, str]]]:
    """Expose the guided statutory workflow used by API, UI and demo reports."""

    return {
        "notifica": [dict(item) for item in LEGAL_NOTIFICATION_AUTOMATION_STEPS],
        "deposito": [dict(item) for item in LEGAL_NOTIFICATION_DEPOSIT_STEPS],
        "allegati": [dict(item) for item in LEGAL_NOTIFICATION_ATTACHMENT_RULES],
        "unep": [
            {
                "id": "unep_canale",
                "title": "Seleziona canale UNEP",
                "body": "Distingui notifica a mani, posta, estero o telematica e usa l'ufficio NEP competente.",
                "source": "PST, XSD UNEP 06/11/2024.",
            },
            {
                "id": "unep_richiesta",
                "title": "Controlla richiesta e destinatario",
                "body": "Atto, richiesta/relata, destinatario, indirizzo o PEC e spese devono essere completi prima del deposito sul canale UNEP.",
                "source": "Artt. 137-149 c.p.c.; canale UNEP.",
            },
            {
                "id": "unep_ricevute",
                "title": "Conserva ricevute e ritorni",
                "body": "Ricevute del portale, pagamenti e ritorno dell'ufficio restano nel fascicolo e non sono prova PEC L. 53.",
                "source": "Audit IUSENTRA notifiche.",
            },
        ],
        "nonPec": [
            {
                "id": "nonpec_tipo",
                "title": "Classifica il canale",
                "body": "Raccomandata, ufficiale giudiziario, consegna a mani, estero o altro canale hanno dati e prove diversi.",
                "source": "Artt. 137-149 c.p.c.",
            },
            {
                "id": "nonpec_date",
                "title": "Registra data e identificativo",
                "body": "Data notifica, identificativo interno e dati di ricezione sono obbligatori per ricostruire il tracciamento storico.",
                "source": "Matrice import dati pratica.",
            },
            {
                "id": "nonpec_prova",
                "title": "Collega la prova documentale",
                "body": "Avviso, relata, ricevuta o prova di consegna devono avere file e impronta verificabile.",
                "source": "Audit IUSENTRA notifiche.",
            },
        ],
    }


def _check_row(
    *,
    id: str,
    label: str,
    source: str,
    passed: bool,
    detail: str,
    blocking: bool = True,
) -> dict[str, Any]:
    if passed:
        status = "superato"
    elif blocking:
        status = "bloccante"
    else:
        status = "da completare"
    return {
        "id": id,
        "label": label,
        "source": source,
        "status": status,
        "detail": detail,
        "blocking": blocking,
    }


def build_notification_normative_checks(payload: dict[str, Any], *, context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return the legal checks applied to the L. 53/1994 notification draft."""

    context = context or _build_context(payload, template=select_relata_template(payload))
    sender_pec_verified = _sender_pec_verified(payload, context)
    recipients_pec_verified = _recipients_pec_verified(payload, context)
    documents = context["documenti"]
    office_acquisition = _office_document_acquisition_state(payload, context)
    office_pec_eml = _office_pec_eml_state(payload)
    directive = resolve_legal_notification_directive(payload, context)
    attachment_manifest = build_notification_attachment_manifest(payload, context=context)
    attestation_required = any(document["necessita_attestazione"] for document in documents)
    attestation_present = not attestation_required or all(
        _document_attestation_text_present(document, payload)
        for document in documents
        if document["necessita_attestazione"]
    )
    return [
        _check_row(
            id="oggetto_l53",
            label="Oggetto PEC obbligatorio",
            source="L. 53/1994, art. 3-bis, comma 4",
            passed=text(payload.get("oggetto_pec")).lower() == LEGAL_NOTIFICATION_SUBJECT,
            detail="La PEC deve usare la formula prevista per la notificazione in proprio.",
        ),
        _check_row(
            id="pec_mittente",
            label="PEC notificante da pubblico elenco",
            source="L. 53/1994, art. 3-bis, comma 1",
            passed=sender_pec_verified,
            detail="La casella del notificante deve essere verificata automaticamente nel pubblico elenco.",
        ),
        _check_row(
            id="pec_destinatario",
            label="PEC destinatario e fonte",
            source="D.L. 179/2012, art. 16-ter",
            passed=context["destinatario"]["fonte_pec_key"] in PUBLIC_PEC_REGISTERS
            and recipients_pec_verified
            and bool(context["destinatario"]["data_verifica_pec"]),
            detail="Sono richiesti esito automatico, fonte pubblica, data e ora della verifica.",
        ),
        _check_row(
            id="destinatario_casistica",
            label="Destinatario coerente con il caso",
            source="; ".join(item["label"] for item in directive.get("caseLegalBasis", [])) or "L. 53/1994",
            passed=directive["role"] not in LEGAL_RECIPIENT_ROLES or directive["role"] in directive["allowedRecipientRoles"],
            detail=directive.get("recipientRule") or "La casistica deve essere verificata prima dell'invio.",
        ),
        _check_row(
            id="allegati",
            label="Allegati della notifica",
            source="Specifiche tecniche DGSIA 7 agosto 2024, art. 26",
            passed=all(item.get("present") for item in attachment_manifest if item.get("phase") == "pec_notifica" and item.get("required")),
            detail="; ".join(f"{item['label']}: {'presente' if item.get('present') else 'mancante'}" for item in attachment_manifest if item.get("phase") == "pec_notifica"),
        ),
        _check_row(
            id="eml_pec_ufficio",
            label="EML PEC ufficio",
            source="Specifiche tecniche DGSIA 7 agosto 2024, artt. 21, 22 e 25",
            passed=bool(office_pec_eml["present"]),
            blocking=bool(office_pec_eml["required"]),
            detail=(
                "EML o Message-ID della PEC dell'ufficio conservato."
                if office_pec_eml["present"] and office_pec_eml["required"]
                else "Non richiesto se il trigger non nasce da PEC dell'ufficio."
                if not office_pec_eml["required"]
                else "Quando la PEC dell'ufficio comunica il rilascio, l'EML originale va conservato come evidenza."
            ),
        ),
        _check_row(
            id="documento_ufficio_acquisito",
            label="Documento ufficio acquisito",
            source="Specifiche tecniche DGSIA 7 agosto 2024, artt. 21, 22 e 25",
            passed=not office_acquisition["acquisitionRequired"] or office_acquisition["acquired"],
            blocking=bool(office_acquisition["blocking"]),
            detail=(
                "Documento comunicato dall'ufficio già collegato a Documenti e atti."
                if office_acquisition["acquired"]
                else "Se la PEC dell'ufficio comunica un documento da notificare, quel documento deve essere collegato prima della relata."
            ),
        ),
        _check_row(
            id="attestazioni",
            label="Attestazioni di conformità",
            source="L. 53/1994, art. 3-bis, comma 2",
            passed=attestation_present,
            detail=(
                "Attestazioni non necessarie per gli allegati selezionati."
                if not attestation_required
                else "Attestazioni richieste per copie da fascicolo, cancelleria o scansioni."
            ),
        ),
        _check_row(
            id="relata",
            label="Relata separata e firma digitale",
            source="L. 53/1994, art. 3-bis, comma 5",
            passed=boolish(_first(payload, "notifica.relata_documento_separato", "relata_documento_separato"))
            and boolish(_first(payload, "notifica.relata_firmata", "relata_firmata")),
            detail="La relata deve essere documento informatico separato e firmato digitalmente.",
        ),
        _check_row(
            id="ricevuta_completa",
            label="RdAC completa",
            source="D.M. 44/2011, art. 18, comma 6",
            passed=boolish(payload.get("ricevuta_completa")) and text(payload.get("ricevuta_tipo")).lower() not in {"breve", "sintetica", "assente"},
            detail="La ricevuta di avvenuta consegna deve essere completa.",
        ),
    ]


def build_notification_audit_trail(
    payload: dict[str, Any],
    *,
    context: dict[str, Any] | None = None,
    phase: str = "notifica",
    evidence_pack: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Create a compact, user-facing audit summary for the guided workflow."""

    context = context or _build_context(payload, template=select_relata_template(payload))
    documents = context["documenti"]
    attestation_blocks = _attestation_blocks(context)
    office_acquisition = _office_document_acquisition_state(payload, context)
    return {
        "phase": phase,
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "practice": context["pratica"]["codice"],
        "recipient": context["destinatario"]["nome_denominazione"],
        "recipientPec": context["destinatario"]["pec"],
        "recipientPecSource": context["destinatario"]["fonte_pec"],
        "documentsCount": len(documents),
        "documents": [
            {
                "name": document["nome_file"],
                "description": document["descrizione"],
                "origin": document["origine"],
                "sha256": document["hash_sha256"],
                "attestationRequired": bool(document["necessita_attestazione"]),
            }
            for document in documents
        ],
        "officeDocumentAcquisition": office_acquisition,
        "attachmentManifest": build_notification_attachment_manifest(payload, context=context),
        "notificationDirective": resolve_legal_notification_directive(payload, context),
        "signaturePlan": build_notification_signature_plan(payload, context=context),
        "timingPlan": build_notification_timing_plan(payload),
        "attestationsGenerated": attestation_blocks,
        "checks": build_notification_normative_checks(payload, context=context),
        "evidencePack": evidence_pack or {},
    }


def build_output_plan(payload: dict[str, Any]) -> dict[str, Any]:
    context = _build_context(payload, template=select_relata_template(payload))
    date = re.sub(r"[^0-9]", "-", context["notifica"]["data"]).strip("-") or datetime.now().strftime("%Y-%m-%d")
    recipient = re.sub(r"[^A-Za-z0-9]+", "_", context["destinatario"]["nome_denominazione"]).strip("_").lower() or "destinatario"
    folder = f"notifica_{date}_{recipient}"
    files = [
        "relata_notifica.pdf",
        "relata_notifica_firmata.pdf oppure relata_notifica.pdf.p7m",
        *[document["nome_file"] for document in context["documenti"] if document["nome_file"]],
        "pec_inviata.eml",
        "ricevuta_accettazione.eml",
        "ricevuta_consegna_completa.eml",
        "eventuali_avvisi_errore.eml",
        "log_notifica.json",
        "distinta_prova_notifica.pdf",
        "scheda_esito_notifica.pdf",
    ]
    return {
        "folder": folder,
        "files": files,
        "workflowSteps": [dict(item) for item in LEGAL_NOTIFICATION_AUTOMATION_STEPS],
        "attachmentRules": [dict(item) for item in LEGAL_NOTIFICATION_ATTACHMENT_RULES],
        "attachmentManifest": build_notification_attachment_manifest(payload, context=context),
        "notificationDirective": resolve_legal_notification_directive(payload, context),
        "signaturePlan": build_notification_signature_plan(payload, context=context),
        "timingPlan": build_notification_timing_plan(payload),
        "normativeChecks": build_notification_normative_checks(payload, context=context),
        "deliveryPlan": build_notification_send_plan(payload, context=context),
        "auditTrail": build_notification_audit_trail(payload, context=context),
    }


def generate_relata_pdf_bytes(payload: dict[str, Any], *, pdfa: bool = False) -> bytes:
    # Il PDF e' il documento sorgente da sottoporre a firma: la prova della
    # firma viene richiesta soltanto dopo che Local Signer lo ha restituito.
    result = validate_legal_notification(payload, require_signed_relata=False)
    if not result.ok:
        raise ValueError("; ".join(result.blockers))

    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import mm
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer

    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        leftMargin=22 * mm,
        rightMargin=22 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title="Relata di notificazione",
    )
    styles = getSampleStyleSheet()
    body = ParagraphStyle(
        "RelataBody",
        parent=styles["BodyText"],
        fontName="Times-Roman",
        fontSize=10.5,
        leading=15,
        spaceAfter=4,
    )
    title = ParagraphStyle(
        "RelataTitle",
        parent=styles["Title"],
        fontName="Times-Bold",
        fontSize=13,
        leading=17,
        spaceAfter=8,
    )
    story = []
    for index, line in enumerate(result.relata_text.splitlines()):
        if not line.strip():
            story.append(Spacer(1, 5))
            continue
        style = title if index < 2 else body
        story.append(Paragraph(escape(line), style))
    doc.build(story)
    data = buffer.getvalue()
    if not pdfa:
        return data

    with tempfile.TemporaryDirectory() as tmp_dir:
        pdf_path = Path(tmp_dir) / "relata_notifica.pdf"
        pdfa_path = Path(tmp_dir) / "relata_notifica_pdfa.pdf"
        pdf_path.write_bytes(data)
        try:
            from pct.validazione import converti_pdfa

            conversion = converti_pdfa(str(pdf_path), str(pdfa_path))
            if conversion.get("ok") and pdfa_path.exists():
                return pdfa_path.read_bytes()
            raise RuntimeError(text(conversion.get("messaggio"), "Conversione PDF/A non completata."))
        except Exception as exc:  # pragma: no cover - dipende dagli strumenti locali PDF/A.
            raise RuntimeError("Conversione PDF/A non completata sul sistema corrente.") from exc


def _client_communication_context(payload: dict[str, Any]) -> dict[str, Any]:
    cliente_nome = text(payload.get("cliente_nome") or _deep_get(payload, "cliente.nome_denominazione"), "Cliente")
    ufficio = text(payload.get("ufficio_giudiziario") or _deep_get(payload, "procedimento.ufficio"))
    rg = text(payload.get("numero_rg") or _deep_get(payload, "procedimento.numero_rg"))
    anno = text(payload.get("anno_rg") or _deep_get(payload, "procedimento.anno_rg"))
    riferimento = f"R.G. {rg}/{anno}" if rg and anno else (f"R.G. {rg or anno}" if rg or anno else "")
    documento = text(payload.get("provvedimento_descrizione") or payload.get("documento_descrizione") or _deep_get(payload, "documento.descrizione"))
    return {
        "cliente": {"nome": cliente_nome},
        "pratica": {"codice": text(payload.get("pratica_codice") or _deep_get(payload, "pratica.codice"))},
        "procedimento": {
            "ufficio": ufficio,
            "numero_rg": rg,
            "anno_rg": anno,
            "riferimento": " - ".join(part for part in (ufficio, riferimento) if part),
        },
        "documento": {"descrizione": documento},
        "studio": {"nome": text(payload.get("studio_nome") or _deep_get(payload, "studio.nome"), "lo Studio")},
        "prossimi_passi": text(payload.get("prossimi_passi"), "Lo studio resta a disposizione per concordare i prossimi passaggi."),
    }


def _client_token_labels() -> dict[str, str]:
    return {
        _token_name(item["token"]): item["label"]
        for item in CLIENT_COMMUNICATION_FIELDS
        if _token_name(item["token"])
    }


def _render_client_template_text(template_text: str, context: dict[str, Any]) -> str:
    labels = _client_token_labels()
    allowed = set(labels)
    output: list[str] = []
    index = 0

    while index < len(template_text):
        start = template_text.find("{{", index)
        if start < 0:
            output.append(template_text[index:])
            break
        end = template_text.find("}}", start + 2)
        if end < 0:
            output.append(template_text[index:])
            break
        output.append(template_text[index:start])
        token = template_text[start + 2:end].strip()
        if token in allowed and "|" not in token and "__" not in token and not _token_has_forbidden_chars(token):
            output.append(text(_context_lookup(context, token)))
        index = end + 2
    return "".join(output).strip()


def build_client_communication(payload: dict[str, Any]) -> LegalWorkflowResult:
    """Prepare an informative communication to the client, without relata."""

    blockers: list[str] = []
    warnings: list[str] = []
    operation = text(payload.get("operazione") or _deep_get(payload, "comunicazione.operazione"))
    if operation != CLIENT_COMMUNICATION_OPERATION:
        blockers.append(block("CLIENT_COMMUNICATION_OPERATION_REQUIRED", "La comunicazione al cliente deve usare il percorso comunicazione_cliente_non_notifica."))
    if not text(payload.get("cliente_nome") or _deep_get(payload, "cliente.nome_denominazione")):
        blockers.append("Seleziona il cliente destinatario della comunicazione.")
    if is_legal_notification_subject(payload.get("oggetto")):
        blockers.append("La comunicazione al cliente non deve usare l'oggetto della notifica L. 53/1994.")
    if boolish(payload.get("genera_relata")):
        blockers.append("La comunicazione al cliente non genera una relata di notificazione.")
    if text(payload.get("relataText") or payload.get("relata_text") or payload.get("relata_override_text")):
        blockers.append("La comunicazione al cliente non deve contenere la relata.")
    template_id = text(payload.get("template_id") or payload.get("modello_cliente"), "aggiornamento_pratica")
    if template_id.startswith("relata_") or get_notification_template(template_id):
        blockers.append("Scegli un modello comunicazione cliente, non un modello relata.")
    template = get_client_communication_template(template_id) or get_client_communication_template("aggiornamento_pratica")
    if not template:
        blockers.append("Modello comunicazione cliente non disponibile.")
    if not text(payload.get("provvedimento_descrizione")):
        warnings.append("Aggiungi una descrizione del provvedimento o documento trasmesso.")

    context = _client_communication_context(payload)
    subject_override = text(payload.get("subject") or payload.get("oggetto"))
    if subject_override and is_legal_notification_subject(subject_override):
        blockers.append("La comunicazione al cliente non deve usare l'oggetto della notifica L. 53/1994.")
    subject_template = text((template or {}).get("subject"), "Aggiornamento pratica")
    subject = subject_override or _render_client_template_text(subject_template, context)
    body_override = multiline_text(payload.get("body_override") or payload.get("corpo") or payload.get("body"))
    if body_override and is_legal_notification_subject(body_override):
        blockers.append("Il corpo della comunicazione non deve riportare l'oggetto della notifica L. 53/1994.")
    body_template = "\n".join(str(line) for line in ((template or {}).get("body_lines") or []))
    body = body_override or _render_client_template_text(body_template, context)
    blockers = list(dict.fromkeys(blockers))
    return LegalWorkflowResult(
        ok=not blockers,
        blockers=blockers,
        warnings=warnings,
        subject=subject,
        body=body,
        template_id=text((template or {}).get("id"), template_id),
        template_label=text((template or {}).get("label"), "Comunicazione cliente"),
        template_version=client_communication_templates_version(),
        next_actions=("Invia al cliente via email ordinaria, PEC informativa o link sicuro.",),
    )


def _hash_text(value: str) -> str:
    import hashlib

    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _payload_hash(payload: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = text(payload.get(key))
        if value:
            return value
    return ""


def _evidence_item(
    *,
    kind: str,
    label: str,
    filename: Any,
    sha256: str = "",
    required: bool = True,
    generated: bool = False,
) -> dict[str, Any]:
    file_text = text(filename)
    digest = text(sha256)
    return {
        "kind": kind,
        "label": label,
        "filename": file_text,
        "sha256": digest,
        "required": required,
        "generated": generated,
    }


def build_notification_evidence_pack(payload: dict[str, Any]) -> dict[str, Any]:
    """Build the notification/deposit evidence inventory with SHA-256 checks."""

    items: list[dict[str, Any]] = []
    notified_documents = payload.get("atti_notificati")
    if isinstance(notified_documents, list) and notified_documents:
        for index, document in enumerate(notified_documents, start=1):
            row = document if isinstance(document, dict) else {"nome_file": document}
            items.append(_evidence_item(
                kind="atto" if index == 1 else f"allegato_{index}",
                label="Atto notificato" if index == 1 else f"Allegato notificato {index}",
                filename=row.get("nome_file") or row.get("filename") or row.get("file") or row.get("riferimento_portale"),
                sha256=text(row.get("hash_sha256") or row.get("sha256")),
            ))
    else:
        items.append(_evidence_item(
            kind="atto",
            label="Atto notificato",
            filename=payload.get("atto_notificato"),
            sha256=_payload_hash(payload, "atto_sha256", "atto_notificato_sha256"),
        ))

    items.extend([
        _evidence_item(
            kind="relata_firmata",
            label="Relata firmata",
            filename=payload.get("relata_firmata"),
            sha256=_payload_hash(payload, "relata_sha256", "relata_firmata_sha256"),
        ),
        _evidence_item(
            kind="pec_inviata",
            label="PEC inviata",
            filename=payload.get("pec_inviata") or payload.get("pec_inviata_file"),
            sha256=_payload_hash(payload, "pec_inviata_sha256", "pec_sha256"),
        ),
    ])
    office_pec = _office_pec_eml_state(payload)
    if office_pec["required"] or office_pec["emlFile"]:
        items.append(_evidence_item(
            kind="pec_ufficio_rilascio",
            label="PEC ufficio rilascio provvedimento",
            filename=office_pec["emlFile"] or office_pec["messageId"],
            sha256=office_pec["sha256"],
            required=bool(office_pec["required"]),
        ))

    recipients = payload.get("destinatari")
    if not isinstance(recipients, list):
        recipients = [{
            "nome": payload.get("destinatario_nome"),
            "rac_file": payload.get("rac_file"),
            "rac_sha256": payload.get("rac_sha256"),
            "rdac_file": payload.get("rdac_file"),
            "rdac_sha256": payload.get("rdac_sha256"),
        }]
    for index, recipient in enumerate(recipients, start=1):
        row = recipient if isinstance(recipient, dict) else {}
        label = text(row.get("nome"), f"destinatario {index}")
        items.append(_evidence_item(
            kind="rac",
            label=f"RAC {label}",
            filename=row.get("rac_file"),
            sha256=text(row.get("rac_sha256")),
        ))
        items.append(_evidence_item(
            kind="rdac_completa",
            label=f"RdAC completa {label}",
            filename=row.get("rdac_file"),
            sha256=text(row.get("rdac_sha256")),
        ))

    warnings = payload.get("avvisi_errore")
    if isinstance(warnings, list):
        for index, warning in enumerate(warnings, start=1):
            row = warning if isinstance(warning, dict) else {"file": warning}
            items.append(_evidence_item(
                kind="avviso_errore",
                label=f"Avviso errore {index}",
                filename=row.get("file") or row.get("filename"),
                sha256=text(row.get("sha256")),
                required=False,
            ))
    elif text(payload.get("avviso_mancata_consegna")):
        items.append(_evidence_item(
            kind="avviso_errore",
            label="Avviso mancata consegna",
            filename=payload.get("avviso_mancata_consegna"),
            sha256=_payload_hash(payload, "avviso_mancata_consegna_sha256", "avviso_sha256"),
            required=False,
        ))

    generated_log = json.dumps(
        {
            "evento": "evidence_pack_notifica",
            "data_generazione": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
            "atto_notificato": text(payload.get("atto_notificato")),
            "destinatario": text(payload.get("destinatario_nome")),
        },
        ensure_ascii=False,
        sort_keys=True,
    )
    items.extend([
        _evidence_item(
            kind="log_json",
            label="Log JSON",
            filename=text(payload.get("log_json_file"), "log_notifica.json"),
            sha256=_payload_hash(payload, "log_json_sha256") or _hash_text(generated_log),
            generated=True,
        ),
        _evidence_item(
            kind="distinta_prova_notifica",
            label="Distinta prova notifica",
            filename=text(payload.get("distinta_prova_notifica"), "distinta_prova_notifica.pdf"),
            sha256=_payload_hash(payload, "distinta_sha256") or _hash_text("distinta_prova_notifica"),
            generated=True,
        ),
        _evidence_item(
            kind="scheda_esito",
            label="Scheda esito",
            filename=text(payload.get("scheda_esito"), "scheda_esito_notifica.pdf"),
            sha256=_payload_hash(payload, "scheda_esito_sha256") or _hash_text("scheda_esito_notifica"),
            generated=True,
        ),
    ])

    missing: list[str] = []
    invalid_hashes: list[str] = []
    for item in items:
        if not item["required"]:
            continue
        if not item["filename"]:
            missing.append(f"{item['label']}: file mancante.")
        if not item["sha256"]:
            missing.append(f"{item['label']}: impronta del file mancante.")
        elif not SHA256_HEX_RE.fullmatch(str(item["sha256"])):
            invalid_hashes.append(f"{item['label']}: impronta del file non valida.")
    return {
        "items": items,
        "missing": missing,
        "invalid_hashes": invalid_hashes,
        "hashes": {item["kind"]: item["sha256"] for item in items if item["sha256"]},
    }


def prepare_pst_failed_notification_workflow(payload: dict[str, Any]) -> LegalWorkflowResult:
    """Prepare the PST area web workflow after failed PEC delivery."""

    blockers: list[str] = []
    warnings: list[str] = []
    if not boolish(payload.get("pec_non_consegnata")):
        blockers.append(block("PEC_FAILED_REQUIRED", "Il workflow PST area web richiede una PEC non consegnata."))
    assessment = text(payload.get("valutazione_avvocato") or payload.get("causa_mancata_consegna"))
    if not assessment:
        blockers.append(block("LAWYER_ASSESSMENT_REQUIRED", "Serve la valutazione dell'avvocato sulla causa della mancata consegna."))
    attributable = boolish(payload.get("causa_imputabile_destinatario"))
    if assessment and not attributable:
        warnings.append("La causa non risulta imputabile al destinatario: prepara un canale alternativo e non dichiarare perfezionata la notifica.")

    evidence_pack = build_notification_evidence_pack(payload)
    if attributable:
        missing_notice = not text(payload.get("avviso_mancata_consegna"))
        if missing_notice:
            blockers.append(block("AVVISO_MANCATA_CONSEGNA_REQUIRED", "Allega l'avviso di mancata consegna ex D.P.R. 68/2005."))
        blockers.extend(block("EVIDENCE_PACK_REQUIRED", item) for item in evidence_pack["missing"])
        blockers.extend(block("HASH_SHA256_INVALID", item) for item in evidence_pack.get("invalid_hashes", []))

    ok = not blockers
    return LegalWorkflowResult(
        ok=ok,
        blockers=list(dict.fromkeys(blockers)),
        warnings=warnings,
        subject="Workflow area web PST" if attributable else "Valutazione canale alternativo",
        body=(
            "Prepara deposito area web PST con atto, relata, RAC e avviso di mancata consegna."
            if attributable and ok
            else "Non dichiarare perfezionata la notifica; valuta nuovo invio o canale alternativo."
        ),
        template_id="workflow_deposito_area_web_pst" if attributable else "nota_mancata_consegna",
        template_label="Workflow deposito area web PST" if attributable else "Nota mancata consegna",
        template_version=template_catalog_version(),
        next_actions=(
            "Verifica la causa con l'avvocato responsabile.",
            "Prepara evidence pack per area web PST.",
            "Procedi solo con conferma manuale sul portale PST.",
        ) if attributable else (
            "Non considerare perfezionata la notifica.",
            "Scegli un canale alternativo o rinnova la notifica.",
        ),
        output_plan={
            "evidencePack": evidence_pack,
            "legalBasis": _legal_source_rows("l53_art3ter", "dpr68_art6_8", "dgsia_2024_art26"),
            "portalSteps": [
                "Predisponi notifica nell'area riservata PST",
                "Carica atto o PEC non perfezionata",
                "Carica relata di notifica",
                "Carica avviso di mancata consegna in formato EML",
                "Scarica certificazione dopo il decorso previsto",
            ],
        },
        log_json={
            "workflow": "pst_area_web_notifica_fallita",
            "evidencePack": evidence_pack,
            "legalBasis": [item["id"] for item in _legal_source_rows("l53_art3ter", "dpr68_art6_8", "dgsia_2024_art26")],
        },
    )


def _file_with_hash(payload: dict[str, Any], file_key: str, hash_key: str, *, label: str, blockers: list[str]) -> dict[str, str]:
    filename = text(payload.get(file_key))
    file_hash = text(payload.get(hash_key)).lower()
    if not filename:
        blockers.append(f"Allega {label}.")
    if filename and not file_hash:
        blockers.append(f"Calcola o inserisci l'impronta del file per {label}.")
    elif file_hash and not SHA256_HEX_RE.fullmatch(file_hash):
        blockers.append(block("HASH_SHA256_INVALID", f"{label}: impronta del file non valida."))
    return {"filename": filename, "sha256": file_hash}


def build_unep_notification_checks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    tipo = normalise_unep_notification_type(payload.get("tipo_notifica_unep") or payload.get("tipo_notifica"))
    telematica = tipo == "telematica"
    estero = tipo == "estero"
    precetto_required = boolish(payload.get("precetto_gia_notificato")) or "precetto" in text(payload.get("atto_descrizione")).lower()
    address_ok = bool(text(payload.get("destinatario_indirizzo"))) and (
        bool(text(payload.get("destinatario_comune"))) or bool(text(payload.get("destinatario_paese")))
    )
    pec_source = normalise_public_register(payload.get("fonte_pec_destinatario"))
    payment_due = boolish(payload.get("spese_unep_dovute"))
    return [
        _check_row(
            id="ufficio_unep",
            label="Ufficio NEP",
            source="PST, XSD UNEP 06/11/2024",
            passed=bool(text(payload.get("ufficio_unep"))),
            detail="La richiesta deve indicare l'ufficio NEP destinatario del deposito.",
        ),
        _check_row(
            id="tipo_notifica",
            label="Tipo notifica",
            source="Canale UNEP",
            passed=tipo in UNEP_NOTIFICATION_TYPES,
            detail="Il canale deve essere classificato tra mani, posta, estero o telematica.",
        ),
        _check_row(
            id="atto_richiesta",
            label="Atto e richiesta",
            source="PST, XSD UNEP 06/11/2024",
            passed=bool(text(payload.get("atto_notificare"))) and bool(text(payload.get("richiesta_o_relata"))),
            detail="Atto da notificare e richiesta/relata sono documenti distinti del fascicolo UNEP.",
        ),
        _check_row(
            id="destinatario",
            label="Destinatario",
            source="Artt. 137-149 c.p.c.",
            passed=bool(text(payload.get("destinatario_nome"))),
            detail="Il destinatario deve essere identificato prima della richiesta.",
        ),
        _check_row(
            id="recapito_destinatario",
            label="Recapito destinatario",
            source="Artt. 137-149 c.p.c.; L. 53/1994 solo se il canale è telematico",
            passed=(
                bool(text(payload.get("destinatario_pec"))) and pec_source in PUBLIC_PEC_REGISTERS
                if telematica
                else address_ok and (not estero or bool(text(payload.get("destinatario_paese"))))
            ),
            detail="Il canale telematico richiede PEC e pubblico elenco; gli altri canali richiedono indirizzo fisico completo.",
        ),
        _check_row(
            id="precetto",
            label="Data notifica precetto",
            source="Controllo operativo UNEP",
            passed=not precetto_required or bool(text(payload.get("data_notifica_precetto"))),
            detail="Quando il precetto è rilevante, la data della sua notifica deve essere esplicita.",
        ),
        _check_row(
            id="spese",
            label="Spese e pagamenti",
            source="Canale UNEP",
            passed=not payment_due or bool(text(payload.get("ricevuta_pagamento"))),
            detail="Se sono dovute spese o anticipazioni, la ricevuta va collegata al fascicolo.",
            blocking=payment_due,
        ),
    ]


def validate_unep_notification_request(payload: dict[str, Any]) -> LegalWorkflowResult:
    """Validate a governed UNEP notification request without treating it as PEC L. 53 proof."""

    blockers: list[str] = []
    warnings: list[str] = []
    tipo = normalise_unep_notification_type(payload.get("tipo_notifica_unep") or payload.get("tipo_notifica"))
    telematica = tipo == "telematica"
    estero = tipo == "estero"
    payment_due = boolish(payload.get("spese_unep_dovute"))
    precetto_required = boolish(payload.get("precetto_gia_notificato")) or "precetto" in text(payload.get("atto_descrizione")).lower()

    if text(payload.get("operazione")) not in {"", UNEP_NOTIFICATION_OPERATION}:
        blockers.append(block("OPERAZIONE_UNEP_REQUIRED", "Usa il canale UNEP per questa richiesta."))
    if not text(payload.get("ufficio_unep")):
        blockers.append(block("UFFICIO_UNEP_REQUIRED", "Indica l'ufficio NEP destinatario."))
    if tipo not in UNEP_NOTIFICATION_TYPES:
        blockers.append(block("TIPO_UNEP_REQUIRED", "Seleziona il tipo di notifica UNEP."))
    if not text(payload.get("destinatario_nome")):
        blockers.append(block("DESTINATARIO_REQUIRED", "Indica il destinatario della notifica UNEP."))
    if telematica:
        if not text(payload.get("destinatario_pec")):
            blockers.append(block("DESTINATARIO_PEC_REQUIRED", "Per notifica telematica UNEP indica la PEC destinatario."))
        if normalise_public_register(payload.get("fonte_pec_destinatario")) not in PUBLIC_PEC_REGISTERS:
            blockers.append(block("DESTINATARIO_FONTE_PEC_REQUIRED", "Per notifica telematica UNEP indica il pubblico elenco PEC."))
    else:
        if not text(payload.get("destinatario_indirizzo")):
            blockers.append(block("DESTINATARIO_INDIRIZZO_REQUIRED", "Indica l'indirizzo fisico del destinatario."))
        if not text(payload.get("destinatario_comune")) and not text(payload.get("destinatario_paese")):
            blockers.append(block("DESTINATARIO_LUOGO_REQUIRED", "Indica comune o paese del destinatario."))
        if estero and not text(payload.get("destinatario_paese")):
            blockers.append(block("DESTINATARIO_PAESE_REQUIRED", "Per notifica all'estero indica il paese destinatario."))
    if precetto_required and not text(payload.get("data_notifica_precetto")):
        blockers.append(block("DATA_PRECETTO_REQUIRED", "Indica la data di notifica del precetto."))

    atto = _file_with_hash(payload, "atto_notificare", "atto_sha256", label="l'atto da notificare", blockers=blockers)
    richiesta = _file_with_hash(payload, "richiesta_o_relata", "richiesta_sha256", label="la richiesta o relata UNEP", blockers=blockers)
    pagamento = {"filename": text(payload.get("ricevuta_pagamento")), "sha256": text(payload.get("ricevuta_pagamento_sha256")).lower()}
    if payment_due:
        pagamento = _file_with_hash(payload, "ricevuta_pagamento", "ricevuta_pagamento_sha256", label="la ricevuta di pagamento UNEP", blockers=blockers)
    elif pagamento["filename"] and pagamento["sha256"] and not SHA256_HEX_RE.fullmatch(pagamento["sha256"]):
        blockers.append(block("HASH_SHA256_INVALID", "Ricevuta pagamento UNEP: impronta del file non valida."))

    checks = build_unep_notification_checks(payload)
    evidence_items = [
        {"kind": "atto", "label": "Atto da notificare", **atto, "required": True},
        {"kind": "richiesta", "label": "Richiesta o relata", **richiesta, "required": True},
    ]
    if pagamento["filename"] or payment_due:
        evidence_items.append({"kind": "pagamento", "label": "Ricevuta pagamento", **pagamento, "required": payment_due})

    body = (
        f"Richiesta UNEP {UNEP_NOTIFICATION_TYPES.get(tipo, tipo)} pronta per revisione e deposito sul canale dedicato."
        if not blockers
        else "Completa i dati UNEP prima di registrare la richiesta come pronta."
    )
    return LegalWorkflowResult(
        ok=not blockers,
        blockers=list(dict.fromkeys(blockers)),
        warnings=warnings,
        subject="Richiesta UNEP",
        body=body,
        template_id="workflow_unep_notifica",
        template_label="Controllo richiesta UNEP",
        template_version=template_catalog_version(),
        next_actions=(
            "Deposita sul canale UNEP dedicato, non nel deposito PCT civile.",
            "Conserva ricevute portale, pagamento e ritorno dell'ufficio nel fascicolo.",
            "Aggiorna lo stato solo dopo prova documentale del ritorno UNEP.",
        ),
        output_plan={
            "workflowSteps": legal_notification_automation_payload()["unep"],
            "normativeChecks": checks,
            "evidencePack": {"items": evidence_items, "missing": [], "invalid_hashes": []},
            "unepRequest": {
                "tipo": tipo,
                "tipoLabel": UNEP_NOTIFICATION_TYPES.get(tipo, tipo),
                "ufficio": text(payload.get("ufficio_unep")),
                "precettoDate": text(payload.get("data_notifica_precetto")),
                "channel": "UNEP",
            },
            "legalBasis": _legal_source_rows("pst_xsd_unep_2024", "cpc_137_149"),
        },
        log_json={
            "evento": "controllo_notifica_unep",
            "tipo": tipo,
            "ufficio": text(payload.get("ufficio_unep")),
            "fascicolo_id": text(payload.get("fascicolo_id") or payload.get("practice_id")),
        },
    )


def build_non_pec_notification_checks(payload: dict[str, Any]) -> list[dict[str, Any]]:
    tipo = normalise_non_pec_notification_type(payload.get("tipo_notifica_non_pec") or payload.get("tipo_notifica"))
    return [
        _check_row(
            id="tipo_notifica",
            label="Tipo notifica",
            source="Artt. 137-149 c.p.c.",
            passed=tipo in NON_PEC_NOTIFICATION_TYPES,
            detail="Il canale non PEC deve essere classificato prima del tracciamento.",
        ),
        _check_row(
            id="data_notifica",
            label="Data notifica",
            source="Tracciamento notifiche",
            passed=bool(text(payload.get("data_notifica"))),
            detail="La data della notifica è il riferimento principale del tracciamento.",
        ),
        _check_row(
            id="notifica_id",
            label="Identificativo notifica",
            source="Matrice dati pratica",
            passed=bool(text(payload.get("notifica_id"))),
            detail="L'identificativo collega il tracciamento alla pratica e ai documenti.",
        ),
        _check_row(
            id="destinatario",
            label="Destinatario",
            source="Artt. 137-149 c.p.c.",
            passed=bool(text(payload.get("destinatario_nome"))),
            detail="Il soggetto notificato deve essere identificato.",
        ),
        _check_row(
            id="atto",
            label="Atto notificato",
            source="Tracciamento notifiche",
            passed=bool(text(payload.get("atto_notificato"))),
            detail="L'atto notificato deve essere riconoscibile nel fascicolo.",
        ),
        _check_row(
            id="prova",
            label="Prova documentale",
            source="Audit IUSENTRA notifiche",
            passed=bool(text(payload.get("prova_file"))),
            detail="Collega avviso, relata, ricevuta o prova di consegna.",
        ),
    ]


def validate_non_pec_notification_tracking(payload: dict[str, Any]) -> LegalWorkflowResult:
    """Validate non-PEC notification tracking equivalent to the historical table fields."""

    blockers: list[str] = []
    warnings: list[str] = []
    tipo = normalise_non_pec_notification_type(payload.get("tipo_notifica_non_pec") or payload.get("tipo_notifica"))

    if text(payload.get("operazione")) not in {"", NON_PEC_NOTIFICATION_OPERATION}:
        blockers.append(block("OPERAZIONE_NON_PEC_REQUIRED", "Usa il canale non PEC per questo tracciamento."))
    if tipo not in NON_PEC_NOTIFICATION_TYPES:
        blockers.append(block("TIPO_NON_PEC_REQUIRED", "Seleziona il tipo di notifica non PEC."))
    if not text(payload.get("data_notifica")):
        blockers.append(block("DATA_NOTIFICA_REQUIRED", "Indica la data della notifica."))
    if not text(payload.get("notifica_id")):
        blockers.append(block("NOTIFICA_ID_REQUIRED", "Indica l'identificativo della notifica."))
    if not text(payload.get("destinatario_nome")):
        blockers.append(block("DESTINATARIO_REQUIRED", "Indica il destinatario della notifica."))
    if not text(payload.get("atto_notificato")):
        blockers.append(block("ATTO_NOTIFICATO_REQUIRED", "Indica l'atto notificato."))

    if tipo == "raccomandata":
        if not text(payload.get("numero_raccomandata")):
            blockers.append(block("RACCOMANDATA_NUMERO_REQUIRED", "Indica il numero della raccomandata."))
        if not text(payload.get("data_spedizione")):
            blockers.append(block("RACCOMANDATA_SPEDIZIONE_REQUIRED", "Indica la data di spedizione della raccomandata."))
        if not text(payload.get("data_ricevuta_raccomandata")):
            blockers.append(block("RACCOMANDATA_RICEZIONE_REQUIRED", "Indica la data di ricezione o compiuta giacenza."))
    elif tipo == "ufficiale_giudiziario":
        if not text(payload.get("ufficio_unep")):
            blockers.append(block("UFFICIO_UNEP_REQUIRED", "Indica l'ufficio dell'ufficiale giudiziario."))
        if not text(payload.get("numero_cronologico")):
            blockers.append(block("CRONOLOGICO_REQUIRED", "Indica il numero cronologico se disponibile dal ritorno dell'ufficio."))
    elif tipo == "mani":
        if not text(payload.get("consegnatario")):
            blockers.append(block("CONSEGNATARIO_REQUIRED", "Indica chi ha ricevuto l'atto."))
    elif tipo == "estero":
        if not text(payload.get("destinatario_paese")):
            blockers.append(block("PAESE_REQUIRED", "Indica il paese destinatario."))
        if not text(payload.get("autorita_o_canale")):
            blockers.append(block("AUTORITA_CANALE_REQUIRED", "Indica autorità o canale usato per l'estero."))
    else:
        warnings.append("Canale non PEC residuale: verifica manuale dell'avvocato obbligatoria prima di considerarlo prova completa.")

    prova = _file_with_hash(payload, "prova_file", "prova_sha256", label="la prova documentale", blockers=blockers)
    checks = build_non_pec_notification_checks(payload)
    source_ids = ("cpc_149", "cpc_137_149") if tipo == "raccomandata" else ("cpc_137_149",)

    body = (
        f"Tracciamento {NON_PEC_NOTIFICATION_TYPES.get(tipo, tipo)} pronto con data, identificativo e prova documentale."
        if not blockers
        else "Completa i dati prima di considerare chiusa la notifica non PEC."
    )
    return LegalWorkflowResult(
        ok=not blockers,
        blockers=list(dict.fromkeys(blockers)),
        warnings=warnings,
        subject="Tracciamento notifica non PEC",
        body=body,
        template_id="workflow_notifica_non_pec",
        template_label="Controllo notifica non PEC",
        template_version=template_catalog_version(),
        next_actions=(
            "Registra data e identificativo nel fascicolo.",
            "Collega la prova documentale con impronta verificabile.",
            "Aggiorna scadenze e attività solo dopo conferma della data di perfezionamento.",
        ),
        output_plan={
            "workflowSteps": legal_notification_automation_payload()["nonPec"],
            "normativeChecks": checks,
            "evidencePack": {
                "items": [{"kind": "prova_non_pec", "label": "Prova documentale", **prova, "required": True}],
                "missing": [],
                "invalid_hashes": [],
            },
            "historicalFields": {
                "DataNotifica": text(payload.get("data_notifica")),
                "TipoNotifica": NON_PEC_NOTIFICATION_TYPES.get(tipo, tipo),
                "DataRicevutaRaccomandata": text(payload.get("data_ricevuta_raccomandata")),
                "NotificaID": text(payload.get("notifica_id")),
            },
            "legalBasis": _legal_source_rows(*source_ids),
        },
        log_json={
            "evento": "controllo_notifica_non_pec",
            "tipo": tipo,
            "notifica_id": text(payload.get("notifica_id")),
            "fascicolo_id": text(payload.get("fascicolo_id") or payload.get("practice_id")),
        },
    )


def build_deposit_normative_checks(payload: dict[str, Any], evidence_pack: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Return checks for depositing proof of a PEC notification."""

    evidence_pack = evidence_pack or build_notification_evidence_pack(payload)
    recipients = payload.get("destinatari")
    if not isinstance(recipients, list):
        recipients = [{
            "nome": payload.get("destinatario_nome"),
            "rac_file": payload.get("rac_file"),
            "rdac_file": payload.get("rdac_file"),
        }]
    receipt_files = [
        text(row.get(field))
        for row in recipients
        if isinstance(row, dict)
        for field in ("rac_file", "rdac_file")
    ]
    originals_ok = bool(receipt_files) and all(Path(filename).suffix.lower() in {".eml", ".msg"} for filename in receipt_files)
    return [
        _check_row(
            id="atti_notificati",
            label="Atti notificati",
            source="Specifiche tecniche DGSIA 7 agosto 2024, art. 26, comma 5",
            passed=bool(payload.get("atti_notificati") or text(payload.get("atto_notificato"))),
            detail="L'atto notificato viene inserito nella busta con gli allegati necessari.",
        ),
        _check_row(
            id="relata_firmata",
            label="Relata firmata",
            source="L. 53/1994, art. 3-bis, comma 5",
            passed=bool(text(payload.get("relata_firmata"))),
            detail="La relata firmata digitalmente va conservata nel pacchetto prova.",
        ),
        _check_row(
            id="pec_inviata",
            label="PEC inviata",
            source="L. 53/1994, art. 3-bis, comma 3",
            passed=bool(text(payload.get("pec_inviata") or payload.get("pec_inviata_file"))),
            detail="Il messaggio inviato resta allegato in originale digitale.",
        ),
        _check_row(
            id="rac_rdac",
            label="RAC e RdAC originali",
            source="L. 53/1994, art. 9; D.M. 44/2011, art. 18, comma 6",
            passed=originals_ok and boolish(payload.get("ricevuta_completa")),
            detail="RAC e RdAC completa devono restare file .eml o .msg per ogni destinatario.",
        ),
        _check_row(
            id="hash",
            label="Impronte dei file",
            source="Audit interno IUSENTRA",
            passed=not evidence_pack.get("missing") and not evidence_pack.get("invalid_hashes"),
            detail="Ogni file richiesto dal pacchetto prova deve avere impronta valida.",
        ),
        _check_row(
            id="dati_atto",
            label="Riferimenti ricevute",
            source="Specifiche tecniche DGSIA 7 agosto 2024, art. 26, comma 5",
            passed=bool(text(payload.get("dati_atto_ricevute"))),
            detail="I dati identificativi delle ricevute vanno indicizzati nel deposito.",
        ),
    ]


def build_deposit_audit_trail(payload: dict[str, Any], evidence_pack: dict[str, Any]) -> dict[str, Any]:
    recipients = payload.get("destinatari")
    if not isinstance(recipients, list):
        recipients = [{
            "nome": payload.get("destinatario_nome"),
            "rac_file": payload.get("rac_file"),
            "rdac_file": payload.get("rdac_file"),
        }]
    return {
        "phase": "deposito_prova",
        "generatedAt": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "documentsCount": len([item for item in evidence_pack.get("items", []) if str(item.get("kind", "")).startswith("atto") or str(item.get("kind", "")).startswith("allegato")]),
        "recipients": [
            {
                "name": text(row.get("nome")),
                "racFile": text(row.get("rac_file")),
                "rdacFile": text(row.get("rdac_file")),
            }
            for row in recipients
            if isinstance(row, dict)
        ],
        "checks": build_deposit_normative_checks(payload, evidence_pack),
        "evidencePack": evidence_pack,
    }


def validate_deposit_notification_proof(payload: dict[str, Any]) -> LegalWorkflowResult:
    """Validate the evidence pack before deposit of notification proof."""

    blockers: list[str] = []
    warnings: list[str] = []
    notified_documents = payload.get("atti_notificati")
    has_notified_documents = isinstance(notified_documents, list) and bool(notified_documents)
    if not has_notified_documents and not text(payload.get("atto_notificato")):
        blockers.append("Inserisci l'atto notificato da depositare come prova.")
    if not text(payload.get("relata_firmata")):
        blockers.append("Allega la relata firmata digitalmente.")
    if not text(payload.get("pec_inviata") or payload.get("pec_inviata_file")):
        blockers.append("Allega il messaggio PEC inviato in originale digitale.")
    if not boolish(payload.get("ricevuta_completa")) and text(payload.get("rdac_tipo")).lower() != "completa":
        blockers.append(block("RICEVUTA_COMPLETA_REQUIRED", "La prova deposito richiede RdAC completa."))

    recipients = payload.get("destinatari")
    if not isinstance(recipients, list):
        recipients = [{
            "nome": payload.get("destinatario_nome"),
            "codice_fiscale_piva": payload.get("destinatario_cf") or payload.get("codice_fiscale_piva"),
            "pec": payload.get("destinatario_pec"),
            "fonte_pec": payload.get("fonte_pec_destinatario"),
            "rac_file": payload.get("rac_file"),
            "rdac_file": payload.get("rdac_file"),
            "rac_sha256": payload.get("rac_sha256"),
            "rdac_sha256": payload.get("rdac_sha256"),
        }]
    if not recipients:
        blockers.append("Indica almeno un destinatario della notifica.")

    for index, recipient in enumerate(recipients, start=1):
        if not isinstance(recipient, dict):
            blockers.append(f"Destinatario {index}: dati ricevute non leggibili.")
            continue
        label = text(recipient.get("nome"), f"destinatario {index}")
        recipient_tax_code = text(
            recipient.get("codice_fiscale_piva")
            or recipient.get("codice_fiscale")
            or recipient.get("destinatario_cf")
            or recipient.get("recipient_tax_code")
        )
        recipient_pec = text(
            recipient.get("pec")
            or recipient.get("destinatario_pec")
            or recipient.get("recipient_address")
            or recipient.get("indirizzo_pec")
        )
        recipient_source = normalise_public_register(
            recipient.get("fonte_pec")
            or recipient.get("fonte_pec_destinatario")
            or recipient.get("recipient_address_source")
            or recipient.get("pubblico_elenco")
        )
        if not recipient_tax_code:
            blockers.append(block("DESTINATARIO_CF_REQUIRED", f"{label}: indica codice fiscale o partita IVA del destinatario collegato a RAC e RdAC."))
        if not recipient_pec:
            blockers.append(block("DESTINATARIO_PEC_REQUIRED", f"{label}: indica l'indirizzo PEC destinatario collegato a RAC e RdAC."))
        if recipient_source not in PUBLIC_PEC_REGISTERS:
            blockers.append(block("DESTINATARIO_FONTE_PEC_REQUIRED", f"{label}: indica il pubblico elenco da cui è stata estratta la PEC."))
        for field, human in (("rac_file", "ricevuta di accettazione"), ("rdac_file", "ricevuta di avvenuta consegna completa")):
            filename = text(recipient.get(field))
            if not filename:
                blockers.append(f"{label}: manca la {human}.")
                continue
            if Path(filename).suffix.lower() not in {".eml", ".msg"}:
                blockers.append(f"{label}: conserva la {human} in originale digitale .eml o .msg.")

    evidence_pack = build_notification_evidence_pack(payload)
    blockers.extend(block("EVIDENCE_PACK_REQUIRED", item) for item in evidence_pack["missing"])
    blockers.extend(block("HASH_SHA256_INVALID", item) for item in evidence_pack.get("invalid_hashes", []))

    if not text(payload.get("dati_atto_ricevute")):
        blockers.append(block("DATI_ATTO_RICEVUTE_REQUIRED", "Indica i riferimenti delle ricevute per il deposito."))

    body = (
        "Prova notifica pronta per il controllo: atto notificato, relata firmata, "
        "messaggio PEC inviato, RAC e RdAC originali per ciascun destinatario."
    )
    return LegalWorkflowResult(
        ok=not blockers,
        blockers=blockers,
        warnings=warnings,
        subject="Deposito prova notifica",
        body=body,
        template_id="distinta_prova_notifica",
        template_label="Distinta prova notifica",
        template_version=template_catalog_version(),
        next_actions=(
            "Inserisci atto notificato e ricevute nella busta telematica.",
            "Controlla che RAC e RdAC restino in originale digitale.",
            "Verifica i riferimenti delle ricevute nel riepilogo del deposito.",
        ),
        output_plan={
            "evidencePack": evidence_pack,
            "workflowSteps": [dict(item) for item in LEGAL_NOTIFICATION_DEPOSIT_STEPS],
            "normativeChecks": build_deposit_normative_checks(payload, evidence_pack),
            "auditTrail": build_deposit_audit_trail(payload, evidence_pack),
        },
        log_json={"evento": "controllo_prova_notifica", "evidencePack": evidence_pack, "audit": build_deposit_audit_trail(payload, evidence_pack)},
    )
