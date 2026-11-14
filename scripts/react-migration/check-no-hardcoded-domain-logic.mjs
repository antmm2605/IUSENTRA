import { failIf, fullRoutes, routeSources } from './full-react-check-utils.mjs'

const violations = []
const forbidden = [
  { pattern: /\bivaRate\s*=|\baliquotaIva\s*=/i, label: 'aliquota IVA canonica' },
  { pattern: /\bcassaRate\s*=|\baliquotaCassa\s*=/i, label: 'aliquota cassa canonica' },
  { pattern: /\bscaglioni\s*=\s*\[/i, label: 'scaglioni tariffari hardcoded' },
  { pattern: /\bDatiAtto\.xml\b|new XMLSerializer\s*\(/i, label: 'generazione XML documentale' },
  { pattern: /\bjsPDF\b|\bpdf-lib\b|new Blob\s*\([\s\S]*?\btype:\s*["\x27]application\/(?:pdf|vnd\.openxmlformats-officedocument\.wordprocessingml\.document)["\x27]/i, label: 'generazione PDF/DOCX frontend' },
  { pattern: /\bsubtle\.sign\s*\(|\bcreateSignedData\s*\(|-----BEGIN (?:[A-Z]+ )?PRIVATE KEY-----|\bprivate_key\b|\bpassword_hash\b/i, label: 'firma o segreti frontend' },
  { pattern: /[A-Z]:\\\\|\/opt\/iusentra\/data/i, label: 'path assoluto nel frontend' },
]

for (const route of fullRoutes()) {
  const sources = routeSources(route)
  const combined = `${sources.component}\n${sources.data}`
  for (const rule of forbidden) {
    const source = rule.label === 'path assoluto nel frontend'
      ? combined.replace(/\bplaceholder=\{?["\x27][^"\x27\r\n]*["\x27]\}?/g, '')
      : combined
    if (rule.pattern.test(source)) {
      violations.push(`${route.route}: ${rule.label}.`)
    }
  }
}

failIf(violations, 'check-no-hardcoded-domain-logic')
