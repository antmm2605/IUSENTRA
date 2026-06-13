# Audit migrazione React

Generato: 2026-05-09T15:07:53.814Z

## Frontend

Dipendenze runtime: @fontsource-variable/geist, @vitejs/plugin-react, class-variance-authority, clsx, lucide-react, radix-ui, react, react-dom, shadcn, tailwind-merge, tw-animate-css, typescript, vite
Script disponibili: dev, test, typecheck, build, build:vite, preview

## Gate React

Route React prefixes: 55
Route React exact: 44
Excluded prefixes: 14
Legacy operational prefixes: 15

## App React

Lazy components: 46
Route checks: 60
Studio module routes: 53

## Aggiornamento manuale 2026-06-12

Assistente vocale Studio 2.253.1 aggiunto come componente topbar caricato in modo pigro. Il catalogo comandi è testato separatamente e il flusso cliente usa API reale con permessi, audit e repository. Audit browser CDP su Docker reale `127.0.0.1:8080`: 330 frasi, 59 destinazioni, voce/PIN, cliente guidato, responsive desktop/tablet/mobile e visual load baseline confermati senza failure.

## Nota operativa

Questo audit fotografa lo stato reale della migrazione. Non promuove route e non modifica il gate.
