# Studio Legale - Invio Telematico (PCT)

Sistema per la gestione dell'invio telematico negli studi legali italiani (Processo Civile Telematico).

## Componenti

- **Firma Digitale**: Gestione firma CAdES (.p7m) e PAdES
- **PEC**: Invio tramite Posta Elettronica Certificata
- **Busta Telematica**: Creazione file `.enc` conforme alle specifiche ministeriali
- **Deposito Penale**: Integrazione con Portale Deposito Atti Penali (PDP)
- **Notifiche**: Gestione notifiche via PEC (ReGINde)

## Installazione

```bash
pip install -r requirements.txt
```

## Utilizzo

```bash
# Crea e invia una busta telematica
python -m pct deposita --atto atto.pdf --allegati allegato1.pdf --tribunale MILANO

# Verifica stato deposito
python -m pct stato --id-deposito 12345

# Invia notifica telematica
python -m pct notifica --destinatario avv.rossi@pec.it --atto notifica.pdf
```

## Struttura

```
pct/
├── __init__.py
├── busta.py          # Creazione busta telematica (.enc)
├── firma.py          # Firma digitale CAdES/PAdES
├── pec.py            # Invio PEC
├── deposito.py       # Gestione deposito (civile/penale)
├── notifica.py       # Notifiche telematiche
├── reginde.py        # Ricerca indirizzi su ReGINde
└── cli.py            # Interfaccia a riga di comando
```

## Requisiti

- Dispositivo di firma digitale (smart card o token USB)
- Account PEC censito su RegIndE
- Accesso al Punto di Accesso (PDA)
