"""
web/blueprints/assistente.py — Assistente virtuale PCT (Lex).

Integrazione Ollama locale — nessuna API key esterna richiesta.
Modello consigliato: mistral, llama3.2, phi3 (configurabile via PCT_OLLAMA_MODEL)

Route:
    GET  /api/assistente/stato   → verifica Ollama + modelli disponibili
    POST /api/assistente/chat    → chat streaming (Server-Sent Events)
"""
from __future__ import annotations

import json
import os

import requests
from flask import (
    Blueprint,
    Response,
    current_app,
    g,
    request,
    stream_with_context,
)

from lex.providers.ollama_runtime import (
    resolved_ollama_api_base_url,
    resolved_ollama_base_url,
    resolved_ollama_chat_model,
    resolved_ollama_keep_alive,
)

assistente = Blueprint("assistente", __name__)

# ── System prompt ──────────────────────────────────────────────────────────────
_SYSTEM_PROMPT = """\
Sei Lex, l'assistente virtuale specializzato in deposito telematico italiano per studi legali.
Parli sempre in italiano, in modo preciso, pratico e professionale.
Se non sei sicuro di qualcosa, dillo chiaramente.

═══ COMPETENZE PRINCIPALI ═══

1. PCT — PROCESSO CIVILE TELEMATICO (PST / polisWeb)
   • Normativa: D.M. 44/2011 e s.m.i.
   • Portale: pst.giustizia.it (autenticazione CNS/CIE/SPID)
   • Struttura busta: ZIP con DatiAtto.xml + atti firmati (.p7m), rinominato .enc
   • DatiAtto.xml: namespace corretto, tag <Attoprincipale> (non AttoprincipAle), hash SHA-256
   • Oggetto PEC: deve iniziare con "DEPOSITO TELEMATICO - {TipoAtto} - RG {n}/{anno}"
   • Dimensione massima busta: ~30 MB

2. STATI DEL DEPOSITO PCT (flusso obbligatorio):
   INVIATO → ACCETTATO_PEC → CONSEGNATO → [WARN_CONTROLLI] → ERRORE_CONTROLLI o ACCETTATO_CANCELLERIA o RIFIUTATO_CANCELLERIA
   • ACCETTATO_PEC: ricevuta PEC entro 5 minuti dall'invio
   • CONSEGNATO: ricevuta consegna PEC (il sistema PST ha preso in carico)
   • WARN_CONTROLLI: controlli superati con avvisi (non bloccante, il fascicolo prosegue)
   • ERRORE_CONTROLLI: blocca l'iter — correggere e reinviare
   • ACCETTATO_CANCELLERIA: depositato definitivamente ✓
   • RIFIUTATO_CANCELLERIA: rifiutato dal cancelliere — leggere motivazione e reinviare

3. PDP — PORTALE DEPOSITO PENALE (appweb.giustizia.it)
   • Normativa: D.Lgs. 150/2022 + D.M. 217/2023
   • Autenticazione: mTLS con certificato CNS/CIE (P12/PEM)
   • API REST: endpoint /depositi, multipart/form-data, risposta JSON
   • Stati: simili al PCT ma con gestione procura distrettuale

4. PAT — PROCESSO AMMINISTRATIVO TELEMATICO (giustizia-amministrativa.it)
   • Normativa: D.P.C.M. 16/02/2016 + D.P.C.S.G.A. 28/07/2021
   • Autenticazione: mTLS SIGA, CNS/CIE/SPID
   • Protocollo: SOAP (WSDL depositoAtto), atto in base64

5. FIRMA DIGITALE
   • Formato obbligatorio: CAdES-BES (NON PAdES per deposito PCT)
   • Estensione: .p7m (PKCS#7 detached)
   • Hash: SHA-256
   • La chain certificati deve essere inclusa
   • Verifica scadenza PRIMA di firmare (blocca il deposito se scaduto)
   • Avviso automatico a 30 giorni dalla scadenza

6. PEC
   • Ricevuta accettazione: entro 5 minuti dall'invio
   • Ricevuta consegna: conferma che il PST ha ricevuto
   • Valore probatorio: equivalente al timestamp RFC 3161 per D.M. 44/2011
   • Se non arriva accettazione entro 10 min: verificare indirizzo PEC destinatario (ReGINde)

═══ ERRORI COMUNI E SOLUZIONI ═══

• "Hash non corrispondente" / "Firma non valida"
  → Il file è stato modificato dopo la firma. Soluzione: rifirmare il documento originale.

• "Certificato scaduto"
  → Rinnovare il dispositivo di firma (token USB / smart card) presso un CAF o fornitore CNS.

• "Formato PDF non valido" / "PDF non conforme"
  → Il PDF non è in formato PDF/A-1b (richiesto per deposito). Convertire con LibreOffice,
    Adobe Acrobat o strumenti online PDF/A converter. Verificare che non ci siano font incorporati mancanti.

• "PEC mittente non censita" / "Indirizzo non trovato in ReGINde"
  → La PEC del mittente non è registrata nel registro nazionale. Verificare in Impostazioni
    che l'indirizzo PEC inserito corrisponda esattamente a quello del REGINDE.

• "Dimensione busta superiore al limite"
  → Ridurre allegati: comprimere PDF con ghostscript o strumenti di ottimizzazione.
    La busta .enc non deve superare ~30 MB.

• "RIFIUTATO_CANCELLERIA"
  → Leggere la motivazione nel messaggio di ritorno PST. Correggere il problema e
    depositare nuovamente (è sempre possibile con lo stesso RG). Casi tipici:
    - Atto non congruo con il procedimento
    - Mancanza di procura alle liti
    - Documenti non leggibili

• "Timeout / nessuna risposta PST"
  → Verificare che il portale PST sia raggiungibile. In caso di manutenzione programata
    (spesso il sabato mattina), attendere e riprovare.

═══ PREPARAZIONE DEPOSITI — CHECKLIST ═══

Civile (PST):
☐ Verificare scadenza certificato di firma (>30 giorni)
☐ Convertire documenti in PDF/A-1b
☐ Firmare con CAdES-BES (.p7m)
☐ Verificare indirizzo PEC tribunale in ReGINde
☐ Controllare dimensione totale busta (<30 MB)
☐ Inviare e attendere ricevuta accettazione

Penale (PDP):
☐ Certificato mTLS valido per autenticazione
☐ Atto principale + allegati pronti
☐ Endpoint /depositi raggiungibile
☐ Salvare idDeposito dalla risposta JSON

Amministrativo (PAT):
☐ Credenziali SIGA configurate
☐ Atto in formato base64
☐ SOAP WSDL depositoAtto disponibile

═══ REGOLE DI COMPORTAMENTO ═══
- Se hai il contesto del fascicolo attivo, usa i dati specifici nelle risposte.
- Per domande di diritto sostanziale (non procedurale), suggerisci di consultare il giudice o un collega specializzato.
- Non inventare stati, procedure o normative: preferisci "non sono sicuro" a informazioni false.
- Quando descrivi errori o stati, usa il nome esatto (es. ACCETTATO_CANCELLERIA, non "accettato dalla cancelleria").
"""


# ── Helpers ────────────────────────────────────────────────────────────────────

def _ollama_url() -> str:
    return resolved_ollama_base_url()


def _ollama_api_url() -> str:
    return resolved_ollama_api_base_url()


def _ollama_model() -> str:
    return resolved_ollama_chat_model("mistral")


def _richiedi_login(fn):
    from functools import wraps

    @wraps(fn)
    def wrapper(*args, **kwargs):
        if not g.get("utente_corrente"):
            return {"errore": "non autenticato"}, 401
        return fn(*args, **kwargs)

    return wrapper


def _build_fascicolo_context(fascicolo_id: str) -> str:
    """Legge il fascicolo dal DB e costruisce un blocco di contesto per il system prompt."""
    if not fascicolo_id:
        return ""
    try:
        db_path = current_app.config.get("FASCICOLI_DB", "")
        if not db_path or not os.path.exists(db_path):
            return ""
        with open(db_path, encoding="utf-8") as fh:
            tutti = json.load(fh)
        # Il DB può essere una lista o un dict {id: fascicolo}
        if isinstance(tutti, dict):
            fasc = tutti.get(fascicolo_id)
        else:
            fasc = next((f for f in tutti if f.get("id") == fascicolo_id), None)
        if not fasc:
            return ""

        lines = ["\n\n═══ CONTESTO FASCICOLO ATTIVO ═══"]
        rg = f"RG {fasc.get('numero_rg','?')}/{fasc.get('anno_rg','?')}"
        lines.append(f"Identificativo: {fasc.get('id', '')}  |  {rg}")
        lines.append(f"Cliente: {fasc.get('nome_cliente', 'N/D')}")
        if fasc.get("controparte"):
            lines.append(f"Controparte: {fasc['controparte']}")
        lines.append(f"Tribunale: {fasc.get('tribunale', 'N/D')}")
        if fasc.get("giudice"):
            lines.append(f"Giudice: {fasc['giudice']}")
        if fasc.get("sezione"):
            lines.append(f"Sezione: {fasc['sezione']}")
        lines.append(f"Stato fascicolo: {fasc.get('stato', 'N/D')}")
        lines.append(f"Oggetto: {fasc.get('oggetto', '')}")
        if fasc.get("avvocato_referente"):
            lines.append(f"Avvocato referente: {fasc['avvocato_referente']}")
        if fasc.get("data_prossima_udienza"):
            lines.append(f"Prossima udienza: {fasc['data_prossima_udienza']}")

        # Ultimi depositi
        depositi = fasc.get("depositi_pct", [])
        if depositi:
            ultimi = sorted(depositi, key=lambda d: d.get("data_invio", ""), reverse=True)[:3]
            lines.append(f"\nUltimi depositi ({len(depositi)} totali):")
            for d in ultimi:
                stato = d.get("stato", "?")
                tipo = d.get("tipo_atto", "?")
                data = d.get("data_invio", "")[:10]
                lines.append(f"  • {tipo} [{stato}] — {data}")

        # Documenti (solo count per non appesantire)
        docs = fasc.get("documenti", [])
        if docs:
            lines.append(f"\nDocumenti presenti: {len(docs)}")

        lines.append("═══ FINE CONTESTO ═══")
        return "\n".join(lines)
    except Exception:
        return ""


# ── Route: stato ──────────────────────────────────────────────────────────────

@assistente.route("/api/assistente/stato")
@_richiedi_login
def assistente_stato():
    try:
        r = requests.get(f"{_ollama_api_url()}/tags", timeout=3)
        modelli = [m["name"] for m in r.json().get("models", [])]
        return {
            "ok": True,
            "url": _ollama_url(),
            "modello_attivo": _ollama_model(),
            "modelli": modelli,
        }
    except requests.exceptions.ConnectionError:
        return {
            "ok": False,
            "errore": "Ollama non raggiungibile",
            "suggerimento": "Avvia Ollama con: ollama serve",
            "modelli": [],
        }, 200
    except Exception as e:
        return {"ok": False, "errore": str(e), "modelli": []}, 200


# ── Route: chat (streaming SSE) ───────────────────────────────────────────────

@assistente.route("/api/assistente/chat", methods=["POST"])
@_richiedi_login
def assistente_chat():
    data = request.get_json(silent=True) or {}
    messages: list = data.get("messages", [])
    fascicolo_id: str = data.get("fascicolo_id", "")

    # System prompt + eventuale contesto fascicolo
    system_content = _SYSTEM_PROMPT + _build_fascicolo_context(fascicolo_id)

    payload = {
        "model": _ollama_model(),
        "messages": [{"role": "system", "content": system_content}] + messages,
        "stream": True,
        "keep_alive": resolved_ollama_keep_alive("10m"),
        "options": {
            "temperature": 0.3,   # risposte più precise/deterministiche
            "num_ctx": 4096,
        },
    }

    def generate():
        try:
            r = requests.post(
                f"{_ollama_api_url()}/chat",
                json=payload,
                stream=True,
                timeout=180,
            )
            for line in r.iter_lines():
                if not line:
                    continue
                try:
                    chunk = json.loads(line)
                    token = chunk.get("message", {}).get("content", "")
                    if token:
                        yield f"data: {json.dumps({'token': token})}\n\n"
                    if chunk.get("done"):
                        yield "data: [DONE]\n\n"
                        return
                except (json.JSONDecodeError, KeyError):
                    continue
        except requests.exceptions.ConnectionError:
            msg = (
                "Ollama non è raggiungibile. "
                "Assicurati che Ollama sia avviato con: `ollama serve`\n"
                f"URL configurato: {_ollama_url()}"
            )
            yield f"data: {json.dumps({'errore': msg})}\n\n"
            yield "data: [DONE]\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'errore': str(e)})}\n\n"
            yield "data: [DONE]\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disabilita il buffering Nginx per SSE
            "Connection": "keep-alive",
        },
    )
