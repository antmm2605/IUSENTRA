# Audit speciale deposito telematico - 13 agosto 2026

## Perimetro

Audit analitico del deposito telematico IUSENTRA confrontato con Studio Telematico 2026 Rel. 021, con controllo specifico del fascicolo `B494AAB9`. Il perimetro comprende catalogo depositi, regole, tabelle, apertura fascicolo, destinazione, documenti, contributo unificato, DatiAtto, firma, indice, Atto.msg, Atto.enc e trasporto PEC locale. Le notifiche legali sono escluse.

## Fonti verificate

- Eseguibile Studio Telematico: `D:\QuickOrganizer\QuickOrganizer.exe`, identificato tramite SHA-256 nell'audit JSON.
- Decompilato completo: `FormSentMailBee.cs`, identificato tramite SHA-256 nell'audit JSON.
- Tabella uffici e servizi: `D:\QuickOrganizer\ListaUfficiGiudiziari.xml`, SHA-256 `a3c4cfd298d989560f82536534869af9613a812bc9bbe820d592987218094709`.
- Database Studio Telematico: `D:\QuickOrganizer\QuickOrganizer.mdb`, SHA-256 `95a3c22aab6568ea29fa75949218f41935904740fbcb9d4aadfb0f15e88fe7f4`.
- Tabelle ministeriali oggetti e schemi XSD presenti nel repository.
- Ricevute reali dei precedenti depositi del fascicolo, compreso il rifiuto per registro diverso e i rilievi su nomi/formati firmati.

## Esito catalogo e regole

- Tipi censiti e verificati: `270/270`.
- Canale PCT civile: `252`.
- Canale UNEP: `18`.
- Regole estratte dal decompilato: `186/186` coperte.
- Regole runtime: `161`; requisiti documentali: `12`; messaggi successivi: `3`; rami sorgente non raggiungibili dal catalogo: `10`.
- Controlli ruolo ministeriale: `270/270`.
- Rami di esenzione del contributo provati: `82`.
- Presidi sui campi obbligatori provati: `407`.
- Errori o tipi aperti nell'audit automatico: `0`.

Per ogni tipo PCT/UNEP l'audit ha generato dati sintetici, applicato le regole estratte, prodotto il DatiAtto previsto, validato l'XML/XSD, creato firme CAdES-BES di prova, composto e riaperto Atto.msg, cifrato e riaperto Atto.enc, controllato MIME, indice, nomi fisici, destinatario CMS e AES-256-CBC. Nessuna PEC è stata inviata.

## Tabelle confrontate

- Uffici con servizi: `1.442`; uffici con servizio di deposito: `659`; uffici con PEC: `791`.
- Righe registro: `2.888`; righe rito: `1.192`.
- Codici oggetto ministeriali: `1.018`.
- Tabelle applicative nel MDB Studio Telematico: `22`; tabelle direttamente pertinenti al deposito: `EMAILS`, `NOMI`, `PRATICHE`, `PrecisazioneCredito`, `TAVOLA`, `Titoli`.
- Uffici PCT operativi confrontati con IUSENTRA: `593`; assenti: `0`; privi di PEC/codice: `0`; PEC discordanti: `0`.

I report macchina completi sono:

- `artifacts/deposito-telematico/audit-studio-telematico-270-2026-08-13.json`;
- `artifacts/deposito-telematico/audit-tabelle-mdb-studio-telematico-2026-08-13.json`;
- `pct/data/cataloghi/studio_telematico_uffici_deposito.json`.

## Controllo fascicolo e destinazione

Il controllo non parte dalla sola voce del menu deposito. Parte dal fascicolo aperto e confronta i suoi dati con la destinazione effettiva ricavata dal tipo selezionato e dalle tabelle Studio Telematico:

1. ufficio e codice ministeriale;
2. PEC ministeriale dell'ufficio;
3. servizio telematico richiesto dal canale;
4. registro/sezione compatibili con il ruolo ministeriale;
5. rito/materia disponibili presso l'ufficio;
6. codice oggetto presente, attivo e compatibile con il registro.

Per `B494AAB9` l'esito atteso e ora presidiato è:

- ufficio: Tribunale di Vicenza, codice `0241160092`;
- PEC: `tribunale.vicenza@civile.ptel.giustiziacert.it`;
- servizio: `JPW_SICID`;
- ruolo ministeriale: `Lavoro`;
- registro/sezione: `LAV`;
- rito: `Lavoro`;
- oggetto Carta docente contro MIM: codice `222050`, padre `222 - Pubblico impiego`.

Il codice `220050` resta distinto ed è collegato al padre `220 - Lavoro dipendente da privato`. Un fascicolo Lavoro non può quindi essere preparato come contenzioso civile ordinario senza produrre un blocco puntuale prima della busta.

È stato inoltre eliminato un ultimo rischio di precedenza del form: se una schermata conserva un vecchio valore `RG`, i registri acquisiti dal fascicolo (`registro_operativo`, `tipo_registro`, `registro_portale`) prevalgono comunque. Sul caso Lavoro il risultato resta quindi `RGL` con ruolo XML `Lavoro`; il valore del form è usato solo quando il fascicolo non contiene alcuna indicazione di registro. Le assegnazioni esplicite ricavate dal decompilato Studio Telematico restano prioritarie quando il relativo generatore le impone.

## Precedenti rilievi coperti

- Registro/sezione errati: il ruolo del fascicolo e la tabella ufficio impongono `Lavoro/LAV` per il caso concreto.
- Nomi fisici non ammessi: la busta usa i nomi logici classificati `Ricorso.pdf.p7m` e `Procura.pdf.p7m`, non i suffissi tecnici di versionamento.
- Firma non riconosciuta: atto, procura e DatiAtto sono verificati come CAdES-BES con `signingCertificateV2`.
- DatiAtto non aderente: XML, indice interno, struttura e XSD vengono validati prima di Atto.enc.
- Contributo unificato: per l'esenzione viene richiesta e allegata la prova documentale; non viene inventato un pagamento.
- Atto principale non apribile: il contenuto PDF incapsulato viene estratto e verificato prima della composizione.

## Prova reale della busta senza invio

La prova è stata eseguita sul fascicolo di produzione `B494AAB9`, usando il dispositivo di firma collegato al PC dell'avvocato. Il PIN è stato trasmesso esclusivamente al Local Signer e non è stato memorizzato nei file, nei log o sul server.

- modalità: simulazione completa, senza invio PEC;
- esito applicativo: `package_ready=true`, compatibilità `100%`, zero blocchi, zero avvisi e zero rilievi di validazione;
- evento audit: `c8dae0ef-f4a9-440c-b071-0687071964a7`, operazione `simulazione_senza_invio`;
- `Atto.msg`: `7.433.431` byte, SHA-256 `C9DFCBE0C4F4BF551E329D01FD274220EB06A90CA0590F51FA0A80659688BAD9`;
- `Atto.enc`: `7.434.253` byte, SHA-256 `A78DA332EE71CCE326014CADC6EAC5F8C42C5889EE77F9B0D8CCA3C7D40714AC`;
- cifratura: CMS `EnvelopedData`, un destinatario, `AES-256-CBC`, certificato ministeriale dell'ufficio `0241160092` valido fino all'11/01/2029;
- allegati MIME: `14`, nell'ordine atteso e senza duplicati o suffissi tecnici di versionamento;
- `DatiAtto.xml.p7m`, `Ricorso.pdf.p7m` e `Procura .pdf.p7m`: firme CAdES-BES verificate, `signingCertificateV2` presente;
- atto principale: PDF interno apribile di 11 pagine, non cifrato e conforme `PDF/A-2B`;
- `DatiAtto`: radice `Ricorso`, ufficio `0241160092`, ruolo `Lavoro`, oggetto `222050`, indice interno presente;
- contributo unificato: modalità `esente`, nessun pagamento inventato, `autocertificazione reddituale.pdf` presente fisicamente nella busta;
- destinatario: `tribunale.vicenza@civile.ptel.giustiziacert.it`.

La prova materiale è stata completata in Google Chrome sul PC reale, nella pagina autenticata di produzione. Dopo la firma locale di `DatiAtto.xml`, l'interfaccia ha mostrato il banner `Simulazione PEC completata senza invio reale: compatibilità 100%`, `8/8` controlli superati, ufficio destinatario `Tribunale di Vicenza`, `Prova busta 100% conforme` e contatore Audit passato da `5` a `6`. Il pulsante `Invia deposito reale` risultava abilitato, ma non è stato premuto. L'account amministrativo temporaneo usato esclusivamente per il collaudo è stato eliminato e la scheda è stata chiusa.

## Stato della prova

La composizione tecnica della busta, il confronto con Studio Telematico e la prova visibile Chrome-Local Signer sono positivi; nessuna PEC è stata inviata. L'esito tecnico preventivo non sostituisce l'esito ministeriale o l'accettazione della cancelleria dopo un eventuale invio reale. Restano da chiudere il deploy sul commit versionato e il riallineamento della copia locale.

Il gate di regressione esteso del deposito ha eseguito `254` test su busta, catalogo, tabelle di destinazione, profili, classificazione, firma, Local Signer, PEC locale, simulazione, ricevute e UI React. Tutti i test sono superati. Il catalogo separato conferma `270/270` tipi e `270/270` controlli di ruolo ministeriale, senza errori.
