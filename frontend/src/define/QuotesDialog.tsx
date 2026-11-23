import { Trash2 } from "lucide-react";
import { useEffect, useState } from "react";
import { api } from "../api";
import type { PastedQuote } from "../types";
import { t } from "../i18n";
import { CardDialog } from "./CardDialog";

export function QuotesDialog({
  projectId,
  onClose,
  onAdded,
  notify,
}: {
  projectId: number;
  onClose: () => void;
  onAdded: (added: number) => void;
  notify: (message: string) => void;
}) {
  const [quotes, setQuotes] = useState<PastedQuote[]>([]);
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    api
      .quotes(projectId)
      .then((data) => setQuotes(data.quotes))
      .catch((error: Error) => notify(error.message));
  }, [projectId, notify]);

  const save = async () => {
    if (!text.trim()) return;
    setSaving(true);
    try {
      const data = await api.addQuotes(projectId, text, url.trim() || null);
      setQuotes(data.quotes);
      setText("");
      onAdded(data.added);
    } catch (error) {
      notify((error as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id: number) => {
    try {
      setQuotes((await api.removeQuote(projectId, id)).quotes);
    } catch (error) {
      notify((error as Error).message);
    }
  };

  return (
    <CardDialog title={t("Cytaty z forów")} onClose={onClose}>
      <p className="text-sm text-mauve">
        {t(
          "Wklej wypowiedzi ludzi z forów lub grup. Każdy akapit to osobny cytat. Trafią do dowodów projektu, a persony i problemy mogą je cytować słowo w słowo.",
        )}
      </p>
      <textarea
        value={text}
        onChange={(e) => setText(e.target.value)}
        rows={6}
        placeholder={t("„Podlewam ręcznie co wieczór, bo nie ufam automatom.”")}
        className="mt-3 w-full resize-y rounded-xl border border-[#e4d6ec] p-3 text-sm outline-none focus:border-pink"
      />
      <input
        value={url}
        onChange={(e) => setUrl(e.target.value)}
        placeholder={t("Link do wątku (opcjonalnie)")}
        className="mt-2 w-full rounded-xl border border-[#e4d6ec] px-3 py-2 text-sm outline-none focus:border-pink"
      />
      <div className="mt-3 flex justify-end">
        <button
          type="button"
          onClick={save}
          disabled={saving || !text.trim()}
          className="rounded-full bg-pink-button px-5 py-2 text-sm font-semibold text-on-pink disabled:opacity-50"
        >
          {saving ? t("Zapisuję…") : t("Dodaj cytaty")}
        </button>
      </div>
      {quotes.length > 0 && (
        <ul className="mt-5 flex flex-col gap-2">
          {quotes.map((quote) => (
            <li key={quote.id} className="group flex items-start gap-2 rounded-xl bg-[#f7f3fb] p-3 text-sm">
              <div className="min-w-0 flex-1">
                <div className="break-words font-serif text-base leading-snug">„{quote.body || quote.title}”</div>
                <div className="mt-1 text-xs text-haze">
                  {quote.url ? (
                    <a href={quote.url} target="_blank" rel="noreferrer" className="underline">
                      {quote.meta.platform}
                    </a>
                  ) : (
                    quote.meta.platform
                  )}
                </div>
              </div>
              <button
                type="button"
                onClick={() => remove(quote.id)}
                className="shrink-0 p-1 text-haze hover:text-plum"
                aria-label={t("Usuń cytat")}
              >
                <Trash2 size={14} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </CardDialog>
  );
}
