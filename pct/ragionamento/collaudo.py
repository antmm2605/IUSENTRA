"""Controlli del contratto del motore, riutilizzabili dalla Lettura e nei replay."""

from .modello import Conclusione, Dubbio, STATI
from .testo import giorno


def verifica_conclusione(voce: Conclusione) -> list[Dubbio]:
    """Indica il riscontro mancante, mantenendo distinti dati e decisioni del motore."""
    fonte = voce.letto
    mancanze = []
    if not (fonte and fonte.oggetto_id and fonte.brano and giorno(fonte.data)):
        mancanze.append(("fonte", "Identificativo, passaggio o data della fonte incompleti.",
                         "il documento o l'evento con il passaggio e la data pertinenti"))
    if not voce.norme or any(not n.get("norma") or not n.get("url") for n in voce.norme):
        mancanze.append(("norma", "Riferimento normativo incompleto.",
                         "l'articolo applicabile con la fonte ufficiale"))
    if not voce.cosa.strip():
        mancanze.append(("adempimento", "Adempimento indeterminato.", "l'azione precisa richiesta"))
    if not voce.come.strip():
        mancanze.append(("modalita", "Modalità dell'adempimento indeterminata.", "il canale o la procedura applicabile"))
    if not voce.perche.strip():
        mancanze.append(("conseguenza", "Conseguenza giuridica indeterminata.",
                         "l'effetto previsto dalla norma o dal provvedimento"))
    if voce.stato not in STATI or (voce.stato in {"fatto", "non_dovuto"} and not voce.prova_o_motivo.strip()):
        mancanze.append(("stato", "Stato dell'adempimento privo di riscontro.",
                         "la prova dell'esecuzione o il motivo per cui l'azione non è dovuta"))
    if voce.stato == "dubbio" and not any(d.testo and d.manca for d in voce.dubbi):
        mancanze.append(("dubbio", "Motivo della verifica incompleto.", "il fatto da verificare e la relativa fonte"))
    t = voce.termine
    if t is None and not voce.motivo_senza_termine:
        mancanze.append(("termine", "Termine indeterminato o senza qualificazione.",
                         "il fatto iniziale e la regola di computo, oppure il motivo per cui il termine non si applica"))
    elif t is not None and (
        not giorno(t.scadenza) or not giorno(t.decorrenza) or not t.evento_decorrenza or not t.computo
        or not t.sospensione_feriale or (t.perentorio is None and not t.natura) or t.giorni_residui is None
        or (t.scaduto and not t.natura and not (t.conseguenze and t.rimedi))
    ):
        mancanze.append(("termine", "Computo o conseguenze del termine incompleti.",
                         "la decorrenza, la scadenza, la natura del termine e gli effetti o rimedi applicabili"))
    return [Dubbio(f"contratto_{campo}", testo, manca, fonte) for campo, testo, manca in mancanze]
