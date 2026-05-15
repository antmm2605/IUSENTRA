import { useEffect, useState } from 'react'
import { Save, ShieldCheck } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import { IusErrorState, IusLoadingState, IusPageShell, IusSuccessState } from '@/components/iusentra'
import { fetchLegalSkillsProfile, saveLegalSkillsProfile } from '../api'

function splitList(value: string) {
  return value.split(',').map((item) => item.trim()).filter(Boolean)
}

export function LegalSkillsProfilePage() {
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [saved, setSaved] = useState(false)
  const [error, setError] = useState('')
  const [firmName, setFirmName] = useState('')
  const [jurisdictions, setJurisdictions] = useState('IT')
  const [areas, setAreas] = useState('')
  const [sourceMode, setSourceMode] = useState('strict')

  useEffect(() => {
    const controller = new AbortController()
    fetchLegalSkillsProfile(controller.signal)
      .then((payload) => {
        if (!payload.ok && payload.message) setError(payload.message)
        const profile = payload.profile
        if (profile) {
          setFirmName(profile.firm_name || '')
          setJurisdictions((profile.jurisdictions || ['IT']).join(', '))
          setAreas((profile.practice_areas || []).join(', '))
          setSourceMode(profile.preferred_source_mode || 'strict')
        }
      })
      .finally(() => setLoading(false))
    return () => controller.abort()
  }, [])

  const submit = async () => {
    setSaving(true)
    setSaved(false)
    setError('')
    const payload = await saveLegalSkillsProfile({
      firm_name: firmName,
      jurisdictions: splitList(jurisdictions),
      practice_areas: splitList(areas),
      preferred_source_mode: sourceMode,
    })
    setSaving(false)
    if (!payload.ok) {
      setError(payload.message || 'Salvataggio non riuscito.')
      return
    }
    setSaved(true)
  }

  if (loading) return <IusLoadingState title="Caricamento profilo" message="Recupero configurazione Legal Skills." />

  return (
    <IusPageShell
      title="Profilo Legal Skills"
      description="Contesto minimo dello studio usato per bloccare risposte senza basi verificabili."
      icon={ShieldCheck}
      area="lex"
      actions={<Button asChild variant="outline"><a href="/legal-skills">Catalogo</a></Button>}
    >
      <Card>
        <CardHeader>
          <CardTitle>Contesto dello studio</CardTitle>
          <p className="text-sm text-muted-foreground">Compila solo dati reali. Le aree possono essere separate da virgole.</p>
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-2">
          {error ? <div className="md:col-span-2"><IusErrorState title="Attenzione" message={error} /></div> : null}
          {saved ? <div className="md:col-span-2"><IusSuccessState title="Profilo aggiornato" message="Le prossime esecuzioni useranno il nuovo contesto." /></div> : null}
          <label className="grid gap-1 text-sm font-medium">
            Nome studio
            <Input value={firmName} onChange={(event) => setFirmName(event.target.value)} placeholder="Nome reale dello studio" />
          </label>
          <label className="grid gap-1 text-sm font-medium">
            Giurisdizioni
            <Input value={jurisdictions} onChange={(event) => setJurisdictions(event.target.value)} placeholder="IT" />
          </label>
          <label className="grid gap-1 text-sm font-medium md:col-span-2">
            Aree seguite
            <Input value={areas} onChange={(event) => setAreas(event.target.value)} placeholder="contratti, privacy, contenzioso" />
          </label>
          <label className="grid gap-1 text-sm font-medium">
            Modalita fonti preferita
            <select className="h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm" value={sourceMode} onChange={(event) => setSourceMode(event.target.value)}>
              <option value="strict">Fonti rigorose</option>
              <option value="balanced">Fonti bilanciate</option>
              <option value="broad">Bozza ampia</option>
            </select>
          </label>
          <div className="flex items-end justify-end">
            <Button type="button" onClick={submit} disabled={saving}>
              <Save aria-hidden="true" />
              {saving ? 'Salvataggio...' : 'Salva profilo'}
            </Button>
          </div>
        </CardContent>
      </Card>
    </IusPageShell>
  )
}
