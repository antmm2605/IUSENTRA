"""Associazione dell'udienza da collegamenti espliciti e identità del procedimento."""
import re
import unicodedata

_RG = re.compile(r"(?<![\d/])(\d{1,7})\s*/\s*(\d{4})(?!\d)")


def _testo(value):
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).casefold().split())


def fascicolo_udienza(appuntamento, fascicoli, sessioni=()):
    """Mai scegliere fra fascicoli concorrenti né abbinare per somiglianza del nome."""
    appointment_id = str(appuntamento.id)
    per_id = {str(f.id): f for f in fascicoli}
    collegati = {
        str(f.id) for f in fascicoli
        if any(str(getattr(a, "id_appuntamento", "")) == appointment_id for a in getattr(f, "attivita", ()))
    }
    collegati.update(str(s.id_fascicolo) for s in sessioni
                     if str(getattr(s, "id_appuntamento", "")) == appointment_id
                     and str(getattr(s, "stato", "")) != "archiviato" and str(s.id_fascicolo) in per_id)
    if collegati:
        return per_id[next(iter(collegati))] if len(collegati) == 1 else None
    procedimento = _testo(getattr(appuntamento, 'procedimento', ''))
    interni = [f for f in fascicoli if procedimento and procedimento == _testo(getattr(f, 'numero', ''))]
    if interni:
        return interni[0] if len(interni) == 1 else None
    ruoli = {f"{int(m.group(1))}/{m.group(2)}" for m in _RG.finditer(
        f"{getattr(appuntamento, 'procedimento', '')} {appuntamento.titolo}")}
    candidati = list(fascicoli)
    if ruoli:
        if len(ruoli) != 1:
            return None
        ruolo = next(iter(ruoli))
        candidati = [f for f in candidati if ruolo in {
            f"{int(m.group(1))}/{m.group(2)}" for m in _RG.finditer(
                f"{getattr(f, 'numero_rg', '')}/{getattr(f, 'anno_rg', '')}")
        }]
        if len(candidati) == 1:
            return candidati[0]
    else:
        # Senza numero di ruolo occorrono cliente, data e ufficio coincidenti.
        giorno = str(appuntamento.data_ora)[:10]
        candidati = [f for f in candidati if str(getattr(f, 'data_prossima_udienza', ''))[:10] == giorno]
        if not getattr(appuntamento, 'id_cliente', '') or not getattr(appuntamento, 'tribunale', ''):
            return None
    client_id = str(getattr(appuntamento, 'id_cliente', '') or '')
    if client_id:
        candidati = [f for f in candidati if str(getattr(f, 'id_cliente', '')) == client_id]
    ufficio = _testo(getattr(appuntamento, 'tribunale', ''))
    if ufficio:
        candidati = [f for f in candidati if _testo(getattr(f, 'tribunale', '')) == ufficio]
    return candidati[0] if len(candidati) == 1 else None
