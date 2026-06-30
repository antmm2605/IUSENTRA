# Firma digitale, PIN e sessioni QuickOrganizer

Generato: 30/06/2026 18:10 (Europe/Rome).

## Cosa emerge

- La sessione firma ruota attorno a `QualifiedCertificate` e a variabili statiche di lavoro come `PCT.QualifiedCertificate` e `PCT.pin`.
- Il PIN risulta usato come dato di sessione/processo per firmare e autenticarsi, non come valore da salvare nel database.
- Il certificato qualificato viene distinto dal certificato di autenticazione web tramite OID/estensioni.
- Le chiamate ai servizi PST/portali usano il certificato web quando richiesto; il deposito usa firma CAdES e cifratura separata.

## Trasferimento in IUSENTRA

- Local Signer deve continuare a chiedere il PIN al momento dell'operazione e tenerlo solo in memoria di sessione strettamente necessaria.
- La firma multipla deve firmare più documenti nella stessa operazione, salvare ogni esito e non derivare mai `Firmato` da nome file o testo.
- Per portali/PST va separato il certificato di autenticazione dal certificato di firma e dal certificato pubblico dell'ufficio.
- Ogni errore PIN/certificato deve bloccare il solo passaggio obbligatorio e lasciare audit comprensibile nel fascicolo.

## Sorgenti decompilati da rileggere

- `QuickOrganizer/QualifiedCertificate.cs`
- `QuickOrganizer/PCT.cs`
- `FormSentMailBee.cs`

### Hit `QualifiedCertificate`

- `FormSentMailBee.cs:15185` - `QualifiedCertificate qualifiedCertificate = new QualifiedCertificate(IsDepositoTelematico: true, IsTest: false, CodiceFiscaleDepositante, _numeroPratica);`
- `FormSentMailBee.cs:15186` - `qualifiedCertificate.TxSignatureReason.Text = "Per autentica e sottoscrizione";`
- `FormSentMailBee.cs:15187` - `qualifiedCertificate.ShowDialog(this);`
- `FormSentMailBee.cs:15188` - `if (qualifiedCertificate.DialogResult != DialogResult.OK)`
- `FormSentMailBee.cs:15624` - `QualifiedCertificate qualifiedCertificate = new QualifiedCertificate(IsDepositoTelematico: false, IsTest: false, string.Empty, _numeroPratica);`
- `FormSentMailBee.cs:15625` - `qualifiedCertificate.TxSignatureReason.Text = "Per autentica e sottoscrizione";`
- `FormSentMailBee.cs:15626` - `qualifiedCertificate.ShowDialog(this);`
- `FormSentMailBee.cs:15627` - `if (qualifiedCertificate.DialogResult != DialogResult.OK)`

### Hit `pin`

- `FormSentMailBee.cs:1170` - `private UltraDateTimeEditor dtCompInventario;`
- `FormSentMailBee.cs:2062` - `this.dtCompInventario = new Infragistics.Win.UltraWinEditors.UltraDateTimeEditor();`
- `FormSentMailBee.cs:2301` - `((System.ComponentModel.ISupportInitialize)this.dtCompInventario).BeginInit();`
- `FormSentMailBee.cs:5878` - `this.ultraGroupBoxAltriDati.Controls.Add(this.dtCompInventario);`
- `FormSentMailBee.cs:5917` - `this.dtCompInventario.DateTime = new System.DateTime(1753, 1, 1, 0, 0, 0, 0);`
- `FormSentMailBee.cs:5918` - `this.dtCompInventario.Font = new System.Drawing.Font("Microsoft Sans Serif", 9f, System.Drawing.FontStyle.Regular, System.Drawing.GraphicsUnit.Point, 0);`
- `FormSentMailBee.cs:5919` - `this.dtCompInventario.FormatString = "";`
- `FormSentMailBee.cs:5920` - `this.dtCompInventario.Location = new System.Drawing.Point(433, 29);`

### Hit `CAdES`

- `QuickOrganizer/PCT.cs:19` - `using SignLib.Cades;`
- `QuickOrganizer/PCT.cs:3316` - `pdfSignature.SignatureStandard = SignatureStandard.Cades;`
- `QuickOrganizer/PCT.cs:3481` - `CadesSignature cadesSignature = new CadesSignature(SecureSoftSerialNumber);`
- `QuickOrganizer/PCT.cs:3482` - `cadesSignature.DigitalSignatureCertificate = QualifiedCertificate;`
- `QuickOrganizer/PCT.cs:3487` - `cadesSignature.HashAlgorithm = SignLib.HashAlgorithm.SHA256;`
- `QuickOrganizer/PCT.cs:3488` - `cadesSignature.SignatureStandard = SignatureStandard.Cades;`
- `QuickOrganizer/PCT.cs:3501` - `cadesSignature.TimeStamping.ServerUrl = new Uri(Settings.Default.TimeServerUrl);`
- `QuickOrganizer/PCT.cs:3504` - `cadesSignature.TimeStamping.UserName = Settings.Default.TimeServerUsername;`

### Hit `PAdES`

- `QuickOrganizer/FormMain.cs:12455` - `case "FirmaDigitalePades":`
- `QuickOrganizer/FormMain.cs:45570` - `UltraToolbarsManagerLeft.Tools["FirmaDigitalePades"].SharedProps.Enabled = true;`
- `QuickOrganizer/FormMain.cs:55622` - `UltraToolbarsManagerRight.Tools["FirmaDigitalePades"].SharedProps.Enabled = true;`
- `QuickOrganizer/FormMain.cs:56682` - `MessageBox.Show(this, "Impossibile firmare in PaDES. Prova a firmare in CaDES.", STL_VERSION, MessageBoxButtons.OK, MessageBoxIcon.Hand);`
- `QuickOrganizer/FormMain.cs:56704` - `MessageBox.Show(this, "Impossibile firmare in PaDES. Prova a firmare in CaDES.", STL_VERSION, MessageBoxButtons.OK, MessageBoxIcon.Hand);`
- `QuickOrganizer/FormMain.cs:59622` - `Infragistics.Win.UltraWinToolbars.ButtonTool buttonTool534 = new Infragistics.Win.UltraWinToolbars.ButtonTool("FirmaDigitalePades");`
- `QuickOrganizer/FormMain.cs:60008` - `Infragistics.Win.UltraWinToolbars.ButtonTool buttonTool756 = new Infragistics.Win.UltraWinToolbars.ButtonTool("FirmaDigitalePades");`
- `QuickOrganizer/FormMain.cs:60875` - `Infragistics.Win.UltraWinToolbars.ButtonTool buttonTool1096 = new Infragistics.Win.UltraWinToolbars.ButtonTool("FirmaDigitalePades");`

### Hit `pkcs`

- `FormSentMailBee.cs:14` - `using System.Security.Cryptography.Pkcs;`
- `FormSentMailBee.cs:15316` - `TextBodyPart textBodyPart = mailMessage.BodyParts.Add("application/pkcs7-mime; name=\"DatiAtto.xml.p7m\"");`
- `FormSentMailBee.cs:15335` - `mailMessage.Attachments.Add(_AttoPrincipale.Nome, _AttoPrincipale.Nome, "", "application/pkcs7-mime", headerCollection, NewAttachmentOptions.None, MailTransferEncoding.None);`
- `FormSentMailBee.cs:15347` - `mailMessage.Attachments.Add(item2.Nome, item2.Nome, "", "application/pkcs7-mime", headerCollection2, NewAttachmentOptions.None, MailTransferEncoding.None);`
- `FormSentMailBee.cs:15462` - `TextBodyPart textBodyPart = mailMessage.BodyParts.Add("application/pkcs7-mime; name=\"DatiAtto.xml.p7m\"");`
- `FormSentMailBee.cs:15475` - `mailMessage.Attachments.Add(_AttoPrincipale.Nome, _AttoPrincipale.Nome, "", "application/pkcs7-mime", headerCollection, NewAttachmentOptions.None, MailTransferEncoding.None);`
- `FormSentMailBee.cs:15487` - `mailMessage.Attachments.Add(item.Nome, item.Nome, "", "application/pkcs7-mime", headerCollection2, NewAttachmentOptions.None, MailTransferEncoding.None);`
- `QuickOrganizer/QualifiedCertificate.cs:164` - `Settings.Default.Utilizza_Pkcs11 = false;`
