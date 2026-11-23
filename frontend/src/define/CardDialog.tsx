import { useEffect, useId, useRef, type ReactNode } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { t } from "../i18n";

export function CardDialog({ title, children, onClose }: {
  title: string;
  children: ReactNode;
  onClose: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const heading = useId();
  useEffect(() => {
    const dialog = ref.current!;
    const trigger = document.activeElement;
    dialog.showModal();
    return () => {
      dialog.close();
      if (trigger instanceof HTMLElement && trigger.isConnected) trigger.focus();
    };
  }, []);
  return createPortal(
    <dialog ref={ref} aria-labelledby={heading}
      className="fixed inset-0 m-auto w-[min(32rem,92vw)] max-h-[85dvh] overflow-auto rounded-2xl bg-white p-6 text-ink shadow-xl backdrop:bg-black/30"
      onCancel={event => { event.preventDefault(); onClose(); }}
      onKeyDown={event => event.stopPropagation()}
      onClick={event => {
        event.stopPropagation();
        if (event.target === ref.current) {
          const rect = ref.current!.getBoundingClientRect();
          if (event.clientX < rect.left || event.clientX > rect.right || event.clientY < rect.top || event.clientY > rect.bottom) onClose();
        }
      }}>
      <header className="mb-4 flex items-start justify-between gap-4">
        <h2 id={heading} className="min-w-0 break-words font-serif text-2xl">{title}</h2>
        <button type="button" onClick={onClose} aria-label={t("Zamknij")} className="rounded-full p-2"><X size={18} /></button>
      </header>
      {children}
    </dialog>, document.body
  );
}
