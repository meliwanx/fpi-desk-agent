import { useEffect, useState } from "react";
import {
  DEFAULT_MODEL_PROTOCOL,
  addModelToPolicy,
  ensureModelPolicyDefault,
  normaliseModelPolicy,
  removeModelFromPolicy,
  setDefaultModelInPolicy,
  updateModelInPolicy,
  type ModelEntry,
  type ModelPolicy,
} from "./modelPolicy";

type Tab = "overview" | "sessions" | "risks" | "tools" | "users" | "models" | "updates";

interface UserInfo {
  id: string;
  email: string;
  display_name: string;
  role: string;
  is_active?: boolean;
}

interface LoginResponse {
  token: string;
  user: UserInfo;
}

interface Summary {
  sessions: { total: number };
  messages: { total: number };
  files: { total: number; uploaded: number };
  tool_calls: { total: number };
  risks: { total: number; open: number };
  usage: {
    input_tokens: number;
    output_tokens: number;
    reasoning_tokens: number;
    cache_read_tokens: number;
    cache_write_tokens: number;
    total_tokens: number;
    cost: number;
  };
}

interface AuditSession {
  id: string;
  title: string;
  workspace: string;
  user_email: string;
  user_display_name: string;
  model_id: string | null;
  provider_id: string | null;
  time_updated: string;
}

interface RiskItem {
  id: string;
  session_id: string;
  kind: string;
  severity: string;
  status: string;
  summary: string;
  evidence_preview: string;
  workspace: string;
  session_title: string;
  employee: { display_name: string; email: string } | null;
  time_updated: string;
}

interface ToolCallItem {
  id: string;
  session_id: string;
  tool: string;
  call_id: string;
  status: string;
  title: string;
  input: Record<string, unknown>;
  output_preview: string;
  workspace: string;
  session_title: string;
  employee: { display_name: string; email: string } | null;
  time_updated: string;
}

interface TranscriptPart {
  id: string;
  type: string;
  data: Record<string, unknown>;
  file?: {
    name: string;
    size: number;
    mime_type: string;
    content_uploaded: boolean;
    download_url: string | null;
  } | null;
  tool_call?: TranscriptToolCall | null;
  usage?: TranscriptUsage | null;
  risks?: TranscriptRisk[];
}

interface TranscriptMessage {
  id: string;
  role: string;
  data: Record<string, unknown>;
  parts: TranscriptPart[];
}

interface TranscriptToolCall {
  tool: string;
  call_id: string;
  status: string;
  title: string;
  input: Record<string, unknown>;
  output_preview: string;
  metadata: Record<string, unknown>;
}

interface TranscriptUsage {
  finish_reason: string;
  input_tokens: number;
  output_tokens: number;
  reasoning_tokens: number;
  cache_read_tokens: number;
  cache_write_tokens: number;
  total_tokens: number;
  cost: number;
}

interface TranscriptRisk {
  id: string;
  kind: string;
  severity: string;
  status: string;
  summary: string;
  evidence_preview: string;
}

interface UpdatePolicy {
  enabled: boolean;
  latest_version: string;
  min_supported_version: string;
  force_update: boolean;
  release_notes: string;
  macos_download_url: string;
  windows_download_url: string;
  linux_download_url: string;
  default_download_url: string;
}

const SESSION_KEY = "fpi-admin-session";

function formatNumber(value: number): string {
  return new Intl.NumberFormat("zh-CN").format(value || 0);
}

function compactDate(value: string): string {
  if (!value) return "";
  return new Date(value).toLocaleString("zh-CN", { hour12: false });
}

function storedSession(): LoginResponse | null {
  try {
    const raw = localStorage.getItem(SESSION_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

function roleLabel(role: string): string {
  return {
    user: "员工",
    assistant: "助手",
    system: "系统",
    tool: "工具",
  }[role] || role || "消息";
}

function partTypeLabel(type: string): string {
  return {
    text: "文本",
    reasoning: "思考",
    tool: "工具",
    tool_call: "工具",
    step_finish: "用量",
    file: "文件",
  }[type] || type || "内容";
}

function formatAuditValue(value: unknown): string {
  if (value === null || value === undefined || value === "") return "-";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value, null, 2);
}

function compactAuditValue(value: unknown, limit = 160): string {
  const text = formatAuditValue(value).replace(/\s+/g, " ").trim();
  return text.length > limit ? `${text.slice(0, limit)}...` : text;
}

function textFromPart(part: TranscriptPart): string {
  const keys = ["text", "content", "message", "output", "result", "title"];
  for (const key of keys) {
    const value = part.data?.[key];
    if (typeof value === "string" && value.trim()) return value;
  }
  if (!part.tool_call && !part.file && !part.usage && Object.keys(part.data || {}).length > 0) {
    return JSON.stringify(part.data, null, 2);
  }
  return "";
}

function KeyValueGrid({ value }: { value: Record<string, unknown> }) {
  const entries = Object.entries(value || {}).filter(([, item]) => item !== undefined && item !== null && item !== "");
  if (entries.length === 0) return <span className="muted">无</span>;
  return (
    <div className="kv-grid">
      {entries.map(([key, item]) => (
        <div className="kv-item" key={key}>
          <span>{key}</span>
          <strong>{compactAuditValue(item)}</strong>
        </div>
      ))}
    </div>
  );
}

function RawDataDetails({ data }: { data: unknown }) {
  return (
    <details className="raw-details">
      <summary>查看原始数据</summary>
      <pre>{JSON.stringify(data, null, 2)}</pre>
    </details>
  );
}

function AuditPartView({ part, token }: { part: TranscriptPart; token: string }) {
  const text = textFromPart(part);
  const hasStructured = Boolean(part.tool_call || part.file || part.usage || (part.risks && part.risks.length > 0));
  return (
    <div className="audit-part">
      <div className="audit-part-header">
        <span className="badge">{partTypeLabel(part.type)}</span>
        {part.risks?.map((risk) => (
          <span className={`pill ${risk.severity}`} key={risk.id}>{risk.summary || risk.kind}</span>
        ))}
      </div>

      {text && <div className="audit-text">{text}</div>}

      {part.file && (
        <div className="audit-box">
          <div>
            <strong>{part.file.name}</strong>
            <div className="muted">{part.file.mime_type || "文件"} · {formatNumber(part.file.size)} bytes</div>
          </div>
          {part.file.content_uploaded && part.file.download_url ? (
            <button className="button outline" onClick={() => void downloadFile(part.file!.download_url!, token)}>下载</button>
          ) : (
            <span className="muted">未同步原件</span>
          )}
        </div>
      )}

      {part.tool_call && (
        <div className="audit-box vertical">
          <div className="audit-box-title">
            <strong>{part.tool_call.title || part.tool_call.tool}</strong>
            <span className="pill">{part.tool_call.status || "unknown"}</span>
          </div>
          <KeyValueGrid value={part.tool_call.input || {}} />
          {part.tool_call.output_preview && (
            <div className="output-preview">{part.tool_call.output_preview}</div>
          )}
        </div>
      )}

      {part.usage && (
        <div className="usage-grid compact">
          <span>输入：{formatNumber(part.usage.input_tokens)}</span>
          <span>输出：{formatNumber(part.usage.output_tokens)}</span>
          <span>推理：{formatNumber(part.usage.reasoning_tokens)}</span>
          <span>总计：{formatNumber(part.usage.total_tokens)}</span>
          <span>结束：{part.usage.finish_reason || "-"}</span>
          <span>成本：${Number(part.usage.cost || 0).toFixed(4)}</span>
        </div>
      )}

      {hasStructured && Object.keys(part.data || {}).length > 0 && <RawDataDetails data={part.data} />}
    </div>
  );
}

async function downloadFile(url: string, token: string): Promise<void> {
  const response = await fetch(url, { headers: { "X-FPI-Session": token } });
  if (!response.ok) throw new Error(await response.text());
  const blob = await response.blob();
  const disposition = response.headers.get("content-disposition") || "";
  const match = disposition.match(/filename="?([^";]+)"?/i);
  const filename = match ? decodeURIComponent(match[1]) : "attachment";
  const objectUrl = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = objectUrl;
  anchor.download = filename;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  URL.revokeObjectURL(objectUrl);
}

function useApi(token: string) {
  return async function api<T>(path: string, init: RequestInit = {}): Promise<T> {
    const headers = new Headers(init.headers);
    if (!(init.body instanceof FormData)) headers.set("Content-Type", "application/json");
    if (token) headers.set("X-FPI-Session", token);
    const response = await fetch(path, { ...init, headers });
    if (!response.ok) throw new Error(await response.text());
    if (response.status === 204) return null as T;
    return response.json() as Promise<T>;
  };
}

export function App() {
  const [session, setSession] = useState<LoginResponse | null>(() => storedSession());
  const [tab, setTab] = useState<Tab>("overview");
  const token = session?.token ?? "";
  const api = useApi(token);

  function logout() {
    localStorage.removeItem(SESSION_KEY);
    setSession(null);
  }

  if (!session) {
    return <Login onLogin={setSession} />;
  }

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">FPI</div>
          <div>
            <div className="brand-title">管理后台</div>
            <div className="brand-subtitle">企业审计与管控</div>
          </div>
        </div>
        <nav className="nav">
          {[
            ["overview", "总览"],
            ["sessions", "会话审计"],
            ["risks", "风险发现"],
            ["tools", "工具调用"],
            ["users", "员工管理"],
            ["models", "模型管控"],
            ["updates", "版本更新"],
          ].map(([key, label]) => (
            <button
              key={key}
              className={`nav-item ${tab === key ? "active" : ""}`}
              onClick={() => setTab(key as Tab)}
            >
              {label}
            </button>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="muted">{session.user.display_name || session.user.email}</div>
          <button className="button ghost full" onClick={logout}>退出登录</button>
        </div>
      </aside>

      <main className="content">
        <header className="page-header">
          <div>
            <h1>{tabTitle(tab)}</h1>
            <p>{tabSubtitle(tab)}</p>
          </div>
          <button className="button outline" onClick={() => window.location.reload()}>刷新</button>
        </header>

        {tab === "overview" && <Overview api={api} />}
        {tab === "sessions" && <Sessions api={api} token={token} />}
        {tab === "risks" && <Risks api={api} />}
        {tab === "tools" && <ToolCalls api={api} />}
        {tab === "users" && <Users api={api} />}
        {tab === "models" && <ModelPolicyPanel api={api} />}
        {tab === "updates" && <UpdatePolicyPanel api={api} />}
      </main>
    </div>
  );
}

function tabTitle(tab: Tab): string {
  return {
    overview: "企业审计总览",
    sessions: "会话审计",
    risks: "风险发现",
    tools: "工具调用",
    users: "员工管理",
    models: "模型管控",
    updates: "版本更新",
  }[tab];
}

function tabSubtitle(tab: Tab): string {
  return {
    overview: "查看员工使用规模、token 消耗、风险和文件同步情况。",
    sessions: "按员工、工作区查看每一条对话记录和上传文件。",
    risks: "集中处理敏感内容、密钥、订阅链接等风险线索。",
    tools: "审计模型调用的本地工具、输入、输出和状态。",
    users: "创建员工账号、查看角色和启用状态。",
    models: "统一控制客户端可见模型和默认模型。",
    updates: "发布客户端版本策略，控制是否强制员工升级。",
  }[tab];
}

function Login({ onLogin }: { onLogin: (payload: LoginResponse) => void }) {
  const [email, setEmail] = useState("admin");
  const [password, setPassword] = useState("admin123");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);

  async function login() {
    setLoading(true);
    setError("");
    try {
      const response = await fetch("/api/company-auth/login", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email, password }),
      });
      if (!response.ok) throw new Error(await response.text());
      const payload = (await response.json()) as LoginResponse;
      localStorage.setItem(SESSION_KEY, JSON.stringify(payload));
      onLogin(payload);
    } catch {
      setError("登录失败，请检查账号和密码");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="login-page">
      <section className="card login-card">
        <div className="brand login-brand">
          <div className="brand-mark">FPI</div>
          <div>
            <div className="brand-title">fpi-agent 管理后台</div>
            <div className="brand-subtitle">企业审计与模型管控</div>
          </div>
        </div>
        <label>账号</label>
        <input className="input" value={email} onChange={(e) => setEmail(e.target.value)} />
        <label>密码</label>
        <input
          className="input"
          type="password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Enter") void login();
          }}
        />
        <button className="button full" disabled={loading} onClick={() => void login()}>
          {loading ? "登录中..." : "登录"}
        </button>
        {error && <p className="error">{error}</p>}
      </section>
    </div>
  );
}

function Overview({ api }: { api: ReturnType<typeof useApi> }) {
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState("");

  useEffect(() => {
    api<Summary>("/api/admin/audit/summary").then(setSummary).catch(() => setError("总览加载失败"));
  }, [api]);

  if (error) return <div className="card error">{error}</div>;
  if (!summary) return <div className="card muted">加载中...</div>;

  const cards = [
    ["会话", summary.sessions.total],
    ["消息", summary.messages.total],
    ["工具调用", summary.tool_calls.total],
    ["开放风险", summary.risks.open],
    ["已同步文件", summary.files.uploaded],
    ["Token", summary.usage.total_tokens],
  ] as const;

  return (
    <div className="grid">
      {cards.map(([label, value]) => (
        <div className="stat-card" key={label}>
          <span>{label}</span>
          <strong>{formatNumber(value)}</strong>
        </div>
      ))}
      <div className="card wide">
        <h2>用量归因</h2>
        <div className="usage-grid">
          <span>输入：{formatNumber(summary.usage.input_tokens)}</span>
          <span>输出：{formatNumber(summary.usage.output_tokens)}</span>
          <span>推理：{formatNumber(summary.usage.reasoning_tokens)}</span>
          <span>缓存读：{formatNumber(summary.usage.cache_read_tokens)}</span>
          <span>缓存写：{formatNumber(summary.usage.cache_write_tokens)}</span>
          <span>成本：${summary.usage.cost.toFixed(4)}</span>
        </div>
      </div>
    </div>
  );
}

function Sessions({ api, token }: { api: ReturnType<typeof useApi>; token: string }) {
  const [query, setQuery] = useState("");
  const [sessions, setSessions] = useState<AuditSession[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [messages, setMessages] = useState<TranscriptMessage[]>([]);

  async function loadSessions() {
    const data = await api<{ items: AuditSession[] }>(`/api/admin/audit/sessions?q=${encodeURIComponent(query)}`);
    setSessions(data.items);
  }

  async function loadTranscript(sessionId: string) {
    setSelected(sessionId);
    const data = await api<{ messages: TranscriptMessage[] }>(`/api/admin/audit/sessions/${encodeURIComponent(sessionId)}/messages`);
    setMessages(data.messages);
  }

  useEffect(() => {
    void loadSessions();
  }, []);

  const files = messages.flatMap((message) =>
    message.parts.filter((part) => part.file).map((part) => ({ partId: part.id, ...part.file! })),
  );

  return (
    <div className="split">
      <section className="card">
        <div className="toolbar">
          <input className="input" placeholder="搜索员工、标题、工作区" value={query} onChange={(e) => setQuery(e.target.value)} />
          <button className="button" onClick={() => void loadSessions()}>搜索</button>
        </div>
        <div className="list">
          {sessions.map((session) => (
            <button
              key={session.id}
              className={`list-item ${selected === session.id ? "active" : ""}`}
              onClick={() => void loadTranscript(session.id)}
            >
              <strong>{session.title || "未命名会话"}</strong>
              <span>{session.user_display_name || session.user_email}</span>
              <small>{session.workspace || "无工作区"} · {compactDate(session.time_updated)}</small>
            </button>
          ))}
        </div>
      </section>
      <section className="card transcript">
        <h2>对话详情</h2>
        {files.length > 0 && (
          <div className="file-list">
            {files.map((file) => (
              <div className="file-row" key={file.partId}>
                <span>{file.name} · {formatNumber(file.size)} bytes</span>
                {file.content_uploaded && file.download_url ? (
                  <button className="button outline" onClick={() => void downloadFile(file.download_url!, token)}>下载</button>
                ) : (
                  <span className="muted">未同步原件</span>
                )}
              </div>
            ))}
          </div>
        )}
        {messages.length === 0 ? (
          <p className="muted">选择左侧会话查看详情</p>
        ) : (
          messages.map((message) => (
            <article className="message" key={message.id}>
              <div className="message-head">
                <span className={`role-badge ${message.role}`}>{roleLabel(message.role)}</span>
                <span className="muted">{message.parts.length} 条内容</span>
              </div>
              {message.parts.map((part) => (
                <AuditPartView key={part.id} part={part} token={token} />
              ))}
            </article>
          ))
        )}
      </section>
    </div>
  );
}

function Risks({ api }: { api: ReturnType<typeof useApi> }) {
  const [items, setItems] = useState<RiskItem[]>([]);

  useEffect(() => {
    api<{ items: RiskItem[] }>("/api/admin/audit/risks").then((data) => setItems(data.items)).catch(() => setItems([]));
  }, [api]);

  return (
    <section className="card">
      <table>
        <thead><tr><th>等级</th><th>类型</th><th>员工</th><th>会话</th><th>证据</th><th>时间</th></tr></thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td><span className={`pill ${item.severity}`}>{item.severity}</span></td>
              <td>{item.kind}</td>
              <td>{item.employee?.display_name || item.employee?.email || "-"}</td>
              <td>{item.session_title || item.session_id}</td>
              <td className="mono">{item.evidence_preview}</td>
              <td>{compactDate(item.time_updated)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function ToolCalls({ api }: { api: ReturnType<typeof useApi> }) {
  const [items, setItems] = useState<ToolCallItem[]>([]);

  useEffect(() => {
    api<{ items: ToolCallItem[] }>("/api/admin/audit/tool-calls").then((data) => setItems(data.items)).catch(() => setItems([]));
  }, [api]);

  return (
    <section className="card">
      <table>
        <thead><tr><th>工具</th><th>状态</th><th>员工</th><th>会话</th><th>输入</th><th>输出摘要</th></tr></thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>{item.tool}</td>
              <td><span className="pill">{item.status}</span></td>
              <td>{item.employee?.display_name || item.employee?.email || "-"}</td>
              <td>{item.session_title || item.session_id}</td>
              <td className="tool-input-cell"><KeyValueGrid value={item.input || {}} /></td>
              <td className="mono">{compactAuditValue(item.output_preview, 260)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </section>
  );
}

function Users({ api }: { api: ReturnType<typeof useApi> }) {
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("user");
  const [error, setError] = useState("");

  async function loadUsers() {
    const data = await api<UserInfo[]>("/api/admin/users");
    setUsers(data);
  }

  async function createUser() {
    setError("");
    try {
      await api("/api/admin/users", {
        method: "POST",
        body: JSON.stringify({ email, display_name: displayName, password, role }),
      });
      setEmail("");
      setDisplayName("");
      setPassword("");
      await loadUsers();
    } catch {
      setError("新增员工失败");
    }
  }

  useEffect(() => {
    void loadUsers();
  }, []);

  return (
    <div className="stack">
      <section className="card">
        <h2>新增员工</h2>
        <div className="form-grid">
          <input className="input" placeholder="账号 / 工号" value={email} onChange={(e) => setEmail(e.target.value)} />
          <input className="input" placeholder="姓名" value={displayName} onChange={(e) => setDisplayName(e.target.value)} />
          <input className="input" placeholder="初始密码" value={password} onChange={(e) => setPassword(e.target.value)} />
          <select className="input" value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="user">员工</option>
            <option value="admin">管理员</option>
          </select>
          <button className="button" onClick={() => void createUser()}>新增</button>
        </div>
        {error && <p className="error">{error}</p>}
      </section>
      <section className="card">
        <table>
          <thead><tr><th>账号</th><th>姓名</th><th>角色</th><th>状态</th></tr></thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id}><td>{user.email}</td><td>{user.display_name}</td><td>{user.role}</td><td>{user.is_active ? "启用" : "停用"}</td></tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

function ModelPolicyPanel({ api }: { api: ReturnType<typeof useApi> }) {
  const [policy, setPolicy] = useState<ModelPolicy | null>(null);
  const [message, setMessage] = useState("");

  async function loadPolicy() {
    const data = await api<ModelPolicy>("/api/admin/model-policy");
    setPolicy(normaliseModelPolicy(data));
  }

  useEffect(() => {
    void loadPolicy();
  }, []);

  function updateModel(index: number, patch: Partial<ModelEntry>) {
    if (!policy) return;
    setPolicy(updateModelInPolicy(policy, index, patch));
  }

  async function savePolicy() {
    if (!policy) return;
    setMessage("");
    try {
      const payload = ensureModelPolicyDefault(policy);
      const saved = await api<ModelPolicy>("/api/admin/model-policy", {
        method: "PUT",
        body: JSON.stringify(payload),
      });
      setPolicy(normaliseModelPolicy(saved));
      setMessage("已保存，员工客户端下次刷新模型列表后生效");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存失败");
    }
  }

  if (!policy) return <section className="card muted">加载中...</section>;

  return (
    <section className="card">
      <div className="toolbar">
        <button
          className="button outline"
          onClick={() => setPolicy(addModelToPolicy(policy, {
            provider_id: `custom_${Math.random().toString(36).slice(2, 8)}`,
            id: "",
            name: "",
            protocol: DEFAULT_MODEL_PROTOCOL,
            base_url: "https://",
            api_key: "",
          }))}
        >
          添加模型
        </button>
        <button className="button" onClick={() => void savePolicy()}>保存策略</button>
      </div>
      <div className="model-list">
        {policy.models.map((model, index) => (
          <div className="model-row" key={`${index}-${model.provider_id}-${model.id}`}>
            <label className="default-model-choice">
              <input
                type="radio"
                name="default-model"
                checked={model.provider_id === policy.default_provider_id && model.id === policy.default_model_id}
                disabled={!model.provider_id.trim() || !model.id.trim()}
                onChange={() => setPolicy(setDefaultModelInPolicy(policy, index))}
              />
              <span>默认</span>
            </label>
            <label className="model-field">
              <span>协议</span>
              <select className="input" value={model.protocol || DEFAULT_MODEL_PROTOCOL} onChange={(e) => updateModel(index, { protocol: e.target.value })}>
                <option value="openai_compatible">OpenAI 兼容</option>
                <option value="anthropic">Anthropic</option>
              </select>
            </label>
            <label className="model-field">
              <span>供应商 ID</span>
              <input className="input" placeholder="custom_provider" value={model.provider_id} onChange={(e) => updateModel(index, { provider_id: e.target.value })} />
            </label>
            <label className="model-field model-field-wide">
              <span>Base URL</span>
              <input className="input" placeholder={model.protocol === "anthropic" ? "Anthropic 可留空" : "https://example.com/v1"} value={model.base_url} onChange={(e) => updateModel(index, { base_url: e.target.value })} />
            </label>
            <label className="model-field">
              <span>Model</span>
              <input className="input" placeholder="gpt-5.5" value={model.id} onChange={(e) => updateModel(index, { id: e.target.value })} />
            </label>
            <label className="model-field">
              <span>显示名称</span>
              <input className="input" placeholder="GPT-5.5" value={model.name} onChange={(e) => updateModel(index, { name: e.target.value })} />
            </label>
            <label className="model-field model-field-wide">
              <span>API Key</span>
              <input
                className="input"
                type="password"
                placeholder={model.masked_key ? `已保存 ${model.masked_key}，留空不修改` : "sk-..."}
                value={model.api_key || ""}
                onChange={(e) => updateModel(index, { api_key: e.target.value })}
              />
            </label>
            <button
              className="button ghost"
              onClick={() => setPolicy(removeModelFromPolicy(policy, index))}
            >
              移除
            </button>
          </div>
        ))}
      </div>
      {message && <p className={message.startsWith("已保存") ? "success" : "error"}>{message}</p>}
    </section>
  );
}

function UpdatePolicyPanel({ api }: { api: ReturnType<typeof useApi> }) {
  const [policy, setPolicy] = useState<UpdatePolicy | null>(null);
  const [message, setMessage] = useState("");

  async function loadPolicy() {
    const data = await api<UpdatePolicy>("/api/admin/update-policy");
    setPolicy(data);
  }

  useEffect(() => {
    void loadPolicy();
  }, []);

  function updatePolicy(patch: Partial<UpdatePolicy>) {
    if (!policy) return;
    setPolicy({ ...policy, ...patch });
  }

  async function savePolicy() {
    if (!policy) return;
    setMessage("");
    try {
      const saved = await api<UpdatePolicy>("/api/admin/update-policy", {
        method: "PUT",
        body: JSON.stringify(policy),
      });
      setPolicy(saved);
      setMessage("已保存，员工客户端启动或下次检查更新时生效");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存失败");
    }
  }

  if (!policy) return <section className="card muted">加载中...</section>;

  return (
    <div className="stack">
      <section className="card">
        <div className="toolbar">
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={policy.enabled}
              onChange={(event) => updatePolicy({ enabled: event.target.checked })}
            />
            <span>启用更新检查</span>
          </label>
          <label className="checkbox-row">
            <input
              type="checkbox"
              checked={policy.force_update}
              onChange={(event) => updatePolicy({ force_update: event.target.checked })}
            />
            <span>新版发布后强制更新</span>
          </label>
          <button className="button" onClick={() => void savePolicy()}>保存策略</button>
        </div>
        <div className="hint">
          把安装包放到服务器、对象存储或 CDN 后，将下载地址填到对应平台。最低可用版本以下的客户端会被强制更新；非强制更新时，旧版本仍可继续使用。
        </div>
        <div className="form-grid update-form">
          <label className="model-field">
            <span>最新版号</span>
            <input
              className="input"
              placeholder="1.4.0"
              value={policy.latest_version}
              onChange={(event) => updatePolicy({ latest_version: event.target.value })}
            />
          </label>
          <label className="model-field">
            <span>最低可用版本</span>
            <input
              className="input"
              placeholder="1.3.0"
              value={policy.min_supported_version}
              onChange={(event) => updatePolicy({ min_supported_version: event.target.value })}
            />
          </label>
          <label className="model-field model-field-wide">
            <span>macOS 下载地址</span>
            <input
              className="input"
              placeholder="https://example.com/fpi-agent-1.4.0.dmg"
              value={policy.macos_download_url}
              onChange={(event) => updatePolicy({ macos_download_url: event.target.value })}
            />
          </label>
          <label className="model-field model-field-wide">
            <span>Windows 下载地址</span>
            <input
              className="input"
              placeholder="https://example.com/fpi-agent-1.4.0.exe"
              value={policy.windows_download_url}
              onChange={(event) => updatePolicy({ windows_download_url: event.target.value })}
            />
          </label>
          <label className="model-field model-field-wide">
            <span>Linux 下载地址</span>
            <input
              className="input"
              placeholder="https://example.com/fpi-agent-1.4.0.deb"
              value={policy.linux_download_url}
              onChange={(event) => updatePolicy({ linux_download_url: event.target.value })}
            />
          </label>
          <label className="model-field model-field-wide">
            <span>默认下载地址</span>
            <input
              className="input"
              placeholder="https://example.com/fpi-agent-1.4.0.zip"
              value={policy.default_download_url}
              onChange={(event) => updatePolicy({ default_download_url: event.target.value })}
            />
          </label>
          <label className="model-field model-field-wide">
            <span>更新说明</span>
            <textarea
              className="input textarea"
              placeholder="本次更新修复了..."
              value={policy.release_notes}
              onChange={(event) => updatePolicy({ release_notes: event.target.value })}
            />
          </label>
        </div>
        {message && <p className={message.startsWith("已保存") ? "success" : "error"}>{message}</p>}
      </section>
    </div>
  );
}
