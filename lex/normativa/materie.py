"""Materia e tipo degli atti della biblioteca «Codici e leggi».

Classificazione deterministica per la consultazione dell'avvocato: nessun
testo viene modificato, l'atto resta identificato dal proprio URN ufficiale
(Normattiva, Gazzetta Ufficiale, EUR-Lex, CNF). La materia si ricava
dall'URN dell'atto o dalla chiave della raccolta; per gli atti non censiti
si usano parole chiave del titolo ufficiale e, in mancanza, «Altre norme».
"""
from __future__ import annotations

import re

COSTITUZIONE = 'Costituzione e fonti'
CIVILE = 'Diritto civile'
FAMIGLIA = 'Persone e famiglia'
PROC_CIVILE = 'Procedura civile e ADR'
GIUSTIZIA = 'Ordinamento giudiziario e spese di giustizia'
PENALE = 'Diritto e procedura penale'
AMMINISTRATIVO = 'Diritto amministrativo e appalti'
LAVORO = 'Lavoro e previdenza'
TRIBUTARIO = 'Diritto tributario'
IMPRESA = 'Impresa, crisi e proprietà intellettuale'
BANCA = 'Banca, finanza e assicurazioni'
CONSUMO = 'Consumatori'
DIGITALE = 'Privacy, digitale e comunicazioni'
AMBIENTE = 'Ambiente, edilizia e beni culturali'
TRASPORTI = 'Circolazione e trasporti'
IMMIGRAZIONE = 'Immigrazione'
FORENSE = 'Professione forense'
UE = 'Diritto dell’Unione europea'
MILITARE = 'Ordinamento militare'
ALTRO = 'Altre norme'

# Ordine di presentazione delle materie nella pagina.
MATERIE = (COSTITUZIONE, CIVILE, FAMIGLIA, PROC_CIVILE, GIUSTIZIA, PENALE,
           AMMINISTRATIVO, LAVORO, TRIBUTARIO, IMPRESA, BANCA, CONSUMO, DIGITALE,
           AMBIENTE, TRASPORTI, IMMIGRAZIONE, FORENSE, UE, MILITARE, ALTRO)

_S = 'urn:nir:stato:'
_DLGS = _S + 'decreto.legislativo:'
_DPR = _S + 'decreto.del.presidente.della.repubblica:'
_L = _S + 'legge:'
_RD = _S + 'regio.decreto:'

PER_URN = {
    _S + 'costituzione': COSTITUZIONE,
    # Codici e disposizioni di attuazione
    _RD + '1942-03-16;262': CIVILE, _RD + '1942-03-30;318': CIVILE,
    _RD + '1940-10-28;1443': PROC_CIVILE, _RD + '1941-12-18;1368': PROC_CIVILE,
    _RD + '1930-10-19;1398': PENALE, _DPR + '1988-09-22;447': PENALE,
    _DLGS + '1989-07-28;271': PENALE,
    'urn:nir:ministero.grazia.e.giustizia:decreto:1989-09-30;334': PENALE,
    _RD + '1942-03-16;267': IMPRESA, _DLGS + '2019-01-12;14': IMPRESA,
    _RD + '1941-01-30;12': GIUSTIZIA,
    _RD + '1941-09-09;1023': MILITARE, _S + 'relazione.e.regio.decreto:1941-02-20;303': MILITARE,
    _DLGS + '2010-03-15;66': MILITARE,
    _RD + '1931-06-18;773': AMMINISTRATIVO,
    # Civile, persone e famiglia
    _L + '1978-07-27;392': CIVILE, _L + '1998-12-09;431': CIVILE, _L + '1995-05-31;218': CIVILE,
    _L + '2017-03-08;24': CIVILE, _DLGS + '2002-10-09;231': CIVILE,
    _L + '1970-12-01;898': FAMIGLIA, _L + '1983-05-04;184': FAMIGLIA, _L + '2006-02-08;54': FAMIGLIA,
    _L + '2016-05-20;76': FAMIGLIA, _L + '1978-05-22;194': FAMIGLIA, _L + '1992-02-05;104': FAMIGLIA,
    _L + '2017-12-22;219': FAMIGLIA,
    # Procedura civile, ADR, notifiche
    _L + '1969-10-07;742': PROC_CIVILE, _L + '1982-11-20;890': PROC_CIVILE, _L + '1994-01-21;53': PROC_CIVILE,
    _DLGS + '2010-03-04;28': PROC_CIVILE, _S + 'decreto.legge:2014-09-12;132': PROC_CIVILE,
    _L + '2014-11-10;162': PROC_CIVILE,
    # Giustizia
    _DPR + '2002-05-30;115': GIUSTIZIA, _L + '1988-04-13;117': GIUSTIZIA, _L + '2001-03-24;89': GIUSTIZIA,
    _DLGS + '2017-07-13;116': GIUSTIZIA,
    # Penale
    _DPR + '1988-09-22;448': PENALE, _DPR + '1990-10-09;309': PENALE, _DPR + '2000-06-30;230': PENALE,
    _DPR + '2002-11-14;313': PENALE, _DLGS + '2000-08-28;274': PENALE, _DLGS + '2001-06-08;231': PENALE,
    _DLGS + '2011-09-06;159': PENALE, _L + '1975-07-26;354': PENALE,
    # Amministrativo e appalti
    _DPR + '1971-11-24;1199': AMMINISTRATIVO, _DPR + '2000-12-28;445': AMMINISTRATIVO,
    _DPR + '2010-10-05;207': AMMINISTRATIVO, _DLGS + '2000-08-18;267': AMMINISTRATIVO,
    _DLGS + '2006-04-12;163': AMMINISTRATIVO, _DLGS + '2010-07-02;104': AMMINISTRATIVO,
    _DLGS + '2013-03-14;33': AMMINISTRATIVO, _DLGS + '2016-04-18;50': AMMINISTRATIVO,
    _DLGS + '2016-08-26;174': AMMINISTRATIVO, _DLGS + '2018-01-02;1': AMMINISTRATIVO,
    _DLGS + '2023-03-31;36': AMMINISTRATIVO, _L + '1981-11-24;689': AMMINISTRATIVO,
    _L + '1990-08-07;241': AMMINISTRATIVO, _L + '2012-11-06;190': AMMINISTRATIVO,
    # Lavoro e previdenza
    _DPR + '1965-06-30;1124': LAVORO, _DLGS + '2001-03-26;151': LAVORO, _DLGS + '2001-03-30;165': LAVORO,
    _DLGS + '2003-04-08;66': LAVORO, _DLGS + '2003-09-10;276': LAVORO, _DLGS + '2006-04-11;198': LAVORO,
    _DLGS + '2008-04-09;81': LAVORO, _DLGS + '2009-10-27;150': LAVORO, _DLGS + '2015-03-04;22': LAVORO,
    _DLGS + '2015-03-04;23': LAVORO, _DLGS + '2015-06-15;81': LAVORO, _DLGS + '2015-09-14;148': LAVORO,
    _L + '1966-07-15;604': LAVORO, _L + '1970-05-20;300': LAVORO, _L + '1999-03-12;68': LAVORO,
    _L + '2010-11-04;183': LAVORO, _L + '2012-06-28;92': LAVORO,
    # Tributario
    _L + '2000-07-27;212': TRIBUTARIO, _DLGS + '2024-11-05;173': TRIBUTARIO,
    _DLGS + '2024-11-14;175': TRIBUTARIO, _DLGS + '2025-03-24;33': TRIBUTARIO,
    # Impresa e proprietà intellettuale
    _L + '1941-04-22;633': IMPRESA, _DLGS + '2011-05-23;79': IMPRESA, _DLGS + '2025-11-27;184': IMPRESA,
    'urn:nir:ministero.sviluppo.economico:decreto:2010-01-13;33': IMPRESA,
    # Banca, finanza, assicurazioni, antiriciclaggio
    _DLGS + '1993-09-01;385': BANCA, _DLGS + '1998-02-24;58': BANCA, _DLGS + '2005-09-07;209': BANCA,
    _DLGS + '2007-11-21;231': BANCA,
    _DLGS + '2005-09-06;206': CONSUMO,
    _DLGS + '2003-06-30;196': DIGITALE, _DLGS + '2005-03-07;82': DIGITALE, _DPR + '2005-02-11;68': DIGITALE,
    _DPR + '1973-03-29;156': DIGITALE,
    _DLGS + '2006-04-03;152': AMBIENTE, _DLGS + '2004-01-22;42': AMBIENTE, _DPR + '2001-06-06;380': AMBIENTE,
    _DPR + '2001-06-08;327': AMBIENTE,
    _DLGS + '1992-04-30;285': TRASPORTI, _DPR + '1952-02-15;328': TRASPORTI, _DLGS + '2005-07-18;171': TRASPORTI,
    _DLGS + '1998-07-25;286': IMMIGRAZIONE,
    _L + '2012-12-31;247': FORENSE, _L + '2023-04-21;49': FORENSE,
    'urn:nir:ministero.giustizia:decreto:2014-03-10;55': FORENSE,
    'urn:nir:ministero.giustizia:decreto:2011-02-21;44': PROC_CIVILE,
    _DLGS + '2022-10-10;149': PROC_CIVILE, _DLGS + '2011-09-01;150': PROC_CIVILE, _DLGS + '2024-10-31;164': PROC_CIVILE,
    _DLGS + '2022-10-10;150': PENALE, _DLGS + '2000-03-10;74': PENALE,
    _DLGS + '2016-08-19;175': AMMINISTRATIVO, _DLGS + '2003-04-09;70': DIGITALE,
    _DLGS + '1997-06-19;218': TRIBUTARIO, _DLGS + '1990-10-31;346': TRIBUTARIO, _DLGS + '1992-12-31;546': TRIBUTARIO,
    _DPR + '1973-09-29;600': TRIBUTARIO, _DPR + '1973-09-29;602': TRIBUTARIO, _DPR + '1972-10-26;633': TRIBUTARIO,
    _DLGS + '2025-08-01;123': TRIBUTARIO, _DLGS + '2026-06-19;117': TRIBUTARIO,
    _DLGS + '2005-06-20;122': CIVILE, _L + '1996-03-07;108': CIVILE,
    _L + '1991-11-21;374': GIUSTIZIA, _L + '1971-03-30;118': FAMIGLIA, _L + '1942-08-17;1150': AMBIENTE,
}

PER_CHIAVE = {
    'costituzione': COSTITUZIONE, 'preleggi': COSTITUZIONE,
    'codice_civile': CIVILE, 'codice_procedura_civile': PROC_CIVILE,
    'codice_penale': PENALE, 'codice_procedura_penale': PENALE,
    'codice_processo_amministrativo': AMMINISTRATIVO, 'cpa_norme_attuazione': AMMINISTRATIVO,
    'cpa_norme_transitorie': AMMINISTRATIVO, 'cpa_norme_coordinamento': AMMINISTRATIVO,
    'codice_strada': TRASPORTI, 'codice_consumo': CONSUMO, 'codice_crisi': IMPRESA,
    'codice_privacy': DIGITALE, '327/1942': TRASPORTI, '117/2017': IMPRESA, '159/2011': PENALE,
    '171/2005': TRASPORTI, '198/2006': LAVORO, '259/2003': DIGITALE, '30/2005': IMPRESA,
    '42/2004': AMBIENTE, '209/2005': BANCA, '36/2023': AMMINISTRATIVO, '50/2016': AMMINISTRATIVO,
    '82/2005': DIGITALE, '152/2006': AMBIENTE, '175/2024': TRIBUTARIO, '1368/1941': PROC_CIVILE,
    '318/1942': CIVILE, '271/1989': PENALE,
    'codice_penale_militare_pace': MILITARE, 'codice_penale_militare_guerra': MILITARE,
    'ordinamento_militare_66_2010': MILITARE, 'militari_attuazione_1023_1941': MILITARE,
    'postale_156_1973': DIGITALE, 'incentivi_184_2025': IMPRESA, 'turismo_79_2011': IMPRESA,
    'giustizia_contabile_174_2016': AMMINISTRATIVO, 'protezione_civile_1_2018': AMMINISTRATIVO,
    'contratti_163_2006': AMMINISTRATIVO, 'navigazione_regolamento_328_1952': TRASPORTI,
    'cpp_regolamento_334_1989': PENALE, 'proprieta_regolamento_33_2010': IMPRESA,
    'contratti_regolamento_207_2010': AMMINISTRATIVO,
    # Atti acquisiti da Normattiva (AKN vigente) il 19/10/2026
    'dl_118_2021': IMPRESA,
    'dl_179_2012': PROC_CIVILE,
    'dl_347_2003': IMPRESA,
    'dl_4_2019': LAVORO,
    'dlgs_101_2018': DIGITALE,
    'dlgs_104_2022': LAVORO,
    'dlgs_112_1999': TRIBUTARIO,
    'dlgs_11_2010': BANCA,
    'dlgs_121_2018': PENALE,
    'dlgs_138_2024': DIGITALE,
    'dlgs_141_2010': BANCA,
    'dlgs_142_2015': IMMIGRAZIONE,
    'dlgs_145_2007': CONSUMO,
    'dlgs_154_2013': FAMIGLIA,
    'dlgs_155_2012': GIUSTIZIA,
    'dlgs_160_2006': GIUSTIZIA,
    'dlgs_170_2004': BANCA,
    'dlgs_192_2005': AMBIENTE,
    'dlgs_201_2022': AMMINISTRATIVO,
    'dlgs_209_2023': TRIBUTARIO,
    'dlgs_209_2024': AMMINISTRATIVO,
    'dlgs_241_1997': TRIBUTARIO,
    'dlgs_24_2023': LAVORO,
    'dlgs_251_2007': IMMIGRAZIONE,
    'dlgs_252_2005': LAVORO,
    'dlgs_25_2008': IMMIGRAZIONE,
    'dlgs_270_1999': IMPRESA,
    'dlgs_28_2015': PENALE,
    'dlgs_30_2007': IMMIGRAZIONE,
    'dlgs_368_2001': LAVORO,
    'dlgs_39_2010': IMPRESA,
    'dlgs_39_2013': AMMINISTRATIVO,
    'dlgs_40_2006': PROC_CIVILE,
    'dlgs_446_1997': TRIBUTARIO,
    'dlgs_471_1997': TRIBUTARIO,
    'dlgs_472_1997': TRIBUTARIO,
    'dlgs_504_1992': TRIBUTARIO,
    'dm_147_2022': FORENSE,
    'dm_150_2023': PROC_CIVILE,
    'dpr_131_1986': TRIBUTARIO,
    'dpr_137_2012': FORENSE,
    'dpr_160_2010': AMBIENTE,
    'dpr_184_2006': AMMINISTRATIVO,
    'dpr_31_2017': AMBIENTE,
    'dpr_394_1999': IMMIGRAZIONE,
    'dpr_513_1997': DIGITALE,
    'dpr_62_2013': AMMINISTRATIVO,
    'dpr_917_1986': TRIBUTARIO,
    'lcost_1_1948': COSTITUZIONE,
    'legge_1034_1971': AMMINISTRATIVO,
    'legge_103_2017': PENALE,
    'legge_110_1975': PENALE,
    'legge_111_2023': TRIBUTARIO,
    'legge_112_2016': FAMIGLIA,
    'legge_129_2004': IMPRESA,
    'legge_132_2025': DIGITALE,
    'legge_146_1990': LAVORO,
    'legge_164_1982': FAMIGLIA,
    'legge_192_1998': IMPRESA,
    'legge_206_2021': PROC_CIVILE,
    'legge_219_2012': FAMIGLIA,
    'legge_220_2012': CIVILE,
    'legge_223_1991': LAVORO,
    'legge_287_1990': IMPRESA,
    'legge_31_2019': PROC_CIVILE,
    'legge_335_1995': LAVORO,
    'legge_3_2012': CIVILE,
    'legge_3_2019': PENALE,
    'legge_400_1988': COSTITUZIONE,
    'legge_401_1989': PENALE,
    'legge_40_2004': FAMIGLIA,
    'legge_447_1995': AMBIENTE,
    'legge_533_1973': LAVORO,
    'legge_55_2015': FAMIGLIA,
    'legge_580_1993': IMPRESA,
    'legge_67_2014': PENALE,
    'legge_69_2019': PENALE,
    'legge_6_2004': FAMIGLIA,
    'legge_75_1958': PENALE,
    'legge_81_2017': LAVORO,
    'legge_87_1953': COSTITUZIONE,
    'legge_91_1992': IMMIGRAZIONE,
    'legge_990_1969': TRASPORTI,
    'legge_9_2007': CIVILE,
}

# Ripiego per atti futuri non censiti: parole del titolo ufficiale, in ordine.
_PAROLE = (
    (r'tribut|impost|fiscal|riscossione|contribuente|accertamento', TRIBUTARIO),
    (r'lavor|previdenz|licenziament|pubblico impiego|infortun', LAVORO),
    (r'penal|reat|penitenziari|stupefacent', PENALE),
    (r'procedura civile|processo civile|notificazion|mediazione', PROC_CIVILE),
    (r'appalt|contratti pubblici|procedimento amministrativo|enti locali', AMMINISTRATIVO),
    (r'bancari|creditizi|finanziari|assicura|riciclaggio', BANCA),
    (r'famiglia|matrimoni|adozion|minori|unioni civili', FAMIGLIA),
    (r'ambient|ediliz|urbanistic|paesaggi|beni culturali', AMBIENTE),
    (r'dati personali|digitale|comunicazioni elettroniche|posta elettronica', DIGITALE),
    (r'societ|impres|fallim|insolvenz|propriet. industriale|autore', IMPRESA),
    (r'strad|circolazione|navigazione|trasport', TRASPORTI),
    (r'stranier|immigrazion|asilo', IMMIGRAZIONE),
    (r'forense|avvocat', FORENSE),
)


def materia(key: str, urn: str, title: str) -> str:
    """Materia di consultazione dell'atto (mai vuota)."""
    if key.startswith('reg_ue_') or 'eur-lex' in (urn or ''):
        return UE
    if key.startswith('codice_deontologico') or (urn or '').startswith('urn:cnf:'):
        return FORENSE
    if key in PER_CHIAVE:
        return PER_CHIAVE[key]
    if urn in PER_URN:
        return PER_URN[urn]
    testo = (title or '').lower()
    return next((m for pattern, m in _PAROLE if re.search(pattern, testo)), ALTRO)


_TIPI_URN = (
    ('costituzione', 'Costituzione'), ('legge.costituzionale', 'Legge costituzionale'), ('decreto.legislativo', 'Decreto legislativo'),
    ('decreto.legge', 'Decreto-legge'), ('decreto.del.presidente.della.repubblica', 'D.P.R.'),
    ('regio.decreto', 'Regio decreto'), (':legge:', 'Legge'), (':decreto:', 'Decreto ministeriale'),
)


def tipo(category: str, key: str, urn: str) -> str:
    """Tipo di fonte per il filtro della pagina (Codice, Legge, Decreto…)."""
    if category == 'Codici':
        return 'Codice'
    if key.startswith('reg_ue_'):
        return 'Regolamento UE'
    if key.startswith('codice_deontologico') or (urn or '').startswith('urn:cnf:'):
        return 'Codice deontologico'
    return next((label for marker, label in _TIPI_URN if marker in (urn or '')), 'Altro atto')
