interface Props {
  phase: string;
}

export function PhasePlaceholder({ phase }: Props) {
  return (
    <div className="pf-fade absolute inset-0 flex items-center justify-center font-serif text-plum" style={{ fontSize: "calc(var(--u) * 16)" }}>
      {phase}
    </div>
  );
}
