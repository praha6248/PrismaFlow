interface Props {
  message: string;
  onClose: () => void;
}

export function Toast({ message, onClose }: Props) {
  return (
    <div
      role="status"
      className="pf-fade-up absolute left-1/2 z-40 -translate-x-1/2 text-center text-mauve"
      style={{
        top: "calc(var(--u) * 98)",
        maxWidth: "calc(var(--u) * 340)",
        padding: "calc(var(--u) * 5) calc(var(--u) * 12)",
        borderRadius: "calc(var(--u) * 10)",
        background: "rgba(255,255,255,0.92)",
        boxShadow: "0 calc(var(--u) * 2) calc(var(--u) * 10) rgba(196, 160, 232, 0.3)",
        fontSize: "calc(var(--u) * 6.4)",
      }}
      onClick={onClose}
    >
      {message}
    </div>
  );
}
