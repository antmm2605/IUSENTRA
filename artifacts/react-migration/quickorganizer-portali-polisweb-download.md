# Portali, PolisWeb e download fascicoli QuickOrganizer

Generato: 30/06/2026 21:39 (Europe/Rome).

## Componenti rilevati

- `BrowserForm.cs` usa WebView2, profilo utente locale e gestione eventi browser.
- `WizardImportaPraticheDaPolisWeb.cs` orchestra ricerca, consultazione e download documenti.
- `WebView2.DevTools.Dom.dll` e `Microsoft.Web.WebView2.*` indicano automazione DOM/portale dentro browser embedded.
- La cartella `QuickOrganizer.exe.WebView2` è runtime/cache browser, da non confondere con logica applicativa primaria.

## URL e portali rilevati nei sorgenti

- http://elsagdatamat.com/bea/pct/siecic/ws/fascicolo
- http://elsagdatamat.com/bea/pct/siecic/ws/fascicolo\
- http://schemas.xmlsoap.org/soap/actor/next\
- http://schemas.xmlsoap.org/soap/envelope/\
- http://schemi.processotelematico.giustizia.it/cassazione/tipi/allegati/v13
- http://schemi.processotelematico.giustizia.it/sigp/tipi/allegati/v3
- http://schemi.processotelematico.giustizia.it/tipi/allegati/v2
- http://schemi.processotelematico.giustizia.it/unep/tipi/allegati/v1
- http://vol.ca.notariato.it/
- http://www.giustizia.it/serviziTelematici/reginde/interrogazioniExt
- http://www.giustizia.it/serviziTelematici/reginde/interrogazioniExt\
- http://www.giustizia.it/serviziTelematici/serviziGenerici\
- http://www.juris.it/Content/Images/uploaded/GoogleAuth2.png
- http://www.netserv.it/anag/security\
- http://www.registroimprese.it/richiedi-subito-documenti
- http://www.w3.org/2001/XMLSchema-instance\
- http://www.w3.org/2001/XMLSchema\
- https://cloud.compedservizi.it/verifica/verify.shtml
- https://ext.processotelematico.giustizia.it/ServiziInterrogazioneRegindeExt/ServiziInterrogazioneSoggetto
- https://ext.processotelematico.giustizia.it/pda/pycons/
- https://ext.processotelematico.giustizia.it/pda/pycons/GLCC/JPW_CASS
- https://ext.processotelematico.giustizia.it/servizi/CatalogoServizi
- https://ext.processotelematicotest.giustizia.it/pda/pycons/
- https://ext.processotelematicotest.giustizia.it/servizi/CatalogoServizi
- https://ivaservizi.agenziaentrate.gov.it
- https://ivaservizi.agenziaentrate.gov.it/portale/
- https://ivaservizi.agenziaentrate.gov.it/portale/informativa
- https://ivaservizi.agenziaentrate.gov.it/portale/web/guest/home
- https://ivaservizi.agenziaentrate.gov.it/ser/fatturewizard/#/controllo
- https://ivaservizi.agenziaentrate.gov.it/ser/fatturewizard/#/trasmissione
- https://portali.giustizia-amministrativa.it/auth/realms/GARealm/protocol/openid-connect/auth?response_type=code&client_id=portaleGA&redirect_uri=https%3A%2F%2Fportali.giustizia-amministrativa.it%2Fportale%2Fpages%2Favvocato%2Fmenu?s&state=4ef81b28-9800-4a57-9a59-9a6f07db605a&login=true&scope=openid
- https://postecert.poste.it/verificatore/service?type=0
- https://pst.giustizia.it/PST/
- https://pst.giustizia.it/PST/it/news.page?metadata_category_frame6=avvisi
- https://pst.giustizia.it/PST/it/news.page?metadata_category_frame6=news_comunicazioni
- https://servizipst.giustizia.it/PST/PAVVP/home
- https://servizipst.giustizia.it/PST/PortaleNotifiche
- https://servizipst.giustizia.it/PST/authentication/it/pst_ar.wp
- https://servizipst.giustizia.it/PST/it/
- https://servizipst.giustizia.it/PST/it/homepage.wp
- https://servizipst.giustizia.it/PST/it/homepage.wp?redirectflag=1
- https://servizipst.giustizia.it/PST/it/pagopa_altripag.wp?actionPath=/ExtStr2/do/pagamentitelematici/initFormAltriPagamenti.action&currentFrame=8
- https://servizipst.giustizia.it/PST/it/pst_2_13.wp
- https://servizipst.giustizia.it/PST/it/pst_2_1_13.wp
- https://servizipst.giustizia.it/PST/it/pst_2_1_14_1.wp
- https://servizipst.giustizia.it/PST/it/pst_2_1_14_2.wp
- https://servizipst.giustizia.it/PST/it/pst_2_1_14_4.wp
- https://servizipst.giustizia.it/PST/it/pst_2_1_1_1.wp
- https://servizipst.giustizia.it/PST/it/pst_2_1_1_2.wp
- https://servizipst.giustizia.it/PST/it/pst_2_1_1_4.wp
- https://servizipst.giustizia.it/PST/it/pst_2_1_2_1.wp
- https://servizipst.giustizia.it/PST/it/pst_2_1_2_2.wp
- https://servizipst.giustizia.it/PST/it/pst_2_1_2_4.wp
- https://servizipst.giustizia.it/PST/it/pst_2_1_3_1.wp
- https://servizipst.giustizia.it/PST/it/pst_2_1_3_2.wp
- https://servizipst.giustizia.it/PST/it/pst_2_1_3_3.wp
- https://servizipst.giustizia.it/PST/it/pst_2_1_3_4.wp
- https://servizipst.giustizia.it/PST/it/pst_2_1_4_1.wp
- https://servizipst.giustizia.it/PST/it/pst_2_1_4_2.wp
- https://servizipst.giustizia.it/PST/it/pst_2_1_4_3.wp
- https://servizipst.giustizia.it/PST/it/pst_2_1_4_4.wp
- https://servizipst.giustizia.it/PST/it/pst_2_1_5_1.wp
- https://servizipst.giustizia.it/PST/it/pst_2_1_5_2.wp
- https://servizipst.giustizia.it/PST/it/pst_2_1_5_3.wp
- https://servizipst.giustizia.it/PST/it/pst_2_1_5_4.wp
- https://servizipst.giustizia.it/PST/it/pst_2_1_6_1.wp
- https://servizipst.giustizia.it/PST/it/pst_2_1_6_2.wp
- https://servizipst.giustizia.it/PST/it/pst_2_1_6_4.wp
- https://servizipst.giustizia.it/PST/it/pst_2_2.wp
- https://servizipst.giustizia.it/PST/it/pst_2_3.wp
- https://servizipst.giustizia.it/PST/it/pst_2_8.wp
- https://servizipst.giustizia.it/PST/it/pst_2_9_1_2.wp?ufficioRicerca=80417740588&registroRicerca=CASSPE&ruoloRicerca=AVV@AVV
- https://servizipst.giustizia.it/PST/it/pst_2_9_2_2.wp?ufficioRicerca=80417740588&registroRicerca=CASSCI&ruoloRicerca=AVV@AVV
- https://servizipst.giustizia.it/PST/it/pst_2_9_2_3.wp?ufficioRicerca=80417740588&registroRicerca=CASSCI&ruoloRicerca=AVV@AVV
- https://servizipst.giustizia.it/PST/smartcard/it/pst_ar.wp
- https://sigit.finanze.it/NIRWeb/login.jsp
- https://sws.firmacerta.it/SignEngineWeb/verifier.xhtml
- https://vol.andxor.it/vol/
- https://web.whatsapp.com/
- https://www.amministrazionicomunali.it/fatturexml/

## Artefatti collegati

- `quickorganizer-registri-consultazione-fascicoli.md` contiene registri, alias IUSENTRA, ruoli e servizi JPW/URN.
- `quickorganizer-portale-lettura-download-fascicolo.md` contiene menu `Importa Pratiche dal PolisWeb`, `Accesso al PolisWeb...`, download singolo/intero fascicolo e ricerca per anno.

## Trasferimento in IUSENTRA

- Tenere portali come connettori governati: autenticazione con certificato, ricerca fascicoli, download documenti, audit e salvataggio in SQL tenant-aware.
- Non mischiare scraping portale con deposito valido: i download alimentano fascicolo e prove, l'invio resta nel flusso deposito/PEC.
- Ogni import deve registrare origine portale, ufficio, RG, ruolo, documento scaricato, hash, data italiana e collegamento a fascicolo.
