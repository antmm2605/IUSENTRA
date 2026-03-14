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


def main():
    cli()


if __name__ == "__main__":
    main()
