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


def main():
    cli()


if __name__ == "__main__":
    main()
