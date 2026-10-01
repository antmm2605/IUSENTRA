"""Studio di esempio del banco di prova di Lex.

I dati riproducono le situazioni che mettono in difficoltà la comprensione
delle domande: cognome e nome in ordine libero, clienti omonimi, nomi quasi
uguali, fascicolo importato dal portale collegato al cliente solo per nome,
termini confermati, proposti (da confermare) e già completati, udienza
sostituita dal deposito di note scritte (art. 127-ter c.p.c.: la scadenza del
termine per le note vale come data dell'udienza).

Data di riferimento del banco: lunedì 5 ottobre 2026 («questa settimana» =
5–11 ottobre 2026). Nessun dato reale: nomi e codici fiscali sono inventati.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

DATA_RIFERIMENTO = "2026-10-05"
SLUG_STUDIO = "studio-banco-lex"


@dataclass(slots=True)
class StudioBanco:
    app: Any
    studio: Any
    admin: Any
    ids: dict[str, str]


def crea_studio(tmp_path: Path) -> StudioBanco:
    from pct.agenda import Agenda, TipoAppuntamento
    from pct.clienti import GestioneClienti, TipoCliente
    from pct.fascicoli import GestioneFascicoli, TipoFascicolo
    from pct.scadenziario import GestioneScadenziario, StatoTermine, TipoTermine
    from pct.storage import StudioDB
    from pct.tenant import GestioneTenant
    from tests.test_web_bootstrap import _cfg_web, _seed_tenant_admin, _write_studio_config
    from web.app import create_app

    _write_studio_config(tmp_path / "config" / "studio.json")
    app = create_app(_cfg_web(tmp_path))
    studio, admin = _seed_tenant_admin(app, studio_nome="Studio Banco Lex", studio_slug=SLUG_STUDIO)
    paths = GestioneTenant(app.config["TENANTS_REGISTRY"]).percorsi_dati(studio.slug, reconcile_aliases=False)
    _write_studio_config(Path(paths["CONFIG_STUDIO_DB"]))
    studio_db = StudioDB.get(paths["STUDIO_DB"])

    clienti = GestioneClienti(db_path=paths["CLIENTI_DB"], studio_db=studio_db)
    fascicoli = GestioneFascicoli(paths["FASCICOLI_DB"], studio_db=studio_db)
    scadenze = GestioneScadenziario(paths["SCADENZIARIO_DB"], studio_db=studio_db)
    agenda = Agenda(db_path=paths["AGENDA_DB"], studio_db=studio_db)
    ids: dict[str, str] = {}

    def persona(chiave: str, nome: str, cognome: str, cf: str) -> str:
        ids[chiave] = clienti.nuovo(TipoCliente.PERSONA_FISICA, nome=nome, cognome=cognome, codice_fiscale=cf).id
        return ids[chiave]

    def fascicolo(chiave: str, titolo: str, *, id_cliente: str = "", nome_cliente: str, **dati: Any) -> str:
        tipo = dati.pop("tipo", TipoFascicolo.CIVILE)
        ids[chiave] = fascicoli.nuovo(titolo, tipo, id_cliente=id_cliente, nome_cliente=nome_cliente, **dati).id
        return ids[chiave]

    def termine(titolo: str, tipo: Any, data: str, fascicolo_id: str, **extra: Any) -> None:
        scadenze.nuova(titolo, tipo, data, id_fascicolo=fascicolo_id, **extra)

    def udienza(titolo: str, data_ora: str, *, cliente: str, rg: str, tribunale: str, id_cliente: str = "") -> None:
        agenda.aggiungi(
            titolo, TipoAppuntamento.UDIENZA, data_ora, 30, tribunale,
            cliente=cliente, id_cliente=id_cliente, procedimento=f"RG {rg}", tribunale=tribunale,
            allow_overlap=True,
        )

    # 1. Gramuglia Caterina — udienza sostituita da note scritte (art. 127-ter c.p.c.).
    gramuglia = persona("gramuglia", "Caterina", "Gramuglia", "GRMCTR75D45G288K")
    f_gramuglia = fascicolo(
        "f_gramuglia", "Gramuglia c. INPS", id_cliente=gramuglia, nome_cliente="Gramuglia Caterina",
        numero_rg="1500/2025", tribunale="Tribunale di Palmi", giudice="Dott. Russo", tipo=TipoFascicolo.LAVORO,
        controparte="INPS",
    )
    termine("Deposito note scritte ex art. 127-ter c.p.c.", TipoTermine.DEPOSITO_MEMORIA, "2026-10-20", f_gramuglia, perentorio=True)
    termine("Deposito ricorso introduttivo", TipoTermine.DEPOSITO_ATTO, "2026-03-01", f_gramuglia, stato=StatoTermine.COMPLETATO)
    udienza("Udienza sostituita da note scritte — Gramuglia c. INPS", "2026-10-20T09:00:00",
            cliente="Gramuglia Caterina", id_cliente=gramuglia, rg="1500/2025", tribunale="Tribunale di Palmi")
    udienza("Udienza di discussione — Gramuglia c. INPS", "2027-01-12T10:30:00",
            cliente="Gramuglia Caterina", id_cliente=gramuglia, rg="1500/2025", tribunale="Tribunale di Palmi")
    udienza("Prima udienza — Gramuglia c. INPS", "2026-05-15T09:30:00",
            cliente="Gramuglia Caterina", id_cliente=gramuglia, rg="1500/2025", tribunale="Tribunale di Palmi")

    # 2. Gramaglia Roberto — cognome quasi uguale: le sue date non vanno mai date a Gramuglia.
    gramaglia = persona("gramaglia", "Roberto", "Gramaglia", "GRMRRT68M12A662T")
    f_gramaglia = fascicolo(
        "f_gramaglia", "Gramaglia c. Comune di Bari", id_cliente=gramaglia, nome_cliente="Gramaglia Roberto",
        numero_rg="775/2026", tribunale="Tribunale di Bari", giudice="Dott.ssa Colella",
    )
    termine("Deposito note scritte ex art. 127-ter c.p.c.", TipoTermine.DEPOSITO_MEMORIA, "2026-10-25", f_gramaglia, perentorio=True)

    # 3-4. Due clienti omonimi «Mario Rossi», distinti dal fascicolo.
    rossi_bari = persona("rossi_bari", "Mario", "Rossi", "RSSMRA70A01A662X")
    f_rossi_bari = fascicolo(
        "f_rossi_bari", "Rossi c. Condominio Aurora", id_cliente=rossi_bari, nome_cliente="Rossi Mario",
        numero_rg="2210/2024", tribunale="Tribunale di Bari", giudice="Dott.ssa Neri", controparte="Condominio Aurora",
    )
    termine("Memoria integrativa art. 171-ter n. 1 c.p.c.", TipoTermine.DEPOSITO_MEMORIA, "2026-10-09", f_rossi_bari, perentorio=True)
    udienza("Prima udienza art. 183 c.p.c. — Rossi c. Condominio Aurora", "2026-11-12T09:30:00",
            cliente="Rossi Mario", id_cliente=rossi_bari, rg="2210/2024", tribunale="Tribunale di Bari")
    rossi_napoli = persona("rossi_napoli", "Mario", "Rossi", "RSSMRA82C15F839Y")
    f_rossi_napoli = fascicolo(
        "f_rossi_napoli", "Opposizione a decreto ingiuntivo Banca Levante", id_cliente=rossi_napoli, nome_cliente="Rossi Mario",
        numero_rg="880/2026", tribunale="Tribunale di Napoli", giudice="Dott. Caputo", controparte="Banca Levante S.p.A.",
    )
    termine("Opposizione a decreto ingiuntivo (art. 641 c.p.c.)", TipoTermine.IMPUGNAZIONE, "2026-10-15", f_rossi_napoli, perentorio=True)

    # 5. Esposito Anna — causa trattenuta in decisione: termini ex art. 190 c.p.c., nessuna udienza futura.
    esposito = persona("esposito", "Anna", "Esposito", "SPSNNA79E50L049P")
    f_esposito = fascicolo(
        "f_esposito", "Esposito c. Verdi Costruzioni", id_cliente=esposito, nome_cliente="Esposito Anna",
        numero_rg="3301/2025", tribunale="Tribunale di Taranto", giudice="Dott. Lamanna", controparte="Verdi Costruzioni S.r.l.",
    )
    termine("Deposito comparsa conclusionale", TipoTermine.DEPOSITO_MEMORIA, "2026-10-07", f_esposito, perentorio=True)
    termine("Deposito memoria di replica", TipoTermine.DEPOSITO_MEMORIA, "2026-10-27", f_esposito, perentorio=True)
    udienza("Udienza di rimessione in decisione — Esposito c. Verdi Costruzioni", "2026-07-08T11:00:00",
            cliente="Esposito Anna", id_cliente=esposito, rg="3301/2025", tribunale="Tribunale di Taranto")

    # 6. De Luca Giovanni — fascicolo importato dal portale, collegato solo per nome (senza identificativo cliente).
    ids["de_luca"] = clienti.nuovo(TipoCliente.PERSONA_FISICA, nome="Giovanni", cognome="De Luca", codice_fiscale="DLCGNN65H20E506Q").id
    f_de_luca = fascicolo(
        "f_de_luca", "Appello De Luca c. Assicurazioni Sud", nome_cliente="De Luca Giovanni",
        numero_rg="512/2026", tribunale="Corte d'Appello di Lecce", giudice="Dott. Greco", controparte="Assicurazioni Sud S.p.A.",
    )
    termine("Notifica atto di appello", TipoTermine.NOTIFICA, "2026-10-30", f_de_luca, perentorio=True)
    udienza("Prima udienza di appello — De Luca c. Assicurazioni Sud", "2026-12-03T10:00:00",
            cliente="De Luca Giovanni", rg="512/2026", tribunale="Corte d'Appello di Lecce")

    # 7. Bianchi Impianti S.r.l. — persona giuridica; termine proposto dalla lettura di una PEC, da confermare.
    ids["bianchi"] = clienti.nuovo(
        TipoCliente.PERSONA_GIURIDICA, ragione_sociale="Bianchi Impianti S.r.l.", partita_iva="06123450729",
    ).id
    f_bianchi = fascicolo(
        "f_bianchi", "Bianchi Impianti c. Lorusso", id_cliente=ids["bianchi"], nome_cliente="Bianchi Impianti S.r.l.",
        numero_rg="450/2026", tribunale="Giudice di Pace di Bari", giudice="Avv. Santoro", controparte="Lorusso Francesco",
    )
    termine("Deposito note scritte ex art. 127-ter c.p.c.", TipoTermine.DEPOSITO_MEMORIA, "2026-10-22", f_bianchi,
            stato=StatoTermine.BOZZA, source_document_name="PEC di cancelleria del 28/09/2026")
    udienza("Prima udienza di comparizione — Bianchi Impianti c. Lorusso", "2026-10-08T09:00:00",
            cliente="Bianchi Impianti S.r.l.", id_cliente=ids["bianchi"], rg="450/2026", tribunale="Giudice di Pace di Bari")

    # 8. Ferraro Luca — cliente senza fascicoli.
    persona("ferraro", "Luca", "Ferraro", "FRRLCU90T10H501W")

    return StudioBanco(app=app, studio=studio, admin=admin, ids=ids)


def accedi(client: Any, banco: StudioBanco) -> None:
    risposta = client.post(
        "/login",
        data={"username": banco.admin.username, "password": "PasswordSicura!123", "studio_slug": banco.studio.slug},
        follow_redirects=False,
    )
    if risposta.status_code != 302:
        raise RuntimeError(f"Accesso allo studio di prova non riuscito: HTTP {risposta.status_code}")
