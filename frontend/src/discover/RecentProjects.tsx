import { ChevronDown, Clock } from "lucide-react";
import { useState } from "react";
import { SHADOW, u } from "../components/ui";
import { plural, t } from "../i18n";
import type { Phase, Project } from "../types";

const PHASE_LABEL: Record<Phase, string> = {
  discover: "Discover",
  define: "Define",
  develop: "Develop",
  deliver: "Deliver",
};

const PHASE_DOT: Record<Phase, string> = {
  discover: "#c9a8f2",
  define: "#f783e9",
  develop: "#9cc3f2",
  deliver: "#f6a38f",
};

function ago(timestamp: number): string {
  const days = Math.floor((Date.now() / 1000 - timestamp) / 86400);
  if (days <= 0) return t("dziś");
  if (days === 1) return t("wczoraj");
  return t("{n} {unit} temu", { n: days, unit: plural(days, "dzień", "dni", "dni") });
}

function Phase({ phase }: { phase: Phase }) {
  return (
    <span className="flex shrink-0 items-center text-haze" style={{ gap: u(1.5) }}>
      <span className="rounded-full" style={{ width: u(3), height: u(3), background: PHASE_DOT[phase] }} />
      {PHASE_LABEL[phase]}
    </span>
  );
}

interface Props {
  projects: Project[];
  top: string;
  onResume: (project: Project) => void;
}

export function RecentProjects({ projects, top, onResume }: Props) {
  const [open, setOpen] = useState(false);
  const sorted = [...projects].sort((a, b) => b.updated_at - a.updated_at);
  const shown = open ? sorted : sorted.slice(0, 3);

  if (!projects.length) return null;

  return (
    <div className="absolute left-1/2 flex -translate-x-1/2 flex-col" style={{ top, width: u(241), gap: u(3) }}>
      <span className="text-center tracking-[0.14em] text-haze" style={{ fontSize: "var(--text-small)" }}>
        {t("ALBO WRÓĆ DO PROJEKTU")}
      </span>
      <div
        className="flex flex-col"
        style={{
          padding: u(2),
          borderRadius: u(10),
          background: "rgba(255, 255, 255, 0.62)",
          border: `${u(0.5)} solid #f1e8f8`,
          boxShadow: SHADOW,
        }}
      >
        <div className="pf-scroll flex flex-col overflow-y-auto" style={{ maxHeight: u(54) }}>
          {shown.map((project) => (
            <button
              key={project.id}
              type="button"
              onClick={() => onResume(project)}
              title={project.name}
              className="flex items-center rounded-md text-left text-ink transition-colors hover:bg-[#fbeffb]"
              style={{ gap: u(4), padding: `${u(2.5)} ${u(4)}`, fontSize: "var(--text-small)" }}
            >
              <span className="min-w-0 flex-1 truncate">{project.name}</span>
              <Phase phase={project.phase} />
              <span className="flex shrink-0 items-center justify-end text-haze" style={{ gap: u(1.5), width: u(34) }}>
                <Clock style={{ width: u(4), height: u(4) }} />
                {ago(project.updated_at)}
              </span>
            </button>
          ))}
        </div>
        {projects.length > 3 && (
          <button
            type="button"
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
            className="flex items-center justify-center rounded-md text-pink-text transition-colors hover:bg-[#fbeffb]"
            style={{ gap: u(1.5), padding: u(2), marginTop: u(1), borderTop: `${u(0.5)} solid #f1e8f8`, fontSize: "var(--text-small)" }}
          >
            {open ? t("Pokaż mniej") : t("Wszystkie ({n})", { n: projects.length })}
            <ChevronDown
              className="transition-transform"
              style={{ width: u(5), height: u(5), transform: open ? "rotate(180deg)" : undefined }}
            />
          </button>
        )}
      </div>
    </div>
  );
}
