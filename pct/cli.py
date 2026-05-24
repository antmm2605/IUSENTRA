"""
Interfaccia a riga di comando per il sistema PCT.
"""

import os
import sys
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

import click

from . import __version__
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
from .messaggi import (
    GestioneMessaggi,
    CanaleMsggio,
    ConfigMessaggistica,
    ConfigEmail,
    ConfigTwilio,
)
from .backup import (
    GestioneBackup,
    TipoBackup,
    StatoBackup,
    FrequenzaBackup,
)
from .auth import (
    GestioneUtenti,
    RuoloUtente,
)
from .fatturazione import GestioneFatturazione
from .pagamenti import GestionePagamenti
from .preventivi import GestionePreventivi
from .golden_paths import build_golden_path_payload, run_golden_path_suites
from .legal_update_pipeline import DEFAULT_SOURCE_ROWS, build_legal_update_pipeline
from .storage_migration_full import attach_migration_rollback_context
from .studio_demo import build_studio_demo_snapshot
from .tenant import DatabaseConfig, DbMode, GestioneTenant
from .cli_operational import cmd_backup_blindato, cmd_crash_test_operativo
from .scadenziario import (
    GestioneScadenziario,
    TipoTermine,
    StatoTermine,
    PRESET_TERMINI,
    calcola_termine,
)
from .timesheet import GestioneTimesheet


for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


def _env_int_option(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)) or default)
        return value if value >= 0 else default
    except (TypeError, ValueError):
        return default


def carica_config(config_path: str | None = None) -> dict:
    """
    Carica la configurazione da config/studio.json (priorità) o da variabili d'ambiente.
    Il percorso del file può essere sovrascritto tramite PCT_STUDIO_CONFIG.
    """
    path = config_path or os.getenv("PCT_STUDIO_CONFIG", "./config/studio.json")
    try:
        from .config_studio import GestioneConfigStudio
        gs = GestioneConfigStudio(path)
        c = gs.config
    except Exception:
        c = None

    def _v(from_cfg, env_key, default=""):
        """Restituisce from_cfg se non vuoto, altrimenti env var, altrimenti default."""
        if from_cfg:
            return from_cfg
        return os.getenv(env_key, default)

    return {
        "pec_indirizzo":  _v(c and c.pec.indirizzo,  "PCT_PEC_INDIRIZZO"),
        "pec_password":   _v(c and c.pec.password,   "PCT_PEC_PASSWORD"),
        "pec_smtp_host":  _v(c and c.pec.smtp_host,  "PCT_PEC_SMTP_HOST", "smtp.pec.aruba.it"),
        "pec_smtp_port":  (c and c.pec.smtp_port) or int(os.getenv("PCT_PEC_SMTP_PORT", "465")),
        "pec_imap_host":  _v(c and c.pec.imap_host,  "PCT_PEC_IMAP_HOST", "imaps.pec.aruba.it"),
        "firma_p12":      _v(c and c.firma.p12_path,  "PCT_FIRMA_P12"),
        "firma_password": _v(c and c.firma.password,  "PCT_FIRMA_PASSWORD"),
        "cf_avvocato":    _v(c and (c.studio.codice_fiscale_avvocato or c.firma.cf_avvocato),
                            "PCT_CF_AVVOCATO"),
        "nome_avvocato":  _v(c and c.studio.avvocato, "PCT_NOME_AVVOCATO"),
        "output_dir":     os.getenv("PCT_OUTPUT_DIR", "./depositi"),
    }


@click.group()
@click.version_option(__version__)
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

    reginde = ClientReGINde()
    tribunale_norm = tribunale.strip()
    ufficio = (
        reginde.ottieni_ufficio(tribunale_norm)
        if tribunale_norm.isdigit()
        else reginde.cerca_ufficio_giudiziario(tribunale_norm)
    )
    if not ufficio:
        click.echo(
            f"Errore: ufficio giudiziario '{tribunale}' non trovato nel registro ufficiale.",
            err=True,
        )
        sys.exit(1)

    dati = DatiBusta(
        codice_ufficio=ufficio.codice,
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

    click.echo(f"Avvio deposito presso {ufficio.nome} ({ufficio.codice})...")
    esito = deposito.deposita(dati, ufficio.codice, attendi_ricevute=not no_ricevute)

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


# ============================================================ MESSAGGI

def _messaggi_config() -> ConfigMessaggistica:
    return ConfigMessaggistica(
        email=ConfigEmail(
            smtp_host=os.getenv("PCT_SMTP_HOST", ""),
            smtp_port=int(os.getenv("PCT_SMTP_PORT", "587")),
            username=os.getenv("PCT_SMTP_USER", ""),
            password=os.getenv("PCT_SMTP_PASS", ""),
            mittente_email=os.getenv("PCT_SMTP_FROM", ""),
            mittente_nome=os.getenv("PCT_STUDIO_NOME", "Studio Legale"),
        ),
        twilio=ConfigTwilio(
            account_sid=os.getenv("TWILIO_ACCOUNT_SID", ""),
            auth_token=os.getenv("TWILIO_AUTH_TOKEN", ""),
            numero_sms=os.getenv("TWILIO_SMS_NUMBER", ""),
            numero_whatsapp=os.getenv("TWILIO_WA_NUMBER", ""),
        ),
        studio_nome=os.getenv("PCT_STUDIO_NOME", "Studio Legale"),
    )


def _messaggi(db="./messaggi/storico.json") -> GestioneMessaggi:
    return GestioneMessaggi(config=_messaggi_config(), db_path=db)


@cli.group("messaggi")
def grp_messaggi():
    """Gestione messaggi (email/SMS/WhatsApp)."""
    pass


@grp_messaggi.command("lista")
@click.option("--canale", default="", help="EMAIL | SMS | WHATSAPP")
@click.option("--stato", default="", help="IN_CODA | INVIATO | CONSEGNATO | FALLITO …")
@click.option("--db", default="./messaggi/storico.json", help="DB messaggi")
def cmd_msg_lista(canale, stato, db):
    """Elenca messaggi nello storico."""
    gm = _messaggi(db)
    messaggi = gm.tutti(
        canale=CanaleMsggio(canale) if canale else None,
    )
    if stato:
        from .messaggi import StatoMessaggio
        messaggi = [m for m in messaggi if m.stato.value == stato]
    click.echo(f"{'ID':<12} {'CANALE':<10} {'STATO':<12} {'DATA':<20} DESTINATARIO")
    click.echo("-" * 72)
    for m in messaggi:
        dest = m.email_destinatario or m.telefono_destinatario or m.nome_destinatario
        click.echo(
            f"{m.id:<12} {m.canale.value:<10} {m.stato.value:<12} "
            f"{m.creato_il[:19]:<20} {dest}"
        )


@grp_messaggi.command("invia-email")
@click.option("--a", "dest", required=True, help="Indirizzo email destinatario")
@click.option("--oggetto", required=True, help="Oggetto email")
@click.option("--testo", required=True, help="Corpo testo")
@click.option("--id-cliente", default="", help="ID cliente (opzionale)")
@click.option("--db", default="./messaggi/storico.json", help="DB messaggi")
def cmd_msg_email(dest, oggetto, testo, id_cliente, db):
    """Invia un'email al destinatario."""
    gm = _messaggi(db)
    try:
        msg = gm.invia_email(
            destinatario=dest,
            oggetto=oggetto,
            corpo_testo=testo,
            id_cliente=id_cliente,
        )
        click.echo(f"Email {msg.stato.value}: {msg.id}")
    except Exception as e:
        click.echo(f"Errore: {e}", err=True)


@grp_messaggi.command("invia-sms")
@click.option("--a", "telefono", required=True, help="Numero E.164 (+39XXXXXXXXXX)")
@click.option("--testo", required=True, help="Testo SMS")
@click.option("--id-cliente", default="", help="ID cliente (opzionale)")
@click.option("--db", default="./messaggi/storico.json", help="DB messaggi")
def cmd_msg_sms(telefono, testo, id_cliente, db):
    """Invia un SMS tramite Twilio."""
    gm = _messaggi(db)
    try:
        msg = gm.invia_sms(telefono=telefono, testo=testo, id_cliente=id_cliente)
        click.echo(f"SMS {msg.stato.value}: {msg.id}")
    except Exception as e:
        click.echo(f"Errore: {e}", err=True)


@grp_messaggi.command("statistiche")
@click.option("--db", default="./messaggi/storico.json", help="DB messaggi")
def cmd_msg_statistiche(db):
    """Mostra statistiche messaggi."""
    stats = _messaggi(db).statistiche()
    click.echo(f"Totale:       {stats['totale']}")
    click.echo(f"Inviati:      {stats['inviati']}")
    click.echo(f"Consegnati:   {stats['consegnati']}")
    click.echo(f"Falliti:      {stats['falliti']}")
    click.echo(f"In coda:      {stats['in_coda']}")
    click.echo("\nPer canale:")
    for c, n in stats["per_canale"].items():
        click.echo(f"  {c:<12} {n}")


# ============================================================ BACKUP

def _backup(backup_dir="./backup") -> GestioneBackup:
    data_paths = {
        "agenda":    os.getenv("PCT_AGENDA_DB", "./agenda/appuntamenti.json"),
        "clienti":   os.getenv("PCT_CLIENTI_DB", "./clienti/anagrafica.json"),
        "fascicoli": os.getenv("PCT_FASCICOLI_DB", "./fascicoli/fascicoli.json"),
        "messaggi":  os.getenv("PCT_MESSAGGI_DB", "./messaggi/storico.json"),
        "documenti": os.getenv("PCT_FASCICOLI_DOCS", "./fascicoli/documenti"),
    }
    return GestioneBackup(directory_backup=backup_dir, percorsi_dati=data_paths)


@cli.group("backup")
def grp_backup():
    """Gestione backup e ripristino."""
    pass


@grp_backup.command("esegui")
@click.option("--tipo", default="COMPLETO", type=click.Choice(["COMPLETO", "INCREMENTALE"]),
              help="Tipo backup")
@click.option("--componenti", default="", help="Componenti separati da virgola (vuoto=tutti)")
@click.option("--nota", default="", help="Nota descrittiva")
@click.option("--dir", "backup_dir", default="./backup", help="Cartella backup")
def cmd_bk_esegui(tipo, componenti, nota, backup_dir):
    """Esegue un backup."""
    gb = _backup(backup_dir)
    comps = [c.strip() for c in componenti.split(",") if c.strip()] or None
    record = gb.esegui_backup(tipo=TipoBackup(tipo), componenti=comps, nota=nota)
    if record.stato == StatoBackup.OK:
        size_mb = round(record.dimensione_bytes / 1024 / 1024, 2)
        click.echo(f"Backup OK: {record.id}")
        click.echo(f"  File:    {record.percorso_file}")
        click.echo(f"  N°file:  {record.num_file}")
        click.echo(f"  Dim:     {size_mb} MB")
    else:
        click.echo(f"Backup FALLITO: {record.errore}", err=True)


@grp_backup.command("lista")
@click.option("--dir", "backup_dir", default="./backup", help="Cartella backup")
def cmd_bk_lista(backup_dir):
    """Elenca i backup disponibili."""
    gb = _backup(backup_dir)
    records = gb.tutti()
    if not records:
        click.echo("Nessun backup trovato.")
        return
    click.echo(f"{'ID':<38} {'TIPO':<12} {'STATO':<10} {'FILE':<6} {'DIM MB':<8} DATA")
    click.echo("-" * 90)
    for r in records:
        size_mb = round(r.dimensione_bytes / 1024 / 1024, 2)
        click.echo(
            f"{r.id:<38} {r.tipo.value:<12} {r.stato.value:<10} "
            f"{r.num_file:<6} {size_mb:<8} {r.timestamp[:19]}"
        )


@grp_backup.command("verifica")
@click.argument("id_backup")
@click.option("--dir", "backup_dir", default="./backup", help="Cartella backup")
def cmd_bk_verifica(id_backup, backup_dir):
    """Verifica l'integrità di un backup."""
    gb = _backup(backup_dir)
    ris = gb.verifica_integrita(id_backup)
    if ris["ok"]:
        click.echo(f"OK — backup integro: {id_backup}")
    else:
        click.echo(f"ATTENZIONE: backup corrotto! {id_backup}", err=True)
        click.echo(f"  Hash atteso:  {ris['hash_atteso']}")
        click.echo(f"  Hash attuale: {ris['hash_attuale']}")


@grp_backup.command("ripristina")
@click.argument("id_backup")
@click.option("--dest", required=True, help="Cartella di destinazione")
@click.option("--componenti", default="", help="Componenti separati da virgola (vuoto=tutti)")
@click.option("--sovrascrivi", is_flag=True, default=False, help="Sovrascrivi file esistenti")
@click.option("--password", default="", help="Password se backup cifrato")
@click.option("--dir", "backup_dir", default="./backup", help="Cartella backup")
def cmd_bk_ripristina(id_backup, dest, componenti, sovrascrivi, password, backup_dir):
    """Ripristina un backup nella destinazione specificata."""
    gb = _backup(backup_dir)
    comps = [c.strip() for c in componenti.split(",") if c.strip()] or None
    try:
        ris = gb.ripristina(
            id_backup, dest,
            componenti=comps,
            password=password,
            sovrascrivi=sovrascrivi,
        )
        click.echo(f"Ripristino completato:")
        click.echo(f"  Ripristinati: {ris['file_ripristinati']}")
        click.echo(f"  Saltati:      {ris['file_saltati']}")
        click.echo(f"  Errori:       {len(ris['errori'])}")
        click.echo(f"  Destinazione: {ris['destinazione']}")
    except Exception as e:
        click.echo(f"Errore: {e}", err=True)


@grp_backup.command("elimina")
@click.argument("id_backup")
@click.option("--dir", "backup_dir", default="./backup", help="Cartella backup")
def cmd_bk_elimina(id_backup, backup_dir):
    """Elimina un backup."""
    gb = _backup(backup_dir)
    try:
        gb.elimina(id_backup)
        click.echo(f"Backup {id_backup} eliminato.")
    except ValueError as e:
        click.echo(f"Errore: {e}", err=True)


@grp_backup.command("statistiche")
@click.option("--dir", "backup_dir", default="./backup", help="Cartella backup")
def cmd_bk_statistiche(backup_dir):
    """Mostra statistiche backup."""
    stats = _backup(backup_dir).statistiche()
    click.echo(f"Totale backup:   {stats['totale']}")
    click.echo(f"Completati:      {stats['ok']}")
    click.echo(f"Falliti:         {stats['falliti']}")
    click.echo(f"Corrotti:        {stats['corrotti']}")
    click.echo(f"Spazio totale:   {stats['dimensione_totale_mb']} MB")
    click.echo(f"Ultimo backup:   {stats['ultimo'] or 'mai'}")


# ============================================================ AUTH

def _utenti(db="./auth/utenti.json", audit="./auth/audit.json") -> GestioneUtenti:
    import secrets
    sk = os.getenv("PCT_SECRET_KEY", secrets.token_hex(32))
    return GestioneUtenti(db_path=db, audit_path=audit, secret_key=sk)


@cli.group("utenti")
def grp_utenti():
    """Gestione utenti e permessi."""
    pass


@grp_utenti.command("lista")
@click.option("--db", default="./auth/utenti.json")
def cmd_utenti_lista(db):
    """Elenca tutti gli utenti."""
    gu = _utenti(db)
    click.echo(f"{'USERNAME':<20} {'RUOLO':<16} {'STATO':<10} NOME")
    click.echo("-" * 70)
    for u in gu.tutti():
        stato = "Attivo" if u.attivo else "Disabilitato"
        click.echo(f"{u.username:<20} {u.ruolo.value:<16} {stato:<10} {u.nome_completo or '—'}")


@grp_utenti.command("crea")
@click.option("--username", required=True)
@click.option("--password", required=True)
@click.option("--ruolo", required=True,
              type=click.Choice([r.value for r in RuoloUtente]))
@click.option("--email", default="")
@click.option("--nome", default="")
@click.option("--db", default="./auth/utenti.json")
def cmd_utenti_crea(username, password, ruolo, email, nome, db):
    """Crea un nuovo utente."""
    gu = _utenti(db)
    try:
        u = gu.crea(username=username, password=password,
                    ruolo=RuoloUtente(ruolo), email=email, nome_completo=nome)
        click.echo(f"Utente creato: {u.username} ({u.ruolo.value})")
    except ValueError as e:
        click.echo(f"Errore: {e}", err=True)


@grp_utenti.command("cambia-password")
@click.argument("username")
@click.option("--password", required=True, prompt=True, hide_input=True,
              confirmation_prompt=True)
@click.option("--db", default="./auth/utenti.json")
def cmd_utenti_password(username, password, db):
    """Cambia la password di un utente."""
    gu = _utenti(db)
    u = gu.get_by_username(username)
    if not u:
        click.echo(f"Utente '{username}' non trovato.", err=True)
        return
    try:
        gu.cambia_password(u.id, password)
        click.echo(f"Password di '{username}' aggiornata.")
    except ValueError as e:
        click.echo(f"Errore: {e}", err=True)


@grp_utenti.command("audit")
@click.option("--username", default="", help="Filtra per username")
@click.option("--azione", default="", help="Filtra per azione")
@click.option("--db", default="./auth/utenti.json")
@click.option("--limit", default=30, show_default=True)
def cmd_utenti_audit(username, azione, db, limit):
    """Mostra il log di audit."""
    gu = _utenti(db)
    id_utente = ""
    if username:
        u = gu.get_by_username(username)
        if u:
            id_utente = u.id
    eventi = gu.audit_log(id_utente=id_utente, azione=azione, limit=limit)
    click.echo(f"{'DATA':<20} {'UTENTE':<15} {'AZIONE':<30} ESITO")
    click.echo("-" * 80)
    for e in eventi:
        click.echo(
            f"{e.timestamp[:19]:<20} {e.username:<15} {e.azione:<30} {e.esito}"
        )


# ============================================================ SCADENZIARIO

def _scadenziario(db="./scadenziario/scadenze.json") -> GestioneScadenziario:
    return GestioneScadenziario(db_path=db)


@cli.group("scadenze")
def grp_scadenze():
    """Gestione scadenziario legale."""
    pass


@grp_scadenze.command("lista")
@click.option("--tipo", default="", help="Tipo termine")
@click.option("--db", default="./scadenziario/scadenze.json")
def cmd_sc_lista(tipo, db):
    """Elenca le scadenze aperte."""
    gs = _scadenziario(db)
    scadenze = gs.tutte(tipo=TipoTermine(tipo) if tipo else None)
    click.echo(f"{'DATA':<12} {'PRIO':<9} {'GG':<5} {'TIPO':<22} TITOLO")
    click.echo("-" * 80)
    for s in scadenze:
        g = s.giorni_alla_scadenza
        g_str = f"{g}gg" if g is not None else "—"
        click.echo(
            f"{s.data_scadenza:<12} {s.priorita.value:<9} {g_str:<5} "
            f"{s.tipo.value[:21]:<22} {s.titolo}"
        )


@grp_scadenze.command("nuova")
@click.option("--titolo", required=True)
@click.option("--data", required=True, help="Data scadenza YYYY-MM-DD")
@click.option("--tipo", default="ALTRO",
              type=click.Choice([t.value for t in TipoTermine]))
@click.option("--perentorio", is_flag=True, default=False)
@click.option("--id-fascicolo", default="")
@click.option("--db", default="./scadenziario/scadenze.json")
def cmd_sc_nuova(titolo, data, tipo, perentorio, id_fascicolo, db):
    """Crea una nuova scadenza."""
    gs = _scadenziario(db)
    try:
        sc = gs.nuova(
            titolo=titolo,
            tipo=TipoTermine(tipo),
            data_scadenza=data,
            id_fascicolo=id_fascicolo,
            perentorio=perentorio,
        )
        click.echo(f"Scadenza creata: {sc.id}")
        click.echo(f"  Scadenza: {sc.data_scadenza} — {sc.titolo}")
    except ValueError as e:
        click.echo(f"Errore: {e}", err=True)


@grp_scadenze.command("preset")
@click.option("--titolo", required=True)
@click.option("--preset", required=True,
              type=click.Choice(list(PRESET_TERMINI.keys())))
@click.option("--decorrenza", required=True, help="Data decorrenza YYYY-MM-DD")
@click.option("--id-fascicolo", default="")
@click.option("--db", default="./scadenziario/scadenze.json")
def cmd_sc_preset(titolo, preset, decorrenza, id_fascicolo, db):
    """Crea una scadenza da preset processuale."""
    gs = _scadenziario(db)
    try:
        sc = gs.nuova_da_preset(
            preset_key=preset,
            titolo=titolo,
            data_decorrenza=decorrenza,
            id_fascicolo=id_fascicolo,
        )
        p = PRESET_TERMINI[preset]
        click.echo(f"Scadenza calcolata: {sc.data_scadenza} ({p['label']})")
        click.echo(f"  ID: {sc.id}")
    except ValueError as e:
        click.echo(f"Errore: {e}", err=True)


@grp_scadenze.command("completa")
@click.argument("id_sc")
@click.option("--note", default="")
@click.option("--db", default="./scadenziario/scadenze.json")
def cmd_sc_completa(id_sc, note, db):
    """Segna una scadenza come completata."""
    gs = _scadenziario(db)
    try:
        gs.completa(id_sc, note=note)
        click.echo(f"Scadenza {id_sc} completata.")
    except ValueError as e:
        click.echo(f"Errore: {e}", err=True)


@grp_scadenze.command("calcola")
@click.option("--da", "data_inizio", required=True, help="Data inizio YYYY-MM-DD")
@click.option("--giorni", default=0, show_default=True, type=int)
@click.option("--mesi", default=0, show_default=True, type=int)
@click.option("--anni", default=0, show_default=True, type=int)
@click.option("--tipo", default="liberi", type=click.Choice(["liberi", "continui", "lavorativi"]))
@click.option("--no-feriale", is_flag=True, default=False,
              help="Ignora sospensione feriale agostana")
def cmd_sc_calcola(data_inizio, giorni, mesi, anni, tipo, no_feriale):
    """Calcola un termine processuale."""
    from datetime import date
    d = date.fromisoformat(data_inizio)
    scad = calcola_termine(
        d,
        giorni=giorni,
        mesi=mesi,
        anni=anni,
        tipo=tipo,
        sospensione_feriale=not no_feriale,
    )
    g_rimasti = (scad - date.today()).days
    click.echo(f"Termine calcolato: {scad.isoformat()}")
    click.echo(f"  Da oggi: {g_rimasti} giorni")


@grp_scadenze.command("imminenti")
@click.option("--giorni", default=7, show_default=True)
@click.option("--db", default="./scadenziario/scadenze.json")
def cmd_sc_imminenti(giorni, db):
    """Mostra scadenze imminenti entro N giorni."""
    gs = _scadenziario(db)
    sc = gs.imminenti(entro_giorni=giorni)
    if not sc:
        click.echo(f"Nessuna scadenza entro {giorni} giorni.")
        return
    click.echo(f"Scadenze entro {giorni} giorni:")
    for s in sc:
        g = s.giorni_alla_scadenza
        pren = " [PERENTORIO]" if s.perentorio else ""
        click.echo(f"  {s.data_scadenza} ({g}gg) — {s.titolo}{pren}")


@grp_scadenze.command("statistiche")
@click.option("--db", default="./scadenziario/scadenze.json")
def cmd_sc_statistiche(db):
    """Mostra statistiche scadenziario."""
    stats = _scadenziario(db).statistiche()
    click.echo(f"Totale:          {stats['totale']}")
    click.echo(f"Aperte:          {stats['aperte']}")
    click.echo(f"Completate:      {stats['completate']}")
    click.echo(f"Scadute:         {stats['scadute']}")
    click.echo(f"Critiche:        {stats['critiche']}")
    click.echo(f"Alta priorità:   {stats['alte']}")
    click.echo(f"Entro 7 giorni:  {stats['imminenti_7gg']}")


# ============================================================ TARIFFARIO

from .tariffario import (
    calcola_compenso,
    tutte_le_materie,
    tutti_i_gradi,
    tutte_le_fasi,
    Materia,
    Grado,
    Fase,
)


@cli.group("tariffario")
def grp_tariffario():
    """Calcolo compensi secondo DM 55/2014."""
    pass


@grp_tariffario.command("materie")
def cmd_tar_materie():
    """Elenca le materie disponibili."""
    for m in tutte_le_materie():
        click.echo(f"  {m.value}")


@grp_tariffario.command("gradi")
def cmd_tar_gradi():
    """Elenca i gradi di giudizio disponibili."""
    for g in tutti_i_gradi():
        click.echo(f"  {g.value}")


@grp_tariffario.command("fasi")
def cmd_tar_fasi():
    """Elenca le fasi processuali disponibili."""
    for f in tutte_le_fasi():
        click.echo(f"  {f.value}")


@grp_tariffario.command("calcola")
@click.option("--materia", required=True,
              type=click.Choice([m.value for m in Materia]))
@click.option("--grado", required=True,
              type=click.Choice([g.value for g in Grado]))
@click.option("--valore", required=True, type=float,
              help="Valore della controversia in euro")
@click.option("--fasi", default="",
              help="Fasi da liquidare separate da virgola (es. STUDIO,INTRODUTTIVA)")
def cmd_tar_calcola(materia, grado, valore, fasi):
    """Calcola il compenso professionale (DM 55/2014)."""
    fasi_list = [Fase(f.strip()) for f in fasi.split(",") if f.strip()] if fasi else list(tutte_le_fasi())
    try:
        r = calcola_compenso(Materia(materia), Grado(grado), valore, fasi_list)
        click.echo(f"Materia:     {r.materia.value}")
        click.echo(f"Grado:       {r.grado.value}")
        click.echo(f"Valore:      € {r.valore_controversia:,.2f}")
        click.echo(f"Scaglione:   {r.scaglione.label}")
        click.echo("")
        click.echo(f"{'FASE':<22} {'MINIMO':>10} {'BASE':>10} {'MASSIMO':>10}")
        click.echo("-" * 56)
        for fase, sc in r.dettaglio.items():
            click.echo(
                f"{fase.value:<22} € {sc.minimo:>8,.2f} € {sc.base:>8,.2f} € {sc.massimo:>8,.2f}"
            )
        click.echo("-" * 56)
        click.echo(
            f"{'TOTALE':<22} € {r.totale_minimo:>8,.2f} € {r.totale_base:>8,.2f} € {r.totale_massimo:>8,.2f}"
        )
        if r.note:
            click.echo(f"\nNote: {r.note}")
    except (ValueError, KeyError) as e:
        click.echo(f"Errore: {e}", err=True)


# ============================================================ PARCELLE (FATTURAZIONE)

from .fatturazione import GestioneFatturazione, StatoParcella, MetodoPagamento


def _fatturazione(db="./fatturazione/parcelle.json") -> GestioneFatturazione:
    return GestioneFatturazione(db_path=db)


def _fmt_parcella(p, verbose: bool = False) -> str:
    line = (
        f"{p.id[:8]:<10} {p.numero:<8} {p.data_emissione:<12} "
        f"{p.stato.value:<10} € {p.totale:>10,.2f}"
    )
    if verbose:
        line += f"\n  Cliente: {p.id_cliente}  Fascicolo: {p.id_fascicolo or '—'}"
        line += f"\n  Scadenza: {p.data_scadenza or '—'}  Metodo: {(p.metodo_pagamento or {MetodoPagamento}).value if p.metodo_pagamento else '—'}"
    return line


@cli.group("parcelle")
def grp_parcelle():
    """Gestione parcelle e fatturazione."""
    pass


@grp_parcelle.command("lista")
@click.option("--stato", default="", help="Filtra per stato (BOZZA, EMESSA, PAGATA, ...)")
@click.option("--cliente", default="", help="Filtra per ID cliente")
@click.option("--verbose", "-v", is_flag=True)
@click.option("--db", default="./fatturazione/parcelle.json")
def cmd_par_lista(stato, cliente, verbose, db):
    """Elenca le parcelle."""
    gf = _fatturazione(db)
    parcelle = gf.per_cliente(cliente) if cliente else gf.tutte()
    if stato:
        try:
            s = StatoParcella(stato)
            parcelle = [p for p in parcelle if p.stato == s]
        except ValueError:
            click.echo(f"Stato non valido: {stato}", err=True)
            return
    click.echo(f"{'ID':<10} {'N.':<8} {'DATA':<12} {'STATO':<10} {'TOTALE':>12}")
    click.echo("-" * 56)
    for p in parcelle:
        click.echo(_fmt_parcella(p, verbose))
    click.echo(f"\nTotale: {len(parcelle)} parcella/e")


@grp_parcelle.command("nuova")
@click.option("--cliente", required=True, help="ID cliente")
@click.option("--fascicolo", default="", help="ID fascicolo (opzionale)")
@click.option("--voce", multiple=True,
              help="Voce: 'descrizione:qta:prezzo' (ripetibile)")
@click.option("--iva/--no-iva", default=True)
@click.option("--cassa/--no-cassa", default=True)
@click.option("--ritenuta/--no-ritenuta", default=False)
@click.option("--bollo/--no-bollo", default=False)
@click.option("--scadenza", default="", help="Data scadenza YYYY-MM-DD")
@click.option("--note", default="")
@click.option("--db", default="./fatturazione/parcelle.json")
def cmd_par_nuova(cliente, fascicolo, voce, iva, cassa, ritenuta, bollo, scadenza, note, db):
    """Crea una nuova parcella."""
    from .fatturazione import VoceParcella
    voci = []
    for v in voce:
        parti = v.split(":")
        if len(parti) < 3:
            click.echo(f"Formato voce non valido: '{v}' (usa descrizione:qta:prezzo)", err=True)
            return
        try:
            voci.append(VoceParcella(
                descrizione=parti[0],
                quantita=float(parti[1]),
                prezzo_unitario=float(parti[2]),
            ))
        except ValueError as e:
            click.echo(f"Errore nella voce '{v}': {e}", err=True)
            return
    if not voci:
        click.echo("Specificare almeno una voce con --voce 'descrizione:qta:prezzo'", err=True)
        return
    gf = _fatturazione(db)
    try:
        p = gf.crea(
            id_cliente=cliente,
            voci=voci,
            creato_da="cli",
            id_fascicolo=fascicolo or None,
            data_scadenza=scadenza or None,
            applica_iva=iva,
            applica_cassa=cassa,
            applica_ritenuta=ritenuta,
            applica_bollo=bollo,
            note=note,
        )
        click.echo(f"Parcella creata: {p.id}  (n. {p.numero})")
        click.echo(f"  Imponibile: € {p.imponibile:,.2f}")
        if p.applica_iva:
            click.echo(f"  IVA 22%:    € {p.iva:,.2f}")
        if p.applica_cassa:
            click.echo(f"  Cassa Forense 4%: € {p.cassa_forense:,.2f}")
        click.echo(f"  Totale:     € {p.totale:,.2f}")
    except Exception as e:
        click.echo(f"Errore: {e}", err=True)


@grp_parcelle.command("stato")
@click.argument("id_parcella")
@click.option("--nuovo-stato", required=True,
              type=click.Choice([s.value for s in StatoParcella]))
@click.option("--data-pagamento", default="", help="Data pagamento YYYY-MM-DD")
@click.option("--metodo", default="",
              type=click.Choice([m.value for m in MetodoPagamento] + [""]))
@click.option("--db", default="./fatturazione/parcelle.json")
def cmd_par_stato(id_parcella, nuovo_stato, data_pagamento, metodo, db):
    """Cambia lo stato di una parcella."""
    gf = _fatturazione(db)
    try:
        gf.cambia_stato(
            id_parcella,
            StatoParcella(nuovo_stato),
            data_pagamento=data_pagamento or None,
            metodo_pagamento=metodo or None,
        )
        click.echo(f"Parcella {id_parcella[:8]} → {nuovo_stato}")
    except ValueError as e:
        click.echo(f"Errore: {e}", err=True)


@grp_parcelle.command("statistiche")
@click.option("--anno", default=None, type=int)
@click.option("--db", default="./fatturazione/parcelle.json")
def cmd_par_statistiche(anno, db):
    """Mostra statistiche di fatturazione."""
    gf = _fatturazione(db)
    stats = gf.statistiche(anno=anno)
    titolo = f"Anno {anno}" if anno else "Tutti gli anni"
    click.echo(f"── Fatturazione — {titolo} ──")
    click.echo(f"Totale parcelle: {stats.get('totale', 0)}")
    click.echo(f"Bozze:           {stats.get('bozze', 0)}")
    click.echo(f"Emesse:          {stats.get('emesse', 0)}")
    click.echo(f"Pagate:          {stats.get('pagate', 0)}")
    click.echo(f"Scadute:         {stats.get('scadute', 0)}")
    click.echo(f"Fatturato tot.:  € {stats.get('fatturato_totale', 0):,.2f}")
    click.echo(f"Incassato:       € {stats.get('incassato', 0):,.2f}")
    click.echo(f"Da incassare:    € {stats.get('da_incassare', 0):,.2f}")


# ============================================================ TEMPLATE ATTI

from .template_atti import GestioneTemplateAtti, CATEGORIE


def _template_atti(db="./template_atti/templates.json") -> GestioneTemplateAtti:
    return GestioneTemplateAtti(db_path=db)


@cli.group("template-atti")
def grp_template_atti():
    """Gestione template per atti processuali."""
    pass


@grp_template_atti.command("lista")
@click.option("--categoria", default="", help="Filtra per categoria")
@click.option("--db", default="./template_atti/templates.json")
def cmd_ta_lista(categoria, db):
    """Elenca i template disponibili."""
    gt = _template_atti(db)
    templates = gt.tutti()
    if categoria:
        templates = [t for t in templates if t.categoria.lower() == categoria.lower()]
    click.echo(f"{'ID':<10} {'CATEGORIA':<20} {'BUILTIN':<8} TITOLO")
    click.echo("-" * 72)
    for t in templates:
        builtin = "✓" if t.builtin else " "
        click.echo(f"{t.id[:8]:<10} {t.categoria:<20} {builtin:<8} {t.titolo}")
    click.echo(f"\nTotale: {len(templates)} template")
    if not categoria:
        click.echo(f"Categorie: {', '.join(CATEGORIE)}")


@grp_template_atti.command("dettaglio")
@click.argument("id_template")
@click.option("--db", default="./template_atti/templates.json")
def cmd_ta_dettaglio(id_template, db):
    """Mostra il testo di un template."""
    gt = _template_atti(db)
    t = gt.get(id_template)
    if not t:
        click.echo(f"Template '{id_template}' non trovato.", err=True)
        return
    click.echo(f"Titolo:    {t.titolo}")
    click.echo(f"Categoria: {t.categoria}")
    click.echo(f"Builtin:   {'sì' if t.builtin else 'no'}")
    if t.note:
        click.echo(f"Note:      {t.note}")
    click.echo("\n── Corpo ──")
    click.echo(t.corpo)


@grp_template_atti.command("nuovo")
@click.option("--titolo", required=True)
@click.option("--categoria", required=True,
              type=click.Choice(CATEGORIE))
@click.option("--corpo", required=True, help="Testo del template (Jinja2). Usa @- per leggere da stdin.")
@click.option("--note", default="")
@click.option("--db", default="./template_atti/templates.json")
def cmd_ta_nuovo(titolo, categoria, corpo, note, db):
    """Crea un nuovo template atto."""
    if corpo == "@-":
        corpo = click.get_text_stream("stdin").read()
    gt = _template_atti(db)
    t = gt.crea(titolo=titolo, categoria=categoria, corpo=corpo, note=note)
    click.echo(f"Template creato: {t.id}")
    click.echo(f"  Titolo: {t.titolo}")


@grp_template_atti.command("elimina")
@click.argument("id_template")
@click.option("--db", default="./template_atti/templates.json")
def cmd_ta_elimina(id_template, db):
    """Elimina un template (solo personalizzati)."""
    gt = _template_atti(db)
    try:
        gt.elimina(id_template)
        click.echo(f"Template {id_template} eliminato.")
    except ValueError as e:
        click.echo(f"Errore: {e}", err=True)


@grp_template_atti.command("genera")
@click.argument("id_template")
@click.option("--var", multiple=True,
              help="Variabile: 'nome=valore' (ripetibile)")
@click.option("--output", "-o", default="", help="File di output (default: stdout)")
@click.option("--db", default="./template_atti/templates.json")
def cmd_ta_genera(id_template, var, output, db):
    """Renderizza un template con le variabili fornite."""
    gt = _template_atti(db)
    variabili = {}
    for v in var:
        if "=" not in v:
            click.echo(f"Formato non valido: '{v}' (usa nome=valore)", err=True)
            return
        k, _, val = v.partition("=")
        variabili[k.strip()] = val.strip()
    try:
        testo = gt.renderizza(id_template, variabili)
        if output:
            Path(output).write_text(testo, encoding="utf-8")
            click.echo(f"Template scritto in: {output}")
        else:
            click.echo(testo)
    except (ValueError, Exception) as e:
        click.echo(f"Errore: {e}", err=True)


# ============================================================ PRIVACY / GDPR

from .privacy import GestioneTrattamenti, TrattamentoDati


def _privacy(db="./privacy/registro.json") -> GestioneTrattamenti:
    return GestioneTrattamenti(db_path=db)


@cli.group("privacy")
def grp_privacy():
    """Registro dei trattamenti dati (GDPR art. 30)."""
    pass


@grp_privacy.command("lista")
@click.option("--tutti", is_flag=True, default=False,
              help="Mostra anche trattamenti disattivati")
@click.option("--db", default="./privacy/registro.json")
def cmd_priv_lista(tutti, db):
    """Elenca i trattamenti nel registro."""
    gt = _privacy(db)
    trattamenti = gt.tutti(solo_attivi=not tutti)
    click.echo(f"{'ID':<10} {'ATTIVO':<8} NOME")
    click.echo("-" * 60)
    for t in trattamenti:
        attivo = "✓" if t.attivo else "✗"
        click.echo(f"{t.id[:8]:<10} {attivo:<8} {t.nome}")
    click.echo(f"\nTotale: {len(trattamenti)}")


@grp_privacy.command("dettaglio")
@click.argument("id_trattamento")
@click.option("--db", default="./privacy/registro.json")
def cmd_priv_dettaglio(id_trattamento, db):
    """Mostra i dettagli di un trattamento."""
    gt = _privacy(db)
    t = gt.get(id_trattamento)
    if not t:
        click.echo(f"Trattamento '{id_trattamento}' non trovato.", err=True)
        return
    click.echo(f"Nome:                  {t.nome}")
    click.echo(f"Finalità:              {t.finalita}")
    click.echo(f"Categoria dati:        {t.categoria_dati}")
    click.echo(f"Base giuridica:        {t.base_giuridica}")
    click.echo(f"Soggetti interessati:  {t.soggetti_interessati}")
    click.echo(f"Destinatari:           {t.destinatari}")
    click.echo(f"Trasf. extra-UE:       {'sì' if t.trasferimento_extra_ue else 'no'}")
    if t.trasferimento_extra_ue:
        click.echo(f"Paese destinazione:    {t.paese_destinazione or '—'}")
    click.echo(f"Termine conservazione: {t.termine_conservazione}")
    click.echo(f"Misure sicurezza:      {t.misure_sicurezza}")
    click.echo(f"Responsabile:          {t.responsabile or '—'}")
    click.echo(f"Attivo:                {'sì' if t.attivo else 'no'}")
    if t.note:
        click.echo(f"Note:                  {t.note}")


@grp_privacy.command("nuovo")
@click.option("--nome", required=True)
@click.option("--finalita", required=True)
@click.option("--categoria-dati", required=True)
@click.option("--base-giuridica", required=True)
@click.option("--soggetti", required=True, help="Soggetti interessati")
@click.option("--destinatari", required=True)
@click.option("--conservazione", required=True, help="Termine di conservazione")
@click.option("--misure-sicurezza", required=True)
@click.option("--responsabile", default="")
@click.option("--extra-ue", is_flag=True, default=False,
              help="Trasferimento extra-UE")
@click.option("--paese", default="")
@click.option("--note", default="")
@click.option("--db", default="./privacy/registro.json")
def cmd_priv_nuovo(nome, finalita, categoria_dati, base_giuridica, soggetti,
                   destinatari, conservazione, misure_sicurezza, responsabile,
                   extra_ue, paese, note, db):
    """Aggiunge un trattamento al registro GDPR."""
    gt = _privacy(db)
    t = gt.nuovo(
        nome=nome,
        finalita=finalita,
        categoria_dati=categoria_dati,
        base_giuridica=base_giuridica,
        soggetti_interessati=soggetti,
        destinatari=destinatari,
        termine_conservazione=conservazione,
        misure_sicurezza=misure_sicurezza,
        responsabile=responsabile or None,
        trasferimento_extra_ue=extra_ue,
        paese_destinazione=paese or None,
        note=note or None,
    )
    click.echo(f"Trattamento creato: {t.id}")
    click.echo(f"  Nome: {t.nome}")


@grp_privacy.command("elimina")
@click.argument("id_trattamento")
@click.option("--db", default="./privacy/registro.json")
def cmd_priv_elimina(id_trattamento, db):
    """Rimuove un trattamento dal registro."""
    gt = _privacy(db)
    try:
        gt.elimina(id_trattamento)
        click.echo(f"Trattamento {id_trattamento} eliminato.")
    except ValueError as e:
        click.echo(f"Errore: {e}", err=True)


# ============================================================ OCR

from .ocr import estrai_testo_da_percorso


class _LegacyOcrGroup(click.Group):
    def parse_args(self, ctx, args):
        if args and args[0] not in self.commands and args[0] not in {"--help", "-h"}:
            args.insert(0, "extract")
        return super().parse_args(ctx, args)


@cli.group("ocr", cls=_LegacyOcrGroup)
def grp_ocr():
    """OCR documentale e OCR legal-grade."""
    pass


@grp_ocr.command("extract")
@click.argument("file", type=click.Path(exists=True))
@click.option("--output", "-o", default="", help="File di output (default: stdout)")
def cmd_ocr_extract(file, output):
    """Estrae testo semplice da un PDF o immagine."""
    try:
        testo = estrai_testo_da_percorso(file)
        if output:
            Path(output).write_text(testo, encoding="utf-8")
            click.echo(f"Testo estratto in: {output}")
        else:
            click.echo(testo)
    except Exception as e:
        click.echo(f"Errore OCR: {e}", err=True)


@grp_ocr.command("run")
@click.argument("target", type=click.Path(exists=True))
@click.option("--tenant", required=True, help="Identificativo studio/tenant.")
@click.option("--storage-root", default="./data/legal_document_evidence/legal_ocr_cli", show_default=True, help="Archivio evidenze OCR.")
@click.option("--primary", default="tesseract", show_default=True, help="Engine OCR primario.")
@click.option("--fallback", default="native-text-fallback", show_default=True, help="Engine OCR fallback.")
@click.option("--allow-cloud", is_flag=True, default=False, help="Consente engine cloud configurati per il tenant.")
@click.option("--document-id", default="", help="ID documento IUSENTRA da collegare all'evidenza.")
@click.option("--fascicolo-id", default="", help="ID fascicolo da collegare all'evidenza.")
@click.option("--report", is_flag=True, default=False, help="Stampa KPI sintetici e path evidenze.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Stampa il report in JSON.")
def cmd_ocr_run(target, tenant, storage_root, primary, fallback, allow_cloud, document_id, fascicolo_id, report, as_json):
    """Esegue OCR legal-grade con QC, fallback, HIL e audit append-only."""
    from legal_ocr import LegalOcrConfig, LegalOcrEvidenceStore, LegalOcrPipeline

    pipeline = LegalOcrPipeline(
        LegalOcrConfig(
            tenant_id=tenant,
            primary_engine=primary,
            fallback_engine=fallback,
            local_first_only=not allow_cloud,
        ),
        LegalOcrEvidenceStore(storage_root, tenant),
    )
    evidences = pipeline.run_path(target, tenant_id=tenant, fascicolo_id=fascicolo_id, document_id=document_id)
    summary = {
        "tenant_id": tenant,
        "target": str(Path(target).resolve()),
        "count": len(evidences),
        "evidences": [
            {
                "run_id": item.get("run_id"),
                "document_id": item.get("document_id"),
                "selected_engine": item.get("selected_engine"),
                "avg_confidence": (item.get("metrics") or {}).get("avg_confidence"),
                "pct_tokens_<0.75": (item.get("metrics") or {}).get("pct_tokens_<0.75"),
                "hil_required": (item.get("qc") or {}).get("hil_required"),
                "evidence_path": item.get("evidence_path"),
                "ocr_text_path": item.get("ocr_text_path"),
                "lex_export_path": (item.get("lex_export") or {}).get("path"),
                "notifications": len(item.get("notification_proposals") or []),
            }
            for item in evidences
        ],
    }
    if as_json:
        click.echo(json.dumps(summary, ensure_ascii=False, indent=2))
    else:
        click.echo(f"OCR legal-grade completato: {summary['count']} evidenze")
        for item in summary["evidences"]:
            click.echo(
                f"- {item['run_id']} engine={item['selected_engine']} conf={item['avg_confidence']} "
                f"HIL={item['hil_required']} evidence={item['evidence_path']}"
            )
            if report and item.get("notifications"):
                click.echo(f"  notifiche proposte: {item['notifications']}")


# ============================================================ REPORT PDF

from .reports import fascicolo_pdf, scadenze_pdf


@cli.group("report")
def grp_report():
    """Generazione report PDF."""
    pass


@grp_report.command("fascicolo")
@click.argument("id_fasc")
@click.option("--output", "-o", required=True, help="File PDF di output")
@click.option("--studio", default="Studio Legale", help="Nome dello studio")
@click.option("--db-fasc", default="./fascicoli/fascicoli.json")
def cmd_rep_fascicolo(id_fasc, output, studio, db_fasc):
    """Genera il report PDF di un fascicolo."""
    gf_mod = _fascicoli(db_fasc)
    f = gf_mod.get(id_fasc)
    if not f:
        click.echo(f"Fascicolo '{id_fasc}' non trovato.", err=True)
        return
    try:
        percorso = fascicolo_pdf(f.to_dict(), output, studio_nome=studio)
        click.echo(f"Report generato: {percorso}")
    except Exception as e:
        click.echo(f"Errore generazione PDF: {e}", err=True)


@grp_report.command("scadenze")
@click.option("--output", "-o", required=True, help="File PDF di output")
@click.option("--studio", default="Studio Legale", help="Nome dello studio")
@click.option("--titolo", default="Scadenziario")
@click.option("--giorni", default=0, type=int,
              help="Solo scadenze entro N giorni (0 = tutte)")
@click.option("--db", default="./scadenziario/scadenze.json")
def cmd_rep_scadenze(output, studio, titolo, giorni, db):
    """Genera il report PDF dello scadenziario."""
    gs = _scadenziario(db)
    if giorni:
        scadenze = gs.imminenti(entro_giorni=giorni)
    else:
        scadenze = gs.tutte()
    try:
        percorso = scadenze_pdf(
            [s.to_dict() if hasattr(s, "to_dict") else s for s in scadenze],
            output,
            titolo=titolo,
            studio_nome=studio,
        )
        click.echo(f"Report generato: {percorso}")
    except Exception as e:
        click.echo(f"Errore generazione PDF: {e}", err=True)


# ============================================================ PORTALE CLIENTI

from .portale import GestionePortale


def _portale(db="./portale/portali.json") -> GestionePortale:
    return GestionePortale(db_path=db)


@cli.group("portale")
def grp_portale():
    """Gestione portale clienti."""
    pass


@grp_portale.command("stato")
@click.argument("id_cliente")
@click.option("--db", default="./portale/portali.json")
def cmd_portale_stato(id_cliente, db):
    """Mostra lo stato del portale per un cliente."""
    gp = _portale(db)
    p = gp.get_by_cliente(id_cliente)
    if not p:
        click.echo(f"Nessun portale attivato per il cliente '{id_cliente}'.")
        return
    click.echo(f"ID portale:     {p.id}")
    click.echo(f"Attivo:         {'sì' if p.is_attivo else 'no'}")
    click.echo(f"Creato il:      {p.creato_il[:10]}")
    click.echo(f"Scade il:       {p.scade_il or 'mai'}")
    click.echo(f"Accessi:        {p.n_accessi}")
    click.echo(f"Ultimo accesso: {(p.ultimo_accesso or '—')[:19]}")
    click.echo(f"Privacy firmata: {'sì' if p.privacy_firmata else 'no'}")


@grp_portale.command("attiva")
@click.argument("id_cliente")
@click.option("--scadenza", default="", help="Data scadenza YYYY-MM-DD (opzionale)")
@click.option("--db", default="./portale/portali.json")
def cmd_portale_attiva(id_cliente, scadenza, db):
    """Attiva il portale per un cliente e stampa il token di accesso."""
    gp = _portale(db)
    from .portale import PermessiPortale
    token, p = gp.crea(
        id_cliente=id_cliente,
        creato_da="cli",
        permessi=PermessiPortale(),
        scade_il=scadenza or None,
    )
    click.echo(f"Portale attivato: {p.id}")
    click.echo(f"  Token di accesso: {token}")
    click.echo(f"  Scade il: {p.scade_il or 'mai'}")
    click.echo("\nATTENZIONE: conservare il token in modo sicuro — non verrà mostrato di nuovo.")


@grp_portale.command("revoca")
@click.argument("id_cliente")
@click.option("--db", default="./portale/portali.json")
def cmd_portale_revoca(id_cliente, db):
    """Revoca l'accesso al portale per un cliente."""
    gp = _portale(db)
    p = gp.get_by_cliente(id_cliente)
    if not p:
        click.echo(f"Nessun portale trovato per '{id_cliente}'.", err=True)
        return
    try:
        gp.revoca(p.id)
        click.echo(f"Portale {p.id} revocato.")
    except ValueError as e:
        click.echo(f"Errore: {e}", err=True)


# ============================================================ NOTIFICHE WHATSAPP

from .notifiche_wa import (
    ConfigWA,
    wa_link,
    invia_messaggio,
    msg_libero,
    msg_promemoria_appuntamento,
    msg_nuova_parcella,
    msg_scadenza_imminente,
    msg_link_portale,
)


@cli.group("notifiche-wa")
def grp_notifiche_wa():
    """Invio messaggi WhatsApp ai clienti."""
    pass


@grp_notifiche_wa.command("link")
@click.argument("numero")
@click.argument("messaggio")
def cmd_wa_link(numero, messaggio):
    """Genera un link wa.me (apre WhatsApp senza configurazione API)."""
    url = wa_link(numero, messaggio)
    click.echo(url)


@grp_notifiche_wa.command("invia")
@click.argument("numero")
@click.argument("messaggio")
@click.option("--studio", default="Studio Legale", help="Nome studio (per template)")
def cmd_wa_invia(numero, messaggio, studio):
    """Invia un messaggio WhatsApp tramite Twilio o CallMeBot (da env)."""
    cfg = ConfigWA.da_env()
    if not cfg.ha_twilio and not cfg.ha_callmebot:
        click.echo(
            "Nessun provider configurato. Imposta le variabili d'ambiente:\n"
            "  Twilio:     PCT_TWILIO_SID, PCT_TWILIO_TOKEN, PCT_TWILIO_NUMERO\n"
            "  CallMeBot:  PCT_CALLMEBOT_KEY",
            err=True,
        )
        return
    try:
        result = invia_messaggio(numero, messaggio, cfg)
        click.echo(f"Messaggio inviato. Risposta: {result.get('status', result)}")
    except Exception as e:
        click.echo(f"Errore invio: {e}", err=True)


@grp_notifiche_wa.command("template")
@click.option("--tipo", required=True,
              type=click.Choice(["appuntamento", "parcella", "scadenza", "portale", "libero"]))
@click.option("--nome-cliente", required=True)
@click.option("--studio", default="Studio Legale")
@click.option("--titolo", default="")
@click.option("--data-ora", default="")
@click.option("--luogo", default="")
@click.option("--numero-parcella", default="")
@click.option("--totale", default=0.0, type=float)
@click.option("--scadenza", default="")
@click.option("--fascicolo", default="")
@click.option("--perentorio", is_flag=True, default=False)
@click.option("--link", default="")
@click.option("--testo-libero", default="")
def cmd_wa_template(tipo, nome_cliente, studio, titolo, data_ora, luogo,
                    numero_parcella, totale, scadenza, fascicolo, perentorio, link, testo_libero):
    """Genera il testo di un messaggio WhatsApp da template."""
    if tipo == "appuntamento":
        msg = msg_promemoria_appuntamento(nome_cliente, titolo, data_ora, luogo, studio)
    elif tipo == "parcella":
        msg = msg_nuova_parcella(nome_cliente, numero_parcella, totale, scadenza, studio)
    elif tipo == "scadenza":
        msg = msg_scadenza_imminente(nome_cliente, titolo, scadenza, fascicolo, perentorio)
    elif tipo == "portale":
        msg = msg_link_portale(nome_cliente, link, studio)
    else:
        msg = msg_libero(nome_cliente, testo_libero, studio)
    click.echo(msg)


# ============================================================ PAGAMENTI

from .pagamenti import GestionePagamenti, StatoPagamento

STATI_PAGAMENTO_VALIDI = [
    StatoPagamento.ATTESO,
    StatoPagamento.PAGATO,
    StatoPagamento.FALLITO,
    StatoPagamento.SCADUTO,
    StatoPagamento.ANNULLATO,
]


def _pagamenti(db_dir="./pagamenti") -> GestionePagamenti:
    return GestionePagamenti(db_dir=db_dir)


@cli.group("pagamenti")
def grp_pagamenti():
    """Gestione link di pagamento digitale."""
    pass


@grp_pagamenti.command("config")
@click.option("--dir", "db_dir", default="./pagamenti")
def cmd_pag_config(db_dir):
    """Mostra i provider di pagamento configurati."""
    gp = _pagamenti(db_dir)
    cfg = gp.config
    attivi = cfg.provider_attivi()
    click.echo(f"Provider attivi: {', '.join(attivi) if attivi else '(nessuno)'}")
    click.echo(f"  Stripe:   {'abilitato' if cfg.stripe.abilitato else 'disabilitato'}")
    click.echo(f"  PayPal:   {'abilitato' if cfg.paypal.abilitato else 'disabilitato'}")
    click.echo(f"  Satispay: {'abilitato' if cfg.satispay.abilitato else 'disabilitato'}")
    click.echo(f"  SumUp:    {'abilitato' if cfg.sumup.abilitato else 'disabilitato'}")
    click.echo(f"  Bonifico: {'abilitato' if cfg.bonifico.abilitato else 'disabilitato'}")
    if cfg.bonifico.abilitato:
        click.echo(f"    IBAN: {cfg.bonifico.iban}")


@grp_pagamenti.command("lista")
@click.option("--stato", default="",
              type=click.Choice(STATI_PAGAMENTO_VALIDI + [""]))
@click.option("--dir", "db_dir", default="./pagamenti")
def cmd_pag_lista(stato, db_dir):
    """Elenca i link di pagamento."""
    gp = _pagamenti(db_dir)
    links = gp.tutti_link()
    if stato:
        links = [lp for lp in links if lp.stato.value == stato]
    click.echo(f"{'ID':<10} {'PARCELLA':<10} {'IMPORTO':>10} {'STATO':<10} {'SCADE':<12} PROVIDER")
    click.echo("-" * 72)
    for lp in links:
        click.echo(
            f"{lp.id[:8]:<10} {lp.id_parcella[:8]:<10} "
            f"€ {lp.importo:>8,.2f} {lp.stato.value:<10} "
            f"{(lp.scade_il or '—')[:10]:<12} {lp.provider_usato or '—'}"
        )
    click.echo(f"\nTotale: {len(links)}")


@grp_pagamenti.command("nuovo-link")
@click.option("--parcella", required=True, help="ID parcella")
@click.option("--cliente", required=True, help="ID cliente")
@click.option("--importo", required=True, type=float, help="Importo in euro")
@click.option("--descrizione", default="Pagamento parcella")
@click.option("--giorni-validita", default=30, show_default=True)
@click.option("--dir", "db_dir", default="./pagamenti")
def cmd_pag_nuovo_link(parcella, cliente, importo, descrizione, giorni_validita, db_dir):
    """Crea un link di pagamento per una parcella."""
    gp = _pagamenti(db_dir)
    try:
        lp = gp.crea_link(
            id_parcella=parcella,
            id_cliente=cliente,
            importo=importo,
            descrizione=descrizione,
            giorni_validita=giorni_validita,
        )
        click.echo(f"Link creato: {lp.id}")
        click.echo(f"  Token:    {lp.token}")
        click.echo(f"  Importo:  € {lp.importo:,.2f}")
        click.echo(f"  Scade il: {lp.scade_il or '—'}")
    except Exception as e:
        click.echo(f"Errore: {e}", err=True)


# ============================================================ IMPOSTAZIONI STUDIO

from .config_studio import (
    GestioneConfigStudio,
    ConfigPEC as _ConfigPEC,
    ConfigSMTP as _ConfigSMTP,
    test_pec_smtp,
    test_pec_imap,
    test_smtp_email,
)


def _cfg_studio(config_path="./config/studio.json") -> GestioneConfigStudio:
    return GestioneConfigStudio(config_path=config_path)


@cli.group("impostazioni")
def grp_impostazioni():
    """Configurazione dello studio (PEC, SMTP, firma, WhatsApp, scheduler)."""
    pass


@grp_impostazioni.command("mostra")
@click.option("--config", default="./config/studio.json")
def cmd_imp_mostra(config):
    """Mostra la configurazione corrente dello studio."""
    gs = _cfg_studio(config)
    c = gs.config
    s = c.studio
    click.echo(f"── Dati Studio ──────────────────────────────")
    click.echo(f"  Nome:       {s.nome or '—'}")
    click.echo(f"  Avvocato:   {s.avvocato or '—'}")
    click.echo(f"  P.IVA:      {s.piva or '—'}")
    click.echo(f"  C.F.:       {s.cf or '—'}")
    click.echo(f"  Indirizzo:  {s.indirizzo or '—'}")
    click.echo(f"  IBAN:       {s.iban or '—'}")
    click.echo(f"\n── PEC ──────────────────────────────────────")
    click.echo(f"  Indirizzo:  {c.pec.indirizzo or '—'}")
    click.echo(f"  SMTP:       {c.pec.smtp_host}:{c.pec.smtp_port}  SSL={'sì' if c.pec.use_ssl else 'no'}")
    click.echo(f"  IMAP:       {c.pec.imap_host}:{c.pec.imap_port}")
    click.echo(f"  Password:   {'configurata' if c.pec.password else 'non impostata'}")
    click.echo(f"\n── Firma Digitale ───────────────────────────")
    click.echo(f"  P12 path:   {c.firma.p12_path or '—'}")
    click.echo(f"  CF avvocato:{c.firma.cf_avvocato or '—'}")
    click.echo(f"  Password:   {'configurata' if c.firma.password else 'non impostata'}")
    click.echo(f"\n── SMTP Email ───────────────────────────────")
    click.echo(f"  Host:       {c.smtp.host or '—'}:{c.smtp.port}")
    click.echo(f"  Username:   {c.smtp.username or '—'}")
    click.echo(f"  From:       {c.smtp.from_address or '—'}")
    click.echo(f"  TLS:        {'sì' if c.smtp.use_tls else 'no'}")
    click.echo(f"\n── WhatsApp ─────────────────────────────────")
    click.echo(f"  Twilio SID: {c.whatsapp.twilio_sid or '—'}")
    click.echo(f"  Twilio num: {c.whatsapp.twilio_numero or '—'}")
    click.echo(f"  CallMeBot:  {'configurato' if c.whatsapp.callmebot_key else '—'}")
    click.echo(f"\n── Scheduler ────────────────────────────────")
    click.echo(f"  Backup:     {c.scheduler.backup_ora}  ({'abilitato' if c.scheduler.backup_abilitato else 'disabilitato'})")
    click.echo(f"  WA remind:  {c.scheduler.wa_reminder_ora}  ({'abilitato' if c.scheduler.wa_reminder_abilitato else 'disabilitato'})")


@grp_impostazioni.command("pec")
@click.option("--indirizzo", required=True, help="Indirizzo PEC (es. studio@pec.aruba.it)")
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True,
              help="Password casella PEC")
@click.option("--smtp-host", default="smtp.pec.aruba.it", show_default=True)
@click.option("--smtp-port", default=465, show_default=True, type=int)
@click.option("--imap-host", default="imaps.pec.aruba.it", show_default=True)
@click.option("--imap-port", default=993, show_default=True, type=int)
@click.option("--no-ssl", is_flag=True, default=False)
@click.option("--config", default="./config/studio.json")
def cmd_imp_pec(indirizzo, password, smtp_host, smtp_port, imap_host, imap_port, no_ssl, config):
    """Configura l'account PEC dello studio."""
    from .config_studio import ConfigPEC
    gs = _cfg_studio(config)
    cfg = gs.config
    cfg.pec = ConfigPEC(
        indirizzo=indirizzo,
        password=password,
        smtp_host=smtp_host,
        smtp_port=smtp_port,
        imap_host=imap_host,
        imap_port=imap_port,
        use_ssl=not no_ssl,
    )
    gs.aggiorna(cfg)
    click.echo(f"PEC configurata: {indirizzo}  (salvata in {config})")


@grp_impostazioni.command("test-pec")
@click.option("--config", default="./config/studio.json")
def cmd_imp_test_pec(config):
    """Testa la connessione PEC (SMTP + IMAP)."""
    gs = _cfg_studio(config)
    c = gs.config.pec
    if not c.indirizzo:
        click.echo("PEC non configurata. Usa: pct impostazioni pec --indirizzo ...", err=True)
        return
    click.echo(f"Test SMTP ({c.smtp_host}:{c.smtp_port})...", nl=False)
    r = test_pec_smtp(c)
    click.echo(f"  {'✓ OK' if r['ok'] else '✗ ERRORE'}  {r['messaggio']}")
    click.echo(f"Test IMAP ({c.imap_host}:{c.imap_port})...", nl=False)
    r = test_pec_imap(c)
    click.echo(f"  {'✓ OK' if r['ok'] else '✗ ERRORE'}  {r['messaggio']}")


@grp_impostazioni.command("smtp")
@click.option("--host", required=True)
@click.option("--port", default=587, type=int, show_default=True)
@click.option("--username", required=True)
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True)
@click.option("--from-address", default="")
@click.option("--from-name", default="")
@click.option("--no-tls", is_flag=True, default=False)
@click.option("--config", default="./config/studio.json")
def cmd_imp_smtp(host, port, username, password, from_address, from_name, no_tls, config):
    """Configura il server SMTP per le email dello studio."""
    from .config_studio import ConfigSMTP
    gs = _cfg_studio(config)
    cfg = gs.config
    cfg.smtp = ConfigSMTP(
        host=host, port=port,
        username=username, password=password,
        from_address=from_address or username,
        from_name=from_name,
        use_tls=not no_tls,
    )
    gs.aggiorna(cfg)
    click.echo(f"SMTP configurato: {username}@{host}:{port}")


@grp_impostazioni.command("test-smtp")
@click.option("--config", default="./config/studio.json")
def cmd_imp_test_smtp(config):
    """Testa la connessione SMTP email."""
    gs = _cfg_studio(config)
    c = gs.config.smtp
    if not c.host:
        click.echo("SMTP non configurato.", err=True)
        return
    click.echo(f"Test SMTP ({c.host}:{c.port})...", nl=False)
    r = test_smtp_email(c)
    click.echo(f"  {'✓ OK' if r['ok'] else '✗ ERRORE'}  {r['messaggio']}")


@grp_impostazioni.command("studio")
@click.option("--nome", default="")
@click.option("--avvocato", default="")
@click.option("--piva", default="")
@click.option("--cf", default="")
@click.option("--indirizzo", default="")
@click.option("--iban", default="")
@click.option("--config", default="./config/studio.json")
def cmd_imp_studio(nome, avvocato, piva, cf, indirizzo, iban, config):
    """Imposta i dati anagrafici dello studio."""
    gs = _cfg_studio(config)
    cfg = gs.config
    if nome:        cfg.studio.nome = nome
    if avvocato:    cfg.studio.avvocato = avvocato
    if piva:        cfg.studio.piva = piva
    if cf:          cfg.studio.cf = cf
    if indirizzo:   cfg.studio.indirizzo = indirizzo
    if iban:        cfg.studio.iban = iban
    gs.aggiorna(cfg)
    click.echo(f"Dati studio aggiornati e salvati in {config}")


@cli.command("crea-superadmin")
@click.option("--username", default="admin", show_default=True, help="Username del superadmin")
@click.option("--password", prompt=True, hide_input=True, confirmation_prompt=True,
              help="Password del superadmin")
@click.option("--email", default="admin@studio.local", show_default=True, help="Email del superadmin")
@click.option("--nome", default="Super Amministratore", show_default=True, help="Nome completo")
@click.option("--auth-db", default="./auth/utenti.json", show_default=True,
              envvar="PCT_AUTH_DB", help="Percorso file utenti JSON")
@click.option("--forza", is_flag=True, default=False,
              help="Aggiorna a SUPERADMIN anche se l'utente esiste già")
def cmd_crea_superadmin(username, password, email, nome, auth_db, forza):
    """Crea o promuove un utente SUPERADMIN per l'accesso al pannello /admin/.

    Da eseguire una volta sola al primo avvio su una nuova installazione
    multi-tenant, oppure per ripristinare l'accesso amministrativo.

    Esempio:

      pct crea-superadmin --username admin --auth-db ./data/auth/utenti.json
    """
    gu = GestioneUtenti(
        db_path=auth_db,
        secret_key=os.getenv("PCT_SECRET_KEY", "dev-secret-pct-2024"),
        crea_admin_se_vuoto=False,
    )

    # Cerca utente esistente con lo stesso username
    esistente = next((u for u in gu.lista() if u.username == username), None)

    if esistente:
        if esistente.ruolo == RuoloUtente.SUPERADMIN and not forza:
            click.echo(f"L'utente '{username}' è già SUPERADMIN. Usa --forza per aggiornare.", err=True)
            sys.exit(0)
        # Promuovi a SUPERADMIN e aggiorna password/dati
        gu.aggiorna(
            esistente.id,
            ruolo=RuoloUtente.SUPERADMIN,
            nome_completo=nome,
            email=email,
        )
        # Aggiorna password separatamente
        from werkzeug.security import generate_password_hash
        gu._utenti[esistente.id].password_hash = generate_password_hash(password)
        gu._salva_utenti()
        click.echo(f"Utente '{username}' promosso a SUPERADMIN.")
    else:
        # Crea nuovo utente SUPERADMIN
        try:
            gu.crea(
                username=username,
                password=password,
                ruolo=RuoloUtente.SUPERADMIN,
                nome_completo=nome,
                email=email,
            )
            click.echo(f"Superadmin '{username}' creato con successo.")
        except Exception as exc:
            click.echo(f"Errore nella creazione: {exc}", err=True)
            sys.exit(1)

    click.echo(f"  Auth DB : {auth_db}")
    click.echo(f"  Username: {username}")
    click.echo(f"  Email   : {email}")
    click.echo(f"  Ruolo   : SUPERADMIN")
    click.echo("Accedi su /login e poi visita /admin/ per gestire gli studi.")


def _copy_database_config(database) -> DatabaseConfig:
    if isinstance(database, DatabaseConfig):
        return DatabaseConfig.from_dict(database.to_dict())
    if hasattr(database, "to_dict"):
        try:
            return DatabaseConfig.from_dict(database.to_dict())
        except Exception:
            return DatabaseConfig.from_dict({})
    return DatabaseConfig.from_dict(database)


def _load_json_report(path: str) -> dict:
    target = Path(str(path or "").strip())
    if not target.exists():
        return {}
    try:
        payload = json.loads(target.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return payload if isinstance(payload, dict) else {}


def _latest_migration_report_path(tm: GestioneTenant, tenant_slug: str, explicit_path: str = "") -> str:
    manual = str(explicit_path or "").strip()
    if manual:
        return manual
    studio = tm.get(tenant_slug)
    candidate = str(getattr(getattr(studio, "database", None), "last_migration_report", "") or "").strip()
    if candidate and Path(candidate).exists():
        return candidate
    backup_dir = Path(tm.percorsi_dati(tenant_slug)["BACKUP_DIR"])
    reports = sorted(backup_dir.glob("storage_migration_full_*.json"))
    return str(reports[-1]) if reports else ""


def _write_rollback_report(tm: GestioneTenant, tenant_slug: str, payload: dict) -> str:
    backup_dir = Path(tm.percorsi_dati(tenant_slug)["BACKUP_DIR"])
    backup_dir.mkdir(parents=True, exist_ok=True)
    output = backup_dir / f"storage_migration_rollback_{tenant_slug}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(output)


@cli.command("migrate")
@click.option("--to", "target", required=False, type=click.Choice(["postgres", "sqlite"], case_sensitive=False), help="Backend target della migrazione ufficiale")
@click.option("--tenant", "tenant_slug", default="", help="Slug tenant. Se omesso e c'e' un solo tenant, viene risolto automaticamente")
@click.option("--registry", default=lambda: os.getenv("PCT_TENANTS_REGISTRY", "./data/tenants.json"), show_default="PCT_TENANTS_REGISTRY o ./data/tenants.json", help="Registry tenant")
@click.option("--host", default="", help="Host PostgreSQL")
@click.option("--port", default=5432, show_default=True, type=int, help="Porta PostgreSQL")
@click.option("--db-name", default="", help="Nome database PostgreSQL")
@click.option("--user", default="", help="Utente PostgreSQL")
@click.option("--password", default="", help="Password PostgreSQL")
@click.option("--ssl/--no-ssl", default=False, help="Connessione SSL verso PostgreSQL")
@click.option("--activate/--no-activate", default=True, help="Attiva il backend target dopo la migrazione")
@click.option("--rollback/--no-rollback", default=False, help="Ripristina il backend precedente usando l'ultimo report di migrazione disponibile.")
@click.option("--report-path", default="", help="Report di migrazione da usare esplicitamente per il rollback.")
@click.option("--secret-key", default=lambda: os.getenv("PCT_SECRET_KEY", ""), help="Secret key per utenti e audit")
def cmd_migrate_storage(target, tenant_slug, registry, host, port, db_name, user, password, ssl, activate, rollback, report_path, secret_key):
    """Esegue la migrazione ufficiale JSON -> SQLite -> PostgreSQL o JSON -> SQLite per un tenant."""
    tm = GestioneTenant(registry_path=registry)
    tenants = tm.lista()

    resolved_slug = (tenant_slug or "").strip().lower()
    if not resolved_slug:
        if len(tenants) == 1:
            resolved_slug = str(tenants[0].slug or "").strip().lower()
        else:
            click.echo("Errore: specifica --tenant oppure lascia un solo tenant nel registry.", err=True)
            sys.exit(1)

    studio = tm.get(resolved_slug)
    if not studio:
        click.echo(f"Errore: tenant '{resolved_slug}' non trovato.", err=True)
        sys.exit(1)

    if rollback:
        report_file = _latest_migration_report_path(tm, resolved_slug, explicit_path=report_path)
        if not report_file:
            click.echo("Errore: nessun report di migrazione disponibile per il rollback.", err=True)
            sys.exit(1)
        report_payload = _load_json_report(report_file)
        rollback_context = dict((report_payload.get("rollback") or {}).get("context") or {})
        previous_payload = dict(rollback_context.get("previous_database_config") or {})
        if not previous_payload:
            click.echo("Errore: il report selezionato non contiene il contesto di rollback.", err=True)
            sys.exit(1)
        restored_config = DatabaseConfig.from_dict(previous_payload)
        tm.aggiorna_db_config(resolved_slug, restored_config)
        if restored_config.is_sqlite:
            tm.provision_storage_backend(resolved_slug, migrate_existing=False)
        restored_studio = tm.get(resolved_slug)
        rollback_payload = {
            "generated_at": datetime.now().replace(microsecond=0).isoformat(),
            "tenant_slug": resolved_slug,
            "source_report_path": report_file,
            "restored_mode": restored_config.normalized_mode,
            "effective_runtime_kind": getattr(getattr(restored_studio, "database", None), "effective_runtime_kind", ""),
            "success": True,
            "silent_fallback_disabled": True,
        }
        rollback_payload["report_path"] = _write_rollback_report(tm, resolved_slug, rollback_payload)
        click.echo(f"Rollback completato per il tenant {resolved_slug}.")
        click.echo(json.dumps(rollback_payload, ensure_ascii=False, indent=2))
        return

    if not target:
        click.echo("Errore: specifica --to oppure usa --rollback.", err=True)
        sys.exit(1)

    previous_config = _copy_database_config(studio.database)
    if target.lower() == "sqlite":
        cfg = DatabaseConfig(mode=DbMode.SQLITE)
        tm.aggiorna_db_config(resolved_slug, cfg)
        payload = tm.provision_storage_backend(resolved_slug, migrate_existing=True)
        if payload.get("migration_report"):
            paths = tm.percorsi_dati(resolved_slug)
            payload["migration_report"] = attach_migration_rollback_context(
                report=dict(payload["migration_report"]),
                paths=paths,
                tenant_slug=resolved_slug,
                previous_database_config=previous_config,
            )
            payload["migration_report_path"] = payload["migration_report"].get("report_path", payload.get("migration_report_path", ""))
        if not payload.get("ok"):
            click.echo("Migrazione verso SQLite non riuscita.", err=True)
            click.echo(json.dumps(payload, ensure_ascii=False, indent=2), err=True)
            sys.exit(1)
        click.echo(f"SQLite pronto per il tenant {resolved_slug}.")
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    current = studio.database
    cfg = DatabaseConfig(
        mode=DbMode.POSTGRESQL,
        host=(host or current.host or "localhost").strip(),
        porta=int(port or current.porta or 5432),
        db_name=(db_name or current.db_name or "").strip(),
        utente=(user or current.utente or "").strip(),
        password=(password or current.password or "").strip(),
        ssl=bool(ssl or current.ssl),
        pool_size=current.pool_size,
        pool_timeout=current.pool_timeout,
        connessione_ok=current.connessione_ok,
        ultimo_test=current.ultimo_test,
        errore_connessione=current.errore_connessione,
        core_runtime_enabled=current.core_runtime_enabled,
        last_migration_report=current.last_migration_report,
        last_migration_at=current.last_migration_at,
    )

    tm.aggiorna_db_config(resolved_slug, cfg)
    payload = tm.provision_storage_backend(
        resolved_slug,
        migrate_existing=True,
        activate_external=bool(activate),
        secret_key=secret_key,
    )
    if payload.get("migration_report"):
        paths = tm.percorsi_dati(resolved_slug)
        payload["migration_report"] = attach_migration_rollback_context(
            report=dict(payload["migration_report"]),
            paths=paths,
            tenant_slug=resolved_slug,
            previous_database_config=previous_config,
        )
        payload["migration_report_path"] = payload["migration_report"].get("report_path", payload.get("migration_report_path", ""))
    if not payload.get("ok"):
        click.echo("Cutover PostgreSQL non riuscito.", err=True)
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2), err=True)
        sys.exit(1)

    click.echo(f"Cutover storage completato per il tenant {resolved_slug}.")
    click.echo(json.dumps(payload, ensure_ascii=False, indent=2))


@cli.command("demo-check")
@click.option("--tenant", "tenant_slug", default="", help="Slug tenant. Se omesso e c'e' un solo tenant, viene risolto automaticamente")
@click.option("--registry", default=lambda: os.getenv("PCT_TENANTS_REGISTRY", "./data/tenants.json"), show_default="PCT_TENANTS_REGISTRY o ./data/tenants.json", help="Registry tenant")
def cmd_demo_check(tenant_slug, registry):
    """Verifica se uno studio e' pronto per un uso reale end-to-end."""
    import sqlite3

    from pct.core_storage_backend import build_core_storage_backend

    tm = GestioneTenant(registry_path=registry)
    tenants = tm.lista()

    resolved_slug = (tenant_slug or "").strip().lower()
    if not resolved_slug:
        if len(tenants) == 1:
            resolved_slug = str(tenants[0].slug or "").strip().lower()
        else:
            click.echo("Errore: specifica --tenant oppure lascia un solo tenant nel registry.", err=True)
            sys.exit(1)

    studio = tm.get(resolved_slug)
    if not studio:
        click.echo(f"Errore: tenant '{resolved_slug}' non trovato.", err=True)
        sys.exit(1)

    paths = tm.percorsi_dati(resolved_slug)
    studio_db = None
    try:
        studio_db = build_core_storage_backend(studio.database, studio_db_path=paths["STUDIO_DB"])
    except (OSError, sqlite3.Error):
        studio_db = None
    if studio_db is not None and getattr(studio_db, "backend_kind", "") == "sqlite":
        try:
            clienti_count = int((studio_db.conn.execute("SELECT COUNT(*) FROM clienti").fetchone() or [0])[0] or 0)
            fascicoli_count = int((studio_db.conn.execute("SELECT COUNT(*) FROM fascicoli").fetchone() or [0])[0] or 0)
        except Exception:
            clienti_count = 0
            fascicoli_count = 0
        if clienti_count == 0 and fascicoli_count == 0:
            json_legacy_present = Path(paths["CLIENTI_DB"]).exists() or Path(paths["FASCICOLI_DB"]).exists()
            if json_legacy_present:
                studio_db = None

    clienti = GestioneClienti(db_path=paths["CLIENTI_DB"], studio_db=studio_db)
    fascicoli = GestioneFascicoli(
        db_path=paths["FASCICOLI_DB"],
        documents_dir=paths["FASCICOLI_DOCS"],
        archive_dir=paths["FASCICOLI_ARCH"],
        studio_db=studio_db,
    )
    preventivi = GestionePreventivi(db_path=paths["PREVENTIVI_DB"], studio_db=studio_db)
    fatturazione = GestioneFatturazione(db_path=paths["FATTURAZIONE_DB"], studio_db=studio_db)
    pagamenti = GestionePagamenti(db_dir=paths["PAGAMENTI_DIR"], studio_db=studio_db)
    timesheet = GestioneTimesheet(db_path=paths["TIMESHEET_DB"], studio_db=studio_db)

    snapshot = build_studio_demo_snapshot(
        clienti=clienti.tutti(stato=None),
        fascicoli=fascicoli.tutti(stato=None),
        preventivi=preventivi.tutti_preventivi(),
        conferimenti=preventivi.tutti_conferimenti(),
        parcelle=fatturazione.tutte(),
        timesheet_entries=timesheet.tutte(),
        payment_links=pagamenti.tutti_link(),
    )

    click.echo(f"Studio: {studio.nome} ({resolved_slug})")
    click.echo(f"Backend effettivo: {getattr(studio.database, 'effective_runtime_kind', 'json')}")
    click.echo(f"Pronto: {'SI' if snapshot['ready'] else 'NO'}")
    click.echo(f"Copertura workflow: {snapshot['ready_steps']}/{snapshot['steps_total']}")
    click.echo(f"Prossima azione: {snapshot['next_action']}")
    click.echo(json.dumps(snapshot, ensure_ascii=False, indent=2))


@cli.command("aggiornamenti-legali")
@click.option("--intelligence-db", default=lambda: os.getenv("PCT_LEGAL_INTELLIGENCE_DB", "./intelligence/motori.json"), show_default="PCT_LEGAL_INTELLIGENCE_DB o ./intelligence/motori.json", help="Anchor del motore legale")
@click.option("--giurisprudenza-db", default=lambda: os.getenv("PCT_GIURISPRUDENZA_DB", "./intelligence/giurisprudenza.json"), show_default="PCT_GIURISPRUDENZA_DB o ./intelligence/giurisprudenza.json", help="Archivio legacy usato solo se il mirror JSON viene abilitato esplicitamente")
@click.option("--source", "source_codes", multiple=True, help="Codice fonte da scansionare. Ripetibile")
@click.option("--no-auto-publish", is_flag=True, default=False, help="Disattiva la pubblicazione automatica dei contenuti idonei")
@click.option("--publish-approved", is_flag=True, default=False, help="Dopo la scansione pubblica tutte le review gia approvate")
@click.option("--cleanup-only", is_flag=True, default=False, help="Pulisce l'archivio da duplicati senza avviare nuove scansioni")
@click.option("--local-ai-url", default=lambda: os.getenv("LOCAL_AI_BASE_URL", ""), help="Endpoint Ollama locale")
@click.option("--local-ai-model", default=lambda: os.getenv("LOCAL_AI_CHAT_MODEL", os.getenv("OLLAMA_MODEL", "mistral")), show_default="LOCAL_AI_CHAT_MODEL o OLLAMA_MODEL o mistral", help="Modello locale per arricchimento AI")
@click.option("--export-json/--no-export-json", default=False, show_default=True, help="Scrive un export JSON amministrativo dopo il ciclo")
@click.option("--mirror-giurisprudenza-json/--no-mirror-giurisprudenza-json", default=False, show_default=True, help="Replica anche nel vecchio archivio giurisprudenza JSON")
@click.option("--per-source-timeout", type=int, default=lambda: _env_int_option("IUSENTRA_LEGAL_UPDATES_ITEM_TIMEOUT_SECONDS", 0), show_default="IUSENTRA_LEGAL_UPDATES_ITEM_TIMEOUT_SECONDS o 0", help="Esegue ogni fonte in un job separato con timeout in secondi")
@click.option("--publish-max-items", type=int, default=lambda: _env_int_option("IUSENTRA_LEGAL_UPDATES_PUBLISH_MAX_ITEMS", 5), show_default="IUSENTRA_LEGAL_UPDATES_PUBLISH_MAX_ITEMS o 5", help="Limite di pubblicazioni automatiche quando si usa il job con timeout")
def cmd_aggiornamenti_legali(intelligence_db, giurisprudenza_db, source_codes, no_auto_publish, publish_approved, cleanup_only, local_ai_url, local_ai_model, export_json, mirror_giurisprudenza_json, per_source_timeout, publish_max_items):
    """Esegue la pipeline del motore di aggiornamento normativo, giurisprudenziale e di prassi."""
    pipeline = build_legal_update_pipeline(
        intelligence_db,
        giurisprudenza_db_path=giurisprudenza_db,
        ai_base_url=local_ai_url,
        ai_model=local_ai_model,
        export_json_enabled=export_json,
        mirror_giurisprudenza_json_enabled=mirror_giurisprudenza_json,
    )
    cleanup_report = pipeline.repository.deduplicate_archive(performed_by="cli")
    report = {"ok": True, "sources": [], "reports": [], "autopublished": {"count": 0, "items": []}}
    if not cleanup_only:
        if int(per_source_timeout or 0) > 0:
            from pct.legal_update_batch_runner import LegalUpdateJobConfig, run_legal_update_batch_with_timeouts

            pipeline.repository.upsert_sources(list(DEFAULT_SOURCE_ROWS))
            selected_sources = list(source_codes) or [
                str(row.get("code") or "")
                for row in pipeline.repository.list_sources(enabled_only=True)
                if str(row.get("code") or "")
            ]
            report = run_legal_update_batch_with_timeouts(
                LegalUpdateJobConfig(
                    intelligence_db=intelligence_db,
                    giurisprudenza_db=giurisprudenza_db,
                    ai_base_url=local_ai_url,
                    ai_model=local_ai_model,
                    export_json_enabled=export_json,
                    mirror_giurisprudenza_json_enabled=mirror_giurisprudenza_json,
                ),
                source_codes=selected_sources,
                auto_publish=not no_auto_publish,
                item_timeout_seconds=int(per_source_timeout or 180),
                publish_max_items=int(publish_max_items or 80),
            )
        else:
            report = pipeline.run_cycle(
                source_codes=list(source_codes) or None,
                auto_publish=not no_auto_publish,
            )

    published_after_review = []
    if publish_approved:
        for row in pipeline.repository.list_review_queue(statuses=("approved",), limit=100):
            published_after_review.append(
                {
                    "review_id": row["id"],
                    "result": pipeline.publish_review(int(row["id"]), reviewer="cli"),
                }
            )

    click.echo(json.dumps(
        {
            "report": report,
            "cleanup": cleanup_report,
            "published_after_review": published_after_review,
            "dashboard": pipeline.dashboard_snapshot(),
        },
        ensure_ascii=False,
        indent=2,
    ))


@cli.command("legal-updates-canary")
@click.option("--intelligence-db", default=lambda: os.getenv("PCT_LEGAL_INTELLIGENCE_DB", "./intelligence/motori.json"), show_default="PCT_LEGAL_INTELLIGENCE_DB o ./intelligence/motori.json", help="Anchor del motore legale")
@click.option("--giurisprudenza-db", default=lambda: os.getenv("PCT_GIURISPRUDENZA_DB", "./intelligence/giurisprudenza.json"), show_default="PCT_GIURISPRUDENZA_DB o ./intelligence/giurisprudenza.json", help="Archivio giurisprudenza per eventuale mirror controllato")
@click.option("--source", "source_code", required=True, help="Codice di una sola fonte da provare")
@click.option("--limit", required=True, type=int, help="Limite obbligatorio di documenti da leggere")
@click.option("--max-seconds", type=int, default=60, show_default=True, help="Budget massimo del canary")
@click.option("--no-publish/--allow-publish", default=True, show_default=True, help="Mantiene disattivata la pubblicazione automatica")
@click.option(
    "--publish-mode",
    type=click.Choice(["off", "guarded", "auto"]),
    default="off",
    show_default=True,
    help="Modalità pubblicazione: off, guarded limitata ai documenti del canary, auto storica",
)
@click.option("--direct-only/--allow-web-search", default=True, show_default=True, help="Usa solo pagina fonte e allegati diretti")
@click.option("--save-diagnostics", is_flag=True, default=False, help="Registra l'esito come ultimo canary della fonte")
@click.option("--json", "as_json", is_flag=True, default=False, help="Stampa output JSON")
def cmd_legal_updates_canary(
    intelligence_db,
    giurisprudenza_db,
    source_code,
    limit,
    max_seconds,
    no_publish,
    publish_mode,
    direct_only,
    save_diagnostics,
    as_json,
):
    """Prova sicura di una fonte legale, senza import massivo."""
    from pct.legal_update_diagnostics import run_legal_updates_canary

    try:
        report = run_legal_updates_canary(
            intelligence_db=intelligence_db,
            giurisprudenza_db=giurisprudenza_db,
            source_code=source_code,
            limit=limit,
            max_seconds=max_seconds,
            no_publish=no_publish,
            publish_mode=publish_mode,
            direct_only=direct_only,
            save_diagnostics=save_diagnostics,
        )
    except Exception as exc:
        if as_json:
            click.echo(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        raise click.ClickException(str(exc))
    if as_json:
        click.echo(json.dumps(report, ensure_ascii=False, indent=2))
        return
    click.echo(
        "Canary aggiornamenti legali: "
        f"{report['source_code']} - {report['processed']} analizzati su "
        f"{report['documents_found']} letti, pubblicazione "
        f"{report.get('publish_mode') or ('disattivata' if report['no_publish'] else 'consentita')}."
    )
    if report.get("errors"):
        click.echo("Errori: " + "; ".join(report["errors"][:3]))


@cli.command("legal-updates-backfill-diagnostics")
@click.option("--intelligence-db", default=lambda: os.getenv("PCT_LEGAL_INTELLIGENCE_DB", "./intelligence/motori.json"), show_default="PCT_LEGAL_INTELLIGENCE_DB o ./intelligence/motori.json", help="Anchor del motore legale")
@click.option("--giurisprudenza-db", default=lambda: os.getenv("PCT_GIURISPRUDENZA_DB", "./intelligence/giurisprudenza.json"), show_default="PCT_GIURISPRUDENZA_DB o ./intelligence/giurisprudenza.json", help="Archivio giurisprudenza per eventuale mirror controllato")
@click.option("--source", "source_code", default="", help="Limita il backfill a una fonte")
@click.option("--review-id", type=int, default=0, help="Limita il backfill a una review")
@click.option("--query", default="", help="Filtro testuale mirato")
@click.option(
    "--missing",
    required=True,
    help="Tipo di diagnosi mancante: attachments, ocr, references, questions o lista separata da virgole",
)
@click.option("--limit", required=True, type=int, help="Limite obbligatorio di elementi")
@click.option("--max-seconds", type=int, default=60, show_default=True, help="Budget massimo del backfill")
@click.option("--include-closed", is_flag=True, default=False, help="Include elementi chiusi")
@click.option("--include-open-data", is_flag=True, default=False, help="Include cataloghi OpenData")
@click.option("--no-publish/--allow-publish", default=True, show_default=True, help="Mantiene disattivata la pubblicazione automatica")
@click.option("--json", "as_json", is_flag=True, default=False, help="Stampa output JSON")
def cmd_legal_updates_backfill_diagnostics(
    intelligence_db,
    giurisprudenza_db,
    source_code,
    review_id,
    query,
    missing,
    limit,
    max_seconds,
    include_closed,
    include_open_data,
    no_publish,
    as_json,
):
    """Backfill diagnostico mirato per allegati, OCR, riferimenti o domande."""
    from pct.legal_update_diagnostics import run_legal_updates_backfill_diagnostics

    try:
        report = run_legal_updates_backfill_diagnostics(
            intelligence_db=intelligence_db,
            giurisprudenza_db=giurisprudenza_db,
            source_code=source_code,
            review_id=review_id,
            query=query,
            missing=missing,
            limit=limit,
            max_seconds=max_seconds,
            include_closed=include_closed,
            include_open_data=include_open_data,
            no_publish=no_publish,
        )
    except Exception as exc:
        if as_json:
            click.echo(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        raise click.ClickException(str(exc))
    if as_json:
        click.echo(json.dumps(report, ensure_ascii=False, indent=2))
        return
    click.echo(
        "Backfill diagnostico aggiornamenti legali: "
        f"{missing}, {report.get('checked', 0)} controllati, "
        f"{report.get('updated', report.get('verification_evidence_saved', 0))} aggiornati."
    )


@cli.command("legal-updates-run-progressive")
@click.option("--intelligence-db", default=lambda: os.getenv("PCT_LEGAL_INTELLIGENCE_DB", "./intelligence/motori.json"), show_default="PCT_LEGAL_INTELLIGENCE_DB o ./intelligence/motori.json", help="Anchor del motore legale")
@click.option("--giurisprudenza-db", default=lambda: os.getenv("PCT_GIURISPRUDENZA_DB", "./intelligence/giurisprudenza.json"), show_default="PCT_GIURISPRUDENZA_DB o ./intelligence/giurisprudenza.json", help="Archivio giurisprudenza per eventuale mirror controllato")
@click.option("--queue-db", default="", help="Percorso esplicito della coda job aggiornamenti legali")
@click.option("--cursor-path", default="", help="Percorso esplicito dei cursori scheduler aggiornamenti legali")
@click.option("--source-budget", type=int, default=3, show_default=True, help="Numero massimo di fonti verdi da eseguire nel ciclo")
@click.option("--publish-max-items", type=int, default=5, show_default=True, help="Numero massimo di pubblicazioni guarded nel ciclo")
@click.option("--item-timeout-seconds", type=int, default=120, show_default=True, help="Timeout per ciascuna fonte/job")
@click.option("--max-attempts", type=int, default=3, show_default=True, help="Tentativi massimi per job in coda")
@click.option("--guarded-only", is_flag=True, default=False, help="Obbligatorio: consente solo pubblicazione guarded")
@click.option("--dry-run", is_flag=True, default=False, help="Mostra solo il piano senza accodare o pubblicare")
@click.option("--local-ai-url", default=lambda: os.getenv("LOCAL_AI_BASE_URL", ""), help="Endpoint Ollama locale")
@click.option("--local-ai-model", default=lambda: os.getenv("LOCAL_AI_CHAT_MODEL", os.getenv("OLLAMA_MODEL", "mistral")), show_default="LOCAL_AI_CHAT_MODEL o OLLAMA_MODEL o mistral", help="Modello locale per arricchimento AI")
@click.option("--json", "as_json", is_flag=True, default=False, help="Stampa output JSON")
def cmd_legal_updates_run_progressive(
    intelligence_db,
    giurisprudenza_db,
    queue_db,
    cursor_path,
    source_budget,
    publish_max_items,
    item_timeout_seconds,
    max_attempts,
    guarded_only,
    dry_run,
    local_ai_url,
    local_ai_model,
    as_json,
):
    """Esegue un ciclo scheduler/autofetch controllato sulle sole fonti verdi."""
    from pct.legal_update_autofetch import LegalAutoFetchConfig, run_legal_update_progressive_cycle

    config = LegalAutoFetchConfig(
        intelligence_db=str(intelligence_db or "./intelligence/motori.json"),
        giurisprudenza_db=str(giurisprudenza_db or ""),
        ai_base_url=str(local_ai_url or ""),
        ai_model=str(local_ai_model or "mistral"),
        queue_db_path=str(queue_db or ""),
        cursor_path=str(cursor_path or ""),
        source_budget=max(1, int(source_budget or 1)),
        publish_max_items=max(0, int(publish_max_items or 0)),
        item_timeout_seconds=max(1, int(item_timeout_seconds or 1)),
        max_attempts=max(1, int(max_attempts or 1)),
        execute_due_sources=True,
    )
    if not guarded_only:
        payload = {
            "ok": False,
            "error": "--guarded-only e' obbligatorio: il ciclo non puo' pubblicare fuori dal guardrail.",
            "mode": "progressive_controlled_cycle",
        }
        if as_json:
            click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        raise click.ClickException(payload["error"])
    try:
        report = run_legal_update_progressive_cycle(
            config,
            guarded_only=True,
            dry_run=bool(dry_run),
        )
    except Exception as exc:
        if as_json:
            click.echo(json.dumps({"ok": False, "error": str(exc)}, ensure_ascii=False, indent=2))
        raise click.ClickException(str(exc))

    if as_json:
        click.echo(json.dumps(report, ensure_ascii=False, indent=2))
        return
    plan = dict(report.get("plan") or {})
    click.echo("Ciclo progressivo aggiornamenti legali")
    click.echo(f"Modalita': {'dry-run' if dry_run else 'esecuzione controllata'}")
    click.echo(f"Fonti selezionate: {plan.get('selected_count', 0)}")
    click.echo(f"Fonti verdi abilitate: {', '.join(report.get('green_source_codes') or [])}")
    click.echo(f"Pubblicazione: guarded-only, limite {config.publish_max_items}")


@cli.command("legal-updates-giurisprudenza-structured-canary")
@click.option("--intelligence-db", default=lambda: os.getenv("PCT_LEGAL_INTELLIGENCE_DB", "./intelligence/motori.json"), show_default="PCT_LEGAL_INTELLIGENCE_DB o ./intelligence/motori.json", help="Anchor del motore legale")
@click.option("--giurisprudenza-db", default=lambda: os.getenv("PCT_GIURISPRUDENZA_DB", "./intelligence/giurisprudenza.json"), show_default="PCT_GIURISPRUDENZA_DB o ./intelligence/giurisprudenza.json", help="Archivio giurisprudenza per eventuale mirror controllato")
@click.option("--limit", type=int, default=100, show_default=True, help="Numero massimo di review da controllare")
@click.option("--local-ai-url", default=lambda: os.getenv("LOCAL_AI_BASE_URL", ""), help="Endpoint Ollama locale")
@click.option("--local-ai-model", default=lambda: os.getenv("LOCAL_AI_CHAT_MODEL", os.getenv("OLLAMA_MODEL", "mistral")), show_default="LOCAL_AI_CHAT_MODEL o OLLAMA_MODEL o mistral", help="Modello locale per arricchimento AI")
@click.option("--json", "as_json", is_flag=True, default=False, help="Stampa output JSON")
def cmd_legal_updates_giurisprudenza_structured_canary(
    intelligence_db,
    giurisprudenza_db,
    limit,
    local_ai_url,
    local_ai_model,
    as_json,
):
    """Verifica schede giurisprudenziali strutturate senza promozione forzata."""
    from pct.legal_update_health_report import build_giurisprudenza_structured_canary

    report = build_giurisprudenza_structured_canary(
        intelligence_db=intelligence_db,
        giurisprudenza_db=giurisprudenza_db,
        ai_base_url=local_ai_url,
        ai_model=local_ai_model,
        limit=limit,
    )
    if as_json:
        click.echo(json.dumps(report, ensure_ascii=False, indent=2))
        return
    click.echo("Canary Archivio Giurisprudenza strutturato")
    click.echo(f"Stato: {report.get('status')}")
    click.echo(f"Candidati completi: {report.get('complete_candidate_count', 0)}")
    click.echo(str(report.get("reason") or ""))


@cli.command("legal-updates-health-report")
@click.option("--intelligence-db", default=lambda: os.getenv("PCT_LEGAL_INTELLIGENCE_DB", "./intelligence/motori.json"), show_default="PCT_LEGAL_INTELLIGENCE_DB o ./intelligence/motori.json", help="Anchor del motore legale")
@click.option("--giurisprudenza-db", default=lambda: os.getenv("PCT_GIURISPRUDENZA_DB", "./intelligence/giurisprudenza.json"), show_default="PCT_GIURISPRUDENZA_DB o ./intelligence/giurisprudenza.json", help="Archivio giurisprudenza per eventuale mirror controllato")
@click.option("--queue-db", default="", help="Percorso esplicito della coda job aggiornamenti legali")
@click.option("--cursor-path", default="", help="Percorso esplicito dei cursori scheduler aggiornamenti legali")
@click.option("--local-ai-url", default=lambda: os.getenv("LOCAL_AI_BASE_URL", ""), help="Endpoint Ollama locale")
@click.option("--local-ai-model", default=lambda: os.getenv("LOCAL_AI_CHAT_MODEL", os.getenv("OLLAMA_MODEL", "mistral")), show_default="LOCAL_AI_CHAT_MODEL o OLLAMA_MODEL o mistral", help="Modello locale per arricchimento AI")
@click.option("--json", "as_json", is_flag=True, default=False, help="Stampa output JSON")
def cmd_legal_updates_health_report(
    intelligence_db,
    giurisprudenza_db,
    queue_db,
    cursor_path,
    local_ai_url,
    local_ai_model,
    as_json,
):
    """Report sanitario del regime controllato aggiornamenti legali."""
    from pct.legal_update_health_report import build_legal_updates_health_report

    report = build_legal_updates_health_report(
        intelligence_db=intelligence_db,
        giurisprudenza_db=giurisprudenza_db,
        ai_base_url=local_ai_url,
        ai_model=local_ai_model,
        queue_db_path=queue_db,
        cursor_path=cursor_path,
    )
    if as_json:
        click.echo(json.dumps(report, ensure_ascii=False, indent=2))
        return

    totals = dict((report.get("source_quality_dashboard") or {}).get("totals") or {})
    retry = dict(report.get("retry_sicuro") or {})
    backfill = dict(report.get("backfill_periodico") or {})
    click.echo("Health report aggiornamenti legali")
    click.echo(f"Stato: {(report.get('readiness') or {}).get('status', 'da verificare')}")
    click.echo(f"Fonti attive: {totals.get('fonti_attive', 0)}")
    click.echo(f"Fonti in osservazione: {totals.get('fonti_in_osservazione', 0)}")
    click.echo(f"Fonti RAG-only: {totals.get('fonti_rag_only', 0)}")
    click.echo(f"Fonti non pubblicabili: {totals.get('fonti_non_pubblicabili', 0)}")
    click.echo(f"Errori fonte/coda: {totals.get('errors', 0)} + {retry.get('failed_or_timeout', 0)}")
    click.echo(f"Backfill mirati pendenti: {backfill.get('pending', {})}")


@cli.command("ai-avanzata")
@click.option("--json", "as_json", is_flag=True, default=False, help="Stampa il payload completo in JSON")
@click.option("--fail-if-blocked", is_flag=True, default=False, help="Ritorna errore se una capacita' abilitata non e' pronta")
def cmd_ai_avanzata(as_json, fail_if_blocked):
    """Mostra lo stato operativo di MTP, LLM Wiki, GLM-OCR e Gemini Embedding 2."""
    from lex.advanced_runtime import build_advanced_ai_capabilities

    payload = build_advanced_ai_capabilities()
    if as_json:
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        click.echo("AI avanzata - stato operativo")
        for code, item in (payload.get("capabilities") or {}).items():
            label = str(item.get("status_label") or item.get("status") or "n.d.")
            message = str(item.get("operator_message") or "")
            click.echo(f"- {code}: {label}")
            if message:
                click.echo(f"  {message}")
    if fail_if_blocked and list(payload.get("blocked") or []):
        raise click.ClickException("Una o piu' capacita' avanzate abilitate non sono pronte")


@cli.command("utf8-integrity")
@click.option("--root", "roots", multiple=True, help="Cartella o file da controllare. Ripetibile; se omesso usa i dati runtime.")
@click.option("--check-only", is_flag=True, default=False, help="Controlla senza modificare i file.")
@click.option("--max-files", type=int, default=0, help="Limite file da scansionare.")
@click.option("--max-file-bytes", type=int, default=0, help="Dimensione massima per file testuale.")
@click.option("--report", "report_path", default="", help="Percorso report JSON.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Stampa il payload completo in JSON")
def cmd_utf8_integrity(roots, check_only, max_files, max_file_bytes, report_path, as_json):
    """Verifica e ripara UTF-8, accenti italiani e mojibake nei dati testuali."""
    from pct.utf8_integrity import run_utf8_integrity_service

    cfg: dict[str, object] = {}
    try:
        from web.app import create_app

        app = create_app()
        cfg = dict(app.config)
    except Exception:
        cfg = {}
    report = run_utf8_integrity_service(
        cfg,
        repair=not check_only,
        roots=list(roots) or None,
        max_files=max_files or None,
        max_file_bytes=max_file_bytes or None,
        report_path=report_path or None,
    )
    if as_json:
        click.echo(json.dumps(report, ensure_ascii=False, indent=2))
        return
    click.echo("Integrità UTF-8 - controllo completato")
    click.echo(f"File controllati: {report.get('checked_files', 0)}")
    click.echo(f"File con anomalie: {report.get('files_with_artifacts', 0)}")
    click.echo(f"File riparati: {report.get('repaired_files', 0)}")
    if report.get("unresolved_replacement_files"):
        click.echo(f"Da verificare: {report.get('unresolved_replacement_files')} file con caratteri non recuperabili")
    if report.get("report_path"):
        click.echo(f"Report: {report.get('report_path')}")


@cli.command("legal-document-understanding-report")
@click.option("--db", "db_path", default="", help="Percorso SQLite della piattaforma documentale.")
@click.option("--storage-root", default="", help="Radice storage probatorio associata al database.")
@click.option("--tenant-id", default="", help="Limita il report a uno studio.")
@click.option("--json", "as_json", is_flag=True, default=False, help="Stampa il report in JSON.")
def cmd_legal_document_understanding_report(db_path, storage_root, tenant_id, as_json):
    """Produce il report metriche Legal Document Understanding."""
    from legal_document_ingestion.metrics import build_legal_document_understanding_report

    resolved_db = db_path or os.getenv("LEGAL_DOCUMENTS_DB") or "./data/legal_document_understanding.sqlite"
    resolved_storage = storage_root or os.getenv("LEGAL_DOCUMENTS_STORAGE") or ""
    report = build_legal_document_understanding_report(
        db_path=resolved_db,
        storage_root=resolved_storage or None,
        tenant_id=tenant_id or None,
    )
    if as_json:
        click.echo(json.dumps(report, ensure_ascii=False, indent=2))
        return
    click.echo("Legal Document Understanding - report metriche")
    click.echo(f"Documenti misurati: {report.get('dataset', {}).get('documents', 0)}")
    click.echo(f"Riduzione lavoro stimata: {report.get('percentuale_riduzione_lavoro_studio_stimata', 0)}%")
    click.echo(f"Obiettivo 80% raggiunto: {'sì' if report.get('target_80_percent_raggiunto') else 'no'}")
    click.echo(str(report.get("nota_misurazione") or ""))


@cli.command("lex-agenti-operativi")
@click.option("--all", "run_all", is_flag=True, default=False, help="Esegue tutti i micro-agenti operativi Lex")
@click.option("--agent", "agent_ids", multiple=True, help="Agent id interno da eseguire. Ripetibile")
@click.option("--json", "as_json", is_flag=True, default=False, help="Stampa il payload completo in JSON")
def cmd_lex_agenti_operativi(run_all, agent_ids, as_json):
    """Esegue subito gli agenti operativi che aggiornano l'inventario Lex."""
    from lex.operational_knowledge.nightly_agents import run_operational_micro_agents
    from pct.scheduler_registry import delegated_operational_agent_specs

    app = None
    app_error = ""
    try:
        from web.app import create_app

        app = create_app()
    except Exception as exc:  # pragma: no cover - difesa CLI runtime
        app_error = str(exc)

    cfg = dict(getattr(app, "config", {}) or {})
    specs = delegated_operational_agent_specs(cfg)
    wanted = {str(agent).strip() for agent in agent_ids if str(agent).strip()}
    if wanted:
        specs = [spec for spec in specs if str(spec.get("agent_id") or "") in wanted or str(spec.get("template_key") or "") in wanted]
    elif not run_all:
        # Senza filtro esplicito esegue comunque tutto: e' il comportamento utile per il controllo "adesso".
        specs = list(specs)

    if not specs:
        raise click.ClickException("Nessun agente operativo Lex selezionato.")

    if app is not None:
        with app.app_context():
            payload = run_operational_micro_agents(app=app, agents=specs)
    else:
        payload = run_operational_micro_agents(config=cfg, agents=specs)
    payload["selected_agents"] = [str(spec.get("agent_id") or "") for spec in specs]
    if app_error:
        payload["app_warning"] = app_error

    if as_json:
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    click.echo("Agenti operativi Lex - esecuzione immediata")
    for result in payload.get("results") or []:
        click.echo(f"- {result.get('agent_id')}: {result.get('status')} - {result.get('summary')}")
        if result.get("missing_keys"):
            click.echo(f"  Da verificare: {', '.join(result.get('missing_keys') or [])}")


@cli.command("golden-path")
@click.option(
    "--run/--no-run",
    "should_run",
    default=True,
    show_default=True,
    help="Esegue davvero le suite ufficiali oppure mostra l'ultimo report disponibile.",
)
@click.option(
    "--report-dir",
    default=lambda: os.getenv("PCT_GOLDEN_PATH_REPORT_DIR", "./data/governance"),
    show_default="PCT_GOLDEN_PATH_REPORT_DIR o ./data/governance",
    help="Directory dove persistire e leggere i report ufficiali dei golden path.",
)
def cmd_golden_path(should_run, report_dir):
    """Esegue o mostra i golden path ufficiali del prodotto."""
    if should_run:
        report = run_golden_path_suites(base_dir=report_dir, cwd=str(Path.cwd()))
        payload = build_golden_path_payload(base_dir=report_dir, report_payload=report)
        payload["report_path"] = report.get("report_path", "")
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    payload = build_golden_path_payload(base_dir=report_dir)
    click.echo(json.dumps(payload, ensure_ascii=False, indent=2))


cli.add_command(cmd_crash_test_operativo)
cli.add_command(cmd_backup_blindato)


def main():
    cli()


if __name__ == "__main__":
    main()
