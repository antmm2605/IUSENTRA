"""Righe selezionabili del timbro editor, senza cambiare i timbri dei flussi nativi."""
from pct.studio_timbro import StudioTimbro


OPTIONAL_STAMP_ROWS = {
    'qualifiche_professionali': ('Qualifica professionale', ''),
    'telefono': ('Telefono', 'Tel. '),
    'email': ('Email studio', 'Email '),
    'pec': ('PEC', 'PEC '),
    'fax': ('Fax', 'Fax '),
    'sito_web': ('Sito web', ''),
}
STAMP_SOURCES = frozenset(OPTIONAL_STAMP_ROWS) | {
    'studio_nome', 'studio_sottotitolo', 'professionista_nome',
    'indirizzo', 'fiscale', 'recapiti', 'righe_extra',
}


def editor_stamp_lines(stamp: StudioTimbro):
    lines = stamp.to_lines()
    contact_style = next((line for line in lines if line['source'] == 'recapiti'),
                         {'font': 'Helvetica', 'size': 9, 'bold': False, 'italic': False, 'align': 'left'})
    result = [dict(line, available=True, selectable=False) for line in lines
              if line['source'] not in {'recapiti', 'qualifiche_professionali'}]
    payload = stamp.to_payload()
    for source, (label, prefix) in OPTIONAL_STAMP_ROWS.items():
        value = str(payload.get(source) or '').strip()
        if not value and source in {'fax', 'sito_web'}:
            continue
        style = next((line for line in lines if line['source'] == source), contact_style)
        row = dict(style, source=source, text=prefix + value if value else '',
                   label=label, available=bool(value), selectable=True)
        if source == 'qualifiche_professionali':
            position = next((i + 1 for i, line in enumerate(result)
                             if line['source'] == 'professionista_nome'), len(result))
            result.insert(position, row)
        else:
            result.append(row)
    return result
