# Schemi ufficiali FatturaPA, copia offline

Acquisiti il 08/10/2026. Il generatore e il percorso di preparazione alla firma usano queste copie senza accesso di rete. Un XML non conforme viene respinto prima del download o della firma; la validazione XSD non sostituisce i controlli fiscali e la ricevuta SdI.

- Schema_VFPR12_v1.2.3.xsd: https://www.fatturapa.gov.it/export/documenti/fatturapa/v1.4/Schema_VFPR12_v1.2.3.xsd
  SHA256: 152944f6eef9f5d69ef6e955ee173b32142b00a8c1c5222fc97dfab5910e8a8c
- xmldsig-core-schema.xsd: https://www.w3.org/TR/2002/REC-xmldsig-core-20020212/xmldsig-core-schema.xsd
  SHA256: 35cf8197da812c85e40d57891b35c94187569ed474a2dac813ce5090dafcd35c

La versione originaria e le medesime impronte sono conservate in docs/specs/ministero/fonti_ufficiali/2026-10-08. Nessuna modifica al contenuto degli schemi. La dipendenza XMLDSig viene risolta soltanto nella cartella locale del pacchetto.

I nomi XML utilizzano l’identificativo completo del trasmittente dichiarato nel tracciato. La numerazione nativa 2000–2100, da 1 a 399999 documenti annui, viene codificata bijettivamente in cinque caratteri alfanumerici con iniziale alfabetica, senza hash o troncamento. Numerazioni fuori dominio sono respinte esplicitamente. I codici originali delle trasmissioni già effettuate restano nelle rispettive evidenze e non vengono riscritti.
