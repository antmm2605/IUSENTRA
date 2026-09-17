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

from pct.archivio_letture.distribuzione import PRESIDI_CHE_SCRIVONO, fatti_per_presidio
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
    modalita = _modalita_termine(fatto.etichetta + " " + fatto.contesto)
    if modalita:
        return modalita == _modalita_termine(testo)
    # Per termini generici serve la fonte esatta, non basta lo stesso giorno.
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
            esiti.append({"fatto_id":fatto.id, "stato":"consegnato", "riferimento":stessa.id, "motivo":"Stesso adempimento già registrato; fonte collegata senza duplicarlo."})
            continue
        if giorno < date.today().isoformat():
            esiti.append({"fatto_id":fatto.id, "stato":"non_pertinente", "motivo":"Data storica del " + format_date_it(giorno) + ": conservata nella lettura, senza creare una nuova urgenza."})
            continue
        modalita = _modalita_termine(fatto.etichetta + " " + fatto.contesto)
        # La parola «termine» non ne prova la natura perentoria.
        from pct.archivio_letture.adempimenti import perentorieta_documentata
        perentorio = perentorieta_documentata(fatto)
        tipo = TipoTermine.TERMINE_PERENTORIO if perentorio else TipoTermine.DEPOSITO_ATTO if modalita == "deposito_note" else TipoTermine.ADEMPIMENTO
        nota = "Data verificata nell’archivio delle letture.\nARCHIVIO_FATTO:" + fatto.id + "\nFonte: " + fatto.tipo + ":" + fatto.oggetto_id
        try:
            nuova = gestore.nuova(titolo=fatto.etichetta[:120] or "Termine letto dai documenti", tipo=tipo, data_scadenza=giorno, id_fascicolo=fid, descrizione=fatto.contesto[:300], note=nota, perentorio=perentorio)
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


CONSEGNATARI = {"scadenziario": _consegna_scadenziario, "agenda": _consegna_agenda}


# ---- il giro di consegna ----------------------------------------------------

def riconcilia_consegne(fascicolo: Any, registro: RegistroLetture, tenant: str) -> dict[str, int]:
    """Retract only untouched machine proposals whose source has been rejected.

    Source facts, rows and delivery references are retained; the reason is
    written both in the affected row and in the delivery ledger.
    """
    from web.helpers import get_scadenziario, get_agenda
    fid = _testo(getattr(fascicolo, "id", ""))
    fatti = {f.id: f for f in registro.fatti(tenant, fid, verifiche=None)}
    scadenziario, agenda = get_scadenziario(), get_agenda()
    scadenze = {s.id: s for s in scadenziario.tutte(id_fascicolo=fid, solo_aperte=False)}
    conti = {"scadenze_rettificate": 0, "agenda_rettificata": 0, "da_verificare": 0}
    # Earlier canonical ids could change when the source was rejected.
    # Recover only untouched, recognisable automatic proposals whose entire
    # source evidence for that hearing day is now rejected.
    for riga in agenda.tutti():
        if _testo(getattr(riga, "procedimento", "")) != _procedimento(fascicolo) or _stato(riga) != "PROGRAMMATO":
            continue
        giorno = _giorno(getattr(riga, "data_ora", ""))
        atteso = "Udienza del " + giorno[8:10] + "/" + giorno[5:7] + "/" + giorno[:4]
        if _testo(getattr(riga, "note", "")) != NOTA_CONSEGNA or _testo(riga.titolo) != atteso:
            continue
        fonti = [f for f in fatti.values() if f.categoria == "data" and f.campo == "udienza" and _giorno(f.valore) == giorno]
        if fonti and all(f.verifica in {"respinta", "ignorata"} for f in fonti):
            from pct.agenda import StatoAppuntamento
            agenda.modifica(riga.id, stato=StatoAppuntamento.ANNULLATO, note=NOTA_CONSEGNA + "\nRettifica automatica: la lettura corrente esclude questa data come udienza. Fonti: " + ", ".join(sorted({f.oggetto_id for f in fonti})))
            conti["agenda_rettificata"] += 1
    for consegna in registro.consegne(tenant, fid):
        fatto = fatti.get(consegna.fatto_id)
        if consegna.stato != "consegnato" or not fatto or fatto.verifica != "respinta":
            continue
        motivo = next((str(p.get("dettaglio") or "") for p in reversed(fatto.prove) if p.get("esito") in {"respinta", "errore"} and p.get("dettaglio")), "")
        if not motivo:
            continue
        riga = scadenze.get(consegna.riferimento) if consegna.presidio == "scadenziario" else agenda.get(consegna.riferimento) if consegna.presidio == "agenda" else None
        stato = str(getattr(getattr(riga, "stato", ""), "value", getattr(riga, "stato", "")))
        # Exact original note/title/date prevents overriding a lawyer's edits.
        if riga is None or _testo(getattr(riga, "note", "")) != NOTA_CONSEGNA or _testo(getattr(riga, "titolo", "")) != fatto.etichetta[:120] or stato not in {"APERTO", "PROGRAMMATO"}:
            conti["da_verificare"] += 1
            continue
        campo_data = "data_scadenza" if consegna.presidio == "scadenziario" else "data_ora"
        if _giorno(getattr(riga, campo_data, "")) != _giorno(fatto.valore):
            conti["da_verificare"] += 1
            continue
        nota = NOTA_CONSEGNA + "\nRettifica automatica della lettura: " + motivo
        if consegna.presidio == "scadenziario":
            scadenziario.aggiorna(riga.id, stato="ANNULLATO", note=nota)
            conti["scadenze_rettificate"] += 1
        else:
            from pct.agenda import StatoAppuntamento
            agenda.modifica(riga.id, stato=StatoAppuntamento.ANNULLATO, note=nota)
            conti["agenda_rettificata"] += 1
        registro.segna_consegna(tenant, fid, fatto.id, consegna.presidio, stato="non_pertinente", riferimento=riga.id, motivo="Proposta automatica annullata: " + motivo, versione_presidio="2026.09.16.riconciliazione.v1")
    if conti["scadenze_rettificate"] or conti["agenda_rettificata"]:
        from web.services.lettura_cache import invalida_lettura
        invalida_lettura(fid)
    return conti



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


def consegna_fascicolo(fascicolo: Any, *, registro: RegistroLetture | None = None) -> dict[str, Any]:
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
    esito["riconciliazione"] = riconcilia_consegne(fascicolo, registro, tenant)
    esito["adempimenti"] = riconcilia_adempimenti(fascicolo, registro, tenant)
    tutti = fatti_fascicolo(fascicolo, verifiche=("verificata", "corretta"))
    for presidio in PRESIDI_CHE_SCRIVONO:
        spettanti = fatti_per_presidio(tutti, presidio.nome)
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


__all__ = ["CONSEGNATARI", "NOTA_CONSEGNA", "ORIGINE", "consegna_fascicolo"]
