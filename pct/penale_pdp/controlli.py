"""Controlli di un deposito PDP prima di aprire il portale.

Replica in anticipo quello che il PDP verifica all'invio e aggiunge le regole
del provvedimento DGSIA 11/07/2023 che il portale non blocca ma la
cancelleria può far valere (A4, testo nativo). Base: manuale utente PDP
(pagine Depositi, Deposito atti successivi, schede degli atti) e art. 5
del provvedimento; atto abilitante: art. 5 co. 5.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Iterable

from . import catalogo
from .controlli_file import LIMITE_DEPOSITO, Esito, FileDeposito, controlla_file
from .regole_atti import e_nomina, regola_per

PROCURE = frozenset({"PM-U", "PM-G", "PMM-U"})


@dataclass
class Richiesta:
    atto: str  # codice tipo atto del PDP
    ufficio: str  # codice tipo ufficio del PDP
    soggetti: list[dict[str, Any]]  # {nome, ruolo: IND|OFF|CIV|RES|COB|TER}
    file: list[FileDeposito]
    dati: dict[str, Any] = field(default_factory=dict)
    procedimento_autorizzato: bool = False
    avocato_pg: bool = False
    avviso_indagini_presente: bool = False  # 408, 411 o 415-bis già nel fascicolo
    procura_speciale_dichiarata: bool = False
    cf_avvocato: str = ""
    avvocatura_stato: bool = False
    uffici_registro: tuple[str, ...] = ()  # uffici dei registri del procedimento (PM-U, GIP-U, DIB-U…)


def _vuoto(valore: Any) -> bool:
    return valore is None or (isinstance(valore, str) and not valore.strip()) or valore == []


def _controlla_dati(richiesta: Richiesta, esiti: list[Esito]) -> None:
    regola = regola_per(richiesta.atto)
    dati = richiesta.dati or {}
    for campo in regola.campi:
        if campo.obbligatorio and _vuoto(dati.get(campo.chiave)):
            esiti.append(Esito("DATO_MANCANTE", "errore", f"Compila «{campo.etichetta}»: il PDP non abilita l'invio senza."))
        if campo.tipo == "importo" and not _vuoto(dati.get(campo.chiave)):
            try:
                importo = Decimal(str(dati[campo.chiave]).replace(",", "."))
                if importo < 0 or importo.as_tuple().exponent < -2:
                    raise InvalidOperation
            except (InvalidOperation, ValueError):
                esiti.append(Esito("IMPORTO", "errore", f"«{campo.etichetta}»: importo in euro con al massimo due decimali."))
    if richiesta.atto.upper() == "P18":
        if all(_vuoto(dati.get(k)) or str(dati.get(k)) == "0" for k in ("anni", "mesi", "giorni")):
            esiti.append(Esito("PENA", "errore", "Indica almeno anni, mesi o giorni della pena."))
        pecuniaria = str(dati.get("pena_pecuniaria") or "")
        tipo_pena = str(dati.get("tipo_pena") or "")
        if pecuniaria and ((tipo_pena == "Reclusione" and pecuniaria != "Multa") or (tipo_pena == "Arresto" and pecuniaria != "Ammenda")):
            esiti.append(Esito("PENA_PECUNIARIA", "errore", "Con la reclusione la pena pecuniaria è la multa; con l'arresto l'ammenda."))
        if pecuniaria and _vuoto(dati.get("importo")):
            esiti.append(Esito("IMPORTO_MANCANTE", "errore", "Indica l'importo della pena pecuniaria."))


def _controlla_soggetti(richiesta: Richiesta, voce: catalogo.VoceAtto, esiti: list[Esito]) -> None:
    if not richiesta.soggetti:
        esiti.append(Esito("SOGGETTI", "errore", "Associa almeno un soggetto rappresentato: ogni deposito PDP è fatto nel suo interesse."))
        return
    non_idonei = [s.get("nome") or "soggetto" for s in richiesta.soggetti
                  if not catalogo.ammesso_per_ruoli(voce, [str(s.get("ruolo") or "")])]
    if non_idonei:
        esiti.append(Esito("RUOLO", "errore", f"L'atto non è ammesso per il ruolo di: {', '.join(non_idonei)}."))
    if regola_per(richiesta.atto).un_solo_soggetto and len(richiesta.soggetti) != 1:
        esiti.append(Esito("UN_SOGGETTO", "errore", "La richiesta di certificato ammette un solo soggetto."))


def _controlla_composizione(richiesta: Richiesta, voce: catalogo.VoceAtto | None, esiti: list[Esito]) -> None:
    ruoli = [f.ruolo for f in richiesta.file]
    principali = ruoli.count("principale")
    if principali == 0:
        esiti.append(Esito("ATTO_MANCANTE", "errore", "Aggiungi l'atto principale firmato."))
    elif principali > 1:
        esiti.append(Esito("PIU_ATTI", "errore", "Il PDP accetta un solo atto principale: gli altri vanno come contestuali o allegati."))
    totale = sum(len(f.dati) for f in richiesta.file)
    if totale > LIMITE_DEPOSITO:
        esiti.append(Esito("DEPOSITO_GRANDE", "errore", "Il deposito supera 500 MB complessivi (art. 5 co. 6)."))
    if "contestuale" in ruoli and not (voce and voce.contestuali):
        esiti.append(Esito("CONTESTUALI", "errore", "Per questo atto il PDP non prevede atti contestuali."))
    if voce and voce.contestuali and voce.contestuali != "*":
        estranei = [f.nome for f in richiesta.file if f.ruolo == "contestuale" and f.tipo_atto and f.tipo_atto not in voce.contestuali]
        if estranei:
            esiti.append(Esito("CONTESTUALE_NON_AMMESSO", "errore", f"Atto contestuale non ammesso con questo deposito: {', '.join(estranei)}."))
    if any(f.ruolo == "contestuale" and not f.tipo_atto for f in richiesta.file):
        esiti.append(Esito("TIPO_CONTESTUALE", "errore", "Indica il tipo di ogni atto contestuale: il PDP lo chiede."))
    procura = regola_per(richiesta.atto).procura_speciale
    if procura and not richiesta.procura_speciale_dichiarata and "allegato" not in ruoli:
        testo = ("l'atto comprende nomina o procura speciale" if procura == "nomina_o_procura"
                 else "la procura speciale è nell'atto o già in atti")
        esiti.append(Esito("PROCURA_SPECIALE", "errore", f"Conferma che {testo}, oppure allega la procura speciale."))
    in_procura = richiesta.ufficio.upper() in PROCURE
    richiede_abilitante = e_nomina(richiesta.atto) and in_procura and not richiesta.avviso_indagini_presente
    if richiede_abilitante and "abilitante" not in ruoli:
        esiti.append(Esito("ABILITANTE", "errore",
                           "Nomina in Procura senza avviso 408, 411 o 415-bis nel fascicolo: allega l'atto abilitante (art. 5 co. 5)."))
    if "abilitante" in ruoli and not (e_nomina(richiesta.atto) and in_procura):
        esiti.append(Esito("ABILITANTE_SUPERFLUO", "avviso", "L'atto abilitante serve solo alla nomina presso la Procura."))


GIP_DELLA_PROCURA = {"PM-U": "GIP-U", "PMM-U": "GIPM-U"}


def _controlla_destinatario(richiesta: Richiesta, esiti: list[Esito]) -> None:
    """Nomina verso un ufficio dove il procedimento non pende.

    Caso reale (PDP, dicembre 2023): nomina con registro «PM: N» inviata al
    Tribunale ordinario, rifiutata con motivazione «Ufficio destinatario non
    coerente». Finché il procedimento è iscritto solo in Procura la nomina va
    alla Procura, o al GIP se il procedimento è davanti a lui.
    """
    registri = {u.upper() for u in richiesta.uffici_registro if u}
    ufficio = richiesta.ufficio.upper()
    if not e_nomina(richiesta.atto) or not registri or ufficio in registri or not registri <= PROCURE | {"PGCAP-U"}:
        return
    if ufficio in {GIP_DELLA_PROCURA.get(r) for r in registri} or (ufficio == "PGCAP-U" and richiesta.avocato_pg):
        return
    esiti.append(Esito("UFFICIO_NON_COERENTE", "avviso",
                       "Il procedimento risulta iscritto solo in Procura: la nomina va alla Procura (o al GIP se il procedimento "
                       "pende davanti a lui). Il PDP rifiuta questi depositi con «Ufficio destinatario non coerente»."))


def controlla(richiesta: Richiesta) -> dict[str, Any]:
    """Esegue tutti i controlli e dice se il deposito è pronto per il portale."""
    esiti: list[Esito] = []
    voce = catalogo.voce(richiesta.atto)
    if voce is None:
        esiti.append(Esito("ATTO_SCONOSCIUTO", "errore", "Atto non presente nel catalogo ufficiale del PDP."))
    else:
        ammessi = {v.codice for v in catalogo.atti_ammessi(richiesta.ufficio, avocato_pg=richiesta.avocato_pg)}
        if voce.codice not in ammessi:
            esiti.append(Esito("UFFICIO", "errore", "Il PDP non consente questo atto verso l'ufficio scelto."))
        if not voce.principale and not richiesta.procedimento_autorizzato:
            esiti.append(Esito("NON_AUTORIZZATO", "errore",
                               "Gli atti successivi si depositano solo sui procedimenti autorizzati: deposita prima la nomina "
                               "oppure aggiorna l'elenco dei procedimenti autorizzati sul PDP."))
        _controlla_soggetti(richiesta, voce, esiti)
        _controlla_destinatario(richiesta, esiti)
    _controlla_dati(richiesta, esiti)
    _controlla_composizione(richiesta, voce, esiti)
    for file in richiesta.file:
        controlla_file(file, cf_avvocato=richiesta.cf_avvocato, avvocatura_stato=richiesta.avvocatura_stato)
        esiti.extend(file.esiti)
    esiti.append(Esito("REVOCA", "info", "La revoca del certificato la verifica il PDP al momento dell'invio."))
    errori = sum(1 for e in esiti if e.livello == "errore")
    avvisi = sum(1 for e in esiti if e.livello == "avviso")
    return {
        "pronto": errori == 0,
        "errori": errori,
        "avvisi": avvisi,
        "esiti": [e.to_dict() for e in esiti],
        "file": [
            {"ruolo": f.ruolo, "nome": f.nome, "oggetto": f.oggetto, "documentoId": f.documento_id, "tipoAtto": f.tipo_atto,
             "dimensione": len(f.dati), "sha256": f.sha256, "firmatari": f.firmatari}
            for f in richiesta.file
        ],
    }


def avviso_indagini_nei_titoli(titoli: Iterable[str]) -> bool:
    """C'è già un avviso 408, 411 o 415-bis fra i documenti del fascicolo? (art. 5 co. 5)."""
    schema = re.compile(r"415[\s-]*bis|conclusione\s+(delle\s+)?indagini|richiesta\s+di\s+archiviazione|\b408\b|\b411\b", re.I)
    return any(schema.search(str(t or "")) for t in titoli)


__all__ = ["Richiesta", "avviso_indagini_nei_titoli", "controlla"]
