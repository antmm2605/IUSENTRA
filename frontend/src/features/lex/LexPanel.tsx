import { useState } from "react";
import { Bot, Send, Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { apiPost } from "@/lib/api/client";
import { endpoints } from "@/lib/api/endpoints";
import type { LexMessage } from "@/types/domain";

export function LexPanel() {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<LexMessage[]>([
    {
      id: "m1",
      role: "assistant",
      content: "Sono Lex in modalità anteprima React. Per risposte operative complete usa ancora il pannello Lex della UI attuale.",
      createdAt: new Date().toISOString(),
    },
  ]);

  async function send() {
    const text = input.trim();
    if (!text) return;
    setInput("");
    const userMsg: LexMessage = { id: crypto.randomUUID(), role: "user", content: text, createdAt: new Date().toISOString() };
    setMessages((current) => [...current, userMsg]);

    const result = await apiPost<{ answer: string }>(
      endpoints.lexChat,
      { message: text, context: { shell: "react", path: location.pathname } },
      { answer: "Lex React non disponibile. Usa il pannello Lex della UI attuale per retrieval, fonti e audit completi." }
    );

    setMessages((current) => [
      ...current,
      { id: crypto.randomUUID(), role: "assistant", content: result.answer, createdAt: new Date().toISOString() },
    ]);
  }

  return (
    <>
      <button
        onClick={() => setOpen(true)}
        className="fixed bottom-24 right-4 z-50 flex h-14 w-14 items-center justify-center rounded-2xl bg-ius-navy text-white shadow-legal transition hover:scale-[1.03] lg:bottom-5"
        aria-label="Apri Lex AI"
      >
        <Sparkles className="h-6 w-6 text-ius-gold" />
      </button>

      {open && (
        <aside className="fixed inset-x-3 bottom-24 top-4 z-50 flex flex-col overflow-hidden rounded-3xl border border-slate-200 bg-white shadow-legal lg:bottom-5 lg:left-auto lg:w-[420px]">
          <header className="flex items-center justify-between gap-3 bg-ius-navy px-5 py-4 text-white">
            <div className="flex items-center gap-3">
              <div className="flex h-11 w-11 items-center justify-center rounded-2xl bg-white/10">
                <Bot className="h-5 w-5 text-ius-gold" />
              </div>
              <div>
                <div className="font-black">Lex AI</div>
                <div className="text-xs text-slate-300">Assistente operativo local-first</div>
              </div>
            </div>
            <button onClick={() => setOpen(false)} className="rounded-xl p-2 hover:bg-white/10" aria-label="Chiudi Lex">
              <X className="h-5 w-5" />
            </button>
          </header>

          <div className="flex-1 space-y-3 overflow-y-auto bg-slate-50 p-4">
            {messages.map((msg) => (
              <div key={msg.id} className={msg.role === "user" ? "flex justify-end" : "flex justify-start"}>
                <div className={`max-w-[85%] rounded-2xl px-4 py-3 text-sm leading-relaxed shadow-sm ${
                  msg.role === "user" ? "bg-ius-blue text-white" : "bg-white text-slate-800"
                }`}>
                  {msg.content}
                </div>
              </div>
            ))}
          </div>

          <footer className="border-t border-slate-200 bg-white p-3">
            <div className="flex gap-2">
              <textarea
                value={input}
                onChange={(event) => setInput(event.target.value)}
                onKeyDown={(event) => {
                  if (event.key === "Enter" && !event.shiftKey) {
                    event.preventDefault();
                    void send();
                  }
                }}
                placeholder="Chiedi a Lex..."
                className="min-h-11 flex-1 resize-none rounded-2xl border border-slate-200 px-4 py-3 text-sm outline-none focus:border-ius-sky"
              />
              <Button onClick={send} className="h-11 w-11 px-0">
                <Send className="h-4 w-4" />
              </Button>
            </div>
          </footer>
        </aside>
      )}
    </>
  );
}
