"""La consegna: l'archivio dà il fatto al presidio, il presidio scrive e conferma.

È l'atto che chiude la catena. I due motori leggono e scrivono i fatti
nell'archivio; l'archivio sa quali presìdi usano quali fatti; qui glieli
consegna. Il presidio che ha un registro proprio — lo scadenziario, l'agenda —
ci scrive una riga e **conferma** indicando quale riga ha creato. Da quel
momento l'archivio non gli ripropone più quel fatto: niente doppioni, e il
giro si ferma.

Tre esiti, tutti dichiarati, nessuno silenzioso:

- **consegnato**: il presidio ha scritto la riga, e il riferimento la ritrova;
- **non pertinente**: il presidio ha guardato e non la scrive, perché quel dato
  è già nel suo registro (una scadenza per quella data esiste già) o perché non
  lo riguarda. Non torna più;
- **rifiutato**: il presidio non è riuscito a scriverla. Il motivo resta e al
  giro successivo si riprova.

Si consegnano solo i fatti che il collaudo ha **verificato** o che l'avvocato
ha **corretto**: una data soltanto plausibile non finisce nello scadenziario
senza che nessuno l'abbia confermata, si chiede nel riquadro delle conferme.

Base normativa delle scadenze create: le stesse del fatto d'origine (termini
processuali del c.p.c. e del D.Lgs. 149/2022); la riga creata resta una
proposta da confermare, non un termine calcolato d'ufficio.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from typing import Any

from pct.archivio_letture.distribuzione import PRESIDI_CHE_SCRIVONO
from pct.registro_letture import RegistroLetture

logger = logging.getLogger(__name__)

# Le scadenze e gli appuntamenti nati da una lettura si riconoscono da questa
# etichetta: l'avvocato deve poter vedere che cosa ha scritto il software.
ORIGINE = "archivio delle letture"
NOTA_CONSEGNA = "Creata dalla lettura automatica dei documenti: da confermare."


def _testo(valore: Any) -> str:
    return " ".join(str(valore or "").split()).strip()


def _giorno(valore: Any) -> str:
    giorno = _testo(valore)[:10]
    if len(giorno) == 10 and giorno[4] == "-" and giorno[7] == "-":
        try:
            date.fromisoformat(giorno)
        except ValueError:
            return ""
        return giorno
    return ""


def _ora(fatto: Any) -> str:
    """L'ora letta insieme alla data, se il motore l'ha trovata: «2026-11-10T09:30»."""
    valore = _testo(getattr(fatto, "valore", ""))
    return valore[11:16] if len(valore) >= 16 and valore[10] == "T" else ""


def _dati_note_scritte(fatto: Any) -> dict[str, str]:
    """Restituisce la modalità solo quando deriva da prova/istituto espliciti."""
    prove = list(getattr(fatto, "prove", []) or [])
    modalita = next((p for p in prove if p.get("codice") == "modalita_note" and p.get("esito") == "ok"), None)
    istituto = next((str(p.get("dettaglio") or "") for p in prove if p.get("codice") == "istituto" and p.get("esito") == "ok"), "")
    etichetta = _testo(getattr(fatto, "etichetta", "")).casefold()
    if not (modalita or istituto == "note_127_ter" or any(x in etichetta for x in ("note in sostituzione", "note scritte"))):
        return {}
    ora = _ora(fatto) or _testo((modalita or {}).get("ora_termine"))[:5]
    return {"hearing_mode": "note_scritte", "hearing_time": ora, "legal_due_at": _giorno(fatto.valore) + (f"T{ora}:00" if ora else "")}


# ---- scadenziario ----------------------------------------------------------

def _modalita_termine(testo: str) -> str:
    testo = _testo(testo).casefold()
    if "opposizione" in testo:
        return "opposizione"
    if "note" in testo and any(v in testo for v in ("deposito", "sostituzione", "trattazione scritta")):
        return "deposito_note"
    if "costituzione" in testo:
        return "costituzione"
    return ""


def _stato(riga: Any) -> str:
    return str(getattr(getattr(riga, "stato", ""), "value", getattr(riga, "stato", ""))).upper()


def _stessa_scadenza(riga: Any, fatto: Any) -> bool:
    if _stato(riga) in {"ANNULLATO", "ANNULLATA", "CANCELLATO"} or _giorno(riga.data_scadenza) != _giorno(fatto.valore):
        return False
    testo = _testo(getattr(riga, "titolo", "")) + " " + _testo(getattr(riga, "note", ""))
    if fatto.id and "ARCHIVIO_FATTO:" + fatto.id in testo:
        return True
    # Una scadenza manuale già presente nello stesso giorno prevale sulla
    # proposta del lettore; tra proposte automatiche serve identità semantica.
    automatico = "ARCHIVIO_FATTO:" in testo or "PEC_AUDIT:" in testo or bool(_testo(getattr(riga, "deadline_profile_code", "")))
    if not automatico:
        return True
    modalita = _modalita_termine(fatto.etichetta + " " + fatto.contesto)
    if modalita:
        return modalita == _modalita_termine(testo)
    return bool(fatto.oggetto_id and fatto.oggetto_id in testo and _testo(riga.titolo) == _testo(fatto.etichetta))


def _consegna_scadenziario(fascicolo: Any, fatti: list[Any]) -> list[dict[str, str]]:
    """Consegna per fatto, tipo e fonte: due adempimenti nello stesso giorno restano distinti."""
    from pct.scadenziario import TipoTermine
    from web.helpers import get_scadenziario
    from pct.formatting import format_date_it
    gestore = get_scadenziario()
    fid = _testo(fascicolo.id)
    esistenti = list(gestore.tutte(id_fascicolo=fid, solo_aperte=False))
    esiti = []
    for fatto in fatti:
        giorno = _giorno(fatto.valore)
        if not giorno:
            esiti.append({"fatto_id":fatto.id, "stato":"non_pertinente", "motivo":"Il fatto non porta una data di calendario."})
            continue
        stessa = next((s for s in esistenti if _stessa_scadenza(s, fatto)), None)
        if stessa:
            testo_esistente = _testo(getattr(stessa, "note", ""))
            automatico_stesso_fatto = bool(fatto.id and "ARCHIVIO_FATTO:" + fatto.id in testo_esistente)
            esiti.append({
                "fatto_id": fatto.id,
                "stato": "consegnato" if automatico_stesso_fatto else "non_pertinente",
                "riferimento": stessa.id,
                "motivo": "Stesso adempimento già registrato; fonte collegata senza duplicarlo.",
            })
            continue
        if giorno < date.today().isoformat():
            esiti.append({"fatto_id":fatto.id, "stato":"non_pertinente", "motivo":"Data storica del " + format_date_it(giorno) + ": conservata nella lettura, senza creare una nuova urgenza."})
            continue
        modalita = _modalita_termine(fatto.etichetta + " " + fatto.contesto)
        # La parola «termine» non ne prova la natura perentoria.
        from pct.archivio_letture.adempimenti import perentorieta_documentata
        perentorio = perentorieta_documentata(fatto)
        tipo = TipoTermine.TERMINE_PERENTORIO if perentorio else TipoTermine.DEPOSITO_ATTO if modalita == "deposito_note" else TipoTermine.ADEMPIMENTO
        nota = "Data verificata nell’archivio delle letture. Creata dalla lettura automatica dei documenti: da confermare.\nARCHIVIO_FATTO:" + fatto.id + "\nFonte: " + fatto.tipo + ":" + fatto.oggetto_id
        try:
            dati_note = _dati_note_scritte(fatto)
            nuova = gestore.nuova(
                titolo=fatto.etichetta[:120] or "Termine letto dai documenti",
                tipo=tipo, data_scadenza=giorno, id_fascicolo=fid,
                descrizione=fatto.contesto[:300], note=nota, perentorio=perentorio,
                hearing_mode=dati_note.get("hearing_mode", ""),
                hearing_time=dati_note.get("hearing_time", ""),
                hearing_mode_source=(f"{fatto.tipo}:{fatto.oggetto_id}" if dati_note else ""),
                legal_due_at=dati_note.get("legal_due_at", ""),
            )
            esistenti.append(nuova)
            esiti.append({"fatto_id":fatto.id, "stato":"consegnato", "riferimento":nuova.id})
        except Exception as exc:
            esiti.append({"fatto_id":fatto.id, "stato":"rifiutato", "motivo":f"{type(exc).__name__}: {exc}"[:200]})
    return esiti


# ---- agenda ----------------------------------------------------------------

def _procedimento(fascicolo: Any) -> str:
    """Il riferimento con cui l'agenda lega un impegno al fascicolo: il numero di ruolo.

    L'appuntamento non ha un campo «fascicolo»: il legame passa dal campo
    `procedimento`, dove lo studio scrive «RG numero/anno».
    """
    numero = _testo(getattr(fascicolo, "numero_rg", ""))
    anno = _testo(getattr(fascicolo, "anno_rg", ""))
    if numero and anno:
        return f"RG {numero}/{anno}"
    return _testo(getattr(fascicolo, "numero", "")) or _testo(getattr(fascicolo, "titolo", ""))[:60]


def _consegna_agenda(fascicolo: Any, fatti: list[Any]) -> list[dict[str, str]]:
    """Una vera udienza richiede data e ora lette: nessun orario inventato."""
    from pct.agenda import TipoAppuntamento
    from web.helpers import get_agenda
    gestore = get_agenda()
    procedimento = _procedimento(fascicolo)
    esistenti = [a for a in gestore.tutti() if _testo(a.procedimento) == procedimento and _stato(a) not in {"ANNULLATO", "CANCELLATO"}]
    esiti = []
    for fatto in fatti:
        giorno, ora = _giorno(fatto.valore), _ora(fatto)
        stessa = next((a for a in esistenti if str(a.tipo.value) == "UDIENZA" and _giorno(a.data_ora) == giorno and (not ora or str(a.data_ora)[11:16] == ora)), None)
        if stessa:
            esiti.append({"fatto_id":fatto.id, "stato":"consegnato", "riferimento":stessa.id, "motivo":"Udienza già presente con data e ora concordanti."})
            continue
        if not giorno or giorno < date.today().isoformat():
            esiti.append({"fatto_id":fatto.id, "stato":"non_pertinente", "motivo":"Data storica conservata nella lettura; non si crea un appuntamento passato."})
            continue
        if not ora:
            esiti.append({"fatto_id":fatto.id, "stato":"rifiutato", "motivo":"La fonte indica il giorno ma non l’orario: l’udienza resta visibile nel fascicolo con ora da acquisire."})
            continue
        try:
            nuova = gestore.aggiungi(titolo=fatto.etichetta[:120] or "Udienza letta dai documenti", tipo=TipoAppuntamento.UDIENZA, data_ora=f"{giorno}T{ora}:00", luogo=_testo(fascicolo.tribunale), allow_overlap=True, procedimento=procedimento, tribunale=_testo(fascicolo.tribunale), cliente=_testo(fascicolo.nome_cliente), id_cliente=_testo(fascicolo.id_cliente), note="Data e ora verificate nell’archivio.\nARCHIVIO_FATTO:" + fatto.id + "\nFonte: " + fatto.tipo + ":" + fatto.oggetto_id)
            esistenti.append(nuova)
            esiti.append({"fatto_id":fatto.id, "stato":"consegnato", "riferimento":nuova.id})
        except Exception as exc:
            esiti.append({"fatto_id":fatto.id, "stato":"rifiutato", "motivo":f"{type(exc).__name__}: {exc}"[:200]})
    return esiti


def _consegna_parti(fascicolo: Any, fatti: list[Any]) -> list[dict[str, str]]:
    from web.services.parti_lette_runtime import consegna_parti

    return consegna_parti(fascicolo, fatti)


CONSEGNATARI = {"scadenziario": _consegna_scadenziario, "agenda": _consegna_agenda, "parti": _consegna_parti}


# ---- il giro di consegna ----------------------------------------------------

def riconcilia_consegne(
    fascicolo: Any,
    registro: RegistroLetture,
    tenant: str,
    *,
    applica: bool = True,
) -> dict[str, Any]:
    """Rettifica solo proposte automatiche intatte sostenute da fonti respinte.

    La ricerca usa sia i fatti grezzi sia la vista canonica. Se l'identità
    canonica è cambiata dopo la riconvalida, il riferimento della consegna e
    giorno/campo permettono di ritrovare le fonti; una riga modificata
    dall'avvocato resta intatta e viene segnalata per verifica. ``applica=False``
    produce lo stesso piano senza scrivere agenda, scadenziario o consegne.
    """
    from pct.archivio_letture import fatti_canonici
    from web.helpers import get_scadenziario, get_agenda

    fid = _testo(getattr(fascicolo, "id", ""))
    grezzi = registro.fatti(tenant, fid, verifiche=None)
    canonici = fatti_canonici(grezzi)
    fatti = {f.id: f for f in [*grezzi, *canonici]}
    scadenziario, agenda = get_scadenziario(), get_agenda()
    scadenze = {s.id: s for s in scadenziario.tutte(id_fascicolo=fid, solo_aperte=False)}
    appuntamenti = {a.id: a for a in agenda.tutti()}
    conti: dict[str, Any] = {
        "scadenze_rettificate": 0,
        "agenda_rettificata": 0,
        "da_verificare": 0,
        "da_rettificare": [],
        "dry_run": not applica,
    }

    def fonti_respinte(consegna: Any, riga: Any) -> list[Any]:
        fatto = fatti.get(consegna.fatto_id)
        if fatto is not None:
            return [fatto] if fatto.verifica in {"respinta", "ignorata"} else []
        giorno = _giorno(getattr(riga, "data_scadenza", "") if consegna.presidio == "scadenziario" else getattr(riga, "data_ora", ""))
        campi = {"termine", "costituzione"} if consegna.presidio == "scadenziario" else {"udienza"}
        fonti = [f for f in grezzi if f.categoria == "data" and f.campo in campi and _giorno(f.valore) == giorno]
        return fonti if fonti and all(f.verifica in {"respinta", "ignorata"} for f in fonti) else []

    def riga_automatica_integra(consegna: Any, riga: Any, fonti: list[Any]) -> bool:
        if riga is None:
            return False
        stato = _stato(riga)
        atteso = "APERTO" if consegna.presidio == "scadenziario" else "PROGRAMMATO"
        if stato != atteso:
            return False
        nota = str(getattr(riga, "note", "") or "")
        prime_righe = (
            {"Data verificata nell’archivio delle letture.", "Data verificata nell’archivio delle letture. " + NOTA_CONSEGNA}
            if consegna.presidio == "scadenziario"
            else {"Data e ora verificate nell’archivio."}
        )
        righe_nota = nota.splitlines()
        if len(righe_nota) != 3 or righe_nota[0] not in prime_righe or righe_nota[1] != "ARCHIVIO_FATTO:" + consegna.fatto_id or not righe_nota[2].startswith("Fonte: "):
            return False
        giorno = _giorno(getattr(riga, "data_scadenza", "") if consegna.presidio == "scadenziario" else getattr(riga, "data_ora", ""))
        compatibili = [f for f in fonti if _giorno(f.valore) == giorno and _testo(f.etichetta)[:120] == _testo(getattr(riga, "titolo", ""))]
        return bool(compatibili)

    for consegna in registro.consegne(tenant, fid):
        if consegna.stato != "consegnato" or consegna.presidio not in {"scadenziario", "agenda"}:
            continue
        riga = scadenze.get(consegna.riferimento) if consegna.presidio == "scadenziario" else appuntamenti.get(consegna.riferimento)
        fonti = fonti_respinte(consegna, riga)
        if not fonti:
            continue
        if not riga_automatica_integra(consegna, riga, fonti):
            conti["da_verificare"] += 1
            continue
        motivo = next((
            str(p.get("dettaglio") or "")
            for fatto in fonti for p in reversed(fatto.prove)
            if p.get("esito") in {"respinta", "errore"} and p.get("dettaglio")
        ), "La fonte corrente non conferma più il dato consegnato.")
        conti["da_rettificare"].append({
            "presidio": consegna.presidio,
            "riferimento": consegna.riferimento,
            "fatto_id": consegna.fatto_id,
            "motivo": motivo,
        })
        if not applica:
            continue
        nota = str(getattr(riga, "note", "") or "") + "\nRettifica automatica della lettura: " + motivo
        if consegna.presidio == "scadenziario":
            scadenziario.aggiorna(riga.id, stato="ANNULLATO", note=nota)
            conti["scadenze_rettificate"] += 1
        else:
            from pct.agenda import StatoAppuntamento
            agenda.modifica(riga.id, stato=StatoAppuntamento.ANNULLATO, note=nota)
            conti["agenda_rettificata"] += 1
        registro.segna_consegna(
            tenant, fid, consegna.fatto_id, consegna.presidio,
            stato="non_pertinente", riferimento=riga.id,
            motivo="Proposta automatica annullata: " + motivo,
            versione_presidio="2026.09.21.riconciliazione.v2",
        )
    if applica and (conti["scadenze_rettificate"] or conti["agenda_rettificata"]):
        from web.services.lettura_cache import invalida_lettura
        invalida_lettura(fid)
    return conti



def riconcilia_modalita_note(fascicolo: Any, registro: RegistroLetture, tenant: str, *, applica: bool = False) -> dict[str, Any]:
    """Allinea ora e modalità delle sole proposte PEC automatiche ancora intatte."""
    import json
    from web.helpers import get_agenda, get_scadenziario

    fid = _testo(getattr(fascicolo, "id", ""))
    oggetti = {(o.tipo, o.oggetto_id): o.impronta for o in registro.oggetti(tenant, fid)}
    fatti = [
        f for f in registro.fatti(tenant, fid, verifiche=("verificata", "corretta"))
        if oggetti.get((f.tipo, f.oggetto_id)) == f.sha256 and f.campo == "termine" and _dati_note_scritte(f).get("hearing_time")
    ]
    per_giorno: dict[str, list[Any]] = {}
    for fatto in fatti:
        per_giorno.setdefault(_giorno(fatto.valore), []).append(fatto)
    scadenziario, agenda = get_scadenziario(), get_agenda()
    piano = []
    for scadenza in scadenziario.tutte(id_fascicolo=fid, solo_aperte=False):
        giorno = _giorno(scadenza.data_scadenza)
        marker = f"PEC_AUDIT:docpresidio:{fid}:"
        note = str(getattr(scadenza, "note", "") or "")
        fonte = re.search(re.escape(marker) + r"([^:\n]+):termine:" + re.escape(giorno), note)
        fatto = next((f for f in per_giorno.get(giorno, []) if fonte and f.oggetto_id == fonte.group(1)), None)
        if not fatto or _stato(scadenza) != "APERTO" or getattr(scadenza, "deadline_profile_code", "") != "PEC_AUTO_PRESIDIO" or getattr(scadenza, "source_event_type", "") != "fascicolo_documenti_audit" or _modalita_termine(scadenza.titolo) != "deposito_note":
            continue
        dati = _dati_note_scritte(fatto)
        appuntamento_id = getattr(scadenza, "id_appuntamento", "")
        appuntamento = agenda.get(appuntamento_id) if appuntamento_id else None
        if appuntamento_id and not (appuntamento is not None and _stato(appuntamento) == "PROGRAMMATO" and str(getattr(appuntamento, "tipo", "").value) == "SCADENZA" and _giorno(appuntamento.data_ora) == giorno and getattr(appuntamento, "external_profile_id", "") == "pec_scadenziario" and marker in str(getattr(appuntamento, "note", "") or "")):
            continue
        if getattr(scadenza, "hearing_mode", "") == "note_scritte" and getattr(scadenza, "hearing_time", "") == dati["hearing_time"] and (appuntamento is None or (appuntamento.hearing_mode == "note_scritte" and appuntamento.hearing_time == dati["hearing_time"] and str(appuntamento.data_ora)[11:16] == dati["hearing_time"])):
            continue
        voce = {"scadenza_id": scadenza.id, "appuntamento_id": getattr(appuntamento, "id", ""), "fatto_id": fatto.id, "giorno": giorno, "ora": dati["hearing_time"]}
        piano.append(voce)
        if not applica:
            continue
        try:
            traccia = json.loads(getattr(scadenza, "trace_json", "") or "[]")
        except (TypeError, ValueError):
            traccia = [{"storico": getattr(scadenza, "trace_json", "")}]
        if not isinstance(traccia, list):
            traccia = [{"storico": traccia}]
        traccia.append({"origine": "archivio_letture", "operazione": "modalita_note_scritte", "versione": "2026.09.21.v1", "fatto_id": fatto.id, "fonte": f"{fatto.tipo}:{fatto.oggetto_id}", "ora_termine": dati["hearing_time"]})
        scadenziario.aggiorna(scadenza.id, hearing_mode="note_scritte", hearing_time=dati["hearing_time"], hearing_mode_source=f"{fatto.tipo}:{fatto.oggetto_id}", legal_due_at=dati["legal_due_at"], trace_json=json.dumps(traccia, ensure_ascii=False))
        if appuntamento is not None:
            agenda.modifica(appuntamento.id, data_ora=f"{giorno}T{dati['hearing_time']}:00", hearing_mode="note_scritte", hearing_time=dati["hearing_time"], note=(str(appuntamento.note or "") + "\nModalità e ora riconciliate dalla fonte documentale verificata: deposito note scritte.").strip())
    if applica and piano:
        from web.services.lettura_cache import invalida_lettura
        invalida_lettura(fid)
    return {"dry_run": not applica, "da_rettificare": piano, "rettificate": len(piano) if applica else 0}


def riconcilia_adempimenti(fascicolo: Any, registro: RegistroLetture, tenant: str, *, applica: bool = True) -> dict[str, Any]:
    """Aggiorna solo scadenze automatiche con prova documentale concordante.

    La chiusura delle note richiede sia l'attestazione del giudice sia un
    deposito delle note accettato dalla cancelleria nella finestra pertinente.
    Conserva note, riferimenti e audit. Nessun cambiamento al flusso deposito.
    """
    import json
    from pct.archivio_letture.adempimenti import perentorieta_documentata, prove_note_depositate
    from pct.agenda import StatoAppuntamento
    from web.helpers import get_agenda, get_scadenziario
    fid = _testo(fascicolo.id)
    oggetti = {(o.tipo, o.oggetto_id): o for o in registro.oggetti(tenant, fid)}
    fatti = [f for f in registro.fatti(tenant, fid, verifiche=("verificata", "corretta")) if (f.tipo, f.oggetto_id) in oggetti and f.sha256 == oggetti[(f.tipo, f.oggetto_id)].impronta]
    prove = prove_note_depositate(fatti)
    scadenziario, agenda = get_scadenziario(), get_agenda()
    scadenze = list(scadenziario.tutte(id_fascicolo=fid, solo_aperte=False))
    esito = {"completate": [], "perentorieta": []}
    for s in scadenze:
        if _stato(s) != "APERTO" or _modalita_termine(_testo(s.titolo)) != "deposito_note":
            continue
        automatica = getattr(s, "deadline_profile_code", "") == "PEC_AUTO_PRESIDIO" and "PEC_AUDIT:" in s.note
        automatica = automatica or ("ARCHIVIO_FATTO:" in s.note and "Data verificata nell’archivio" in s.note)
        if not automatica:
            continue
        giorno = _giorno(s.data_scadenza)
        precedenti = [_giorno(x.data_scadenza) for x in scadenze if _modalita_termine(_testo(x.titolo)) == "deposito_note" and _giorno(x.data_scadenza) < giorno]
        limite = max(precedenti, default="0001-01-01")
        depositi = [d for d in list(getattr(fascicolo, "depositi_pct", []) or []) if _stato(d) == "ACCETTATO_CANCELLERIA" and _modalita_termine("deposito " + _testo(getattr(d, "nome_atto_principale", ""))) == "deposito_note" and limite < _giorno(getattr(d, "timestamp", "")) <= giorno]
        prova = next((p for p in prove if p["giorno"] == giorno), None)
        tipo_rettifica = ""
        if prova and depositi:
            tipo_rettifica = "note_depositate"
            evidenza = {**prova, "depositi_accettati": sorted(d.id for d in depositi)}
            nota = "Adempimento riscontrato: il provvedimento dà atto del deposito delle note scritte; la cancelleria ne ha accettato il deposito. Fonte: " + prova["tipo"] + ":" + prova["oggetto_id"] + "; SHA-256: " + prova["sha256"] + "; fatti: " + ", ".join(prova["fatti"]) + "; depositi: " + ", ".join(evidenza["depositi_accettati"]) + "."
            esito["completate"].append(s.id)
        elif not s.perentorio:
            perentori = [f for f in fatti if _giorno(f.valore) == giorno and perentorieta_documentata(f)]
            if not perentori:
                continue
            tipo_rettifica = "perentorieta_documentata"
            evidenza = {"fatti": [f.id for f in perentori], "fonti": [{"tipo": f.tipo, "oggetto_id": f.oggetto_id, "sha256": f.sha256, "estratto": f.contesto} for f in perentori]}
            nota = "Natura perentoria indicata espressamente nel provvedimento: " + ", ".join(f.id for f in perentori) + "."
            esito["perentorieta"].append(s.id)
        if not applica or not tipo_rettifica:
            continue
        try:
            traccia = json.loads(s.trace_json or "[]")
        except (ValueError, TypeError):
            traccia = [{"storico": s.trace_json}]
        if not isinstance(traccia, list):
            traccia = [{"storico": traccia}]
        traccia.append({"origine": "archivio_letture", "operazione": tipo_rettifica, "versione": "2026.09.17.v1", "prova": evidenza})
        scadenziario.aggiorna(s.id, trace_json=json.dumps(traccia, ensure_ascii=False), **({"perentorio": True, "note": (s.note + "\n" + nota).strip()} if tipo_rettifica == "perentorieta_documentata" else {}))
        if tipo_rettifica == "note_depositate":
            scadenziario.completa(s.id, note=nota)
            appuntamento = agenda.get(getattr(s, "id_appuntamento", "")) if getattr(s, "id_appuntamento", "") else None
            if appuntamento and _stato(appuntamento) == "PROGRAMMATO" and _giorno(appuntamento.data_ora) == giorno and _modalita_termine(appuntamento.titolo) == "deposito_note" and _testo(appuntamento.procedimento) == _procedimento(fascicolo):
                agenda.modifica(appuntamento.id, stato=StatoAppuntamento.COMPLETATO, note=(appuntamento.note + "\n" + nota).strip())
    if applica and any(esito.values()):
        from web.services.lettura_cache import invalida_lettura
        invalida_lettura(fid)
    return esito


def consegna_fascicolo(fascicolo: Any, *, registro: RegistroLetture | None = None, applica_riconciliazioni: bool = True) -> dict[str, Any]:
    """Consegna ai presìdi i fatti che spettano loro e non hanno ancora preso.

    Non rilegge nulla: prende i fatti dall'archivio, chiede al presidio di
    scriverli, registra la conferma. A consegne chiuse questa funzione non ha
    più niente da fare e il giro si ferma.
    """
    from web.services.archivio_letture_runtime import fatti_fascicolo
    from web.services.registro_letture_runtime import registro_corrente, tenant_corrente

    registro = registro or registro_corrente()
    tenant = tenant_corrente()
    fascicolo_id = _testo(getattr(fascicolo, "id", ""))
    esito: dict[str, Any] = {"fascicolo_id": fascicolo_id, "presidi": {}, "consegnati": 0, "non_pertinenti": 0, "rifiutati": 0}
    if not fascicolo_id:
        return esito
    esito["riconciliazione"] = riconcilia_consegne(fascicolo, registro, tenant, applica=applica_riconciliazioni)
    esito["modalita_note"] = riconcilia_modalita_note(fascicolo, registro, tenant, applica=applica_riconciliazioni)
    esito["adempimenti"] = riconcilia_adempimenti(fascicolo, registro, tenant, applica=applica_riconciliazioni)
    from web.services.rettifiche_letture_storiche import riconcilia_storico
    esito["riconciliazione_storica"] = riconcilia_storico(fascicolo, registro, tenant, applica=applica_riconciliazioni)
    tutti = fatti_fascicolo(fascicolo, verifiche=("verificata", "corretta"))
    for presidio in PRESIDI_CHE_SCRIVONO:
        spettanti = [fatto for fatto in tutti if presidio.gli_serve(fatto)]
        da_prendere = registro.da_consegnare(tenant, fascicolo_id, presidio.nome, spettanti)
        # Il vecchio confronto sul solo giorno non registrava il riferimento:
        # riconciliare quelle consegne con le identità semantiche attuali.
        da_rivedere = {c.fatto_id for c in registro.consegne(tenant, fascicolo_id) if c.presidio == presidio.nome and c.versione_presidio != presidio.versione and c.stato == "non_pertinente" and not c.riferimento}
        aggiunti = {f.id for f in da_prendere}
        da_prendere.extend(f for f in spettanti if f.id in da_rivedere and f.id not in aggiunti)
        if not da_prendere:
            esito["presidi"][presidio.nome] = {"spettanti": len(spettanti), "consegnati": 0, "non_pertinenti": 0, "rifiutati": 0}
            continue
        consegnatario = CONSEGNATARI.get(presidio.nome)
        if consegnatario is None:
            continue
        try:
            risultati = consegnatario(fascicolo, da_prendere)
        except Exception as exc:
            # Il presidio non ha potuto lavorare: i fatti restano da consegnare
            # e il motivo si registra su ciascuno, così si riprova al giro dopo.
            logger.exception("Consegna al presidio %s non riuscita per il fascicolo %s", presidio.nome, fascicolo_id)
            risultati = [{"fatto_id": fatto.id, "stato": "rifiutato", "motivo": f"{type(exc).__name__}: {exc}"[:200]} for fatto in da_prendere]
        conteggi = {"spettanti": len(spettanti), "consegnati": 0, "non_pertinenti": 0, "rifiutati": 0}
        for riga in risultati:
            stato = str(riga.get("stato") or "rifiutato")
            try:
                registro.segna_consegna(
                    tenant, fascicolo_id, str(riga.get("fatto_id") or ""), presidio.nome,
                    stato=stato, riferimento=str(riga.get("riferimento") or ""),
                    motivo=str(riga.get("motivo") or ""), versione_presidio=presidio.versione,
                )
            except Exception as exc:
                logger.debug("Conferma di consegna non registrata (%s): %s", presidio.nome, exc)
                continue
            chiave = {"consegnato": "consegnati", "non_pertinente": "non_pertinenti", "rifiutato": "rifiutati"}.get(stato, "rifiutati")
            conteggi[chiave] += 1
            esito[chiave] += 1
        esito["presidi"][presidio.nome] = conteggi
    if esito["consegnati"]:
        from web.services.lettura_cache import invalida_lettura

        invalida_lettura(fascicolo_id)
    return esito


__all__ = ["CONSEGNATARI", "NOTA_CONSEGNA", "ORIGINE", "consegna_fascicolo", "riconcilia_modalita_note"]
