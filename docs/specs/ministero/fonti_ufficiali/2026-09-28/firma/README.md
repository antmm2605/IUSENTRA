# Firma digitale: prestatori, firma remota e dispositivi (consultazione del 28/09/2026)

Fonti usate per `pct/data/cataloghi/firma_digitale.json`, `pct/firma_remota/` e
`local_signer_mod/dispositivi_firma.py`.

## Prestatori qualificati

- AgID, *Prestatori di servizi fiduciari attivi in Italia* (aggiornamento 01/07/2025):
  https://www.agid.gov.it/it/piattaforme/firma-elettronica-qualificata/prestatori-di-servizi-fiduciari-attivi-in-italia
- Base normativa: Reg. eIDAS 910/2014 artt. 22, 26, 29 e All. II; CAD D.Lgs. 82/2005 artt. 20 e 29;
  D.M. 44/2011 art. 12 per gli atti del processo telematico.

## Protocolli di firma remota

| Protocollo | Prestatori | Fonte | Copia qui |
|---|---|---|---|
| ArubaSignService (ARSS), SOAP | Aruba, Actalis | WSDL pubblico `https://arss.arubapec.it/ArubaSignService/ArubaSignService?wsdl` e `https://arss.actalis.it/ArubaSignService/ArubaSignService?wsdl` | `aruba_arss_ArubaSignService.wsdl.xml`, `actalis_arss_ArubaSignService.wsdl.xml` |
| Sign Web Services (SWS), SOAP | Namirial | WSDL pubblico `https://sws.namirialtsp.com/SignEngineWeb/sign-services?wsdl`; SWS Integration Guide `https://docs.namirial.app/products/sws/customer_documentation/integration` | `namirial_sws_sign-services.wsdl.xml` |
| Cloud Signature Consortium (CSC API v1.0.4.0 e v2.0.0.2), REST | InfoCert, Intesi Group, Namirial e ogni prestatore che rilascia un indirizzo CSC | `https://cloudsignatureconsortium.org/wp-content/uploads/2020/01/CSC_API_V1_1.0.4.0.pdf`, `https://cloudsignatureconsortium.org/wp-content/uploads/2023/04/csc-api-v2.0.0.2.pdf` | (solo riferimento) |

Operazioni usate:

- **ARSS**: `listCert` (certificati del titolare), `sendCredential` (`SMS`, `ARUBACALL`),
  `signhash` (`certID`, `hash`, `hashtype=SHA256`, `identity`, `requirecert`). Identità `auth`:
  `otpPwd`, `typeHSM=COSIGN`, `typeOtpAuth` (dominio del contratto), `user`, `userPWD`.
- **SWS**: `getOTPList`, `sendOtpBySMS`, `sendOtpByPUSH`, `getCertificate`,
  `signPkcs1` (`credentials`: `idOtp`, `otp`, `password`, `username`; `preferences.hashAlgorithm=SHA256`).
- **CSC**: `auth/login`, `credentials/list`, `credentials/info`, `credentials/sendOTP` (v1),
  `credentials/authorize` (v1: `PIN`, `OTP`; v2: `authData`), `signatures/signHash`
  (`signAlgo=1.2.840.113549.1.1.1`, SHA-256 `2.16.840.1.101.3.4.2.1`), `auth/revoke`.

Al prestatore arriva solo l'impronta SHA-256 da firmare; le buste CAdES-BES e PAdES si costruiscono
in IUSENTRA con lo stesso profilo della firma con smart card e la firma ricevuta si verifica con il
certificato prima di salvare. Password, PIN e OTP non si salvano.

Per gli altri prestatori dell'elenco AgID non risulta un'API di firma remota pubblica per i gestionali:
si firma dall'app del prestatore e si carica il file con «Firma esterna».

## Dispositivi (smart card e token)

Librerie PKCS#11 per produttore (Windows, Linux, macOS) da elenchi d'uso dei software di firma e
dalle pagine dei prestatori; il Local Signer le cerca nelle cartelle dichiarate nel catalogo e
dà la precedenza al produttore scelto in Impostazioni → Firma digitale.

- Bit4id (token e smart card della maggior parte dei prestatori; driver indicato anche da Namirial e Poste)
- Athena / ASE Card, Incard, Oberthur / IDEMIA, Siemens / Atos CardOS
- Thales SafeNet eToken, Thales / Gemalto IDPrime, Charismathics, Namirial (Oki), Italtel (carte storiche)
- OpenSC (driver aperto)
