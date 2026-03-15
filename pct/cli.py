"""
Interfaccia a riga di comando per il sistema PCT.
"""

import os
import sys
import json
from pathlib import Path
from typing import Optional

import click

from .busta import DatiBusta, Allegato
from .pec import ConfigPEC
from .deposito import DepositoCivile, DepositoPenale
from .notifica import NotificaTelematica, RelataDiNotifica
from .reginde import ClientReGINde
from .firma import FirmaDigitale
from .agenda import Agenda, TipoAppuntamento, StatoAppuntamento
from .clienti import (
    GestioneClienti,
    TipoCliente,
    StatoCliente,
    RiferimentoProcedimento,
)
from .fascicoli import (
    GestioneFascicoli,
    TipoFascicolo,
    StatoFascicolo,
    TipoAttivita,
    EsitoAttivita,
)


def carica_config() -> dict:
    """Carica configurazione da file .env o variabili d'ambiente."""
    config = {
        "pec_indirizzo": os.getenv("PCT_PEC_INDIRIZZO", ""),
        "pec_password": os.getenv("PCT_PEC_PASSWORD", ""),
        "pec_smtp_host": os.getenv("PCT_PEC_SMTP_HOST", "smtp.pec.aruba.it"),
        "pec_smtp_port": int(os.getenv("PCT_PEC_SMTP_PORT", "465")),
        "pec_imap_host": os.getenv("PCT_PEC_IMAP_HOST", "imaps.pec.aruba.it"),
        "firma_p12": os.getenv("PCT_FIRMA_P12", ""),
        "firma_password": os.getenv("PCT_FIRMA_PASSWORD", ""),
        "cf_avvocato": os.getenv("PCT_CF_AVVOCATO", ""),
        "nome_avvocato": os.getenv("PCT_NOME_AVVOCATO", ""),
        "output_dir": os.getenv("PCT_OUTPUT_DIR", "./depositi"),
    }
    return config


@click.group()
@click.version_option("1.0.0")
def cli():
    """PCT - Sistema di deposito telematico per studi legali italiani."""
    pass


@cli.command("deposita")
@click.option("--atto", required=True, type=click.Path(exists=True), help="Atto principale (PDF/A)")
@click.option("--tribunale", required=True, help="Nome tribunale (es. MILANO, ROMA)")
@click.option("--oggetto", required=True, help="Oggetto del deposito")
@click.option("--tipo-atto", default="MEMORIA", help="Tipo atto (RICORSO, MEMORIA, CITAZIONE...)")
@click.option("--allegato", multiple=True, type=click.Path(exists=True), help="Allegati aggiuntivi")
@click.option("--rg", help="Numero RG (es. 1234/2024)")
@click.option("--no-firma", is_flag=True, default=False, help="Salta la firma digitale")
@click.option("--no-ricevute", is_flag=True, default=False, help="Non attendere ricevute")
def cmd_deposita(atto, tribunale, oggetto, tipo_atto, allegato, rg, no_firma, no_ricevute):
    """Deposita un atto telematicamente presso un tribunale."""
    config = carica_config()

    if not config["pec_indirizzo"]:
        click.echo("Errore: configurare PCT_PEC_INDIRIZZO nelle variabili d'ambiente.", err=True)
        sys.exit(1)

    config_pec = ConfigPEC(
        indirizzo=config["pec_indirizzo"],
        password=config["pec_password"],
        smtp_host=config["pec_smtp_host"],
        smtp_port=config["pec_smtp_port"],
        imap_host=config["pec_imap_host"],
    )

    firma = None
    if not no_firma and config["firma_p12"] and Path(config["firma_p12"]).exists():
        firma = FirmaDigitale(
            config["firma_p12"],
            config["firma_password"].encode(),
        )
        click.echo(f"Firma digitale caricata: {firma.intestatario}")

    allegati = [Allegato(percorso=a, descrizione=Path(a).stem) for a in allegato]

    numero_rg = anno_rg = None
    if rg and "/" in rg:
        numero_rg, anno_str = rg.split("/", 1)
        anno_rg = int(anno_str) if anno_str.isdigit() else None

    dati = DatiBusta(
        codice_ufficio="",
        codice_registro="CIVILE",
        oggetto=oggetto,
        tipo_atto=tipo_atto,
        atto_principale=atto,
        allegati=allegati,
        numero_rg=numero_rg,
        anno_rg=anno_rg,
        cf_mittente=config["cf_avvocato"],
        operatore=config["nome_avvocato"],
    )

    deposito = DepositoCivile(config_pec, firma=firma, output_dir=config["output_dir"])

    click.echo(f"Avvio deposito presso Tribunale di {tribunale}...")
    esito = deposito.deposita(dati, tribunale, attendi_ricevute=not no_ricevute)

    click.echo(f"\nEsito deposito:")
    click.echo(f"  ID:      {esito.id_deposito}")
    click.echo(f"  Stato:   {esito.stato}")
    click.echo(f"  PEC:     {esito.pec_destinatario}")
    click.echo(f"  Busta:   {esito.busta_path}")
    click.echo(f"  Messaggio: {esito.messaggio}")

    esito_path = deposito.salva_esito(esito)
    click.echo(f"\nEsito salvato in: {esito_path}")


@cli.command("notifica")
@click.option("--atto", required=True, type=click.Path(exists=True), help="Atto da notificare (PDF/A firmato)")
@click.option("--destinatario-pec", required=True, help="PEC del destinatario")
@click.option("--destinatario", required=True, help="Nome del destinatario")
@click.option("--cf-destinatario", required=True, help="Codice fiscale del destinatario")
@click.option("--procedimento", help="Numero di procedimento")
@click.option("--autorita", help="Autorità giudiziaria")
def cmd_notifica(atto, destinatario_pec, destinatario, cf_destinatario, procedimento, autorita):
    """Invia una notifica telematica via PEC."""
    config = carica_config()

    if not config["pec_indirizzo"]:
        click.echo("Errore: configurare PCT_PEC_INDIRIZZO.", err=True)
        sys.exit(1)

    config_pec = ConfigPEC(
        indirizzo=config["pec_indirizzo"],
        password=config["pec_password"],
        smtp_host=config["pec_smtp_host"],
        smtp_port=config["pec_smtp_port"],
        imap_host=config["pec_imap_host"],
    )

    relata = RelataDiNotifica(
        notificante=config["nome_avvocato"],
        cf_notificante=config["cf_avvocato"],
        pec_notificante=config["pec_indirizzo"],
        destinatario=destinatario,
        cf_destinatario=cf_destinatario,
        pec_destinatario=destinatario_pec,
        atto_notificato=Path(atto).name,
        data_ora=__import__("datetime").datetime.now().strftime("%d/%m/%Y %H:%M"),
        numero_procedimento=procedimento,
        autorita_giudiziaria=autorita,
    )

    notifica = NotificaTelematica(config_pec)

    click.echo(f"Invio notifica a {destinatario} ({destinatario_pec})...")
    esito = notifica.notifica(atto, destinatario_pec, relata)

    click.echo(f"\nEsito notifica:")
    click.echo(f"  Stato:   {esito['esito']}")
    click.echo(f"  Busta:   {esito.get('busta_path', 'N/A')}")
    click.echo(f"  Messaggio: {esito.get('messaggio', '')}")


@cli.command("cerca-pec")
@click.argument("tribunale")
def cmd_cerca_pec(tribunale):
    """Cerca l'indirizzo PEC di un tribunale."""
    reginde = ClientReGINde()
    ufficio = reginde.cerca_ufficio_giudiziario(tribunale)
    if ufficio:
        click.echo(f"Tribunale: {ufficio.nome}")
        click.echo(f"Distretto: {ufficio.distretto}")
        click.echo(f"PEC:       {ufficio.pec}")
        click.echo(f"Codice:    {ufficio.codice}")
    else:
        click.echo(f"Tribunale '{tribunale}' non trovato.", err=True)
        sys.exit(1)


@cli.command("lista-tribunali")
def cmd_lista_tribunali():
    """Elenca i tribunali disponibili nel registro."""
    reginde = ClientReGINde()
    uffici = reginde.elenca_uffici()
    click.echo(f"{'Tribunale':<30} {'Codice':<12} {'PEC'}")
    click.echo("-" * 80)
    for ufficio in uffici:
        click.echo(f"{ufficio.nome:<30} {ufficio.codice:<12} {ufficio.pec}")


# ------------------------------------------------------------------ AGENDA

TIPI_VALIDI = [t.value for t in TipoAppuntamento]
STATI_VALIDI = [s.value for s in StatoAppuntamento]


def _agenda() -> Agenda:
    db = os.getenv("PCT_AGENDA_DB", "./agenda/appuntamenti.json")
    return Agenda(db_path=db)


def _fmt_app(a, verbose: bool = False) -> str:
    dt = a.data_ora_dt.strftime("%d/%m/%Y %H:%M")
    fine = a.fine_dt.strftime("%H:%M")
    riga = f"[{a.id}] {dt}-{fine}  {a.tipo.value:<14} {a.stato.value:<12} {a.titolo}"
    if verbose:
        if a.cliente:
            riga += f"\n         Cliente:      {a.cliente}"
        if a.procedimento:
            riga += f"\n         Procedimento: {a.procedimento}"
        if a.luogo:
            riga += f"\n         Luogo:        {a.luogo}"
        if a.note:
            riga += f"\n         Note:         {a.note}"
    return riga


@cli.group("agenda")
def grp_agenda():
    """Gestione agenda digitale dello studio."""
    pass


@grp_agenda.command("aggiungi")
@click.option("--titolo", required=True, help="Titolo dell'appuntamento")
@click.option("--tipo", required=True,
              type=click.Choice(TIPI_VALIDI, case_sensitive=False),
              help="Tipo appuntamento")
@click.option("--data-ora", required=True,
              help="Data e ora ISO 8601, es. 2024-03-15T10:00:00")
@click.option("--durata", default=60, show_default=True,
              help="Durata in minuti")
@click.option("--luogo", default="", help="Luogo / aula")
@click.option("--cliente", default="", help="Nome del cliente")
@click.option("--cf-cliente", default="", help="Codice fiscale cliente")
@click.option("--procedimento", default="", help="Numero RG o procedimento")
@click.option("--tribunale", default="", help="Tribunale di riferimento")
@click.option("--avvocato", default="", help="Avvocato responsabile")
@click.option("--note", default="", help="Note libere")
@click.option("--reminder", default=60, show_default=True,
              help="Reminder N minuti prima")
def cmd_aggiungi(titolo, tipo, data_ora, durata, luogo, cliente, cf_cliente,
                 procedimento, tribunale, avvocato, note, reminder):
    """Aggiunge un nuovo appuntamento all'agenda."""
    agenda = _agenda()
    try:
        app = agenda.aggiungi(
            titolo=titolo,
            tipo=TipoAppuntamento(tipo.upper()),
            data_ora=data_ora,
            durata_minuti=durata,
            luogo=luogo,
            cliente=cliente,
            cf_cliente=cf_cliente,
            procedimento=procedimento,
            tribunale=tribunale,
            avvocato=avvocato,
            note=note,
            reminder_minuti=reminder,
        )
        click.echo(f"Appuntamento aggiunto: {app.id}")
        click.echo(_fmt_app(app, verbose=True))
    except ValueError as e:
        click.echo(f"Errore: {e}", err=True)
        sys.exit(1)


@grp_agenda.command("lista")
@click.option("--oggi", is_flag=True, default=False, help="Solo appuntamenti di oggi")
@click.option("--settimana", is_flag=True, default=False, help="Questa settimana")
@click.option("--mese", is_flag=True, default=False, help="Questo mese")
@click.option("--tipo", type=click.Choice(TIPI_VALIDI, case_sensitive=False),
              default=None, help="Filtra per tipo")
@click.option("--stato", type=click.Choice(STATI_VALIDI, case_sensitive=False),
              default=None, help="Filtra per stato")
@click.option("--cliente", default=None, help="Filtra per nome cliente")
@click.option("-v", "--verbose", is_flag=True, default=False)
def cmd_lista(oggi, settimana, mese, tipo, stato, cliente, verbose):
    """Elenca appuntamenti in agenda."""
    from datetime import date as dt_date
    agenda = _agenda()
    oggi_d = dt_date.today()

    if oggi:
        apps = agenda.per_giorno(oggi_d)
    elif settimana:
        apps = agenda.per_settimana(oggi_d)
    elif mese:
        apps = agenda.per_mese(oggi_d.year, oggi_d.month)
    else:
        apps = agenda.tutti()

    if tipo:
        apps = [a for a in apps if a.tipo == TipoAppuntamento(tipo.upper())]
    if stato:
        apps = [a for a in apps if a.stato == StatoAppuntamento(stato.upper())]
    if cliente:
        apps = [a for a in apps if cliente.lower() in a.cliente.lower()]

    if not apps:
        click.echo("Nessun appuntamento trovato.")
        return

    click.echo(f"{'ID':<10} {'Data/Ora':<18} {'Tipo':<14} {'Stato':<12} Titolo")
    click.echo("-" * 80)
    for a in apps:
        click.echo(_fmt_app(a, verbose=verbose))


@grp_agenda.command("cerca")
@click.argument("testo")
@click.option("-v", "--verbose", is_flag=True, default=False)
def cmd_cerca(testo, verbose):
    """Cerca appuntamenti per testo libero."""
    agenda = _agenda()
    apps = agenda.cerca(testo=testo)
    if not apps:
        click.echo("Nessun risultato.")
        return
    for a in apps:
        click.echo(_fmt_app(a, verbose=verbose))


@grp_agenda.command("dettaglio")
@click.argument("id_app")
def cmd_dettaglio(id_app):
    """Mostra il dettaglio di un appuntamento."""
    agenda = _agenda()
    app = agenda.get(id_app.upper())
    if not app:
        click.echo(f"Appuntamento '{id_app}' non trovato.", err=True)
        sys.exit(1)
    click.echo(json.dumps(app.to_dict(), ensure_ascii=False, indent=2))


@grp_agenda.command("modifica")
@click.argument("id_app")
@click.option("--titolo", default=None)
@click.option("--data-ora", default=None)
@click.option("--durata", default=None, type=int)
@click.option("--luogo", default=None)
@click.option("--note", default=None)
@click.option("--cliente", default=None)
@click.option("--procedimento", default=None)
def cmd_modifica(id_app, **campi):
    """Modifica un appuntamento esistente."""
    agenda = _agenda()
    campi_puliti = {k.replace("-", "_"): v for k, v in campi.items() if v is not None}
    try:
        app = agenda.modifica(id_app.upper(), **campi_puliti)
        click.echo(f"Appuntamento {app.id} aggiornato.")
        click.echo(_fmt_app(app, verbose=True))
    except KeyError as e:
        click.echo(str(e), err=True)
        sys.exit(1)


@grp_agenda.command("stato")
@click.argument("id_app")
@click.argument("nuovo_stato", type=click.Choice(STATI_VALIDI, case_sensitive=False))
def cmd_stato(id_app, nuovo_stato):
    """Cambia lo stato di un appuntamento."""
    agenda = _agenda()
    try:
        app = agenda.cambia_stato(id_app.upper(), StatoAppuntamento(nuovo_stato.upper()))
        click.echo(f"Stato aggiornato: {app.stato.value}")
    except KeyError as e:
        click.echo(str(e), err=True)
        sys.exit(1)


@grp_agenda.command("elimina")
@click.argument("id_app")
@click.confirmation_option(prompt="Sei sicuro di voler eliminare questo appuntamento?")
def cmd_elimina(id_app):
    """Elimina un appuntamento."""
    agenda = _agenda()
    try:
        agenda.elimina(id_app.upper())
        click.echo(f"Appuntamento {id_app.upper()} eliminato.")
    except KeyError as e:
        click.echo(str(e), err=True)
        sys.exit(1)


@grp_agenda.command("reminder")
@click.option("--entro", default=60, show_default=True,
              help="Mostra reminder che scadono entro N minuti")
def cmd_reminder(entro):
    """Mostra gli appuntamenti con reminder imminente."""
    agenda = _agenda()
    apps = agenda.prossimi_reminder(entro_minuti=entro)
    if not apps:
        click.echo(f"Nessun reminder nei prossimi {entro} minuti.")
        return
    click.echo(f"Reminder imminenti (entro {entro} min):")
    for a in apps:
        minuti_mancanti = int(
            (a.data_ora_dt - __import__("datetime").datetime.now()).total_seconds() / 60
        )
        click.echo(f"  [{a.id}] tra {minuti_mancanti} min  — {a.titolo}")


@grp_agenda.command("statistiche")
def cmd_statistiche():
    """Mostra statistiche dell'agenda."""
    agenda = _agenda()
    stats = agenda.statistiche()
    click.echo(f"Totale appuntamenti: {stats['totale']}")
    click.echo(f"Oggi:                {stats['oggi']}")
    click.echo(f"Questa settimana:    {stats['questa_settimana']}")
    click.echo(f"Questo mese:         {stats['questo_mese']}")
    click.echo("\nPer tipo:")
    for tipo, n in stats["per_tipo"].items():
        if n:
            click.echo(f"  {tipo:<16} {n}")
    click.echo("\nPer stato:")
    for stato, n in stats["per_stato"].items():
        if n:
            click.echo(f"  {stato:<16} {n}")


# ================================================================ CLIENTI

def _clienti() -> GestioneClienti:
    db = os.getenv("PCT_CLIENTI_DB", "./clienti/anagrafica.json")
    return GestioneClienti(db_path=db)


def _fmt_cliente(c, verbose: bool = False) -> str:
    tipo = "PF" if c.tipo == TipoCliente.PERSONA_FISICA else "PG"
    cf = c.codice_fiscale or c.partita_iva or ""
    riga = f"[{c.id}] {c.nome_completo:<30} {tipo}  {c.stato.value:<12} {cf}"
    if verbose:
        if c.recapiti.cellulare or c.recapiti.telefono:
            riga += f"\n         Tel: {c.recapiti.cellulare or c.recapiti.telefono}"
        if c.recapiti.email:
            riga += f"\n         Email: {c.recapiti.email}"
        if str(c.indirizzo_residenza):
            riga += f"\n         Indirizzo: {c.indirizzo_residenza}"
        if c.avvocato_referente:
            riga += f"\n         Avv.: {c.avvocato_referente}"
        if c.procedimenti_attivi:
            proc = ", ".join(f"RG {p.numero_rg}/{p.anno}" for p in c.procedimenti_attivi)
            riga += f"\n         Procedimenti: {proc}"
    return riga


@cli.group("clienti")
def grp_clienti():
    """Gestione anagrafica clienti dello studio."""
    pass


@grp_clienti.command("nuovo")
@click.option("--tipo", type=click.Choice(["PF", "PG"], case_sensitive=False),
              required=True, help="PF=Persona fisica, PG=Persona giuridica")
@click.option("--nome", default="", help="Nome (persona fisica)")
@click.option("--cognome", default="", help="Cognome (persona fisica)")
@click.option("--ragione-sociale", default="", help="Ragione sociale (persona giuridica)")
@click.option("--cf", default="", help="Codice fiscale")
@click.option("--piva", default="", help="Partita IVA")
@click.option("--email", default="", help="Email")
@click.option("--cellulare", default="", help="Cellulare")
@click.option("--telefono", default="", help="Telefono fisso")
@click.option("--pec", default="", help="PEC")
@click.option("--avvocato", default="", help="Avvocato referente")
@click.option("--note", default="", help="Note")
def cmd_clienti_nuovo(tipo, nome, cognome, ragione_sociale, cf, piva,
                      email, cellulare, telefono, pec, avvocato, note):
    """Aggiunge un nuovo cliente all'anagrafica."""
    gc = _clienti()
    tipo_enum = TipoCliente.PERSONA_FISICA if tipo.upper() == "PF" else TipoCliente.PERSONA_GIURIDICA
    try:
        c = gc.nuovo(
            tipo=tipo_enum,
            nome=nome, cognome=cognome,
            ragione_sociale=ragione_sociale,
            codice_fiscale=cf, partita_iva=piva,
            avvocato_referente=avvocato, note=note,
        )
        if email or cellulare or telefono or pec:
            gc.aggiorna_recapiti(c.id, email=email, cellulare=cellulare,
                                 telefono=telefono, pec=pec)
        click.echo(f"Cliente aggiunto: {c.id}")
        click.echo(_fmt_cliente(c, verbose=True))
    except ValueError as e:
        click.echo(f"Errore: {e}", err=True)
        sys.exit(1)


@grp_clienti.command("lista")
@click.option("--stato", type=click.Choice([s.value for s in StatoCliente],
              case_sensitive=False), default="ATTIVO", show_default=True)
@click.option("--tipo", type=click.Choice(["PF", "PG"], case_sensitive=False),
              default=None)
@click.option("-v", "--verbose", is_flag=True, default=False)
def cmd_clienti_lista(stato, tipo, verbose):
    """Elenca i clienti in anagrafica."""
    gc = _clienti()
    stato_e = StatoCliente(stato) if stato else None
    tipo_e = (TipoCliente.PERSONA_FISICA if tipo and tipo.upper() == "PF"
              else TipoCliente.PERSONA_GIURIDICA if tipo else None)
    clienti = gc.tutti(stato=stato_e, tipo=tipo_e)
    if not clienti:
        click.echo("Nessun cliente trovato.")
        return
    click.echo(f"{'ID':<10} {'Nome':<30} {'Tipo'} {'Stato':<12} CF/P.IVA")
    click.echo("-" * 75)
    for c in clienti:
        click.echo(_fmt_cliente(c, verbose=verbose))


@grp_clienti.command("cerca")
@click.argument("testo")
@click.option("-v", "--verbose", is_flag=True, default=False)
def cmd_clienti_cerca(testo, verbose):
    """Cerca clienti per nome, CF, P.IVA, email o procedimento."""
    gc = _clienti()
    risultati = gc.cerca(testo=testo)
    if not risultati:
        click.echo("Nessun risultato.")
        return
    for c in risultati:
        click.echo(_fmt_cliente(c, verbose=verbose))


@grp_clienti.command("dettaglio")
@click.argument("id_cliente")
def cmd_clienti_dettaglio(id_cliente):
    """Mostra la scheda completa di un cliente."""
    gc = _clienti()
    c = gc.get(id_cliente.upper())
    if not c:
        click.echo(f"Cliente '{id_cliente}' non trovato.", err=True)
        sys.exit(1)
    click.echo(json.dumps(c.to_dict(), ensure_ascii=False, indent=2))


@grp_clienti.command("modifica")
@click.argument("id_cliente")
@click.option("--nome", default=None)
@click.option("--cognome", default=None)
@click.option("--cf", default=None)
@click.option("--email", default=None)
@click.option("--cellulare", default=None)
@click.option("--telefono", default=None)
@click.option("--avvocato", default=None)
@click.option("--note", default=None)
@click.option("--stato", type=click.Choice([s.value for s in StatoCliente],
              case_sensitive=False), default=None)
def cmd_clienti_modifica(id_cliente, nome, cognome, cf, email, cellulare,
                          telefono, avvocato, note, stato):
    """Modifica i dati di un cliente."""
    gc = _clienti()
    try:
        campi = {k: v for k, v in {
            "nome": nome, "cognome": cognome,
            "codice_fiscale": cf.upper() if cf else None,
            "avvocato_referente": avvocato, "note": note,
            "stato": StatoCliente(stato) if stato else None,
        }.items() if v is not None}
        if campi:
            gc.aggiorna(id_cliente.upper(), **campi)
        recapiti = {k: v for k, v in {
            "email": email, "cellulare": cellulare, "telefono": telefono
        }.items() if v is not None}
        if recapiti:
            gc.aggiorna_recapiti(id_cliente.upper(), **recapiti)
        c = gc.get(id_cliente.upper())
        click.echo(f"Cliente {c.id} aggiornato.")
        click.echo(_fmt_cliente(c, verbose=True))
    except KeyError as e:
        click.echo(str(e), err=True)
        sys.exit(1)


@grp_clienti.command("elimina")
@click.argument("id_cliente")
@click.confirmation_option(prompt="Sei sicuro di voler eliminare questo cliente?")
def cmd_clienti_elimina(id_cliente):
    """Elimina un cliente dall'anagrafica."""
    gc = _clienti()
    try:
        gc.elimina(id_cliente.upper())
        click.echo(f"Cliente {id_cliente.upper()} eliminato.")
    except KeyError as e:
        click.echo(str(e), err=True)
        sys.exit(1)


@grp_clienti.command("procedimento")
@click.argument("id_cliente")
@click.option("--rg", required=True, help="Numero RG (es. 1234)")
@click.option("--anno", type=int, default=None, help="Anno procedimento")
@click.option("--tribunale", default="", help="Tribunale competente")
@click.option("--descrizione", default="", help="Breve descrizione")
def cmd_clienti_procedimento(id_cliente, rg, anno, tribunale, descrizione):
    """Aggiunge un procedimento a un cliente."""
    import datetime
    gc = _clienti()
    try:
        proc = RiferimentoProcedimento(
            numero_rg=rg,
            anno=anno or datetime.date.today().year,
            tribunale=tribunale,
            descrizione=descrizione,
            data_apertura=datetime.date.today().isoformat(),
        )
        gc.aggiungi_procedimento(id_cliente.upper(), proc)
        click.echo(f"Procedimento RG {rg}/{anno or ''} aggiunto.")
    except KeyError as e:
        click.echo(str(e), err=True)
        sys.exit(1)


@grp_clienti.command("statistiche")
def cmd_clienti_statistiche():
    """Mostra statistiche dell'anagrafica clienti."""
    gc = _clienti()
    stats = gc.statistiche()
    click.echo(f"Totale clienti:           {stats['totale']}")
    click.echo(f"Con procedimenti attivi:  {stats['con_procedimenti_attivi']}")
    click.echo(f"Documenti scaduti:        {stats['documenti_scaduti']}")
    click.echo("\nPer tipo:")
    for t, n in stats["per_tipo"].items():
        if n:
            click.echo(f"  {t:<22} {n}")
    click.echo("\nPer stato:")
    for s, n in stats["per_stato"].items():
        if n:
            click.echo(f"  {s:<22} {n}")


# ================================================================ FASCICOLI

def _fascicoli() -> GestioneFascicoli:
    return GestioneFascicoli(
        db_path=os.getenv("PCT_FASCICOLI_DB", "./fascicoli/fascicoli.json"),
        documents_dir=os.getenv("PCT_FASCICOLI_DOCS", "./fascicoli/documenti"),
        archive_dir=os.getenv("PCT_FASCICOLI_ARCH", "./fascicoli/archivio"),
    )


def _fmt_fasc(f, verbose: bool = False) -> str:
    sc = f.prossima_scadenza
    sc_txt = f" | pross.scad: {sc.data}" if sc else ""
    riga = (f"[{f.id}] {f.numero}  {f.stato.value:<12} {f.tipo.value:<15}"
            f" {f.titolo[:35]}{sc_txt}")
    if verbose:
        if f.nome_cliente:
            riga += f"\n         Cliente:    {f.nome_cliente}"
        if f.rg_completo:
            riga += f"\n         RG:         {f.rg_completo}"
        if f.tribunale:
            riga += f"\n         Tribunale:  {f.tribunale}"
        if f.avvocato_referente:
            riga += f"\n         Avv.:       {f.avvocato_referente}"
        riga += f"\n         Docs: {f.documenti_count}  Attività: {f.attivita_count}"
    return riga


@cli.group("fascicoli")
def grp_fascicoli():
    """Gestione fascicoli (cartelle legali) dello studio."""
    pass


@grp_fascicoli.command("nuovo")
@click.option("--titolo", required=True, help="Titolo del fascicolo")
@click.option("--tipo", required=True,
              type=click.Choice([t.value for t in TipoFascicolo], case_sensitive=False),
              help="Tipo procedimento")
@click.option("--cliente", default="", help="ID cliente")
@click.option("--controparte", default="", help="Nome della controparte")
@click.option("--tribunale", default="", help="Tribunale competente")
@click.option("--rg", default="", help="Numero RG")
@click.option("--anno-rg", default=0, type=int, help="Anno RG")
@click.option("--avvocato", default="", help="Avvocato referente")
@click.option("--oggetto", default="", help="Oggetto della causa")
@click.option("--valore", default=0.0, type=float, help="Valore causa in euro")
@click.option("--note", default="", help="Note")
def cmd_fasc_nuovo(titolo, tipo, cliente, controparte, tribunale, rg,
                   anno_rg, avvocato, oggetto, valore, note):
    """Crea un nuovo fascicolo."""
    gf = _fascicoli()
    nome_cliente = ""
    if cliente:
        gc = _clienti()
        c = gc.get(cliente.upper())
        nome_cliente = c.nome_completo if c else ""
    try:
        f = gf.nuovo(
            titolo=titolo,
            tipo=TipoFascicolo(tipo.upper()),
            id_cliente=cliente.upper() if cliente else "",
            nome_cliente=nome_cliente,
            controparte=controparte,
            tribunale=tribunale,
            numero_rg=rg,
            anno_rg=anno_rg,
            avvocato_referente=avvocato,
            oggetto=oggetto,
            valore_causa=valore,
            note=note,
        )
        click.echo(f"Fascicolo creato: {f.numero} [{f.id}]")
        click.echo(_fmt_fasc(f, verbose=True))
    except ValueError as e:
        click.echo(f"Errore: {e}", err=True)
        sys.exit(1)


@grp_fascicoli.command("lista")
@click.option("--stato", type=click.Choice([s.value for s in StatoFascicolo],
              case_sensitive=False), default=None)
@click.option("--tipo", type=click.Choice([t.value for t in TipoFascicolo],
              case_sensitive=False), default=None)
@click.option("--archiviati", is_flag=True, default=False,
              help="Mostra solo archiviati")
@click.option("-v", "--verbose", is_flag=True, default=False)
def cmd_fasc_lista(stato, tipo, archiviati, verbose):
    """Elenca i fascicoli."""
    gf = _fascicoli()
    stato_e = StatoFascicolo(stato) if stato else None
    tipo_e = TipoFascicolo(tipo) if tipo else None
    fascicoli = gf.tutti(stato=stato_e, tipo=tipo_e, archiviati=archiviati)
    if not fascicoli:
        click.echo("Nessun fascicolo trovato.")
        return
    for f in fascicoli:
        click.echo(_fmt_fasc(f, verbose=verbose))


@grp_fascicoli.command("cerca")
@click.argument("testo")
@click.option("--archiviati", is_flag=True, default=False)
@click.option("-v", "--verbose", is_flag=True, default=False)
def cmd_fasc_cerca(testo, archiviati, verbose):
    """Cerca fascicoli per testo libero."""
    gf = _fascicoli()
    risultati = gf.cerca(testo=testo, archiviati=archiviati)
    if not risultati:
        click.echo("Nessun risultato.")
        return
    for f in risultati:
        click.echo(_fmt_fasc(f, verbose=verbose))


@grp_fascicoli.command("dettaglio")
@click.argument("id_fasc")
def cmd_fasc_dettaglio(id_fasc):
    """Mostra il dettaglio completo di un fascicolo."""
    gf = _fascicoli()
    f = gf.get(id_fasc.upper())
    if not f:
        click.echo(f"Fascicolo '{id_fasc}' non trovato.", err=True)
        sys.exit(1)
    click.echo(json.dumps(f.to_dict(), ensure_ascii=False, indent=2))


@grp_fascicoli.command("stato")
@click.argument("id_fasc")
@click.argument("nuovo_stato",
                type=click.Choice([s.value for s in StatoFascicolo], case_sensitive=False))
@click.option("--note", default="", help="Note sul cambio di stato")
@click.option("--avvocato", default="", help="Avvocato che esegue l'operazione")
def cmd_fasc_stato(id_fasc, nuovo_stato, note, avvocato):
    """Cambia lo stato di un fascicolo."""
    gf = _fascicoli()
    try:
        f = gf.cambia_stato(id_fasc.upper(), StatoFascicolo(nuovo_stato.upper()),
                            note=note, avvocato=avvocato)
        click.echo(f"Stato aggiornato: {f.stato.value}")
    except (KeyError, ValueError) as e:
        click.echo(str(e), err=True)
        sys.exit(1)


@grp_fascicoli.command("attivita")
@click.argument("id_fasc")
@click.option("--tipo", required=True,
              type=click.Choice([t.value for t in TipoAttivita], case_sensitive=False))
@click.option("--data", required=True, help="Data YYYY-MM-DD")
@click.option("--titolo", required=True, help="Titolo attività")
@click.option("--luogo", default="", help="Luogo")
@click.option("--avvocato", default="", help="Avvocato")
@click.option("--note", default="", help="Note")
def cmd_fasc_attivita(id_fasc, tipo, data, titolo, luogo, avvocato, note):
    """Aggiunge un'attività processuale a un fascicolo."""
    gf = _fascicoli()
    try:
        att = gf.aggiungi_attivita(
            id_fasc.upper(),
            tipo=TipoAttivita(tipo.upper()),
            data=data,
            titolo=titolo,
            luogo=luogo,
            avvocato=avvocato,
            note=note,
        )
        click.echo(f"Attività aggiunta: [{att.id}] {att.titolo} — {att.data}")
    except (KeyError, ValueError) as e:
        click.echo(str(e), err=True)
        sys.exit(1)


@grp_fascicoli.command("definisci")
@click.argument("id_fasc")
@click.option("--esito", default="", help="Esito finale della causa")
@click.option("--motivo", default="", help="Motivo della chiusura")
@click.option("--note", default="", help="Note")
@click.option("--avvocato", default="", help="Avvocato")
def cmd_fasc_definisci(id_fasc, esito, motivo, note, avvocato):
    """Marca un fascicolo come DEFINITO (pronto per archiviazione)."""
    gf = _fascicoli()
    try:
        f = gf.definisci(id_fasc.upper(), esito_finale=esito, motivo=motivo,
                         note=note, avvocato=avvocato)
        click.echo(f"Fascicolo {f.numero} definito. Esito: {esito or 'N/D'}")
    except (KeyError, ValueError) as e:
        click.echo(str(e), err=True)
        sys.exit(1)


@grp_fascicoli.command("archivia")
@click.argument("id_fasc")
@click.option("--avvocato", default="", help="Avvocato che archivia")
@click.option("--no-zip", is_flag=True, default=False, help="Non creare archivio ZIP")
def cmd_fasc_archivia(id_fasc, avvocato, no_zip):
    """Archivia definitivamente un fascicolo (crea ZIP dei documenti)."""
    gf = _fascicoli()
    try:
        f = gf.archivia(id_fasc.upper(), crea_zip=not no_zip, avvocato=avvocato)
        click.echo(f"Fascicolo {f.numero} archiviato.")
        if f.archivio and f.archivio.percorso_zip:
            click.echo(f"Archivio ZIP: {f.archivio.percorso_zip}")
    except (KeyError, ValueError) as e:
        click.echo(str(e), err=True)
        sys.exit(1)


@grp_fascicoli.command("scadenze")
@click.option("--giorni", default=7, show_default=True,
              help="Mostra scadenze entro N giorni")
def cmd_fasc_scadenze(giorni):
    """Mostra fascicoli con scadenze imminenti."""
    gf = _fascicoli()
    scadenze = gf.fascicoli_con_scadenze_imminenti(entro_giorni=giorni)
    if not scadenze:
        click.echo(f"Nessuna scadenza nei prossimi {giorni} giorni.")
        return
    for item in scadenze:
        f = item["fascicolo"]
        sc = item["scadenza"]
        click.echo(f"[{f.numero}] {f.titolo}")
        click.echo(f"         Scadenza: {sc.data} — {sc.titolo}")


@grp_fascicoli.command("statistiche")
def cmd_fasc_statistiche():
    """Mostra statistiche dei fascicoli."""
    gf = _fascicoli()
    stats = gf.statistiche()
    click.echo(f"Totale fascicoli:    {stats['totale']}")
    click.echo(f"Attivi:              {stats['attivi']}")
    click.echo(f"Definiti:            {stats['definiti']}")
    click.echo(f"Archiviati:          {stats['archiviati']}")
    click.echo(f"Totale documenti:    {stats['totale_documenti']}")
    click.echo(f"Totale attività:     {stats['totale_attivita']}")
    click.echo("\nPer tipo:")
    for t, n in stats["per_tipo"].items():
        if n:
            click.echo(f"  {t:<20} {n}")
    click.echo("\nPer stato:")
    for s, n in stats["per_stato"].items():
        if n:
            click.echo(f"  {s:<20} {n}")


def main():
    cli()


if __name__ == "__main__":
    main()
