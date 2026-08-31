// Classificatore ministeriale PST condiviso.
//
// Estratto da TelematicoSurfacePage (wizard di acquisizione) per poter essere
// riusato dal pannello "Fascicolo d'ufficio": entrambi devono dedurre lo stesso
// servizio PST a partire dal registro/rito del fascicolo, altrimenti la
// consultazione diretta interroga una tabella ministeriale diversa da quella
// del wizard e il PST risponde con zero righe.

export type PstMinisterialProfile = {
  schema?: string
  materia?: string
  registro?: string
  tipo_registro?: string
  quick_filter?: string
  tabella_ministeriale?: string
  servizio_pst_preferito?: string
  registro_portale?: string
}

function asText(value: unknown, fallback = ''): string {
  const raw = String(value ?? fallback).trim()
  return raw || fallback
}

function normaliseSearch(value: string): string {
  return value.toLowerCase().normalize('NFD').replace(/[\u0300-\u036f]/g, '')
}

export function pstMinisterialProfileFromText(value: unknown): PstMinisterialProfile {
  const raw = normaliseSearch(asText(value))
  if (!raw) return {}
  if (raw.includes('cass') && raw.includes('penal')) {
    return {
      schema: 'cassazione penale',
      materia: 'Cassazione penale',
      registro: 'CASSPE',
      tipo_registro: 'CASSPE',
      quick_filter: 'cassazione penale',
      tabella_ministeriale: 'JPW_CASSPE',
      servizio_pst_preferito: 'JPW_CASSPE',
      registro_portale: 'CASSPE',
    }
  }
  if (raw.includes('cass') && raw.includes('civil')) {
    return {
      schema: 'cassazione civile',
      materia: 'Cassazione civile',
      registro: 'CASSCI',
      tipo_registro: 'CASSCI',
      quick_filter: 'cassazione civile',
      tabella_ministeriale: 'JPW_CASSCI',
      servizio_pst_preferito: 'JPW_CASSCI',
      registro_portale: 'CASSCI',
    }
  }
  if (raw.includes('lavor') || raw.includes('previd') || raw.includes('assistenz') || raw.includes('sicid_lavoro') || raw.includes('jpw_sil')) {
    return {
      schema: 'lavoro',
      materia: 'Lavoro e previdenza',
      registro: 'LAV',
      tipo_registro: 'LAV',
      quick_filter: 'lavoro',
      tabella_ministeriale: 'SICID_LAVORO',
      servizio_pst_preferito: raw.includes('silp') ? 'JPW_SILP_DISTR' : 'JPW_SIL_DISTR',
      registro_portale: 'LAV',
    }
  }
  if (raw.includes('volontar') || raw.includes('sivg')) {
    return {
      schema: 'volontaria',
      materia: 'Volontaria giurisdizione',
      registro: 'VG',
      tipo_registro: 'VG',
      quick_filter: 'volontaria',
      tabella_ministeriale: 'SICID_VOLONTARIA_GIURISDIZIONE',
      servizio_pst_preferito: 'JPW_SIVG',
      registro_portale: 'VG',
    }
  }
  if (raw.includes('simin')) {
    return {
      schema: 'minori',
      materia: 'Minorenni',
      registro: 'MIN',
      tipo_registro: 'MIN',
      quick_filter: 'minori',
      tabella_ministeriale: 'SICID_SIMIN',
      servizio_pst_preferito: 'JPW_SIMIN',
      registro_portale: 'MIN',
    }
  }
  if (raw.includes('minor') || raw.includes('minoren') || raw.includes('sicid_minori') || raw.includes('jpw_min')) {
    return {
      schema: 'minori',
      materia: 'Minorenni',
      registro: 'MIN',
      tipo_registro: 'MIN',
      quick_filter: 'minori',
      tabella_ministeriale: 'SICID_MINORI',
      servizio_pst_preferito: 'JPW_MIN',
      registro_portale: 'MIN',
    }
  }
  if (raw.includes('falliment') || raw.includes('concors')) {
    return {
      schema: 'procedure concorsuali',
      materia: 'Procedure concorsuali',
      registro: 'FALL',
      tipo_registro: 'FALL',
      quick_filter: 'procedure concorsuali',
      tabella_ministeriale: 'SIECIC_PROCEDURE_CONCORSUALI',
      servizio_pst_preferito: 'JPW_SIECIC',
      registro_portale: 'FALL',
    }
  }
  if (raw.includes('immobil') || raw.includes('pignor')) {
    return {
      schema: 'esecuzioni immobiliari',
      materia: 'Esecuzioni immobiliari',
      registro: 'ESIM',
      tipo_registro: 'ESIM',
      quick_filter: 'esecuzioni immobiliari',
      tabella_ministeriale: 'SIECIC_ESECUZIONI_IMMOBILIARI',
      servizio_pst_preferito: 'JPW_SIECIC',
      registro_portale: 'ESIM',
    }
  }
  if (raw.includes('mobil') || raw.includes('esecuz') || raw.includes('siecic')) {
    return {
      schema: 'esecuzioni mobiliari',
      materia: 'Esecuzioni mobiliari',
      registro: raw.includes('siecic') && !raw.includes('esecuz') ? 'SIECIC' : 'ESM',
      tipo_registro: raw.includes('siecic') && !raw.includes('esecuz') ? 'SIECIC' : 'ESM',
      quick_filter: 'esecuzioni mobiliari',
      tabella_ministeriale: 'SIECIC_ESECUZIONI_MOBILIARI',
      servizio_pst_preferito: 'JPW_SIECIC',
      registro_portale: raw.includes('siecic') && !raw.includes('esecuz') ? 'SIECIC' : 'ESM',
    }
  }
  if (raw.includes('giudice di pace') || raw.includes('sigp') || raw.includes('gdp')) {
    return {
      schema: 'giudice di pace',
      materia: 'Giudice di Pace',
      registro: 'GDP',
      tipo_registro: 'GDP',
      quick_filter: 'giudice di pace',
      tabella_ministeriale: 'SIGP_GIUDICE_DI_PACE',
      servizio_pst_preferito: 'JPW_SIGP',
      registro_portale: 'GDP',
    }
  }
  if (raw.includes('sicid') || raw.includes('civil') || raw.includes('rgn') || raw.includes('contenzioso')) {
    return {
      schema: 'civile',
      materia: 'Civile ordinario',
      registro: 'CC',
      tipo_registro: 'CC',
      quick_filter: 'civile',
      tabella_ministeriale: 'SICID_CONTENZIOSO_CIVILE',
      servizio_pst_preferito: 'JPW_SICID',
      registro_portale: 'CC',
    }
  }
  return {}
}

/**
 * Deduce il profilo ministeriale unendo piu' campi descrittivi del fascicolo
 * (registro portale, rito, materia, oggetto, titolo). Il primo marcatore utile
 * vince, come nel wizard.
 */
export function pstMinisterialProfileFromParts(...parts: unknown[]): PstMinisterialProfile {
  const text = parts
    .map((part) => asText(part))
    .filter(Boolean)
    .join(' ')
  return pstMinisterialProfileFromText(text)
}
