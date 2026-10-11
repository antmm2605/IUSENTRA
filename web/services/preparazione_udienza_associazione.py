"""Associazione dell'udienza da collegamenti espliciti e identità del procedimento."""
import re
import unicodedata
from pct.pec_case_identity import case_identity_evidence

_RG = re.compile(r"(?<![\d/])(\d{1,7})\s*/\s*(\d{4})(?!\d)")


def _testo(value):
    return " ".join(unicodedata.normalize("NFKC", str(value or "")).casefold().split())


def verifica_collegamento_esplicito(appuntamento, fascicolo):
    """Una scelta dell'operatore non autorizza a sovrascrivere riscontri discordanti."""
    from pct.udienze.repository import PreparazioneConflict
    if getattr(appuntamento, "id_fascicolo", "") and appuntamento.id_fascicolo != fascicolo.id:
        raise PreparazioneConflict("Fascicolo dell'udienza discordante dal collegamento registrato.")
    if appuntamento.id_cliente and appuntamento.id_cliente != fascicolo.id_cliente:
        raise PreparazioneConflict("Cliente dell'udienza discordante dal fascicolo scelto.")
    ruoli = {f"{int(m.group(1))}/{m.group(2)}" for m in _RG.finditer(str(appuntamento.procedimento or ""))}
    if len(ruoli) > 1:
        raise PreparazioneConflict("Più numeri di ruolo nell'udienza: collegamento da verificare.")
    evidence = case_identity_evidence({"numero_ruolo_certificato": next(iter(ruoli), ""),
        "cliente": appuntamento.cliente, "ufficio": appuntamento.tribunale}, fascicolo)
    if evidence["conflicts"]:
        raise PreparazioneConflict("Collegamento dell'udienza discordante: " + "; ".join(evidence["conflicts"]))
    if appuntamento.cliente and fascicolo.nome_cliente and not evidence["client_name_match"]:
        raise PreparazioneConflict("Nome e cognome del cliente dell'udienza discordanti dal fascicolo.")


def fascicolo_udienza(appuntamento, fascicoli, sessioni=()):
    """Mai scegliere fra fascicoli concorrenti né abbinare per somiglianza del nome."""
    appointment_id = str(appuntamento.id)
    per_id = {str(f.id): f for f in fascicoli}
    collegati = {
        str(f.id) for f in fascicoli
        if any(str(getattr(a, "id_appuntamento", "")) == appointment_id for a in getattr(f, "attivita", ()))
    }
    if getattr(appuntamento, "id_fascicolo", ""):
        collegati.add(str(appuntamento.id_fascicolo))
    collegati.update(str(s.id_fascicolo) for s in sessioni
                     if appointment_id in {str(getattr(s, "id_appuntamento", "")),
                                           str(getattr(s, "id_appuntamento_rinvio", ""))}
                     and str(s.id_fascicolo) in per_id)
    if collegati:
        return per_id.get(next(iter(collegati))) if len(collegati) == 1 else None
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
        profile = {'numero_ruolo_certificato': ruolo,
                   'cliente': getattr(appuntamento, 'cliente', ''),
                   'ufficio': getattr(appuntamento, 'tribunale', '')}
        verificati = []
        for fascicolo in candidati:
            evidence = case_identity_evidence(profile, fascicolo)
            if not evidence['conflicts'] and all(evidence[key] for key in
                    ('rg_match', 'client_name_match', 'office_match')):
                verificati.append(fascicolo)
        candidati = verificati
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
    if ufficio and not ruoli:
        candidati = [f for f in candidati if _testo(getattr(f, 'tribunale', '')) == ufficio]
    return candidati[0] if len(candidati) == 1 else None
