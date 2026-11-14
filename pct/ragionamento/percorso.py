"""Proiezione cronologica del quadro, con la fonte e il valore di ogni passaggio."""

from .modello import EventoCausa, Fonte
from .regole.contesto import Contesto
from .testo import giorno, pulito


def ricostruisci_percorso(ctx: Contesto) -> list[EventoCausa]:
    eventi: list[EventoCausa] = []

    def registra(tipo: str, data: str, descrizione: str, fonte: Fonte, stato: str) -> None:
        giorno_evento = giorno(data)
        eventi.append(EventoCausa(tipo, giorno_evento.isoformat() if giorno_evento else "", descrizione, fonte, stato))

    for campo, descrizione in (("data_apertura", "Apertura del fascicolo nello studio"),
                               ("data_chiusura", "Chiusura registrata dallo studio")):
        data = pulito(ctx.fascicolo.get(campo))[:10]
        if giorno(data) and ctx.fascicolo_id:
            registra(campo, data, descrizione, Fonte(ctx.fascicolo_id, brano=campo, data=data, tipo="fascicolo"),
                     "registrato")

    for atto in ctx.della_causa():
        if not atto.id:
            continue
        descrizione = atto.etichetta or atto.nome
        registra("atto", atto.data, descrizione, Fonte(atto.id, atto.nome, data=atto.data), "documentato")

    for deposito in ctx.depositi:
        if not deposito.fonte_id:
            continue
        atto = ctx.atto(deposito.fonte_id)
        # Le copie EML sono tracce documentali. Il loro oggetto non prova un esito.
        registra("deposito", deposito.data, deposito.titolo,
                 Fonte(deposito.fonte_id, atto.nome if atto else deposito.titolo, data=deposito.data,
                       tipo="documento" if atto else "registro_depositi"),
                 "invio_registrato" if deposito.stato_registro else "esito_da_verificare")
        if deposito.stato_registro:
            registra("esito_deposito", deposito.data_esito, deposito.titolo,
                     Fonte(deposito.fonte_id, deposito.titolo, data=deposito.data_esito, tipo="registro_depositi"),
                     deposito.stato_registro)

    for atto_id, consegna in ctx.consegne_verificate.items():
        atto = ctx.atto(atto_id)
        data, prova = consegna.get("data", ""), consegna.get("riferimento", "")
        if atto and atto.appartenenza == "causa" and giorno(data) and prova:
            registra("consegna_notifica", data, atto.nome, Fonte(prova, data=data, tipo="prova_notifica"), "verificato")

    for comunicazione in ctx.comunicazioni:
        atto = ctx.atto(comunicazione.fonte_id)
        if atto and atto.appartenenza == "causa":
            registra("comunicazione", comunicazione.data, atto.nome,
                     Fonte(atto.id, atto.nome, data=atto.data), "documentato")

    for udienza in ctx.udienze:
        if udienza.fonte:
            registra("udienza_fissata", udienza.data, udienza.modalita, udienza.fonte, "fissato")
    for termine in ctx.termini:
        registra("termine_assegnato", termine.scadenza, termine.adempimento, termine.fonte, "assegnato")

    distinti = {(e.tipo, e.data, e.descrizione, e.fonte.oggetto_id): e for e in eventi}
    return sorted(distinti.values(), key=lambda e: (not e.data, e.data, e.tipo, e.fonte.oggetto_id))
