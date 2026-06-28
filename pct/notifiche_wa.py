"""
pct/notifiche_wa.py — Notifiche WhatsApp al cliente.

Supporta due modalità:
  1. Link diretto wa.me (sempre disponibile, nessuna chiave API)
  2. Twilio WhatsApp API (se PCT_TWILIO_SID + PCT_TWILIO_TOKEN configurati)
  3. CallMeBot API (se PCT_CALLMEBOT_KEY configurato — gratuito per uso personale)

Il sistema genera automaticamente messaggi preformattati per:
  - Promemoria appuntamento (24h/1h prima)
  - Nuova parcella emessa
  - Scadenza imminente
  - Link portale cliente
  - Messaggio libero
"""
from __future__ import annotations


from pct.formatting import format_euro_it
import os
import urllib.parse
from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from typing import Optional


# ================================================================ Template messaggi

def msg_promemoria_appuntamento(
    nome_cliente: str,
    titolo: str,
    data_ora: datetime,
    luogo: str,
    studio_nome: str,
) -> str:
    data_fmt = data_ora.strftime("%d/%m/%Y")
    ora_fmt  = data_ora.strftime("%H:%M")
    msg = (
        f"Gentile {nome_cliente},\n\n"
        f"Le ricordiamo l'appuntamento di *{titolo}*\n"
        f"📅 {data_fmt} alle {ora_fmt}"
    )
    if luogo:
        msg += f"\n📍 {luogo}"
    msg += f"\n\n— {studio_nome}"
    return msg


def msg_nuova_parcella(
    nome_cliente: str,
    numero: str,
    totale: float,
    scadenza: Optional[str],
    studio_nome: str,
) -> str:
    msg = (
        f"Gentile {nome_cliente},\n\n"
        f"È disponibile la parcella n. *{numero}*\n"
        f"💶 Importo: *{format_euro_it(totale)}*"
    )
    if scadenza:
        msg += f"\n📆 Scadenza pagamento: {scadenza}"
    msg += f"\n\nPer qualsiasi chiarimento non esiti a contattarci.\n— {studio_nome}"
    return msg


def msg_scadenza_imminente(
    nome_avvocato: str,
    titolo: str,
    scadenza: date,
    fascicolo: str,
    perentorio: bool,
) -> str:
    giorni = (scadenza - date.today()).days
    urgenza = "⚠️ PERENTORIO" if perentorio else "📌"
    msg = (
        f"{urgenza} *Scadenza imminente*\n\n"
        f"Pratica: {fascicolo}\n"
        f"Scadenza: *{titolo}*\n"
        f"📅 {scadenza.strftime('%d/%m/%Y')}"
    )
    if giorni == 0:
        msg += " — *OGGI*"
    elif giorni == 1:
        msg += " — domani"
    else:
        msg += f" — tra {giorni} giorni"
    return msg


def msg_link_portale(
    nome_cliente: str,
    link: str,
    studio_nome: str,
) -> str:
    return (
        f"Gentile {nome_cliente},\n\n"
        f"Può seguire lo stato della sua pratica, caricare documenti e firmare il consenso "
        f"privacy direttamente dal suo portale personale:\n\n"
        f"🔗 {link}\n\n"
        f"Il link è strettamente personale e sicuro.\n— {studio_nome}"
    )


def msg_libero(
    nome_cliente: str,
    testo: str,
    studio_nome: str,
) -> str:
    return f"Gentile {nome_cliente},\n\n{testo}\n\n— {studio_nome}"


# ================================================================ Canali di invio

def wa_link(numero: str, messaggio: str) -> str:
    """
    Genera un link wa.me per aprire WhatsApp con messaggio precompilato.
    Funziona su mobile (apre l'app) e desktop (apre WhatsApp Web).
    """
    # Normalizza numero: rimuovi spazi, trattini; assicura formato internazionale
    numero = numero.strip().replace(" ", "").replace("-", "").replace("(", "").replace(")", "")
    if numero.startswith("0") and not numero.startswith("00"):
        numero = "+39" + numero[1:]  # presumi Italia
    numero = numero.lstrip("+")
    encoded = urllib.parse.quote(messaggio, safe="")
    return f"https://wa.me/{numero}?text={encoded}"


def invia_twilio(
    numero_dest: str,
    messaggio: str,
    account_sid: str,
    auth_token: str,
    numero_mittente: str,
) -> dict:
    """
    Invia WhatsApp tramite Twilio API.
    Richiede: pip install twilio
    numero_mittente: es. "whatsapp:+14155238886"
    """
    try:
        from twilio.rest import Client
        client = Client(account_sid, auth_token)
        numero = numero_dest.strip()
        if not numero.startswith("+"):
            numero = "+39" + numero.lstrip("0")
        msg = client.messages.create(
            body=messaggio,
            from_=numero_mittente if numero_mittente.startswith("whatsapp:") else f"whatsapp:{numero_mittente}",
            to=f"whatsapp:{numero}",
        )
        return {"ok": True, "sid": msg.sid, "status": msg.status}
    except ImportError:
        return {"ok": False, "errore": "Twilio non installato. Usa: pip install twilio"}
    except Exception as e:
        return {"ok": False, "errore": str(e)}


def invia_callmebot(
    numero_dest: str,
    messaggio: str,
    api_key: str,
) -> dict:
    """
    Invia WhatsApp tramite CallMeBot API (gratuito, richiede registrazione).
    https://www.callmebot.com/blog/free-api-whatsapp-messages/
    """
    import urllib.request
    numero = numero_dest.strip().replace(" ", "")
    if not numero.startswith("+"):
        numero = "+39" + numero.lstrip("0")
    url = (
        f"https://api.callmebot.com/whatsapp.php"
        f"?phone={urllib.parse.quote(numero)}"
        f"&text={urllib.parse.quote(messaggio)}"
        f"&apikey={api_key}"
    )
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            body = resp.read().decode(errors="replace")
            ok = resp.status == 200 and "Message queued" in body
            return {"ok": ok, "risposta": body[:200]}
    except Exception as e:
        return {"ok": False, "errore": str(e)}


# ================================================================ Dispatcher

@dataclass
class ConfigWA:
    """Configurazione canali WhatsApp — letta dall'app.config di Flask."""
    twilio_sid:      str = ""
    twilio_token:    str = ""
    twilio_numero:   str = ""   # es. "whatsapp:+14155238886"
    callmebot_key:   str = ""

    @staticmethod
    def da_env() -> "ConfigWA":
        return ConfigWA(
            twilio_sid=os.getenv("PCT_TWILIO_SID", ""),
            twilio_token=os.getenv("PCT_TWILIO_TOKEN", ""),
            twilio_numero=os.getenv("PCT_TWILIO_NUMERO", ""),
            callmebot_key=os.getenv("PCT_CALLMEBOT_KEY", ""),
        )

    @property
    def ha_twilio(self) -> bool:
        return bool(self.twilio_sid and self.twilio_token and self.twilio_numero)

    @property
    def ha_callmebot(self) -> bool:
        return bool(self.callmebot_key)


def invia_messaggio(
    numero: str,
    messaggio: str,
    config: ConfigWA,
) -> dict:
    """
    Invia il messaggio tramite il canale disponibile.
    Priorità: Twilio > CallMeBot > link wa.me (solo URL, non invia automaticamente).
    """
    if config.ha_twilio:
        return invia_twilio(numero, messaggio,
                            config.twilio_sid, config.twilio_token, config.twilio_numero)
    if config.ha_callmebot:
        return invia_callmebot(numero, messaggio, config.callmebot_key)
    # Fallback: restituisce il link wa.me per invio manuale
    return {"ok": None, "wa_link": wa_link(numero, messaggio),
            "info": "Nessuna API configurata — usa il link per inviare manualmente."}


# ================================================================ Promemoria automatici

def promemoria_appuntamenti_di_domani(
    agenda,
    get_cliente_fn,
    config: ConfigWA,
    studio_nome: str,
) -> list[dict]:
    """
    Controlla gli appuntamenti di domani e invia promemoria ai clienti con cellulare.
    Restituisce lista di {id_appuntamento, numero, esito}.
    """
    domani = date.today() + timedelta(days=1)
    risultati = []
    for app in agenda.tutti():
        if app.data_ora_dt.date() != domani:
            continue
        if not app.id_cliente:
            continue
        cliente = get_cliente_fn(app.id_cliente)
        if not cliente:
            continue
        numero = getattr(getattr(cliente, "recapiti", None), "cellulare", "") or ""
        if not numero:
            continue
        msg = msg_promemoria_appuntamento(
            nome_cliente=cliente.nome_completo,
            titolo=app.titolo,
            data_ora=app.data_ora,
            luogo=getattr(app, "luogo", "") or "",
            studio_nome=studio_nome,
        )
        esito = invia_messaggio(numero, msg, config)
        risultati.append({
            "id_appuntamento": app.id,
            "cliente":         cliente.nome_completo,
            "numero":          numero,
            "esito":           esito,
        })
    return risultati
