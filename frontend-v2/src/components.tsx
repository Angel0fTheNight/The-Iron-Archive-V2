import type { ReactNode } from "react";

export function Icon({ name, size = 18 }: { name: string; size?: number }) {
  const paths: Record<string, ReactNode> = {
    grid: (
      <>
        <rect x="3" y="3" width="7" height="7" rx="1" />
        <rect x="14" y="3" width="7" height="7" rx="1" />
        <rect x="3" y="14" width="7" height="7" rx="1" />
        <rect x="14" y="14" width="7" height="7" rx="1" />
      </>
    ),
    book: (
      <>
        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2Z" />
      </>
    ),
    agents: (
      <>
        <path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2" />
        <circle cx="9" cy="7" r="4" />
        <path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
      </>
    ),
    pipeline: (
      <>
        <circle cx="6" cy="5" r="2" />
        <circle cx="18" cy="12" r="2" />
        <circle cx="6" cy="19" r="2" />
        <path d="M8 5h3a3 3 0 0 1 3 3v1a3 3 0 0 0 3 3h-3a3 3 0 0 0-3 3v1a3 3 0 0 1-3 3" />
      </>
    ),
    check: (
      <>
        <path d="m9 11 3 3L22 4" />
        <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11" />
      </>
    ),
    image: (
      <>
        <rect x="3" y="3" width="18" height="18" rx="2" />
        <circle cx="8.5" cy="8.5" r="1.5" />
        <path d="m21 15-5-5L5 21" />
      </>
    ),
    pulse: (
      <>
        <path d="M3 12h4l2-7 4 14 2-7h6" />
      </>
    ),
    list: (
      <>
        <path d="M8 6h13M8 12h13M8 18h13" />
        <path d="M3 6h.01M3 12h.01M3 18h.01" />
      </>
    ),
    settings: (
      <>
        <circle cx="12" cy="12" r="3" />
        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0v-.09a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 1 1-4 0z" />
      </>
    ),
    close: (
      <>
        <path d="m18 6-6 6-6-6" />
        <path d="M6 6h12v12H6z" />
      </>
    ),
    arrow: (
      <>
        <path d="m5 19 14-14" />
        <path d="M5 5h14v14" />
      </>
    ),
    menu: (
      <>
        <path d="M3 12h18M3 6h18M3 18h18" />
      </>
    ),
    search: (
      <>
        <circle cx="11" cy="11" r="8" />
        <path d="m21 21-4.34-4.34" />
      </>
    ),
    bell: (
      <>
        <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
        <path d="M13.73 21a2 2 0 0 1-3.46 0" />
      </>
    ),
    chevron: (
      <>
        <path d="m7 9 4 4 4-4" />
      </>
    ),
    shield: (
      <>
        <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10" />
      </>
    ),
    clock: (
      <>
        <circle cx="12" cy="12" r="10" />
        <polyline points="12 6 12 18 16 14" />
      </>
    ),
  };
  return <span style={{ display: "inline-block", width: size, height: size }}>{paths[name]}</span>;
}

export function Button({ variant = "gold", disabled = false, children, onClick }: { variant?: "gold" | "danger"; disabled?: boolean; children: ReactNode; onClick?: () => void }) {
  return (
    <button className={`button ${variant}`} disabled={disabled} onClick={onClick}>
      {children}
    </button>
  );
}

export function Panel({ title, eyebrow, children, action }: { title: string; eyebrow?: string; children: ReactNode; action?: ReactNode }) {
  return (
    <div className="panel">
      <div className="panel-head">
        <div>
          {eyebrow && <div className="eyebrow">{eyebrow}</div>}
          <h2>{title}</h2>
        </div>
        {action}
      </div>
      <div style={{ padding: "22px" }}>{children}</div>
    </div>
  );
}

export function StatusDot({ tone }: { tone?: "green" | "gold" | "muted" | "blue" } = {}) {
  return (
    <span className={`status-dot ${tone || "muted"}`}>
      <span />
    </span>
  );
}

export function ServiceCard({
  label,
  value,
  status,
  detail,
}: {
  label: string;
  value: string;
  status: "operational" | "detected" | "not-verified" | "not-available";
  detail: string;
}) {
  const toneMap: Record<string, "green" | "gold" | "muted"> = {
    operational: "green",
    detected: "muted",
    "not-verified": "gold",
    "not-available": "muted",
  };
  return (
    <div className="service-card">
      <div className="service-card-head">
        <div className="service-card-label">{label}</div>
        <StatusDot tone={toneMap[status]} />
      </div>
      <div className="service-card-value">{value}</div>
      <div className="service-card-detail">{detail}</div>
    </div>
  );
}
