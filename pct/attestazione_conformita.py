"""Attestazione di conformità del difensore, scritta sul PDF e poi firmata digitalmente.

Base normativa: D.Lgs. 82/2005 (CAD) art. 22, comma 2 (copia informatica di documento analogico) e
art. 23-bis, comma 2 (copia informatica di documento informatico); potere di attestazione del
difensore: art. 196-octies disp. att. c.p.c. e, nel processo amministrativo, art. 136, comma 2-ter,
c.p.a. L'attestazione si inserisce nella copia informatica e si sottoscrive con firma digitale.

Come nella prassi (la procura attestata allegata dall'avvocato il 28/09/2026): l'avvocato apre il
documento nel lettore e disegna col mouse due riquadri, uno per l'attestazione (titolo, formula,
luogo e data, «Avv. Cognome Nome», «(sottoscrizione tramite firma digitale)») e uno per la firma
testo, il suo nome e cognome sotto «Vera ed autentica». Carattere e dimensione si scelgono per
ciascuno. Senza riquadro l'attestazione va nello spazio libero dell'ultima pagina o, se non c'è
posto, in una pagina aggiunta. Poi il documento si firma in PAdES con la firma visibile
«Per autentica e sottoscrizione» in basso. Le pagine restano quelle dell'originale: si aggiunge testo.
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass
from datetime import date
from typing import Any

from pct.attestazione_disegno import CALLIGRAFICI, CARATTERI, STILI, blocco_nel_riquadro, blocco_testo, firma_nel_riquadro, font

TIPI = {
    "analogico": "all’originale analogico",
    "informatico": "al documento informatico",
}
TITOLO = "ATTESTAZIONE DI CONFORMITA’"
FORMULA = ("Il sottoscritto Avv. {avvocato} attesta, ai sensi di legge, che la presente copia "
           "informatica è conforme {origine} dal quale è estratta.")
DICITURA_FIRMA = "(sottoscrizione tramite firma digitale)"
POSIZIONI = {"spazio_libero": "Nello spazio libero dell’ultima pagina", "pagina": "In una pagina aggiunta"}
_ALIAS_POSIZIONE = {"fondo": "spazio_libero", "ultima": "spazio_libero"}
MARGINE = 56.7  # 2 cm
#: Il fondo della pagina resta alla firma visibile «Per autentica e sottoscrizione».
RISERVA_FIRMA_VISIBILE = 72.0
_LATO_MINIMO = 0.01


@dataclass(frozen=True)
class Riquadro:
    """Riquadro disegnato dall'avvocato: pagina (da 1) e frazioni della pagina dall'angolo in alto a sinistra."""

    pagina: int
    x: float
    y: float
    larghezza: float
    altezza: float

    @classmethod
    def da_dati(cls, dati: Any, nome: str) -> "Riquadro | None":
        if not dati:
            return None
        if not isinstance(dati, dict):
            raise ValueError(f"Riquadro {nome} non valido.")
        try:
            riquadro = cls(pagina=int(dati.get("pagina") or 0), x=float(dati.get("x")), y=float(dati.get("y")),
                           larghezza=float(dati.get("larghezza")), altezza=float(dati.get("altezza")))
        except (TypeError, ValueError) as exc:
            raise ValueError(f"Riquadro {nome} non valido.") from exc
        dentro = 0 <= riquadro.x and 0 <= riquadro.y and riquadro.x + riquadro.larghezza <= 1.0001 \
            and riquadro.y + riquadro.altezza <= 1.0001
        if riquadro.pagina < 1 or not dentro or min(riquadro.larghezza, riquadro.altezza) < _LATO_MINIMO:
            raise ValueError(f"Riquadro {nome} fuori dalla pagina o troppo piccolo: disegnalo di nuovo.")
        return riquadro


@dataclass(frozen=True)
class Attestazione:
    avvocato: str
    firma: str
    luogo: str
    data: date
    tipo: str = "analogico"
    testo: str = ""
    carattere_testo: str = "arial"
    dimensione_testo: float = 12
    testo_firma: str = ""
    carattere_firma: str = "arial"
    stile_firma: str = "normale"
    dimensione_firma: float = 14
    posizione: str = "spazio_libero"
    riquadro_attestazione: Riquadro | None = None
    riquadro_firma: Riquadro | None = None

    def testo_attestazione(self) -> str:
        """La formula (o il testo scritto dall'avvocato) con nome e tipo di originale."""
        origine = TIPI.get(self.tipo, TIPI["analogico"])
        return (self.testo or FORMULA).replace("{avvocato}", self.avvocato).replace("{origine}", origine)

    def luogo_data(self) -> str:
        return f"{self.luogo}, {self.data.strftime('%d.%m.%Y')}"

    def paragrafi(self) -> list[str]:
        return [TITOLO, self.testo_attestazione(), self.luogo_data(), f"Avv. {self.firma}", DICITURA_FIRMA]


@dataclass(frozen=True)
class Esito:
    pdf: bytes
    pagina: int
    pagina_aggiunta: bool
    dimensione_testo: float
    dimensione_firma: float | None = None
    pagine: tuple[int, ...] = ()

    def descrizione(self) -> str:
        if self.pagina_aggiunta:
            testo = "Nell’ultima pagina non c’era spazio: l’attestazione è in una pagina aggiunta."
        else:
            testo = f"Attestazione scritta a pagina {self.pagina}."
        if self.dimensione_firma is not None:
            testo += " Firma testo sotto «Vera ed autentica» inserita."
        return testo


def cognome_nome(nome: str) -> str:
    """«Giuseppe Montagnese» → «Montagnese Giuseppe», come si firma l'attestazione."""
    parti = nome.split()
    return " ".join([parti[-1], *parti[:-1]]) if len(parti) == 2 else nome


def da_dati(dati: dict[str, Any], *, avvocato: str = "", luogo: str = "") -> Attestazione:
    """Valida le scelte dell'avvocato (valori ammessi, dimensioni ragionevoli, data reale, riquadri)."""
    def testo(chiave: str, predefinito: str = "", massimo: int = 200) -> str:
        valore = re.sub(r"[ \t]+", " ", str(dati.get(chiave) or predefinito)).strip()
        if len(valore) > massimo:
            raise ValueError(f"Il campo «{chiave}» è troppo lungo.")
        return valore

    def numero(chiave: str, predefinito: float, minimo: float, massimo: float) -> float:
        try:
            valore = float(str(dati.get(chiave) or predefinito).replace(",", "."))
        except ValueError as exc:
            raise ValueError(f"Dimensione non valida: {chiave}.") from exc
        if not minimo <= valore <= massimo:
            raise ValueError(f"La dimensione deve essere tra {minimo:g} e {massimo:g} punti.")
        return valore

    nome = testo("avvocato", avvocato, 120)
    if not nome:
        raise ValueError("Indica il nome dell'avvocato che attesta.")
    sede = testo("luogo", luogo, 80)
    if not sede:
        raise ValueError("Indica il luogo dell'attestazione.")
    grezza = testo("data", date.today().isoformat(), 10)
    try:
        giorno = date.fromisoformat(grezza)
    except ValueError as exc:
        raise ValueError("Data dell'attestazione non valida.") from exc
    tipo = testo("tipo", "analogico", 20)
    carattere_testo, carattere_firma = testo("carattereTesto", "arial", 20), testo("carattereFirma", "arial", 20)
    stile_firma = testo("stileFirma", "normale", 20)
    posizione = testo("posizione", "spazio_libero", 20)
    posizione = _ALIAS_POSIZIONE.get(posizione, posizione)
    if tipo not in TIPI or carattere_testo not in CARATTERI or carattere_firma not in {**CARATTERI, **CALLIGRAFICI}:
        raise ValueError("Scelta non prevista per tipo o carattere.")
    if stile_firma not in STILI or posizione not in POSIZIONI:
        raise ValueError("Scelta non prevista per stile della firma o posizione.")
    riquadro_firma = Riquadro.da_dati(dati.get("riquadroFirma"), "della firma")
    testo_firma = testo("testoFirma", nome, 120) or nome
    return Attestazione(
        avvocato=nome, firma=testo("firma", cognome_nome(nome), 120) or cognome_nome(nome), luogo=sede, data=giorno,
        tipo=tipo, testo=testo("testo", "", 1200), carattere_testo=carattere_testo,
        dimensione_testo=numero("dimensioneTesto", 12, 7, 16), testo_firma=testo_firma, carattere_firma=carattere_firma,
        stile_firma=stile_firma, dimensione_firma=numero("dimensioneFirma", 14, 7, 40), posizione=posizione,
        riquadro_attestazione=Riquadro.da_dati(dati.get("riquadroAttestazione"), "dell'attestazione"),
        riquadro_firma=riquadro_firma,
    )


def _in_punti(riquadro: Riquadro, pagina: Any) -> tuple[float, float, float, float]:
    """Riquadro in punti PDF: x sinistra, y alto (origine in basso a sinistra), larghezza, altezza."""
    box = pagina.cropbox
    larghezza, altezza = float(box.width), float(box.height)
    return (float(box.left) + riquadro.x * larghezza, float(box.bottom) + (1 - riquadro.y) * altezza,
            riquadro.larghezza * larghezza, riquadro.altezza * altezza)


def _sovrapponi(scrittore: Any, indice: int, disegni: list[Any]) -> None:
    from pypdf import PdfReader
    from reportlab.pdfgen import canvas

    pagina = scrittore.pages[indice]
    box = pagina.mediabox
    buffer = io.BytesIO()
    tela = canvas.Canvas(buffer, pagesize=(float(box.right), float(box.top)))
    for disegno in disegni:
        disegno(tela)
    tela.showPage()
    tela.save()
    pagina.merge_page(PdfReader(io.BytesIO(buffer.getvalue())).pages[0])


def applica_con_esito(pdf: bytes, att: Attestazione, *, riserva_basso: float = RISERVA_FIRMA_VISIBILE) -> Esito:
    """Scrive attestazione e firma testo nei riquadri scelti, o l'attestazione nello spazio libero."""
    from pypdf import PdfReader, PdfWriter

    from pct import attestazione_spazio

    lettore = PdfReader(io.BytesIO(pdf))
    if lettore.is_encrypted:
        raise ValueError("Il PDF è protetto da password: sbloccalo prima di attestarne la conformità.")
    scrittore = PdfWriter(clone_from=lettore)
    totale = len(scrittore.pages)
    for riquadro in (att.riquadro_attestazione, att.riquadro_firma):
        if riquadro and riquadro.pagina > totale:
            raise ValueError(f"Il documento ha {totale} pagine: il riquadro è a pagina {riquadro.pagina}.")
    corpo = font(att.carattere_testo, "normale")
    disegni: dict[int, list[Any]] = {}
    pagina_aggiunta = False

    if att.riquadro_attestazione:
        indice = att.riquadro_attestazione.pagina - 1
        x, y, larghezza, altezza = _in_punti(att.riquadro_attestazione, scrittore.pages[indice])
        blocco = blocco_nel_riquadro(att.paragrafi(), corpo, att.dimensione_testo, larghezza, altezza)
        disegni.setdefault(indice, []).append(lambda tela, b=blocco, x=x, y=y: b.disegna(tela, x, y))
    else:
        ultima = scrittore.pages[-1]
        larghezza_pagina = float(ultima.cropbox.width)
        blocco = blocco_testo(att.paragrafi(), corpo, att.dimensione_testo,
                              max(min(larghezza_pagina * 0.5, larghezza_pagina - 2 * MARGINE), 220.0))
        spazio = None
        if att.posizione == "spazio_libero":
            spazio = attestazione_spazio.cerca(pdf, blocco.larghezza, blocco.altezza, riserva_basso=riserva_basso)
        if spazio is not None:
            x, y = float(ultima.cropbox.left) + spazio.x, float(ultima.cropbox.bottom) + spazio.y_alto
            indice = totale - 1
            disegni.setdefault(indice, []).append(lambda tela, b=blocco, x=x, y=y: b.disegna(tela, x, y))
        else:
            box = ultima.mediabox
            scrittore.add_blank_page(width=float(box.width), height=float(box.height))
            indice, pagina_aggiunta = totale, True
            disegni.setdefault(indice, []).append(
                lambda tela, b=blocco, a=float(box.height): b.disegna(tela, MARGINE, a - MARGINE))
    pagina_attestazione = indice + 1

    dimensione_firma = None
    if att.riquadro_firma:
        indice_firma = att.riquadro_firma.pagina - 1
        x, y, larghezza, altezza = _in_punti(att.riquadro_firma, scrittore.pages[indice_firma])
        firma = firma_nel_riquadro(att.testo_firma, font(att.carattere_firma, att.stile_firma),
                                   att.dimensione_firma, larghezza, altezza)
        dimensione_firma = firma.dimensione
        disegni.setdefault(indice_firma, []).append(lambda tela, f=firma, x=x, y=y: f.disegna(tela, x, y))

    for indice_pagina, elenco in sorted(disegni.items()):
        _sovrapponi(scrittore, indice_pagina, elenco)
    uscita = io.BytesIO()
    scrittore.write(uscita)
    return Esito(pdf=uscita.getvalue(), pagina=pagina_attestazione, pagina_aggiunta=pagina_aggiunta,
                 dimensione_testo=blocco.dimensione, dimensione_firma=dimensione_firma,
                 pagine=tuple(sorted(indice_pagina + 1 for indice_pagina in disegni)))


def applica(pdf: bytes, att: Attestazione) -> bytes:
    return applica_con_esito(pdf, att).pdf


def opzioni() -> dict[str, Any]:
    return {
        "tipi": [{"id": k, "etichetta": f"Copia informatica conforme {v}"} for k, v in TIPI.items()],
        "caratteri": [{"id": k, "etichetta": v[0]} for k, v in CARATTERI.items()],
        "caratteriFirma": [{"id": k, "etichetta": v[0]} for k, v in {**CARATTERI, **CALLIGRAFICI}.items()],
        "stiliFirma": [{"id": s, "etichetta": s.replace("_", " ").capitalize()} for s in STILI],
        "posizioni": [{"id": k, "etichetta": v} for k, v in POSIZIONI.items()],
        "formula": FORMULA,
        "titolo": TITOLO,
        "dicituraFirma": DICITURA_FIRMA,
    }


__all__ = ["Attestazione", "CARATTERI", "Esito", "FORMULA", "Riquadro", "applica", "applica_con_esito",
           "cognome_nome", "da_dati", "opzioni"]
