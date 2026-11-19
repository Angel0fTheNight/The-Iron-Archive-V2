import { useEffect, useMemo, useState } from "react";
import {
  Agent,
  Job,
  Episode,
  Role,
  Event,
  Doctor,
  DataState,
  api,
  createDataState,
} from "./data";
import { Button, Icon, Panel, StatusDot, ServiceCard } from "./components";

function Sidebar({
  active,
  setActive,
  open,
  close,
}: {
  active: string;
  setActive: (v: string) => void;
  open: boolean;
  close: () => void;
}) {
  return (
    <>
      <div className={`scrim ${open ? "show" : ""}`} onClick={close} />
      <aside className={`sidebar ${open ? "open" : ""}`}>
        <div className="brand">
          <div className="sigil"><span>IA</span></div>
          <div>
            <strong>THE IRON ARCHIVE</strong>
            <small>CENTRAL DE COMANDO V2</small>
          </div>
        </div>
        <div className="nav-label">SISTEMAS DO ARQUIVO</div>
        <nav>
          {navigation.map((item) => (
            <button
              key={item.id}
              className={active === item.id ? "active" : ""}
              onClick={() => { setActive(item.id); close(); }}
            >
              <Icon name={item.icon} />
              <span>{item.label}</span>
              {item.badge && <b>{item.badge}</b>}
            </button>
          ))}
        </nav>
        <div className="sidebar-foot">
          <div className="local-card">
            <div className="local-title">
              <StatusDot /> MODO LOCAL-FIRST
            </div>
            <p>Apenas leitura (Etapa 1). Nenhuma gravação é realizada.</p>
            <div>
              <span>Ambiente</span>
              <strong>Desenvolvimento</strong>
            </div>
          </div>
          <div className="profile">
            <div className="avatar">OP</div>
            <div>
              <strong>Operador do Arquivo</strong>
              <small>Administrador local</small>
            </div>
            <Icon name="chevron" size={16} />
          </div>
        </div>
      </aside>
    </>
  );
}

function Topbar({ menu }: { menu: () => void }) {
  const [searchOpen, setSearchOpen] = useState(false);
  return (
    <header className="topbar">
      <button className="mobile-menu" onClick={menu} aria-label="Abrir navegação">
        <Icon name="menu" />
      </button>
      <div className={`global-search ${searchOpen ? "mobile-open" : ""}`}>
        <Icon name="search" size={16} />
        <input aria-label="Pesquisar no arquivo" placeholder="Pesquisar no arquivo..." />
        <kbd>⌘ K</kbd>
      </div>
      <div className="top-actions">
        <button className="search-toggle" onClick={() => setSearchOpen(!searchOpen)} aria-label="Pesquisar">
          <Icon name="search" />
        </button>
        <div className="service">
          <StatusDot /> <span>Serviços operacionais</span>
        </div>
        <div className="divider" />
        <button className="icon-button" aria-label="Notificações" disabled>
          <Icon name="bell" /> <i />
        </button>
        <div className="date">
          <small>DATA DO ARQUIVO</small>
          <strong>ETAPA 1 — SOMENTE LEITURA</strong>
        </div>
      </div>
    </header>
  );
}

function AgentCard({ agent, onClick }: { agent: Agent; onClick: () => void }) {
  const tone = agent.status === "Em espera" ? "muted" : agent.status === "Em revisão" ? "gold" : "green";
  return (
    <button className="agent-card" onClick={onClick} disabled={!agent.name}>
      <div className="agent-top">
        <div className="agent-mark"><span>{agent.id}</span></div>
        <div className="agent-state">
          <StatusDot tone={tone} /> {agent.status}
        </div>
      </div>
      <div className="agent-name">{agent.name}</div>
      <div className="agent-role">{agent.role}</div>
      <div className="agent-rule" />
      <p>{agent.task}</p>
      <div className="progress"><span style={{ width: `${agent.progress}%` }} /></div>
      <em>{agent.progress}% de progresso na tarefa</em>
    </button>
  );
}

function EpisodeHero({ episode }: { episode: Episode | null }) {
  const title = episode ? episode.title : "O Guardião da Fortaleza Vidro Negro";
  const goal = episode ? episode.goal : "Um juramento ancestral. Uma fortaleza engolida pelas cinzas. E o último guardião de um segredo que deveria ter morrido com os antigos reis.";
  return (
    <section className="episode-hero">
      <div className="hero-content">
        <div className="episode-kicker"><span>EM PRODUÇÃO</span> <i /> EPISÓDIO {episode ? String(episode.id).padStart(3, '0') : '001'}</div>
        <h2>{title}</h2>
        <p>{goal}</p>
        <div className="hero-meta">
          <span><b>—</b> Duração prevista</span>
          <span><b>—</b> Quadros do storyboard</span>
          <span><b>—</b> Concluído</span>
        </div>
        <button className="continue-button" disabled>ABRIR EPISÓDIO <Icon name="arrow" size={16} /></button>
      </div>
      <div className="hero-art" aria-hidden="true">
        <div className="moon" /><div className="mountain m1" /><div className="mountain m2" /><div className="keep"><i /><i /><i /><span /></div><div className="mist" />
      </div>
    </section>
  );
}

function PipelineReal({ jobs }: { jobs: Job[] }) {
  const episodes = useMemo(() => {
    const map = new Map<number, { id: number; title: string; jobs: Job[] }>();
    jobs.forEach((j) => {
      if (!map.has(j.episode_id)) {
        map.set(j.episode_id, { id: j.episode_id, title: j.title, jobs: [] });
      }
      map.get(j.episode_id)!.jobs.push(j);
    });
    return Array.from(map.values()).sort((a, b) => a.id - b.id);
  }, [jobs]);

  return (
    <main className="main">
      <div className="page-heading">
        <div>
          <div className="eyebrow">SISTEMAS DO ARQUIVO</div>
          <h1>Fluxo de Produção</h1>
          <p>Estágios reais dos jobs por episódio, sem inventar dependências.</p>
        </div>
      </div>

      {episodes.length ? episodes.map((ep) => (
        <Panel key={ep.id} title={ep.title} eyebrow={`EPISÓDIO #${ep.id}`}>
          <div className="pipeline">
            {ep.jobs.length ? ep.jobs.sort((a, b) => a.id - b.id).map((j, index) => (
              <div className={`stage ${j.status}`} key={j.id}>
                <div className="stage-track">{index < ep.jobs.length - 1 && <i />}<span>{String(index + 1).padStart(2, "0")}</span></div>
                <strong>{j.role}</strong>
                <small>{j.status} · #{j.id}</small>
              </div>
            )) : (
              <div className="empty-state">
                <strong>Sem jobs</strong>
                <p>Este episódio não possui jobs registrados.</p>
              </div>
            )}
          </div>
        </Panel>
      )) : (
        <div className="empty-state">
          <Icon name="pipeline" size={32} />
          <strong>Nenhum episódio com jobs</strong>
          <p>O backend não retornou dados de pipeline.</p>
        </div>
      )}
    </main>
  );
}

function ApprovalQueue({ jobs }: { jobs: Job[] }) {
  const waiting = jobs.filter((j) => j.status === "waiting_approval");
  const [selected, setSelected] = useState<Job | null>(null);
  return (
    <Panel title="Fila de Aprovação" eyebrow={`${waiting.length} ${waiting.length === 1 ? "ITEM AGUARDANDO" : "ITENS AGUARDANDO"}`}>
      <div className="approval-list">
        {waiting.length === 0 ? (
          <div className="empty-state">
            <Icon name="shield" size={28} />
            <strong>Nenhum item aguardando aprovação</strong>
            <p>Os dados de jobs vêm do backend via /api/jobs.</p>
          </div>
        ) : (
          waiting.map((item) => (
            <button className="approval-row" key={item.id} onClick={() => setSelected(item)} disabled>
              <div className={`preview ${item.role === "artist" ? "gold" : item.role === "maester" ? "green" : "blue"}`}><span>IA</span></div>
              <div className="approval-copy">
                <small>{item.kind.toUpperCase()}</small>
                <strong>{item.title || `Job #${item.id}`}</strong>
                <p>{item.role} · {item.status}</p>
              </div>
              <Icon name="chevron" size={16} />
            </button>
          ))
        )}
      </div>
      {selected && (
        <div className="modal-wrap" role="dialog" aria-modal="true">
          <div className="modal-backdrop" onClick={() => setSelected(null)} />
          <div className="modal">
            <div className="modal-head">
              <div>
                <small>REVISÃO DO JOB</small>
                <h3>{selected.title || `Job #${selected.id}`}</h3>
              </div>
              <button onClick={() => setSelected(null)}><Icon name="close" /></button>
            </div>
            <div className={`review-preview ${selected.role === "artist" ? "gold" : selected.role === "maester" ? "green" : "blue"}`}>
              <div className="review-sigil">IRON<br />ARCHIVE</div>
              <span>DADOS DO BACKEND V2</span>
            </div>
            <div className="integration-note">
              <Icon name="shield" size={18} />
              <p><strong>Leitura apenas (Etapa 1).</strong> Esta visualização exibe dados reais do SQLite via Command Center. Nenhuma ação de aprovação ou rejeição é enviada.</p>
            </div>
            <div className="modal-actions">
              <Button variant="danger" disabled>REJEITAR</Button>
              <Button variant="gold" disabled>APROVAR</Button>
            </div>
          </div>
        </div>
      )}
    </Panel>
  );
}

function SystemHealth({ doctor }: { doctor: Doctor | null }) {
  const stats = doctor ? [
    {
      label: "PYTHON",
      value: doctor.python,
      unit: "",
      sub: "Intérprete do backend",
      pct: 100,
    },
    {
      label: "COMFYUI V2",
      value: doctor.comfyui?.reachable ? "Disponível" : "Indisponível",
      unit: "",
      sub: doctor.comfyui?.error || doctor.comfyui?.status ? `Status: ${doctor.comfyui.status || "erro"}` : "Verificar serviço",
      pct: doctor.comfyui?.reachable ? 100 : 0,
    },
    {
      label: "HERMES MODO",
      value: doctor.hermes_mode || "Não configurado",
      unit: "",
      sub: "Modo de execução",
      pct: doctor.hermes_mode ? 50 : 0,
    },
  ] : [
    { label: "PYTHON", value: "—", unit: "", sub: "Não disponível", pct: 0 },
    { label: "COMFYUI V2", value: "—", unit: "", sub: "Não disponível", pct: 0 },
    { label: "HERMES MODO", value: "—", unit: "", sub: "Não disponível", pct: 0 },
  ];

  const tools = doctor?.tools || {};
  return (
    <Panel title="Saúde do Sistema" eyebrow="RECURSOS LOCAIS">
      <div className="health-grid">
        {stats.map((s) => (
          <div className="health-item" key={s.label}>
            <small>{s.label}</small>
            <div>
              <strong>{s.value}</strong> <span>{s.unit}</span>
            </div>
            <div className="health-bar"><i style={{ width: `${s.pct}%` }} /></div>
            <p>{s.sub}</p>
          </div>
        ))}
      </div>
      <div className="model-row">
        <div>
          <span className="model-icon">LM</span>
          <div>
            <small>MODELO LOCAL</small>
            <strong>Hermes Agent</strong>
          </div>
        </div>
        <span className="configured">
          <StatusDot /> {doctor ? "DISPONÍVEL" : "INDISPONÍVEL"}
        </span>
      </div>
      <div style={{ padding: "0 22px 22px", fontSize: "7px", color: "#656967", letterSpacing: "0.1em", lineHeight: 1.6 }}>
        <strong>Ferramentas detectadas:</strong><br />
        {Object.entries(tools).map(([name, path]) => (
          <div key={name} style={{ marginBottom: 2 }}>
            {name}: {path ? path : "não encontrada"}
          </div>
        ))}
        {doctor?.paths && Object.entries(doctor.paths).map(([key, p]) => (
          <div key={`path-${key}`} style={{ marginBottom: 2 }}>
            {key}: {p.path} ({p.exists ? "existe" : "não encontrado"})
          </div>
        ))}
      </div>
    </Panel>
  );
}

function Activity({ events }: { events: Event[] }) {
  const fallback: Event[] = [
    { id: 0, job_id: 0, event: "Não disponível", at: "—", role: "Sistema" },
  ];
  const visible = events.length ? events : fallback;
  return (
    <Panel title="Atividade Recente" eyebrow="LOG DE EVENTOS">
      <div className="timeline">
        {visible.map((item) => (
          <div className="timeline-item" key={item.at + item.job_id}>
            <time>{item.at ? new Date(item.at).toLocaleTimeString("pt-BR", { hour: "2-digit", minute: "2-digit" }) : "—"}</time>
            <div className="timeline-mark"><StatusDot tone={item.tone as any} /><i /></div>
            <div>
              <small>{item.role || "Sistema"}</small>
              <strong>{item.event}</strong>
              {item.job_id && <p>Job #{item.job_id}</p>}
            </div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

function Overview({ roles, jobs, episodes }: { roles: Role[]; jobs: Job[]; episodes: Episode[] }) {
  const agentsFromRoles: Agent[] = useMemo(() => roles.map((r) => ({
    id: r.role.substring(0, 2).toUpperCase(),
    name: r.label.split(" — ")[0] || r.role,
    role: r.label.split(" — ")[1] || r.label,
    status: "Não disponível",
    task: `Tipo: ${r.kind}`,
    detail: `Papel do sistema V2`,
    progress: 0,
  })), [roles]);

  return (
    <main className="main">
      <div className="page-heading">
        <div>
          <div className="eyebrow">THE IRON ARCHIVE · OPERAÇÕES</div>
          <h1>Central de Comando</h1>
          <p>Supervisione o arquivo. Oriente os agentes. Dê forma à lenda.</p>
        </div>
        <div className="shift"><span><Icon name="clock" size={15} /> CICLO DE PRODUÇÃO</span> <strong>Etapa 01 <i /> Somente leitura</strong></div>
      </div>
      <EpisodeHero episode={episodes[0] || null} />
      <section className="section-block">
        <div className="section-title">
          <div>
            <span>O CONSELHO DO ARQUIVO</span>
            <h2>Rede de Agentes</h2>
          </div>
          <div className="network"><StatusDot /> {roles.length} papéis · {jobs.length} jobs</div>
        </div>
        <div className="agent-grid">{agentsFromRoles.map((a) => <AgentCard agent={a} key={a.name} onClick={() => {}} />)}</div>
      </section>
      <footer>
        <span>THE IRON ARCHIVE · CENTRAL DE COMANDO V2</span>
        <span>PROTÓTIPO LOCAL · SOMENTE LEITURA · ETAPA 1</span>
      </footer>
    </main>
  );
}

/* ============================================================
   TELA: EPISÓDIOS
   ============================================================ */
function EpisodeList({ episodes, jobs }: { episodes: Episode[]; jobs: Job[] }) {
  const [selectedEpisode, setSelectedEpisode] = useState<Episode | null>(null);
  const episodeJobs = selectedEpisode ? jobs.filter((j) => j.episode_id === selectedEpisode.id) : [];

  return (
    <main className="main">
      <div className="page-heading">
        <div>
          <div className="eyebrow">SISTEMAS DO ARQUIVO</div>
          <h1>Episódios</h1>
          <p>Listagem real de episódios e seus jobs associados no backend V2.</p>
        </div>
      </div>

      <section className="section-block">
        <div className="section-title">
          <div>
            <span>EPISÓDIOS</span>
            <h2>Catálogo</h2>
          </div>
          <div className="network"><StatusDot /> {episodes.length} episódio(s)</div>
        </div>

        <div className="agent-grid">
          {episodes.length ? episodes.map((ep) => (
            <button
              key={ep.id}
              className={`agent-card${selectedEpisode?.id === ep.id ? " active" : ""}`}
              onClick={() => setSelectedEpisode(ep.id === (selectedEpisode?.id || -1) ? null : ep)}
            >
              <div className="agent-top">
                <div className="agent-mark"><span>{String(ep.id).padStart(2, "0")}</span></div>
                <div className="agent-state">
                  <StatusDot tone="muted" /> {ep.slug}
                </div>
              </div>
              <div className="agent-name">{ep.title}</div>
              <div className="agent-role">{ep.goal.length > 60 ? ep.goal.slice(0, 60) + "…" : ep.goal}</div>
              <div className="agent-rule" />
              <p>Criado em: {new Date(ep.created_at).toLocaleString("pt-BR")}</p>
              <div className="progress"><span style={{ width: "50%" }} /></div>
              <em>{episodeJobs.length} job(s) associado(s)</em>
            </button>
          )) : (
            <div className="empty-state">
              <Icon name="book" size={32} />
              <strong>Nenhum episódio encontrado</strong>
              <p>O backend não retornou episódios via /api/episodes.</p>
            </div>
          )}
        </div>
      </section>

      {selectedEpisode && (
        <Panel title={`Jobs — ${selectedEpisode.title}`} eyebrow={`EPISÓDIO #${selectedEpisode.id}`}>
          <div className="approval-list">
            {episodeJobs.length ? episodeJobs.map((j) => (
              <button className="approval-row" key={j.id} disabled>
                <div className={`preview ${j.role === "artist" ? "gold" : j.role === "maester" ? "green" : "blue"}`}><span>{j.role.substring(0, 2).toUpperCase()}</span></div>
                <div className="approval-copy">
                  <small>{j.kind.toUpperCase()}</small>
                  <strong>{j.title || `Job #${j.id}`}</strong>
                  <p>{j.role} · {j.status} · tentativas: {j.attempts}</p>
                  {j.error && <p style={{ color: "#a97873", fontSize: "7px", marginTop: 4 }}>{j.error}</p>}
                </div>
                <Icon name="chevron" size={16} />
              </button>
            )) : (
              <div className="empty-state">
                <strong>Nenhum job para este episódio</strong>
                <p>Não há jobs associados ao episódio selecionado.</p>
              </div>
            )}
          </div>
        </Panel>
      )}
    </main>
  );
}

/* ============================================================
   TELA: AGENTES
   ============================================================ */
function AgentStatus({ roles, jobs }: { roles: Role[]; jobs: Job[] }) {
  const agentsWithJobs = roles.map((r) => {
    const roleJobs = jobs.filter((j) => j.role === r.role);
    const latest = roleJobs.sort((a, b) => new Date(b.updated_at).getTime() - new Date(a.updated_at).getTime())[0];
    return {
      role: r,
      latest,
      count: roleJobs.length,
      waiting: roleJobs.filter((j) => j.status === "waiting_approval").length,
      done: roleJobs.filter((j) => j.status === "done").length,
      failed: roleJobs.filter((j) => j.status === "failed").length,
    };
  });

  return (
    <main className="main">
      <div className="page-heading">
        <div>
          <div className="eyebrow">SISTEMAS DO ARQUIVO</div>
          <h1>Agentes</h1>
          <p>Seis papéis do sistema V2 com estados reais dos jobs.</p>
        </div>
      </div>

      <section className="section-block">
        <div className="section-title">
          <div>
            <span>O CONSELHO DO ARQUIVO</span>
            <h2>Rede de Agentes</h2>
          </div>
          <div className="network"><StatusDot /> {roles.length} papéis · {jobs.length} jobs totais</div>
        </div>

        <div className="agent-grid">
          {agentsWithJobs.map(({ role, latest, count, waiting, done, failed }) => {
            const tone = latest ? (latest.status === "waiting_approval" ? "gold" : latest.status === "done" ? "green" : "muted") : "muted";
            return (
              <button className="agent-card" key={role.role} disabled>
                <div className="agent-top">
                  <div className="agent-mark"><span>{role.role.substring(0, 2).toUpperCase()}</span></div>
                  <div className="agent-state">
                    <StatusDot tone={tone} /> {latest ? latest.status : "sem jobs"}
                  </div>
                </div>
                <div className="agent-name">{role.label.split(" — ")[0] || role.role}</div>
                <div className="agent-role">{role.label.split(" — ")[1] || role.role}</div>
                <div className="agent-rule" />
                <p>Tipo: {role.kind} · Jobs: {count}</p>
                <div className="progress"><span style={{ width: "40%" }} /></div>
                <em>{done} concluído · {waiting} aguardando · {failed} falhou</em>
              </button>
            );
          })}
        </div>
      </section>
    </main>
  );
}

/* ============================================================
   TELA: ESTÚDIO VISUAL
   ============================================================ */
function StudioVisual({ jobs }: { jobs: Job[] }) {
  const [outputOpen, setOutputOpen] = useState<{ jobId: number; content: string | null; loading: boolean } | null>(null);

  const artistJobs = jobs.filter((j) => j.role === "artist" && j.kind === "render");

  const fetchOutput = async (jobId: number) => {
    setOutputOpen({ jobId, content: null, loading: true });
    try {
      const res = await fetch(`/api/jobs/${jobId}/output`, { cache: "no-store" });
      if (!res.ok) {
        setOutputOpen({ jobId, content: `Erro HTTP ${res.status} ao carregar output.`, loading: false });
        return;
      }
      const text = await res.text();
      setOutputOpen({ jobId, content: text || "(output vazio)", loading: false });
    } catch (e) {
      setOutputOpen({ jobId, content: `Erro ao conectar: ${e instanceof Error ? e.message : "desconhecido"}`, loading: false });
    }
  };

  return (
    <main className="main">
      <div className="page-heading">
        <div>
          <div className="eyebrow">SISTEMAS DO ARQUIVO</div>
          <h1>Estúdio Visual</h1>
          <p>Jobs do Artist e metadados de saída. Nenhuma geração de imagem é realizada aqui.</p>
        </div>
      </div>

      <section className="section-block">
        <div className="section-title">
          <div>
            <span>ESTÚDIO VISUAL</span>
            <h2>Render de Imagens</h2>
          </div>
          <div className="network"><StatusDot tone="muted" /> {artistJobs.length} job(s) de render</div>
        </div>

        <div className="agent-grid">
          {artistJobs.length ? artistJobs.map((j) => {
            const canView = j.output_available === true;
            return (
              <button className="agent-card" key={j.id} onClick={canView ? () => fetchOutput(j.id) : undefined} disabled={!canView}>
                <div className="agent-top">
                  <div className="agent-mark"><span>AR</span></div>
                  <div className="agent-state">
                    <StatusDot tone={j.status === "done" ? "green" : j.status === "waiting_approval" ? "gold" : "muted"} />
                    {j.status}
                  </div>
                </div>
                <div className="agent-name">Job #{j.id}</div>
                <div className="agent-role">{j.title || "Render SDXL"}</div>
                <div className="agent-rule" />
                <p>Output disponível: {canView ? "sim" : "não"}</p>
                {canView ? (
                  <div className="progress"><span style={{ width: "30%" }} /></div>
                ) : (
                  <div className="empty-state" style={{ fontSize: "7px", color: "#81827e", marginTop: 8 }}>Arquivo de saída ainda não disponível</div>
                )}
                <em>Tentativas: {j.attempts}</em>
              </button>
            );
          }) : (
            <div className="empty-state">
              <Icon name="image" size={32} />
              <strong>Nenhum job de render</strong>
              <p>Não há jobs do Artist (role: artist, kind: render) no backend.</p>
            </div>
          )}
        </div>
      </section>

      {outputOpen && (
        <div className="modal-wrap" role="dialog" aria-modal="true">
          <div className="modal-backdrop" onClick={() => setOutputOpen(null)} />
          <div className="modal">
            <div className="modal-head">
              <div>
                <small>OUTPUT DO JOB #{outputOpen.jobId}</small>
                <h3>Conteúdo do arquivo de saída</h3>
              </div>
              <button onClick={() => setOutputOpen(null)}><Icon name="close" /></button>
            </div>
            <div style={{ padding: "20px", fontSize: "8px", fontFamily: "monospace", color: "#c9c5bd", background: "#11161b", border: "1px solid #272d31", maxHeight: "400px", overflowY: "auto" }}>
              {outputOpen.loading ? "Carregando output..." : outputOpen.content || "(sem conteúdo)"}
            </div>
            <div className="modal-actions">
              <Button variant="gold" disabled onClick={() => setOutputOpen(null)}>FECHAR</Button>
            </div>
          </div>
        </div>
      )}
    </main>
  );
}

/* ============================================================
   TELA: MONITOR DO SISTEMA
   ============================================================ */
function SystemMonitor({ doctor }: { doctor: Doctor | null }) {
  return (
    <main className="main">
      <div className="page-heading">
        <div>
          <div className="eyebrow">SISTEMAS DO ARQUIVO</div>
          <h1>Monitor do Sistema</h1>
          <p>Dados reais de diagnóstico do backend via GET /api/doctor.</p>
        </div>
      </div>

      <SystemHealth doctor={doctor} />

      <section className="section-block" style={{ marginTop: 30 }}>
        <div className="section-title">
          <div>
            <span>DIAGNÓSTICO</span>
            <h2>Estado dos Serviços</h2>
          </div>
        </div>
        <div className="service-grid">
          <ServiceCard
            label="PYTHON"
            value={doctor?.python || "—"}
            status={doctor?.python ? "detected" : "not-available"}
            detail="Intérprete do backend"
          />
          <ServiceCard
            label="HERMES AGENT"
            value={doctor?.hermes_mode || "—"}
            status="not-verified"
            detail="Execução não validada"
          />
          <ServiceCard
            label="COMFYUI V2"
            value={
              doctor?.comfyui?.enabled === false || !doctor?.comfyui
                ? "Monitoramento desativado"
                : doctor.comfyui.reachable
                  ? "Alcançável"
                  : "Não alcançável"
            }
            status={doctor?.comfyui?.reachable ? "operational" : "not-verified"}
            detail={
              doctor?.comfyui?.enabled === false
                ? "Diagnóstico desativado nas configurações"
                : !doctor?.comfyui
                  ? "Sem resposta do endpoint doctor"
                  : doctor.comfyui.reachable
                    ? "http://127.0.0.1:8188"
                    : doctor.comfyui.error || "Erro de conexão"
            }
          />
          <ServiceCard
            label="FFMPEG"
            value={
              doctor?.tools?.ffmpeg ? "Executável detectado" : "Não detectado"
            }
            status={doctor?.tools?.ffmpeg ? "detected" : "not-available"}
            detail={doctor?.tools?.ffmpeg || "Não encontrado no PATH"}
          />
          <ServiceCard
            label="GPU NVIDIA"
            value={
              doctor?.tools?.["nvidia-smi"]
                ? "Ferramenta nvidia-smi detectada"
                : "Não detectado"
            }
            status={doctor?.tools?.["nvidia-smi"] ? "detected" : "not-available"}
            detail="Uso de VRAM não disponível"
          />
        </div>
      </section>
    </main>
  );
}

/* ============================================================
   TELA: CONFIGURAÇÕES
   ============================================================ */
function SettingsView({ doctor }: { doctor: Doctor | null }) {
  return (
    <main className="main">
      <div className="page-heading">
        <div>
          <div className="eyebrow">SISTEMAS DO ARQUIVO</div>
          <h1>Configurações</h1>
          <p>Informações de diagnóstico disponíveis para consulta. Sem edição.</p>
        </div>
      </div>

      <Panel title="Diagnóstico do Backend" eyebrow="CONFIGURAÇÕES V2">
        <div style={{ padding: "20px", fontSize: "8px", lineHeight: 1.8, color: "#c9c5bd" }}>
          <p><strong>Versão Python:</strong> {doctor?.python || "—"}</p>
          <p><strong>Modo de execução Hermes:</strong> {doctor?.hermes_mode || "—"}</p>
          <p><strong>ComfyUI V2 alcançável:</strong> {doctor?.comfyui?.reachable ? "Sim" : "Não"}</p>
          {doctor?.comfyui?.error && <p><strong>Erro ComfyUI:</strong> {doctor.comfyui.error}</p>}
          <hr style={{ border: 0, borderTop: "1px solid #272d31", margin: "12px 0" }} />
          <p><strong>Caminhos configurados:</strong></p>
          {doctor?.paths && Object.entries(doctor.paths).map(([key, p]) => (
            <p key={key} style={{ marginLeft: "16px", fontSize: "7px", color: "#81827e" }}>
              {key}: {p.path} — {p.exists ? "existe" : "não encontrado"}
            </p>
          ))}
          <hr style={{ border: 0, borderTop: "1px solid #272d31", margin: "12px 0" }} />
          <p><strong>Ferramentas detectadas no PATH:</strong></p>
          {doctor?.tools && Object.entries(doctor.tools).map(([name, path]) => (
            <p key={name} style={{ marginLeft: "16px", fontSize: "7px", color: "#81827e" }}>
              {name}: {path || "não encontrada"}
            </p>
          ))}
          <hr style={{ border: 0, borderTop: "1px solid #272d31", margin: "12px 0" }} />
          <p><em>Todos os dados acima são obtidos via GET /api/doctor. Nenhum campo é editável nesta etapa.</em></p>
        </div>
      </Panel>

      <section className="section-block" style={{ marginTop: 30 }}>
        <div className="section-title">
          <div>
            <span>RESTRIÇÕES ETAPA 1</span>
            <h2>O que não está disponível</h2>
          </div>
        </div>
        <div className="placeholder-panel" style={{ textAlign: "left", maxWidth: "700px", margin: "0 auto" }}>
          <ul style={{ fontSize: "8px", color: "#81827e", lineHeight: 1.8, marginLeft: "20px" }}>
            <li>Não há edição de configurações do backend.</li>
            <li>Não há aprovação ou rejeição de jobs.</li>
            <li>Não há execução de pipeline ou geração de imagens.</li>
            <li>Não há download de modelos ou dependências.</li>
            <li>Não há alteração de SQLite, Git, jobs, approvals ou skills.</li>
            <li>O ComfyUI e o Artist permanecem pausados.</li>
          </ul>
        </div>
      </section>
    </main>
  );
}

/* ============================================================
   TELA: PLACEHOLDER (mantido para navegação futura)
   ============================================================ */
function Placeholder({ id }: { id: string }) {
  const item = navigation.find((n) => n.id === id)!;
  return (
    <main className="main placeholder-page">
      <div className="eyebrow">SISTEMAS DO ARQUIVO</div>
      <h1>{item.label}</h1>
      <div className="placeholder-panel">
        <div className="placeholder-icon"><Icon name={item.icon} size={32} /></div>
        <span>MÓDULO PRONTO PARA INTEGRAÇÃO</span>
        <h2>Área de {item.label}</h2>
        <p>Este destino está incluído na estrutura da central de comando. O fluxo de produção completo será conectado a interfaces locais em uma futura etapa de implementação.</p>
        <div className="integration-note"><Icon name="shield" /><p><strong>Protótipo de frontend.</strong> Nenhuma chamada aos serviços Hermes, SQLite, ComfyUI ou Python é realizada aqui.</p></div>
      </div>
    </main>
  );
}

const navigation = [
  { id: "overview", label: "Visão Geral", icon: "grid" },
  { id: "episodes", label: "Episódios", icon: "book" },
  { id: "agents", label: "Agentes", icon: "agents" },
  { id: "pipeline", label: "Fluxo de Produção", icon: "pipeline" },
  { id: "approvals", label: "Central de Aprovação", icon: "check", badge: 0 },
  { id: "studio", label: "Estúdio Visual", icon: "image" },
  { id: "monitor", label: "Monitor do Sistema", icon: "pulse" },
  { id: "logs", label: "Registros de Atividade", icon: "list" },
  { id: "settings", label: "Configurações", icon: "settings" },
];

export default function App() {
  const [active, setActive] = useState("overview");
  const [mobileNav, setMobileNav] = useState(false);
  const [selectedAgent, setSelectedAgent] = useState<Agent | null>(null);

  const [episodesState, setEpisodesState] = useState<DataState<Episode[]>>(createDataState<Episode[]>());
  const [jobsState, setJobsState] = useState<DataState<Job[]>>(createDataState<Job[]>());
  const [rolesState, setRolesState] = useState<DataState<Role[]>>(createDataState<Role[]>());
  const [eventsState, setEventsState] = useState<DataState<Event[]>>(createDataState<Event[]>());
  const [doctorState, setDoctorState] = useState<DataState<Doctor>>(createDataState<Doctor>());

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [eps, jobs, roles, logs, doc] = await Promise.all([
          api.episodes().catch(() => ({ episodes: [] })),
          api.jobs().catch(() => ({ jobs: [] })),
          api.roles().catch(() => ({ roles: [] })),
          api.logs(100).catch(() => ({ events: [] })),
          api.doctor().catch(() => null),
        ]);
        if (!cancelled) {
          setEpisodesState({ data: eps.episodes, loading: false, error: null });
          setJobsState({ data: jobs.jobs, loading: false, error: null });
          setRolesState({ data: roles.roles, loading: false, error: null });
          setEventsState({ data: logs.events, loading: false, error: null });
          setDoctorState({ data: doc, loading: false, error: null });
        }
      } catch (e) {
        if (!cancelled) {
          setEpisodesState({ data: null, loading: false, error: e instanceof Error ? e.message : "Erro desconhecido" });
          setJobsState({ data: null, loading: false, error: e instanceof Error ? e.message : "Erro desconhecido" });
          setRolesState({ data: null, loading: false, error: e instanceof Error ? e.message : "Erro desconhecido" });
          setEventsState({ data: null, loading: false, error: e instanceof Error ? e.message : "Erro desconhecido" });
          setDoctorState({ data: null, loading: false, error: e instanceof Error ? e.message : "Erro desconhecido" });
        }
      }
    }
    load();
    return () => { cancelled = true; };
  }, []);

  useEffect(() => {
    window.scrollTo({ top: 0, behavior: "smooth" });
  }, [active]);

  const loading = episodesState.loading || jobsState.loading || rolesState.loading;
  const error = episodesState.error || jobsState.error || rolesState.error || eventsState.error || doctorState.error;
  const episodes = episodesState.data || [];
  const jobs = jobsState.data || [];
  const roles = rolesState.data || [];
  const events = eventsState.data || [];
  const doctor = doctorState.data;

  return (
    <div className="app-shell">
      <Sidebar active={active} setActive={setActive} open={mobileNav} close={() => setMobileNav(false)} />
      <div className="workspace">
        <Topbar menu={() => setMobileNav(true)} />
        {error && (
          <div style={{ padding: "16px 24px", background: "#2d1a1a", border: "1px solid #593e3d", color: "#a97873", fontSize: "9px", marginBottom: 20 }}>
            <strong>Erro ao conectar ao backend:</strong> {error}<br />
            <small>Verifique se o Command Center está rodando em http://127.0.0.1:8765</small>
          </div>
        )}
        {loading ? (
          <main className="main"><div className="empty-state"><strong>Carregando dados do backend...</strong><p>Aguarde enquanto a central de comando consulta os endpoints GET do V2.</p></div></main>
        ) : active === "overview" ? (
          <Overview roles={roles} jobs={jobs} episodes={episodes} />
        ) : active === "episodes" ? (
          <EpisodeList episodes={episodes} jobs={jobs} />
        ) : active === "agents" ? (
          <AgentStatus roles={roles} jobs={jobs} />
        ) : active === "pipeline" ? (
          <PipelineReal jobs={jobs} />
        ) : active === "approvals" ? (
          <ApprovalQueue jobs={jobs} />
        ) : active === "studio" ? (
          <StudioVisual jobs={jobs} />
        ) : active === "monitor" ? (
          <SystemMonitor doctor={doctor} />
        ) : active === "logs" ? (
          <Activity events={events} />
        ) : active === "settings" ? (
          <SettingsView doctor={doctor} />
        ) : (
          <Placeholder id={active} />
        )}
       </div>
      {selectedAgent && (
        <div className="drawer-wrap">
          <div className="drawer-backdrop" onClick={() => setSelectedAgent(null)} />
          <aside className="detail-drawer">
            <button className="drawer-close" onClick={() => setSelectedAgent(null)}><Icon name="close" /></button>
            <div className="agent-mark large"><span>{selectedAgent.id}</span></div>
            <div className="eyebrow">AGENTE DO ARQUIVO</div>
            <h2>{selectedAgent.name}</h2>
            <p className="drawer-role">{selectedAgent.role}</p>
            <div className="drawer-status"><StatusDot tone="muted" /><span>{selectedAgent.status}</span></div>
            <div className="drawer-section"><small>ATRIBUIÇÃO ATUAL</small><strong>{selectedAgent.task}</strong><p>{selectedAgent.detail}</p><div className="progress"><span style={{ width: `${selectedAgent.progress}%` }} /></div><em>{selectedAgent.progress}% de progresso na tarefa</em></div>
            <div className="drawer-section"><small>STATUS DA INTEGRAÇÃO</small><div className="integration-note"><Icon name="shield" /><p><strong>Leitura apenas (Etapa 1).</strong> Os comandos permanecem desativados até que uma interface de backend local seja configurada.</p></div></div>
            <Button variant="gold" disabled>ABRIR CONSOLE DO AGENTE</Button>
          </aside>
        </div>
      )}
    </div>
  );
}
