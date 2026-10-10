"""Catalogo dei campi dell'editor: usa il resolver dei modelli, senza inferenze."""
from __future__ import annotations

from datetime import datetime
import re

from pct.formatting import DISPLAY_TIMEZONE, format_date_it, format_euro_it
from pct.template_atti_prefill import build_prefill_context, resolve_field
from pct.archivio_letture.date_campi_modello import CAMPI_DATE

CLIENT_FIELDS = {
    "nome_completo": "Nome completo", "nome": "Nome", "cognome": "Cognome",
    "codice_fiscale": "Codice fiscale", "data_nascita": "Data di nascita",
    "luogo_nascita": "Luogo di nascita", "provincia_nascita": "Provincia di nascita",
    "nazionalita": "Nazionalità", "sesso": "Sesso", "ragione_sociale": "Ragione sociale",
    "partita_iva": "Partita IVA", "forma_giuridica": "Forma giuridica",
    "rappresentante_legale": "Rappresentante legale", "cf_rappresentante": "Codice fiscale del rappresentante",
    "codice_ateco": "Codice ATECO", "data_costituzione": "Data di costituzione",
}
MATTER_FIELDS = {
    "numero": "Numero fascicolo", "titolo": "Titolo", "oggetto": "Oggetto",
    "numero_rg": "Numero R.G.", "anno_rg": "Anno R.G.", "tribunale": "Ufficio giudiziario",
    "sezione": "Sezione", "giudice": "Giudice", "controparte": "Controparte",
    "cf_controparte": "Codice fiscale controparte", "avvocato_controparte": "Difensore controparte",
    "avvocato_referente": "Avvocato referente", "avvocato_dominus": "Avvocato dominus",
    "qualifica_giudiziale_titolare": "Qualifica processuale del cliente",
    "tipo_procedimento": "Tipo di procedimento", "tipo_registro": "Registro processuale",
    "ruolo_sezione": "Ruolo e sezione", "attore_principale": "Attore principale",
    "ctu": "Consulente tecnico d’ufficio", "ctp": "Consulente tecnico di parte",
    "valore_causa": "Valore della causa",
    "data_prossima_udienza": "Data della prossima udienza",
    "data_prima_udienza": "Data della prima udienza",
    "data_notifica_citazione": "Data di notifica della citazione",
    "data_apertura": "Data di apertura del fascicolo",
    "data_chiusura": "Data di chiusura del fascicolo",
}
FIELDS = [("cliente." + key, label, "Anagrafica") for key, label in CLIENT_FIELDS.items()]
for address, group in [("indirizzo_residenza", "Residenza"), ("indirizzo_domicilio", "Domicilio"), ("indirizzo_sede_legale", "Sede legale")]:
    FIELDS += [("cliente." + address + "." + key, label, group) for key, label in {
        "via": "Via", "civico": "Civico", "cap": "CAP", "comune": "Comune", "provincia": "Provincia", "nazione": "Nazione",
    }.items()]
FIELDS += [("cliente.recapiti." + key, label, "Recapiti") for key, label in {"telefono": "Telefono", "cellulare": "Cellulare", "email": "Email", "pec": "PEC"}.items()]
FIELDS += [("cliente.documento." + key, label, "Documento d’identità") for key, label in {"numero": "Numero documento", "rilasciato_da": "Rilasciato da", "data_rilascio": "Data rilascio", "data_scadenza": "Scadenza documento"}.items()]
FIELDS += [("fascicolo." + key, label, "Fascicolo") for key, label in MATTER_FIELDS.items()]
FIELDS += [("fascicolo." + key, label, "Date processuali") for key, label in CAMPI_DATE.items()]
FIELDS += [("studio_timbro." + key, label, "Studio e avvocato") for key, label in {
    "studio_nome": "Nome studio", "professionista_nome": "Avvocato",
    "indirizzo_riga": "Indirizzo studio", "cap_citta_provincia": "Località studio",
    "telefono": "Telefono studio", "fax": "Fax studio", "codice_fiscale": "Codice fiscale avvocato",
    "partita_iva": "Partita IVA studio", "pec": "PEC avvocato", "email": "Email studio",
    "sito_web": "Sito studio", "foro": "Foro",
}.items()]
FIELDS += [("studio.citta", "Comune studio", "Studio e avvocato")]
FIELDS += [("studio.provincia", "Provincia studio", "Studio e avvocato"),
           ("studio.cap", "CAP studio", "Studio e avvocato")]
FIELDS += [("studio_timbro.nome_professionista", "Nome dell’avvocato (senza titolo)", "Studio e avvocato")]
FIELDS += [("documento.data_atto", "Data dell’atto (oggi)", "Dati dell’atto")]
STAMP_ROW_FIELDS = {
    "studio_nome": "riga_studio", "studio_sottotitolo": "studio_sottotitolo",
    "professionista_nome": "professionista_nome", "qualifiche_professionali": "qualifiche_professionali",
    "indirizzo": "riga_indirizzo", "fiscale": "riga_fiscale", "recapiti": "riga_recapiti",
}
FIELDS += [("studio_timbro." + key, label, "Timbro completo") for key, label in {
    "riga_studio": "Intestazione studio", "studio_sottotitolo": "Sottotitolo studio",
    "qualifiche_professionali": "Qualifiche professionali", "riga_indirizzo": "Indirizzo e località",
    "riga_fiscale": "Dati fiscali", "riga_recapiti": "Recapiti e PEC configurata",
}.items()]
FIELD_IDS = frozenset(key for key, _, _ in FIELDS)


def linked_fields_catalog(*, cliente=None, fascicolo=None, config=None, studio_timbro=None, date_processuali=None):
    """Proietta soltanto dati archiviati autorizzati; le assenze restano esplicite."""
    if cliente is not None and fascicolo is not None and str(getattr(fascicolo, "id_cliente", "")) != str(getattr(cliente, "id", "")):
        raise ValueError("Il cliente non è quello collegato al fascicolo.")
    context = build_prefill_context(cliente=cliente, fascicolo=fascicolo, config=config, studio_timbro=studio_timbro)
    context["documento"] = {"data_atto": datetime.now(DISPLAY_TIMEZONE).date().isoformat()}
    from pct.studio_timbro import StudioTimbro
    stamp_payload = dict(context["studio_timbro"])
    stamp_payload["pec"] = context["studio"].get("pec", "")
    context["studio_timbro"]["nome_professionista"] = re.sub(
        r"^(?:avv\.?|avvocato|avvocata)\s+", "",
        str(stamp_payload.get("professionista_nome") or "").strip(), flags=re.I,
    )
    for line in StudioTimbro.from_payload(stamp_payload).to_lines():
        row_key = STAMP_ROW_FIELDS.get(line["source"])
        if row_key:
            context["studio_timbro"][row_key] = line["text"]
    result = []
    for key, label, group in FIELDS:
        field = resolve_field(key, [key], context).to_dict()
        if key == "studio_timbro.pec":
            # La PEC operativa proviene dalla sezione PEC delle impostazioni,
            # anche quando nel timbro è rimasto un indirizzo precedente.
            field = resolve_field(key, ["studio.pec"], context).to_dict()
        if key == "documento.data_atto":
            field.update(source="today", source_label="Data odierna (Europe/Rome)", confidence="high")
        if key.removeprefix("fascicolo.") in CAMPI_DATE:
            field = (date_processuali or {}).get(key, {
                **field, "value": "", "missing_reason": "Data non ancora riscontrata in una fonte del procedimento.",
            })
        value = str(field["value"] or "").strip()
        if value and key.rsplit(".", 1)[-1].startswith("data_"):
            value = format_date_it(value)
        elif value and key == "fascicolo.valore_causa":
            value = format_euro_it(field["value"])
        result.append({**field, "id": key, "label": label, "group": group, "value": value, "available": bool(value) and not field["conflict"]})
    return result


def date_modello_da_fatti(fatti, *, fascicolo_id, oggetti):
    """Proietta fatti SQL correnti, mantenendo discordanza e documento probatorio."""
    current = {(o.tipo, o.oggetto_id, o.impronta) for o in oggetti if o.presente}
    result = {}
    for field in CAMPI_DATE:
        candidates = [f for f in fatti if f.fascicolo_id == fascicolo_id
                      and f.categoria == "metadato_fascicolo" and f.campo == field
                      and f.verifica in {"verificata", "corretta"}
                      and (f.tipo, f.oggetto_id, f.sha256) in current
                      and any(p.get("codice") == "identita_congiunta_provvedimento"
                              and p.get("esito") == "ok" for p in f.prove)]
        values = {f.valore for f in candidates}
        if not values:
            continue
        conflict = len(values) != 1
        result["fascicolo." + field] = {
            "value": "" if conflict else next(iter(values)), "source": "documenti",
            "source_label": "Fonte del fascicolo", "confidence": "high",
            "editable": True, "required": False, "privacy_level": "studio",
            "missing_reason": "Le fonti indicano date discordanti." if conflict else "",
            "warnings": [], "conflict": conflict,
            "alternatives": [{"value": f.valore, "documentId": f.oggetto_id,
                              "sha256": f.sha256, "passaggio": f.contesto} for f in candidates],
        }
    return result


def template_linked_html(html: str, *, context=None, matter_id='', client_id=''):
    """Modello riutilizzabile: elimina i valori della precedente associazione.

    Il testo libero resta intenzionalmente invariato: soltanto i campi marcati
    sono sostituibili automaticamente, senza dedurre dati personali dal testo.
    """
    from lxml import html as parser

    root = parser.fragment_fromstring(html, create_parent='div')
    fields = {field['id']: field for field in (context or [])}
    labels = {key: label for key, label, _ in FIELDS}
    missing = []
    for node in root.iter():
        if not isinstance(node.tag, str):
            continue
        if node.tag.lower() in {'script', 'iframe', 'object', 'embed', 'link', 'meta'} or any(key.lower().startswith('on') for key in node.attrib):
            raise ValueError('Il documento contiene elementi non consentiti nel modello.')
        for attribute in ('href', 'src'):
            destination = ''.join((node.get(attribute) or '').split()).lower()
            if destination.startswith(('javascript:', 'vbscript:', 'file:')):
                raise ValueError('Il documento contiene un collegamento non consentito.')
        key = node.get('data-iu-linked-field')
        if key is None:
            continue
        if key not in FIELD_IDS:
            raise ValueError('Campo collegato non consentito.')
        field = fields.get(key)
        value = field['value'] if field and field['available'] else '[' + labels[key] + ']'
        if field and field['available']:
            date_format = node.get('data-iu-date-format')
            if date_format in {'long', 'long-padded', 'dots'}:
                from datetime import datetime
                try:
                    parsed = datetime.strptime(value.replace('.', '/'), '%d/%m/%Y')
                except ValueError as error:
                    raise ValueError('Il campo collegato non contiene una data valida.') from error
                months = ('gennaio', 'febbraio', 'marzo', 'aprile', 'maggio', 'giugno', 'luglio', 'agosto', 'settembre', 'ottobre', 'novembre', 'dicembre')
                day = f'{parsed.day:02}' if date_format == 'long-padded' else str(parsed.day)
                value = parsed.strftime('%d.%m.%Y') if date_format == 'dots' else f'{day} {months[parsed.month - 1]} {parsed.year}'
            if node.get('data-iu-text-case') == 'upper':
                value = value.upper()
            elif node.get('data-iu-text-case') == 'lower':
                value = value.lower()
            elif node.get('data-iu-text-case') == 'title':
                connectors = {'di', 'del', 'della', 'delle', 'dei', 'degli', 'da', 'a', 'al', 'alla', 'e'}
                value = re.sub(r'[^\W\d_]+', lambda match: match.group() if match.start() > 0
                               and match.group() in connectors else match.group().capitalize(), value.lower())
            if node.get('data-iu-value-format') == 'cf-grouped':
                compact = re.sub(r'\s', '', value)
                if re.fullmatch(r'[A-Za-z0-9]{16}', compact):
                    value = ' '.join((compact[:3], compact[3:6], compact[6:11], compact[11:]))
        if context is not None and not (field and field['available']):
            missing.append(labels[key])
        # Conserva il primo contenitore della formattazione, senza il valore vecchio.
        target = node
        while len(target) and target[0].tag in {'span', 'strong', 'em', 'b', 'i', 'u', 's', 'a'}:
            target = target[0]
        for child in list(target):
            target.remove(child)
        target.text = value
        # Un valore di campo è atomico: non conservare code del precedente valore.
        ancestor = target
        while ancestor is not node:
            ancestor.tail = None
            parent = ancestor.getparent()
            for sibling in list(parent)[1:]:
                parent.remove(sibling)
            ancestor = parent
        for attribute in ('data-iu-linked-matter', 'data-iu-linked-client'):
            node.attrib.pop(attribute, None)
        node.set('contenteditable', 'false')
        node.attrib.pop('data-iu-linked-manual', None)
        if context is not None:
            node.set('data-iu-linked-matter', matter_id)
            node.set('data-iu-linked-client', client_id)
        # Anche il modello vuoto deve eliminare la destinazione precedente.
        anchors = list(node.iter('a'))
        parent = node.getparent()
        if parent is not None and parent.tag == 'a':
            anchors.append(parent)
        for anchor in anchors:
            if not (anchor.get('href') or '').lower().startswith('mailto:'):
                continue
            if key.endswith('.pec'):
                anchor.set('href', 'mailto:' + (field['value'] if field and field['available'] else ''))
            else:
                anchor.drop_tag()
    return ''.join(parser.tostring(child, encoding='unicode') for child in root), list(dict.fromkeys(missing))
