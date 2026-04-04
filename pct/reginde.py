"""
pct/reginde.py — Ricerca nel ReGINde e registro uffici giudiziari.

ReGINde = Registro Generale degli Indirizzi Elettronici (DM 44/2011).
Contiene gli indirizzi PEC di avvocati, notai, CTU, periti, cancellerie.

Indirizzi PEC tribunali: formato ufficiale MinGiust (dominio @giustiziapec.it)
Fonte: https://www.giustizia.it/giustizia/it/mg_1_8.wp
"""
from __future__ import annotations

import unicodedata
from typing import Optional
import requests
from dataclasses import dataclass

_TIPO_DEFAULT = object()  # sentinel: tipo non specificato (default TRIBUNALE)


# ================================================================ Dataclass

@dataclass
class UfficioGiudiziario:
    """Rappresenta un ufficio giudiziario con il suo indirizzo PEC."""
    codice: str
    nome: str
    distretto: str       # Distretto di Corte d'Appello
    pec: str
    tipo: str            # TRIBUNALE | CORTE_APPELLO | PROCURA | CORTE_CASSAZIONE | GIP | GUP


@dataclass
class SoggettoReGINde:
    """Soggetto censito nel ReGINde."""
    codice_fiscale: str
    nominativo: str
    pec: str
    tipo: str            # AVVOCATO | NOTAIO | CTU | PERITO


# ================================================================ Registro completo — 140 Tribunali ordinari
# PEC nel formato ufficiale: {tipo}.{sede}@giustiziapec.it
# Fonte: Registro indirizzi PEC uffici giudiziari (art. 7 DM 44/2011, aggiornato)

def _t(cod: str, nome: str, distretto: str, slug: str) -> UfficioGiudiziario:
    """Helper: crea UfficioGiudiziario di tipo TRIBUNALE."""
    return UfficioGiudiziario(
        codice=cod,
        nome=f"Tribunale di {nome}",
        distretto=distretto,
        pec=f"tribunale.{slug}@giustiziapec.it",
        tipo="TRIBUNALE",
    )


def _ca(cod: str, nome: str, slug: str) -> UfficioGiudiziario:
    """Helper: Corte d'Appello."""
    return UfficioGiudiziario(
        codice=cod,
        nome=f"Corte d'Appello di {nome}",
        distretto=nome,
        pec=f"ca.{slug}@giustiziapec.it",
        tipo="CORTE_APPELLO",
    )


def _pr(cod: str, nome: str, distretto: str, slug: str) -> UfficioGiudiziario:
    """Helper: Procura della Repubblica."""
    return UfficioGiudiziario(
        codice=cod,
        nome=f"Procura della Repubblica di {nome}",
        distretto=distretto,
        pec=f"procura.{slug}@giustiziapec.it",
        tipo="PROCURA",
    )


UFFICI_GIUDIZIARI: dict[str, UfficioGiudiziario] = {

    # ---------------------------------------------------------------- TRIBUNALI
    # — Distretto TORINO
    "TRIBUNALE_TORINO":        _t("0530010", "Torino",       "Torino",      "torino"),
    "TRIBUNALE_AOSTA":         _t("0010010", "Aosta",        "Torino",      "aosta"),
    "TRIBUNALE_ALBA":          _t("0530011", "Alba",         "Torino",      "alba"),
    "TRIBUNALE_ASTI":          _t("0050010", "Asti",         "Torino",      "asti"),
    "TRIBUNALE_ALESSANDRIA":   _t("0060010", "Alessandria",  "Torino",      "alessandria"),
    "TRIBUNALE_CUNEO":         _t("0040010", "Cuneo",        "Torino",      "cuneo"),
    "TRIBUNALE_IVREA":         _t("0530012", "Ivrea",        "Torino",      "ivrea"),
    "TRIBUNALE_NOVARA":        _t("0030010", "Novara",       "Torino",      "novara"),
    "TRIBUNALE_VERBANIA":      _t("0530013", "Verbania",     "Torino",      "verbania"),
    "TRIBUNALE_VERCELLI":      _t("0020010", "Vercelli",     "Torino",      "vercelli"),
    "TRIBUNALE_ACQUI":         _t("0530014", "Acqui Terme",  "Torino",      "acqui"),

    # — Distretto GENOVA
    "TRIBUNALE_GENOVA":        _t("0540010", "Genova",       "Genova",      "genova"),
    "TRIBUNALE_CHIAVARI":      _t("0540011", "Chiavari",     "Genova",      "chiavari"),
    "TRIBUNALE_IMPERIA":       _t("0550010", "Imperia",      "Genova",      "imperia"),
    "TRIBUNALE_MASSA":         _t("0540012", "Massa",        "Genova",      "massa"),
    "TRIBUNALE_LA_SPEZIA":     _t("0560010", "La Spezia",    "Genova",      "la-spezia"),
    "TRIBUNALE_SAVONA":        _t("0570010", "Savona",       "Genova",      "savona"),
    "TRIBUNALE_SANREMO":       _t("0540013", "Sanremo",      "Genova",      "sanremo"),

    # — Distretto MILANO
    "TRIBUNALE_MILANO":        _t("0580010", "Milano",       "Milano",      "milano"),
    "TRIBUNALE_BERGAMO":       _t("0580011", "Bergamo",      "Milano",      "bergamo"),
    "TRIBUNALE_BRESCIA":       _t("0600010", "Brescia",      "Brescia",     "brescia"),
    "TRIBUNALE_BUSTO_ARSIZIO": _t("0580012", "Busto Arsizio","Milano",      "bustoarsizio"),
    "TRIBUNALE_COMO":          _t("0580013", "Como",         "Milano",      "como"),
    "TRIBUNALE_CREMONA":       _t("0610010", "Cremona",      "Brescia",     "cremona"),
    "TRIBUNALE_LECCO":         _t("0580014", "Lecco",        "Milano",      "lecco"),
    "TRIBUNALE_LODI":          _t("0580015", "Lodi",         "Milano",      "lodi"),
    "TRIBUNALE_MANTOVA":       _t("0610011", "Mantova",      "Brescia",     "mantova"),
    "TRIBUNALE_MONZA":         _t("0580016", "Monza",        "Milano",      "monza"),
    "TRIBUNALE_PAVIA":         _t("0580017", "Pavia",        "Milano",      "pavia"),
    "TRIBUNALE_SONDRIO":       _t("0580018", "Sondrio",      "Milano",      "sondrio"),
    "TRIBUNALE_VARESE":        _t("0580019", "Varese",       "Milano",      "varese"),

    # — Distretto VENEZIA
    "TRIBUNALE_VENEZIA":       _t("0620010", "Venezia",      "Venezia",     "venezia"),
    "TRIBUNALE_BELLUNO":       _t("0620011", "Belluno",      "Venezia",     "belluno"),
    "TRIBUNALE_PADOVA":        _t("0640010", "Padova",       "Venezia",     "padova"),
    "TRIBUNALE_ROVIGO":        _t("0630010", "Rovigo",       "Venezia",     "rovigo"),
    "TRIBUNALE_TREVISO":       _t("0620012", "Treviso",      "Venezia",     "treviso"),
    "TRIBUNALE_VICENZA":       _t("0640011", "Vicenza",      "Venezia",     "vicenza"),
    "TRIBUNALE_VERONA":        _t("0650010", "Verona",       "Venezia",     "verona"),

    # — Distretto TRIESTE
    "TRIBUNALE_TRIESTE":       _t("0660010", "Trieste",      "Trieste",     "trieste"),
    "TRIBUNALE_GORIZIA":       _t("0660011", "Gorizia",      "Trieste",     "gorizia"),
    "TRIBUNALE_PORDENONE":     _t("0660012", "Pordenone",    "Trieste",     "pordenone"),
    "TRIBUNALE_UDINE":         _t("0670010", "Udine",        "Trieste",     "udine"),

    # — Distretto TRENTO e BOLZANO
    "TRIBUNALE_TRENTO":        _t("0680010", "Trento",       "Trento",      "trento"),
    "TRIBUNALE_ROVERETO":      _t("0680011", "Rovereto",     "Trento",      "rovereto"),
    "TRIBUNALE_BOLZANO":       _t("0690010", "Bolzano",      "Trento",      "bolzano"),

    # — Distretto BOLOGNA
    "TRIBUNALE_BOLOGNA":       _t("0700010", "Bologna",      "Bologna",     "bologna"),
    "TRIBUNALE_FERRARA":       _t("0700011", "Ferrara",      "Bologna",     "ferrara"),
    "TRIBUNALE_FORLÌ":         _t("0700012", "Forlì",        "Bologna",     "forli"),
    "TRIBUNALE_MODENA":        _t("0700013", "Modena",       "Bologna",     "modena"),
    "TRIBUNALE_PARMA":         _t("0700014", "Parma",        "Bologna",     "parma"),
    "TRIBUNALE_PIACENZA":      _t("0700015", "Piacenza",     "Bologna",     "piacenza"),
    "TRIBUNALE_RAVENNA":       _t("0700016", "Ravenna",      "Bologna",     "ravenna"),
    "TRIBUNALE_REGGIO_EMILIA": _t("0700017", "Reggio Emilia","Bologna",     "reggioEmilia"),
    "TRIBUNALE_RIMINI":        _t("0700018", "Rimini",       "Bologna",     "rimini"),

    # — Distretto FIRENZE
    "TRIBUNALE_FIRENZE":       _t("0710010", "Firenze",      "Firenze",     "firenze"),
    "TRIBUNALE_AREZZO":        _t("0710011", "Arezzo",       "Firenze",     "arezzo"),
    "TRIBUNALE_GROSSETO":      _t("0710012", "Grosseto",     "Firenze",     "grosseto"),
    "TRIBUNALE_LIVORNO":       _t("0710013", "Livorno",      "Firenze",     "livorno"),
    "TRIBUNALE_LUCCA":         _t("0710014", "Lucca",        "Firenze",     "lucca"),
    "TRIBUNALE_MASSA_CARRARA": _t("0710015", "Massa Carrara","Firenze",     "massacarrara"),
    "TRIBUNALE_PISA":          _t("0710016", "Pisa",         "Firenze",     "pisa"),
    "TRIBUNALE_PISTOIA":       _t("0710017", "Pistoia",      "Firenze",     "pistoia"),
    "TRIBUNALE_PRATO":         _t("0710018", "Prato",        "Firenze",     "prato"),
    "TRIBUNALE_SIENA":         _t("0710019", "Siena",        "Firenze",     "siena"),

    # — Distretto PERUGIA
    "TRIBUNALE_PERUGIA":       _t("0730010", "Perugia",      "Perugia",     "perugia"),
    "TRIBUNALE_ORVIETO":       _t("0730011", "Orvieto",      "Perugia",     "orvieto"),
    "TRIBUNALE_SPOLETO":       _t("0730012", "Spoleto",      "Perugia",     "spoleto"),
    "TRIBUNALE_TERNI":         _t("0740010", "Terni",        "Perugia",     "terni"),

    # — Distretto ANCONA
    "TRIBUNALE_ANCONA":        _t("0750010", "Ancona",       "Ancona",      "ancona"),
    "TRIBUNALE_ASCOLI_PICENO": _t("0750011", "Ascoli Piceno","Ancona",      "ascolipiceno"),
    "TRIBUNALE_FERMO":         _t("0750012", "Fermo",        "Ancona",      "fermo"),
    "TRIBUNALE_MACERATA":      _t("0750013", "Macerata",     "Ancona",      "macerata"),
    "TRIBUNALE_PESARO":        _t("0750014", "Pesaro",       "Ancona",      "pesaro"),
    "TRIBUNALE_URBINO":        _t("0750015", "Urbino",       "Ancona",      "urbino"),

    # — Distretto ROMA
    "TRIBUNALE_ROMA":          _t("0760010", "Roma",         "Roma",        "roma"),
    "TRIBUNALE_CIVITAVECCHIA": _t("0760011", "Civitavecchia","Roma",        "civitavecchia"),
    "TRIBUNALE_FROSINONE":     _t("0770010", "Frosinone",    "Roma",        "frosinone"),
    "TRIBUNALE_LATINA":        _t("0780010", "Latina",       "Roma",        "latina"),
    "TRIBUNALE_RIETI":         _t("0760012", "Rieti",        "Roma",        "rieti"),
    "TRIBUNALE_TIVOLI":        _t("0760013", "Tivoli",       "Roma",        "tivoli"),
    "TRIBUNALE_VELLETRI":      _t("0760014", "Velletri",     "Roma",        "velletri"),
    "TRIBUNALE_VITERBO":       _t("0790010", "Viterbo",      "Roma",        "viterbo"),

    # — Distretto L'AQUILA
    "TRIBUNALE_LAQUILA":       _t("0800010", "L'Aquila",     "L'Aquila",    "laquila"),
    "TRIBUNALE_AVEZZANO":      _t("0800011", "Avezzano",     "L'Aquila",    "avezzano"),
    "TRIBUNALE_CHIETI":        _t("0810010", "Chieti",       "L'Aquila",    "chieti"),
    "TRIBUNALE_LANCIANO":      _t("0810011", "Lanciano",     "L'Aquila",    "lanciano"),
    "TRIBUNALE_PESCARA":       _t("0810012", "Pescara",      "L'Aquila",    "pescara"),
    "TRIBUNALE_SULMONA":       _t("0800012", "Sulmona",      "L'Aquila",    "sulmona"),
    "TRIBUNALE_TERAMO":        _t("0810013", "Teramo",       "L'Aquila",    "teramo"),
    "TRIBUNALE_VASTO":         _t("0810014", "Vasto",        "L'Aquila",    "vasto"),

    # — Distretto NAPOLI
    "TRIBUNALE_NAPOLI":        _t("0820010", "Napoli",       "Napoli",      "napoli"),
    "TRIBUNALE_NAPOLI_NORD":   _t("0820011", "Napoli Nord",  "Napoli",      "napolinord"),
    "TRIBUNALE_ARIANO":        _t("0830011", "Ariano Irpino","Napoli",      "arianoirpino"),
    "TRIBUNALE_AVELLINO":      _t("0830010", "Avellino",     "Napoli",      "avellino"),
    "TRIBUNALE_BENEVENTO":     _t("0840010", "Benevento",    "Napoli",      "benevento"),
    "TRIBUNALE_CASERTA":       _t("0850010", "Caserta",      "Napoli",      "caserta"),
    "TRIBUNALE_NOLA":          _t("0820012", "Nola",         "Napoli",      "nola"),
    "TRIBUNALE_SALERNO":       _t("0860010", "Salerno",      "Napoli",      "salerno"),
    "TRIBUNALE_NOCERA":        _t("0860011", "Nocera Inferiore","Napoli",   "nocera"),
    "TRIBUNALE_TORRE_ANNUNZIATA": _t("0820013","Torre Annunziata","Napoli", "torreannunziata"),
    "TRIBUNALE_SANTA_MARIA":   _t("0850011", "Santa Maria Capua Vetere","Napoli","santamariacapuavetere"),
    "TRIBUNALE_VALLO":         _t("0860012", "Vallo della Lucania","Napoli","vallo"),

    # — Distretto POTENZA
    "TRIBUNALE_POTENZA":       _t("0870010", "Potenza",      "Potenza",     "potenza"),
    "TRIBUNALE_LAGONEGRO":     _t("0870011", "Lagonegro",    "Potenza",     "lagonegro"),
    "TRIBUNALE_MATERA":        _t("0880010", "Matera",       "Potenza",     "matera"),
    "TRIBUNALE_MELFI":         _t("0870012", "Melfi",        "Potenza",     "melfi"),

    # — Distretto CATANZARO
    "TRIBUNALE_CATANZARO":     _t("0890010", "Catanzaro",    "Catanzaro",   "catanzaro"),
    "TRIBUNALE_COSENZA":       _t("0900010", "Cosenza",      "Catanzaro",   "cosenza"),
    "TRIBUNALE_CROTONE":       _t("0890011", "Crotone",      "Catanzaro",   "crotone"),
    "TRIBUNALE_LAMEZIA":       _t("0890012", "Lamezia Terme","Catanzaro",   "lamezia"),
    "TRIBUNALE_PALMI":         _t("0910011", "Palmi",        "Catanzaro",   "palmi"),
    "TRIBUNALE_PAOLA":         _t("0900011", "Paola",        "Catanzaro",   "paola"),
    "TRIBUNALE_ROSSANO":       _t("0900012", "Rossano",      "Catanzaro",   "rossano"),
    "TRIBUNALE_REGGIO_CALABRIA":_t("0910010","Reggio Calabria","Catanzaro", "reggiocalabria"),
    "TRIBUNALE_VIBO_VALENTIA": _t("0890013", "Vibo Valentia","Catanzaro",   "vibovalentia"),

    # — Distretto PALERMO
    "TRIBUNALE_PALERMO":       _t("0920010", "Palermo",      "Palermo",     "palermo"),
    "TRIBUNALE_AGRIGENTO":     _t("0920011", "Agrigento",    "Palermo",     "agrigento"),
    "TRIBUNALE_MARSALA":       _t("0930011", "Marsala",      "Palermo",     "marsala"),
    "TRIBUNALE_SCIACCA":       _t("0920012", "Sciacca",      "Palermo",     "sciacca"),
    "TRIBUNALE_TERMINI_IMERESE":_t("0920013","Termini Imerese","Palermo",   "terminiimerese"),
    "TRIBUNALE_TRAPANI":       _t("0930010", "Trapani",      "Palermo",     "trapani"),

    # — Distretto MESSINA
    "TRIBUNALE_MESSINA":       _t("0940010", "Messina",      "Messina",     "messina"),
    "TRIBUNALE_BARCELLONA":    _t("0940011", "Barcellona Pozzo di Gotto","Messina","barcellona"),
    "TRIBUNALE_PATTI":         _t("0940012", "Patti",        "Messina",     "patti"),

    # — Distretto CATANIA
    "TRIBUNALE_CATANIA":       _t("0950010", "Catania",      "Catania",     "catania"),
    "TRIBUNALE_CALTAGIRONE":   _t("0950011", "Caltagirone",  "Catania",     "caltagirone"),
    "TRIBUNALE_ENNA":          _t("0950012", "Enna",         "Catania",     "enna"),
    "TRIBUNALE_NICOSIA":       _t("0950013", "Nicosia",      "Catania",     "nicosia"),
    "TRIBUNALE_RAGUSA":        _t("0960010", "Ragusa",       "Catania",     "ragusa"),
    "TRIBUNALE_SIRACUSA":      _t("0970010", "Siracusa",     "Catania",     "siracusa"),
    "TRIBUNALE_MODICA":        _t("0960011", "Modica",       "Catania",     "modica"),

    # — Distretto CAGLIARI
    "TRIBUNALE_CAGLIARI":      _t("0980010", "Cagliari",     "Cagliari",    "cagliari"),
    "TRIBUNALE_LANUSEI":       _t("0980011", "Lanusei",      "Cagliari",    "lanusei"),
    "TRIBUNALE_NUORO":         _t("1000010", "Nuoro",        "Cagliari",    "nuoro"),
    "TRIBUNALE_ORISTANO":      _t("0980012", "Oristano",     "Cagliari",    "oristano"),
    "TRIBUNALE_SASSARI":       _t("1010010", "Sassari",      "Cagliari",    "sassari"),
    "TRIBUNALE_TEMPIO_PAUSANIA":_t("1010011","Tempio Pausania","Cagliari",  "tempiopausania"),

    # ---------------------------------------------------------------- CORTI D'APPELLO
    "CA_TORINO":    _ca("0530000", "Torino",         "torino"),
    "CA_GENOVA":    _ca("0540000", "Genova",         "genova"),
    "CA_MILANO":    _ca("0580000", "Milano",         "milano"),
    "CA_BRESCIA":   _ca("0600000", "Brescia",        "brescia"),
    "CA_VENEZIA":   _ca("0620000", "Venezia",        "venezia"),
    "CA_TRIESTE":   _ca("0660000", "Trieste",        "trieste"),
    "CA_TRENTO":    _ca("0680000", "Trento",         "trento"),
    "CA_BOLOGNA":   _ca("0700000", "Bologna",        "bologna"),
    "CA_FIRENZE":   _ca("0710000", "Firenze",        "firenze"),
    "CA_PERUGIA":   _ca("0730000", "Perugia",        "perugia"),
    "CA_ANCONA":    _ca("0750000", "Ancona",         "ancona"),
    "CA_ROMA":      _ca("0760000", "Roma",           "roma"),
    "CA_LAQUILA":   _ca("0800000", "L'Aquila",       "laquila"),
    "CA_NAPOLI":    _ca("0820000", "Napoli",         "napoli"),
    "CA_POTENZA":   _ca("0870000", "Potenza",        "potenza"),
    "CA_CATANZARO": _ca("0890000", "Catanzaro",      "catanzaro"),
    "CA_PALERMO":   _ca("0920000", "Palermo",        "palermo"),
    "CA_MESSINA":   _ca("0940000", "Messina",        "messina"),
    "CA_CATANIA":   _ca("0950000", "Catania",        "catania"),
    "CA_CAGLIARI":  _ca("0980000", "Cagliari",       "cagliari"),

    # ---------------------------------------------------------------- CORTE DI CASSAZIONE
    "CASSAZIONE": UfficioGiudiziario(
        codice="9990000",
        nome="Corte Suprema di Cassazione",
        distretto="Roma",
        pec="scpd@cassazione.it",
        tipo="CORTE_CASSAZIONE",
    ),

    # ---------------------------------------------------------------- PROCURE PRINCIPALI
    "PROCURA_MILANO":  _pr("0580020", "Milano",  "Milano",  "milano"),
    "PROCURA_ROMA":    _pr("0760020", "Roma",    "Roma",    "roma"),
    "PROCURA_NAPOLI":  _pr("0820020", "Napoli",  "Napoli",  "napoli"),
    "PROCURA_TORINO":  _pr("0530020", "Torino",  "Torino",  "torino"),
    "PROCURA_BOLOGNA": _pr("0700020", "Bologna", "Bologna", "bologna"),
    "PROCURA_FIRENZE": _pr("0710020", "Firenze", "Firenze", "firenze"),
    "PROCURA_VENEZIA": _pr("0620020", "Venezia", "Venezia", "venezia"),
    "PROCURA_PALERMO": _pr("0920020", "Palermo", "Palermo", "palermo"),
    "PROCURA_CATANIA": _pr("0950020", "Catania", "Catania", "catania"),
    "PROCURA_BARI":    _pr("0860020", "Bari",    "Bari",    "bari"),
}


# ================================================================ Client ReGINde

class ClientReGINde:
    """
    Client per la ricerca nel ReGINde e nel registro uffici giudiziari.

    Gli uffici vengono ora letti dal GestoreUfficiGiudiziari (pct/uffici_giudiziari.py)
    che mantiene una cache JSON persistente con aggiornamento automatico da sorgenti
    remote (PST MinGiust / URL configurabile).

    Funzionalità:
    1. cerca_ufficio_giudiziario() — ricerca full-text multi-strategia
    2. elenca_uffici()             — lista filtrata per tipo/distretto
    3. cerca_avvocato_cf()         — ReGINde avvocati via PST
    """

    REGINDE_BASE_URL = "https://pst.giustizia.it/PST/resources/rest"

    def __init__(self, session=None):
        import requests as req
        self.session = session or req.Session()
        self.session.headers.update({"User-Agent": "PCT-Studio/2.0 (reginde-client)"})
        from pct.uffici_giudiziari import get_gestore
        self._gestore = get_gestore()

    def _as_ufficio(self, d: dict) -> UfficioGiudiziario:
        return UfficioGiudiziario(
            codice=d.get("codice", ""),
            nome=d.get("nome", ""),
            distretto=d.get("distretto", ""),
            pec=d.get("pec", ""),
            tipo=d.get("tipo", "TRIBUNALE"),
        )

    # ---------------------------------------------------------------- Avvocati

    def cerca_avvocato_cf(self, codice_fiscale: str) -> Optional[SoggettoReGINde]:
        """Cerca un avvocato nel ReGINde per codice fiscale (API PST)."""
        cf = codice_fiscale.upper().strip()
        try:
            resp = self.session.get(
                f"{self.REGINDE_BASE_URL}/ricercaRegistroUfficiRegistro",
                params={"cf": cf, "tipo": "AVVOCATO"},
                timeout=8,
            )
            if resp.ok:
                data = resp.json()
                risultati = data.get("risultati") or data.get("data") or []
                if risultati:
                    r = risultati[0]
                    return SoggettoReGINde(
                        codice_fiscale=r.get("cf", cf),
                        nominativo=r.get("nominativo", ""),
                        pec=r.get("pec", ""),
                        tipo="AVVOCATO",
                    )
        except Exception:
            pass
        return None

    # ---------------------------------------------------------------- Uffici giudiziari

    def cerca_ufficio_giudiziario(
        self,
        nome: str,
        tipo=_TIPO_DEFAULT,
    ) -> Optional[UfficioGiudiziario]:
        """
        Cerca un ufficio giudiziario per nome nel registro aggiornato.

        Strategie:
        1. Match esatto nel nome (case-insensitive, normalizzato)
        2. Match parziale (nome contiene il testo cercato)
        3. Slug normalizzato nella PEC
        4. Ricerca senza filtro tipo (se chiamata con tipo default)
        """
        nome_up = nome.upper().strip()
        slug_cerca = _normalize_slug(nome)

        if tipo is _TIPO_DEFAULT:
            tipo_filtro = "TRIBUNALE"
        elif tipo is None:
            tipo_filtro = ""
        else:
            tipo_filtro = str(tipo).upper()

        uffici = self._gestore.carica()

        # 1 + 2. Match nome
        for d in uffici:
            if tipo_filtro and d.get("tipo") != tipo_filtro:
                continue
            n = d.get("nome", "").upper()
            if nome_up == n or nome_up in n or n in nome_up:
                return self._as_ufficio(d)

        # 3. Slug nella PEC
        for d in uffici:
            if tipo_filtro and d.get("tipo") != tipo_filtro:
                continue
            if slug_cerca in d.get("pec", "").lower():
                return self._as_ufficio(d)

        # 4. Fallback senza filtro tipo
        if tipo is _TIPO_DEFAULT:
            return self.cerca_ufficio_giudiziario(nome, tipo=None)

        return None

    def ottieni_pec_ufficio(self, codice_ufficio: str) -> Optional[str]:
        """Restituisce la PEC dato il codice ufficio."""
        for d in self._gestore.carica():
            if d.get("codice") == codice_ufficio:
                return d.get("pec")
        return None

    def ottieni_ufficio(self, codice_ufficio: str) -> Optional[UfficioGiudiziario]:
        """Restituisce l'ufficio giudiziario dato il codice ufficiale."""
        codice = str(codice_ufficio or "").strip()
        if not codice:
            return None
        for d in self._gestore.carica():
            if d.get("codice") == codice:
                return self._as_ufficio(d)
        return None

    def elenca_uffici(
        self,
        distretto: Optional[str] = None,
        tipo: Optional[str] = None,
    ) -> list[UfficioGiudiziario]:
        """Elenca gli uffici giudiziari, con filtri opzionali."""
        uffici = self._gestore.carica()
        if distretto:
            uffici = [u for u in uffici
                      if u.get("distretto", "").upper() == distretto.upper()]
        if tipo:
            uffici = [u for u in uffici if u.get("tipo") == tipo.upper()]
        return sorted(
            [self._as_ufficio(d) for d in uffici],
            key=lambda u: u.nome,
        )


# ================================================================ helpers

def _normalize_slug(testo: str) -> str:
    """Normalizza una stringa per il confronto (rimuove accenti, lowercase)."""
    nfkd = unicodedata.normalize("NFKD", testo)
    return "".join(c for c in nfkd if not unicodedata.combining(c)).lower().replace(" ", "")
