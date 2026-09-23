"""DatiAtto.xml degli atti di parte Cassazione v21 predisposti (vedi pct.cassazione_atti_v21).

Struttura presa da `docs/specs/ministero/parte/parte_v21/Parte-cassazione.xsd` e
`base_v21/tipi-base.xsd`:
- istanze (AttoProcedimento): solo riferimento al procedimento e IndiceBusta;
- IstanzaOscuramento: codice fiscale della parte e tipologia di oscuramento;
- RicorsoErroreMateriale, RevocazioneExArt391ter, RevocazioneExArt391quater (AttoIntroduttivo):
  date di notifica, provvedimento della Corte impugnato, materia, spese di giustizia, anagrafica,
  motivi di revocazione con il numero dell'art. 395 o dell'art. 391-quater, DocumentiECLI.

Il mixin e usato da `pct.busta.BustaTelematica`: finche gli atti non sono attivati ogni tentativo
di generazione si ferma con un messaggio per l'avvocato.
"""

from __future__ import annotations

import re
from copy import deepcopy
from typing import Any

from lxml import etree

from pct.cassazione_atti_v21 import (
    CASSAZIONE_ATTI_V21_NON_ATTIVI_MESSAGE,
    MOTIVI_REVOCAZIONE,
    ROOT_OSCURAMENTO,
    ROOT_RICHIESTA_VISIBILITA,
    ROOTS_INTRODUTTIVI,
    ROOTS_PROCEDIMENTO_SEMPLICE,
    cassazione_atti_v21_attivi,
)
from pct.cassazione_xsd_tables import (
    CASSAZIONE_ATTI_NS,
    CASSAZIONE_PARTE_NS,
    CASSAZIONE_TIPI_NS,
    cassazione_enumeration_values,
    cassazione_parte_child_enumeration,
)

_CODICE_FISCALE_RE = re.compile(r"[A-Z]{6}[0-9]{2}[A-Z][0-9]{2}[A-Z][0-9]{3}[A-Z]|[0-9]{11}")


class CassazioneAttiV21DatiAttoMixin:
    """Metodi DatiAtto per gli atti Cassazione v21; richiede gli helper di BustaTelematica."""

    def _aggiungi_dati_atti_cassazione_v21(self, root: etree._Element) -> bool:
        if not cassazione_atti_v21_attivi():
            raise ValueError(CASSAZIONE_ATTI_V21_NON_ATTIVI_MESSAGE)
        root_name = self._datiatto_root_name()
        if root_name in ROOTS_PROCEDIMENTO_SEMPLICE:
            return True
        if root_name == ROOT_RICHIESTA_VISIBILITA:
            self._aggiungi_richiesta_visibilita_cassazione_v21(root)
            return True
        if root_name == ROOT_OSCURAMENTO:
            self._aggiungi_oscuramento_cassazione_v21(root)
            return True
        if root_name in ROOTS_INTRODUTTIVI:
            self._aggiungi_introduttivo_cassazione_v21(root, root_name)
            return True
        raise ValueError(
            f"Generatore Cassazione v21 non disponibile per la radice ministeriale {root_name!r}."
        )

    def _aggiungi_richiesta_visibilita_cassazione_v21(self, root: etree._Element) -> None:
        anagrafica = self._anagrafica_procedimento_node()
        parti = anagrafica.xpath(
            "./*[local-name()='Partecipanti']/*[local-name()='Parte']"
        )
        avvocati = anagrafica.xpath(
            "./*[local-name()='Soggetti']/*[local-name()='Avvocato']"
        )
        if not parti:
            raise ValueError(
                "Parte assistita mancante nell'anagrafica della richiesta di visibilità Cassazione."
            )
        parte_source = parti[0]
        parte_id = str(parte_source.get("ID") or "").strip()
        if not parte_id:
            raise ValueError(
                "Identificativo della parte mancante nella richiesta di visibilità Cassazione."
            )

        avvocato_source = next(
            (
                avvocato
                for avvocato in avvocati
                if parte_id
                in {
                    str(ref or "").strip()
                    for ref in avvocato.xpath(
                        "./*[local-name()='parteRappresentata']/@ref"
                    )
                }
            ),
            None,
        )
        if avvocato_source is None:
            raise ValueError(
                "Avvocato collegato alla parte mancante nella richiesta di visibilità Cassazione."
            )

        parte = deepcopy(parte_source)
        parte.tag = f"{{{CASSAZIONE_PARTE_NS}}}Parte"
        avvocato = deepcopy(avvocato_source)
        avvocato.tag = f"{{{CASSAZIONE_PARTE_NS}}}Avvocato"
        for riferimento in list(
            avvocato.xpath("./*[local-name()='parteRappresentata']")
        ):
            if str(riferimento.get("ref") or "").strip() != parte_id:
                avvocato.remove(riferimento)
        if not avvocato.xpath(
            "./*[local-name()='parteRappresentata'][@ref=$parte_id]",
            parte_id=parte_id,
        ):
            raise ValueError(
                "Riferimento della parte rappresentata mancante nella richiesta di visibilità Cassazione."
            )

        root.append(parte)
        root.append(avvocato)

    def _aggiungi_oscuramento_cassazione_v21(self, root: etree._Element) -> None:
        codice = re.sub(r"\s+", "", self._required_extra_text(
            "oscuramento_parte_codice_fiscale", "Codice fiscale della parte da oscurare"
        )).upper()
        if not _CODICE_FISCALE_RE.fullmatch(codice):
            raise ValueError("Codice fiscale della parte da oscurare non valido.")
        tipologia = self._required_extra_text("oscuramento_tipologia", "Tipologia di oscuramento")
        ammesse = {value for value, _ in cassazione_parte_child_enumeration(ROOT_OSCURAMENTO, "Privacy")}
        if tipologia not in ammesse:
            raise ValueError("Tipologia di oscuramento non valida: seleziona una voce ministeriale.")
        etree.SubElement(root, f"{{{CASSAZIONE_PARTE_NS}}}Parte").text = codice
        etree.SubElement(root, f"{{{CASSAZIONE_PARTE_NS}}}Privacy").text = tipologia

    def _aggiungi_introduttivo_cassazione_v21(self, root: etree._Element, root_name: str) -> None:
        request_date = self._required_extra_text("data_richiesta_notifica_cassazione", "Data della prima notifica")
        # Obbligatoria nello XSD v21 e distinta dalla prima notifica: non si ricava in automatico.
        effective_date = self._required_extra_text(
            "data_effettiva_notifica_cassazione", "Data di perfezionamento dell'ultima notifica"
        )
        etree.SubElement(root, f"{{{CASSAZIONE_PARTE_NS}}}dataRichiestaNotifica").text = self._format_date_field(
            request_date, "Data della prima notifica"
        )
        etree.SubElement(root, f"{{{CASSAZIONE_PARTE_NS}}}dataEffettivaNotifica").text = self._format_date_field(
            effective_date, "Data di perfezionamento della notifica"
        )
        self._aggiungi_provvedimento_impugnato_cassazione(root)
        self._aggiungi_inizio_primo_grado_cassazione(root, required=False)
        self._aggiungi_materia_cassazione(root)
        if self.dati.valore_causa is not None:
            etree.SubElement(root, f"{{{CASSAZIONE_PARTE_NS}}}valoreCausa").text = f"{float(self.dati.valore_causa):.2f}"
        self._aggiungi_spese_giustizia_cassazione(root, integration=False)
        if not root.xpath("./*[local-name()='speseGiustizia']"):
            raise ValueError("Spese di giustizia non definite: indica pagamento, debito o esenzione.")
        root.append(self._anagrafica_procedimento_node())
        if root_name in MOTIVI_REVOCAZIONE:
            self._aggiungi_motivi_revocazione_cassazione_v21(root, root_name)
        etree.SubElement(root, f"{{{CASSAZIONE_ATTI_NS}}}DocumentiECLI")

    def _aggiungi_motivi_revocazione_cassazione_v21(self, root: etree._Element, root_name: str) -> None:
        container_name, item_name, article_type = MOTIVI_REVOCAZIONE[root_name]
        raw = self._datiatto_extra().get("motivi_revocazione_cassazione")
        items = [item for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
        if not items:
            raise ValueError("Motivi di revocazione mancanti: inserisci almeno un motivo prima di generare la busta.")
        allowed = cassazione_enumeration_values(article_type)
        container = etree.SubElement(root, f"{{{CASSAZIONE_TIPI_NS}}}{container_name}")
        for index, item in enumerate(items, start=1):
            number = str(item.get("numero") or index).strip()
            article = str(item.get("numero_articolo") or "").strip()
            if not number or article not in allowed:
                raise ValueError("Numero del motivo o riferimento normativo del motivo di revocazione non validi.")
            attrs: dict[str, Any] = {"numeroMotivo": number}
            page = str(item.get("pagina") or "").strip()
            if page:
                if not page.isdigit() or int(page) <= 0:
                    raise ValueError("Pagina del motivo di revocazione non valida.")
                attrs["riferimentoPagina"] = page
            # tipi-base.xsd v21 usa l'attributo numeroArt395 per entrambi i tipi di revocazione.
            attrs["numeroArt395"] = article
            node = etree.SubElement(container, f"{{{CASSAZIONE_TIPI_NS}}}{item_name}", **attrs)
            self._append_text_if_present(node, CASSAZIONE_TIPI_NS, "descrizione", item.get("descrizione"))


__all__ = ["CassazioneAttiV21DatiAttoMixin"]
