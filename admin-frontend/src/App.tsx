import { useEffect, useState } from "react";
import {
  DEFAULT_MODEL_PROTOCOL,
  addModelToPolicy,
  ensureModelPolicyDefault,
  normaliseModelPolicy,
  setDefaultModelInPolicy,
  updateModelInPolicy,
  type ModelEntry,
  type ModelPolicy,
} from "./modelPolicy";

type Tab =
  | "overview"
  | "sessions"
  | "allInfo"
  | "analytics"
  | "risks"
  | "tools"
  | "feedback"
  | "users"
  | "actions"
  | "models"
  | "updates";

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
  activity: {
    daily_active_users: number;
    online_users: number;
    online_sessions: number;
    redis?: {
      enabled: boolean;
      available: boolean;
    };
    series: Array<{
      date: string;
      active_users: number;
      session_count: number;
    }>;
  };
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

interface CompanySession {
  id: string;
  user_id: string;
  user_email: string;
  user_display_name: string;
  user_role: string;
  user_is_active: boolean;
  device_id: string;
  device_name: string;
  platform: string;
  app_version: string;
  ip_address: string;
  user_agent: string;
  is_online: boolean;
  expires_at: string;
  revoked_at: string | null;
  time_created: string;
  last_seen_at: string;
  revoked_by_email: string;
  revoked_reason: string;
}

interface AuditSession {
  id: string;
  title: string;
  workspace: string;
  user_id?: string;
  user_email: string;
  user_display_name: string;
  model_id: string | null;
  provider_id: string | null;
  time_created: string;
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

interface AdminActionItem {
  id: string;
  actor_user_id: string;
  actor_email: string;
  actor_display_name: string;
  action: string;
  target_type: string;
  target_id: string;
  metadata: Record<string, unknown>;
  time_created: string;
  time_updated: string;
}

interface FeedbackItem {
  id: string;
  user_id: string;
  user_email: string;
  user_display_name: string;
  description: string;
  image_original_filename: string;
  image_mime_type: string;
  image_size_bytes: number;
  image_sha256: string;
  image_download_url: string | null;
  time_created: string;
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
  model_id: string | null;
  provider_id: string | null;
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

interface AuditEntry extends TranscriptPart {
  time_created: string;
  message: {
    id: string;
    role: string;
    data: Record<string, unknown>;
    model_id: string | null;
    provider_id: string | null;
    time_created: string;
  };
  session: AuditSession | null;
}

interface UpdatePolicy {
  enabled: boolean;
  latest_version: string;
  min_supported_version: string;
  force_update: boolean;
  release_notes: string;
  macos_asset_id: string;
  windows_asset_id: string;
  linux_asset_id: string;
  default_asset_id: string;
  macos_asset: UpdateAsset | null;
  windows_asset: UpdateAsset | null;
  linux_asset: UpdateAsset | null;
  default_asset: UpdateAsset | null;
  macos_download_url: string;
  windows_download_url: string;
  linux_download_url: string;
  default_download_url: string;
}

interface UpdateAsset {
  id: string;
  platform: string;
  version: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
  signature: string;
  uploaded_by_user_id: string;
  uploaded_by_email: string;
  uploaded_by_display_name: string;
  download_count: number;
  time_created: string;
  time_updated: string;
}

type UpdateAssetIdKey = "macos_asset_id" | "windows_asset_id" | "linux_asset_id" | "default_asset_id";
type UpdateAssetKey = "macos_asset" | "windows_asset" | "linux_asset" | "default_asset";

const UPDATE_ASSET_SLOTS: Array<{
  platform: string;
  label: string;
  assetIdKey: UpdateAssetIdKey;
  assetKey: UpdateAssetKey;
}> = [
  { platform: "macos", label: "macOS", assetIdKey: "macos_asset_id", assetKey: "macos_asset" },
  { platform: "windows", label: "Windows", assetIdKey: "windows_asset_id", assetKey: "windows_asset" },
  { platform: "linux", label: "Linux", assetIdKey: "linux_asset_id", assetKey: "linux_asset" },
  { platform: "default", label: "默认包", assetIdKey: "default_asset_id", assetKey: "default_asset" },
];

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

function modelLabel(modelId?: string | null, providerId?: string | null): string {
  if (providerId && modelId) return `${providerId} / ${modelId}`;
  return modelId || providerId || "";
}

function partTypeLabel(type: string): string {
  return {
    text: "文本",
    reasoning: "思考",
    tool: "工具",
    tool_call: "工具",
    "step-finish": "用量",
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

function previewFromPart(part: TranscriptPart): string {
  const text = textFromPart(part);
  if (text) return compactAuditValue(text, 120);
  if (part.tool_call) return compactAuditValue(part.tool_call.title || part.tool_call.tool, 120);
  if (part.file) return compactAuditValue(part.file.name, 120);
  if (part.usage) return `Token ${formatNumber(part.usage.total_tokens)} · $${Number(part.usage.cost || 0).toFixed(4)}`;
  return compactAuditValue(part.data, 120);
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
            ["allInfo", "全部信息"],
            ["analytics", "数据分析"],
            ["risks", "风险发现"],
            ["tools", "工具调用"],
            ["feedback", "问题反馈"],
            ["users", "员工管理"],
            ["actions", "管控日志"],
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
        {tab === "allInfo" && <AllAuditInfo api={api} token={token} />}
        {tab === "analytics" && <Analytics api={api} token={token} />}
        {tab === "risks" && <Risks api={api} />}
        {tab === "tools" && <ToolCalls api={api} />}
        {tab === "feedback" && <FeedbackPanel api={api} token={token} />}
        {tab === "users" && <Users api={api} />}
        {tab === "actions" && <AdminActions api={api} />}
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
    allInfo: "全部信息",
    analytics: "数据分析",
    risks: "风险发现",
    tools: "工具调用",
    feedback: "问题反馈",
    users: "员工管理",
    actions: "管控日志",
    models: "模型管控",
    updates: "版本更新",
  }[tab];
}

function tabSubtitle(tab: Tab): string {
  return {
    overview: "查看员工使用规模、token 消耗、风险和文件同步情况。",
    sessions: "以会话为单位查看记录，点击表格行后查看完整详情。",
    allInfo: "跨会话查看所有消息片段、工具调用、文件和用量记录。",
    analytics: "深度分析用户行为、模型使用、成本趋势，导出数字资产数据。",
    risks: "集中处理敏感内容、密钥、订阅链接等风险线索。",
    tools: "审计模型调用的本地工具、输入、输出和状态。",
    feedback: "查看员工提交的问题描述和截图。",
    users: "创建员工账号、查看角色和启用状态。",
    actions: "追踪管理员的下载、踢号、批量管控等关键动作。",
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
    ["今日活跃", summary.activity.daily_active_users],
    ["在线员工", summary.activity.online_users],
    ["在线设备", summary.activity.online_sessions],
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
      <div className="card wide">
        <h2>近 30 天活跃</h2>
        <div className="activity-strip">
          {summary.activity.series.slice(-14).map((item) => (
            <div className="activity-day" key={item.date}>
              <strong>{formatNumber(item.active_users)}</strong>
              <span>{item.date.slice(5)}</span>
            </div>
          ))}
        </div>
        <p className="muted">
          Redis 在线态：{summary.activity.redis?.available ? "已启用" : "未启用或不可用"}，数据库 last_seen 作为兜底。
        </p>
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
  const selectedSession = sessions.find((session) => session.id === selected) || null;

  return (
    <div className="audit-workspace session-audit-workspace">
      <section className="card audit-table-card">
        <div className="toolbar">
          <input className="input" placeholder="搜索员工、标题、工作区" value={query} onChange={(e) => setQuery(e.target.value)} />
          <button className="button" onClick={() => void loadSessions()}>搜索</button>
        </div>
        <div className="table-scroll">
          <table className="session-table table">
            <thead>
              <tr>
                <th>会话</th>
                <th>员工</th>
                <th>工作区</th>
                <th>模型</th>
                <th>更新时间</th>
              </tr>
            </thead>
            <tbody>
              {sessions.map((session) => (
                <tr
                  key={session.id}
                  className={selected === session.id ? "is-selected" : ""}
                  onClick={() => void loadTranscript(session.id)}
                >
                  <td>
                    <strong>{session.title || "未命名会话"}</strong>
                    <div className="muted mono">{session.id}</div>
                  </td>
                  <td>
                    <strong>{session.user_display_name || session.user_email}</strong>
                    <div className="muted">{session.user_email}</div>
                  </td>
                  <td className="mono">{session.workspace || "无工作区"}</td>
                  <td>{session.model_id || "-"}<div className="muted">{session.provider_id || ""}</div></td>
                  <td>{compactDate(session.time_updated)}</td>
                </tr>
              ))}
              {sessions.length === 0 && (
                <tr>
                  <td colSpan={5} className="muted">暂无会话</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
      <section className="card transcript audit-detail">
        <div className="detail-header">
          <div>
            <h2>对话详情</h2>
            {selectedSession && (
              <div className="detail-meta">
                <span>{selectedSession.user_display_name || selectedSession.user_email}</span>
                <span>{selectedSession.workspace || "无工作区"}</span>
                <span>{compactDate(selectedSession.time_updated)}</span>
              </div>
            )}
          </div>
        </div>
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
          <p className="muted">选择上方会话查看详情</p>
        ) : (
          messages.map((message) => (
            <article className="message" key={message.id}>
              <div className="message-head">
                <span className={`role-badge ${message.role}`}>{roleLabel(message.role)}</span>
                {modelLabel(message.model_id, message.provider_id) && (
                  <span className="model-badge">模型：{modelLabel(message.model_id, message.provider_id)}</span>
                )}
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

function AllAuditInfo({ api, token }: { api: ReturnType<typeof useApi>; token: string }) {
  const [query, setQuery] = useState("");
  const [type, setType] = useState("");
  const [entries, setEntries] = useState<AuditEntry[]>([]);
  const [total, setTotal] = useState(0);
  const [selected, setSelected] = useState<string | null>(null);

  async function loadEntries() {
    const params = new URLSearchParams({ limit: "200" });
    if (query.trim()) params.set("q", query.trim());
    if (type) params.set("part_type", type);
    const data = await api<{ total: number; items: AuditEntry[] }>(`/api/admin/audit/entries?${params.toString()}`);
    setEntries(data.items);
    setTotal(data.total);
    if (selected && !data.items.some((entry) => entry.id === selected)) {
      setSelected(null);
    }
  }

  useEffect(() => {
    void loadEntries();
  }, []);

  const selectedEntry = entries.find((entry) => entry.id === selected) || null;

  return (
    <div className="audit-workspace all-info-workspace">
      <section className="card audit-table-card">
        <div className="toolbar">
          <input className="input" placeholder="搜索员工、会话、工作区、内容" value={query} onChange={(e) => setQuery(e.target.value)} />
          <select className="input audit-filter-select" value={type} onChange={(event) => setType(event.target.value)}>
            <option value="">全部类型</option>
            <option value="text">文本</option>
            <option value="tool">工具</option>
            <option value="step-finish">用量</option>
            <option value="file">文件</option>
            <option value="reasoning">思考</option>
          </select>
          <button className="button" onClick={() => void loadEntries()}>搜索</button>
          <span className="muted">共 {formatNumber(total)} 条</span>
        </div>
        <div className="table-scroll">
          <table className="entries-table table">
            <thead>
              <tr>
                <th>时间</th>
                <th>员工</th>
                <th>会话</th>
                <th>角色</th>
                <th>类型</th>
                <th>内容摘要</th>
              </tr>
            </thead>
            <tbody>
              {entries.map((entry) => (
                <tr
                  key={entry.id}
                  className={selected === entry.id ? "is-selected" : ""}
                  onClick={() => setSelected(entry.id)}
                >
                  <td>{compactDate(entry.time_created)}</td>
                  <td>
                    <strong>{entry.session?.user_display_name || entry.session?.user_email || "-"}</strong>
                    <div className="muted">{entry.session?.user_email || ""}</div>
                  </td>
                  <td>
                    <strong>{entry.session?.title || "未命名会话"}</strong>
                    <div className="muted mono">{entry.session?.workspace || "无工作区"}</div>
                  </td>
                  <td><span className={`role-badge ${entry.message.role}`}>{roleLabel(entry.message.role)}</span></td>
                  <td><span className="badge">{partTypeLabel(entry.type)}</span></td>
                  <td>{previewFromPart(entry)}</td>
                </tr>
              ))}
              {entries.length === 0 && (
                <tr>
                  <td colSpan={6} className="muted">暂无内容</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </section>
      <section className="card audit-detail">
        <div className="detail-header">
          <div>
            <h2>信息详情</h2>
            {selectedEntry && (
              <div className="detail-meta">
                <span>{selectedEntry.session?.title || selectedEntry.session?.id || "-"}</span>
                <span>{roleLabel(selectedEntry.message.role)}</span>
                {modelLabel(selectedEntry.message.model_id, selectedEntry.message.provider_id) && (
                  <span>模型：{modelLabel(selectedEntry.message.model_id, selectedEntry.message.provider_id)}</span>
                )}
                <span>{compactDate(selectedEntry.time_created)}</span>
              </div>
            )}
          </div>
        </div>
        {selectedEntry ? (
          <>
            <AuditPartView part={selectedEntry} token={token} />
            <RawDataDetails data={selectedEntry} />
          </>
        ) : (
          <p className="muted">选择上方信息查看详情</p>
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

function adminActionLabel(action: string): string {
  return {
    "audit.file.download": "下载审计文件",
    revoke_company_session: "踢单个会话",
    revoke_company_user_sessions: "踢员工全部设备",
    revoke_company_sessions_bulk: "批量踢号",
  }[action] || action || "-";
}

function AdminActions({ api }: { api: ReturnType<typeof useApi> }) {
  const [items, setItems] = useState<AdminActionItem[]>([]);
  const [actionFilter, setActionFilter] = useState("");
  const [error, setError] = useState("");

  async function loadActions() {
    setError("");
    const query = actionFilter ? `?action=${encodeURIComponent(actionFilter)}` : "";
    try {
      const data = await api<{ items: AdminActionItem[] }>(`/api/admin/audit/admin-actions${query}`);
      setItems(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "管控日志加载失败");
    }
  }

  useEffect(() => {
    void loadActions();
  }, []);

  return (
    <section className="card">
      <div className="toolbar">
        <select className="input action-filter" value={actionFilter} onChange={(event) => setActionFilter(event.target.value)}>
          <option value="">全部动作</option>
          <option value="audit.file.download">下载审计文件</option>
          <option value="revoke_company_session">踢单个会话</option>
          <option value="revoke_company_user_sessions">踢员工全部设备</option>
          <option value="revoke_company_sessions_bulk">批量踢号</option>
        </select>
        <button className="button" onClick={() => void loadActions()}>查询</button>
      </div>
      {error && <p className="error">{error}</p>}
      <table>
        <thead><tr><th>时间</th><th>管理员</th><th>动作</th><th>目标</th><th>详情</th></tr></thead>
        <tbody>
          {items.map((item) => (
            <tr key={item.id}>
              <td>{compactDate(item.time_created)}</td>
              <td>
                <strong>{item.actor_display_name || item.actor_email}</strong>
                <div className="muted">{item.actor_email}</div>
              </td>
              <td><span className="pill">{adminActionLabel(item.action)}</span></td>
              <td className="mono">{item.target_type}:{item.target_id}</td>
              <td className="mono">{compactAuditValue(item.metadata, 240)}</td>
            </tr>
          ))}
        </tbody>
      </table>
      {items.length === 0 && !error && <p className="muted empty-state">暂无管控日志</p>}
    </section>
  );
}

function FeedbackPanel({ api, token }: { api: ReturnType<typeof useApi>; token: string }) {
  const [items, setItems] = useState<FeedbackItem[]>([]);
  const [error, setError] = useState("");
  const [deletingId, setDeletingId] = useState("");

  async function loadFeedback() {
    setError("");
    try {
      const data = await api<{ items: FeedbackItem[] }>("/api/admin/feedback");
      setItems(data.items);
    } catch (err) {
      setError(err instanceof Error ? err.message : "反馈加载失败");
    }
  }

  useEffect(() => {
    void loadFeedback();
  }, []);

  async function deleteFeedback(feedbackId: string) {
    const confirmed = window.confirm("确定删除这条反馈吗？删除后图片附件也会一起清理。");
    if (!confirmed) return;
    setError("");
    setDeletingId(feedbackId);
    try {
      await api(`/api/admin/feedback/${encodeURIComponent(feedbackId)}`, { method: "DELETE" });
      setItems((current) => current.filter((item) => item.id !== feedbackId));
    } catch (err) {
      setError(err instanceof Error ? err.message : "反馈删除失败");
    } finally {
      setDeletingId("");
    }
  }

  if (error) return <section className="card error">{error}</section>;

  return (
    <section className="card">
      {items.length === 0 ? (
        <p className="muted">暂无反馈</p>
      ) : (
        <div className="feedback-list">
          {items.map((item) => (
            <article className="feedback-item" key={item.id}>
              <div className="feedback-head">
                <div>
                  <strong>{item.user_display_name || item.user_email || "未知员工"}</strong>
                  <div className="muted">{item.user_email || "-"} · {compactDate(item.time_created)}</div>
                </div>
                <button
                  className="button ghost danger-text"
                  disabled={deletingId === item.id}
                  onClick={() => void deleteFeedback(item.id)}
                >
                  {deletingId === item.id ? "删除中" : "删除"}
                </button>
              </div>
              <p className="feedback-description">{item.description}</p>
              {item.image_download_url && (
                <FeedbackImagePreview
                  url={item.image_download_url}
                  token={token}
                  alt={item.image_original_filename || "反馈附图"}
                />
              )}
              {item.image_original_filename && (
                <div className="feedback-file">
                  <span>{item.image_original_filename}</span>
                  <small>{item.image_mime_type || "image"} · {formatNumber(item.image_size_bytes)} bytes · {item.image_sha256.slice(0, 16)}...</small>
                </div>
              )}
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function FeedbackImagePreview({ url, token, alt }: { url: string; token: string; alt: string }) {
  const [previewUrl, setPreviewUrl] = useState("");
  const [error, setError] = useState("");

  useEffect(() => {
    let cancelled = false;
    let objectUrl = "";
    setPreviewUrl("");
    setError("");

    async function loadImage() {
      try {
        const response = await fetch(url, { headers: { "X-FPI-Session": token } });
        if (!response.ok) throw new Error(await response.text());
        const blob = await response.blob();
        objectUrl = URL.createObjectURL(blob);
        if (!cancelled) setPreviewUrl(objectUrl);
      } catch (err) {
        if (!cancelled) setError(err instanceof Error ? err.message : "附图加载失败");
      }
    }

    void loadImage();
    return () => {
      cancelled = true;
      if (objectUrl) URL.revokeObjectURL(objectUrl);
    };
  }, [url, token]);

  if (error) return <div className="feedback-preview-error">{error}</div>;
  if (!previewUrl) return <div className="feedback-preview-loading">附图加载中...</div>;

  return (
    <div className="feedback-preview">
      <img className="feedback-preview-image" src={previewUrl} alt={alt} />
    </div>
  );
}

function Users({ api }: { api: ReturnType<typeof useApi> }) {
  const [users, setUsers] = useState<UserInfo[]>([]);
  const [sessions, setSessions] = useState<CompanySession[]>([]);
  const [selectedSessionIds, setSelectedSessionIds] = useState<string[]>([]);
  const [email, setEmail] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("user");
  const [revokeReason, setRevokeReason] = useState("管理员强制重新登录");
  const [message, setMessage] = useState("");
  const [error, setError] = useState("");

  async function loadUsers() {
    const data = await api<UserInfo[]>("/api/admin/users");
    setUsers(data);
  }

  async function loadSessions() {
    const data = await api<{ items: CompanySession[] }>("/api/admin/sessions");
    setSessions(data.items);
  }

  async function loadAll() {
    await Promise.all([loadUsers(), loadSessions()]);
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
      await loadAll();
    } catch {
      setError("新增员工失败");
    }
  }

  function toggleSession(sessionId: string, checked: boolean) {
    setSelectedSessionIds((current) =>
      checked ? Array.from(new Set([...current, sessionId])) : current.filter((id) => id !== sessionId),
    );
  }

  function sessionsForUser(userId: string) {
    return sessions.filter((session) => session.user_id === userId);
  }

  async function revokeSession(sessionId: string) {
    setMessage("");
    await api(`/api/admin/sessions/${encodeURIComponent(sessionId)}/revoke`, {
      method: "POST",
      body: JSON.stringify({ reason: revokeReason }),
    });
    setSelectedSessionIds((current) => current.filter((id) => id !== sessionId));
    setMessage("已踢下线，用户下次请求会回到登录页");
    await loadSessions();
  }

  async function revokeUserSessions(userId: string) {
    setMessage("");
    await api(`/api/admin/users/${encodeURIComponent(userId)}/revoke-sessions`, {
      method: "POST",
      body: JSON.stringify({ reason: revokeReason }),
    });
    setSelectedSessionIds([]);
    setMessage("已踢下线该员工的全部设备");
    await loadSessions();
  }

  async function revokeSelectedSessions() {
    if (selectedSessionIds.length === 0) return;
    setMessage("");
    await api("/api/admin/sessions/revoke-bulk", {
      method: "POST",
      body: JSON.stringify({ session_ids: selectedSessionIds, reason: revokeReason }),
    });
    setSelectedSessionIds([]);
    setMessage(`已批量踢下线 ${selectedSessionIds.length} 个会话`);
    await loadSessions();
  }

  useEffect(() => {
    void loadAll();
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
        <div className="toolbar">
          <h2>在线与踢号</h2>
          <input
            className="input"
            placeholder="踢号原因"
            value={revokeReason}
            onChange={(event) => setRevokeReason(event.target.value)}
          />
          <button className="button outline" onClick={() => void loadSessions()}>刷新在线状态</button>
          <button
            className="button danger"
            disabled={selectedSessionIds.length === 0}
            onClick={() => void revokeSelectedSessions()}
          >
            批量踢下线
          </button>
        </div>
        {message && <p className="success">{message}</p>}
        <table>
          <thead><tr><th></th><th>员工</th><th>设备</th><th>平台</th><th>版本</th><th>IP</th><th>状态</th><th>最近活跃</th><th>操作</th></tr></thead>
          <tbody>
            {sessions.map((session) => (
              <tr key={session.id}>
                <td>
                  <input
                    type="checkbox"
                    checked={selectedSessionIds.includes(session.id)}
                    onChange={(event) => toggleSession(session.id, event.target.checked)}
                  />
                </td>
                <td>{session.user_display_name || session.user_email}</td>
                <td>{session.device_name || session.device_id || "未知设备"}</td>
                <td>{session.platform || "-"}</td>
                <td>{session.app_version || "-"}</td>
                <td>{session.ip_address || "-"}</td>
                <td><span className={`pill ${session.is_online ? "success" : "muted-pill"}`}>{session.is_online ? "在线" : "离线"}</span></td>
                <td>{compactDate(session.last_seen_at)}</td>
                <td>
                  <button className="button ghost danger-text" onClick={() => void revokeSession(session.id)}>踢下线</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
      <section className="card">
        <table>
          <thead><tr><th>账号</th><th>姓名</th><th>角色</th><th>状态</th><th>在线设备</th><th>操作</th></tr></thead>
          <tbody>
            {users.map((user) => (
              <tr key={user.id}>
                <td>{user.email}</td>
                <td>{user.display_name}</td>
                <td>{user.role}</td>
                <td>{user.is_active ? "启用" : "停用"}</td>
                <td>{sessionsForUser(user.id).filter((session) => session.is_online).length}</td>
                <td>
                  <button className="button ghost danger-text" onClick={() => void revokeUserSessions(user.id)}>踢全部设备</button>
                </td>
              </tr>
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
            enabled: true,
            api_key: "",
          }))}
        >
          添加模型
        </button>
        <button className="button" onClick={() => void savePolicy()}>保存策略</button>
      </div>
      <div className="model-list">
        {policy.models.map((model, index) => {
          const enabled = model.enabled !== false;
          return (
          <div className={`model-row ${enabled ? "" : "is-disabled"}`} key={`${index}-${model.provider_id}-${model.id}`}>
            <label className="default-model-choice">
              <input
                type="radio"
                name="default-model"
                checked={model.provider_id === policy.default_provider_id && model.id === policy.default_model_id}
                disabled={!enabled || !model.provider_id.trim() || !model.id.trim()}
                onChange={() => setPolicy(setDefaultModelInPolicy(policy, index))}
              />
              <span>默认</span>
            </label>
            <button
              className={`button ghost ${enabled ? "" : "button-state-muted"}`}
              onClick={() => updateModel(index, { enabled: !enabled })}
            >
              {enabled ? "禁用" : "启用"}
            </button>
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
          </div>
          );
        })}
      </div>
      {message && <p className={message.startsWith("已保存") ? "success" : "error"}>{message}</p>}
    </section>
  );
}

function UpdatePolicyPanel({ api }: { api: ReturnType<typeof useApi> }) {
  const [policy, setPolicy] = useState<UpdatePolicy | null>(null);
  const [message, setMessage] = useState("");
  const [uploadingSlot, setUploadingSlot] = useState<string | null>(null);
  const [assetSignatures, setAssetSignatures] = useState<Record<string, string>>({});

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
        body: JSON.stringify({
          enabled: policy.enabled,
          latest_version: policy.latest_version,
          min_supported_version: policy.min_supported_version,
          force_update: policy.force_update,
          release_notes: policy.release_notes,
          macos_asset_id: policy.macos_asset_id,
          windows_asset_id: policy.windows_asset_id,
          linux_asset_id: policy.linux_asset_id,
          default_asset_id: policy.default_asset_id,
          macos_download_url: policy.macos_download_url,
          windows_download_url: policy.windows_download_url,
          linux_download_url: policy.linux_download_url,
          default_download_url: policy.default_download_url,
        }),
      });
      setPolicy(saved);
      setMessage("已保存，员工客户端启动或下次检查更新时生效");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存失败");
    }
  }

  async function uploadAsset(slot: (typeof UPDATE_ASSET_SLOTS)[number], file: File | null) {
    if (!policy || !file) return;
    const version = policy.latest_version.trim();
    if (!version) {
      setMessage("请先填写最新版号，再上传安装包");
      return;
    }

    const form = new FormData();
    form.set("platform", slot.platform);
    form.set("version", version);
    form.set("signature", (assetSignatures[slot.platform] ?? policy[slot.assetKey]?.signature ?? "").trim());
    form.set("file", file);

    setMessage("");
    setUploadingSlot(slot.platform);
    try {
      const asset = await api<UpdateAsset>("/api/admin/update-assets/upload", {
        method: "POST",
        body: form,
      });
      setPolicy({
        ...policy,
        [slot.assetIdKey]: asset.id,
        [slot.assetKey]: asset,
      });
      setMessage(`${slot.label} 安装包已上传，请保存策略后生效`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "上传失败");
    } finally {
      setUploadingSlot(null);
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
          直接上传各平台安装包，服务器会作为文件存储提供下载。最低可用版本以下的客户端会被强制更新；非强制更新时，旧版本仍可继续使用。
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
          <div className="model-field model-field-wide">
            <span>安装包文件</span>
            <div className="update-asset-grid">
              {UPDATE_ASSET_SLOTS.map((slot) => {
                const asset = policy[slot.assetKey];
                const isUploading = uploadingSlot === slot.platform;
                return (
                  <div className="update-asset-panel" key={slot.platform}>
                    <div className="update-asset-head">
                      <strong>{slot.label}</strong>
                      <span>{asset ? `v${asset.version}` : "未上传"}</span>
                    </div>
                    {asset ? (
                      <div className="update-asset-meta">
                        <b>{asset.original_filename}</b>
                        <span>{asset.mime_type || "文件"} · {formatNumber(asset.size_bytes)} bytes</span>
                        <span>上传人：{asset.uploaded_by_display_name || asset.uploaded_by_email || "-"}</span>
                        <span>上传时间：{compactDate(asset.time_created)}</span>
                        <span>下载次数：{formatNumber(asset.download_count)}</span>
                        <span>SHA-256：{asset.sha256.slice(0, 16)}...</span>
                        <span>应用内更新签名：{asset.signature ? `${asset.signature.slice(0, 18)}...` : "未配置"}</span>
                      </div>
                    ) : (
                      <p className="muted">员工端匹配不到该平台包时会使用默认包。</p>
                    )}
                    <textarea
                      className="input textarea"
                      placeholder="粘贴 Tauri .sig 文件内容；留空则只能打开安装包兜底"
                      value={assetSignatures[slot.platform] ?? asset?.signature ?? ""}
                      onChange={(event) =>
                        setAssetSignatures({
                          ...assetSignatures,
                          [slot.platform]: event.target.value,
                        })
                      }
                    />
                    <label className={`button outline file-button ${isUploading ? "disabled" : ""}`}>
                      <input
                        type="file"
                        disabled={isUploading}
                        onChange={(event) => {
                          const selected = event.currentTarget.files?.[0] ?? null;
                          event.currentTarget.value = "";
                          void uploadAsset(slot, selected);
                        }}
                      />
                      {isUploading ? "上传中..." : asset ? "替换文件" : "上传文件"}
                    </label>
                  </div>
                );
              })}
            </div>
          </div>
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

// ============================================================================
// Analytics Tab - 数据分析
// ============================================================================

interface UserAnalytics {
  period_days: number;
  total_users: number;
  user_list: Array<{
    user_id: string;
    user_email: string;
    user_display_name: string;
    session_count: number;
    message_count: number;
    total_tokens: number;
    total_cost: number;
    avg_tokens_per_session: number;
  }>;
  session_distribution: Record<string, number>;
}

interface ModelAnalytics {
  period_days: number;
  model_list: Array<{
    model_id: string;
    provider_id: string;
    session_count: number;
    message_count: number;
    total_tokens: number;
    input_tokens: number;
    output_tokens: number;
    total_cost: number;
    avg_cost_per_session: number;
  }>;
}

interface ToolAnalytics {
  period_days: number;
  total_calls: number;
  tool_list: Array<{
    tool_name: string;
    call_count: number;
    success_count: number;
    error_count: number;
    success_rate: number;
  }>;
}

interface ContentAnalytics {
  period_days: number;
  messages_by_role: Record<string, number>;
  files_by_type: Array<{
    mime_type: string;
    count: number;
    total_size_mb: number;
  }>;
  session_message_distribution: Record<string, number>;
}

interface TimelineAnalytics {
  period_days: number;
  timeline: Array<{
    date: string;
    session_count: number;
    active_users: number;
    total_tokens: number;
    total_cost: number;
  }>;
}

function Analytics({ api, token }: { api: ReturnType<typeof useApi>; token: string }) {
  const [days, setDays] = useState(30);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [userStats, setUserStats] = useState<UserAnalytics | null>(null);
  const [modelStats, setModelStats] = useState<ModelAnalytics | null>(null);
  const [toolStats, setToolStats] = useState<ToolAnalytics | null>(null);
  const [contentStats, setContentStats] = useState<ContentAnalytics | null>(null);
  const [timeline, setTimeline] = useState<TimelineAnalytics | null>(null);

  useEffect(() => {
    void loadAnalytics();
  }, [days]);

  async function loadAnalytics() {
    setLoading(true);
    setError("");
    try {
      async function loadOne<T>(path: string): Promise<T | null> {
        try {
          return await api<T>(path);
        } catch (error) {
          console.error("加载分析接口失败:", path, error);
          return null;
        }
      }

      const [users, models, tools, content, time] = await Promise.all([
        loadOne<UserAnalytics>(`/api/admin/audit/analytics/users?days=${days}`),
        loadOne<ModelAnalytics>(`/api/admin/audit/analytics/models?days=${days}`),
        loadOne<ToolAnalytics>(`/api/admin/audit/analytics/tools?days=${days}`),
        loadOne<ContentAnalytics>(`/api/admin/audit/analytics/content?days=${days}`),
        loadOne<TimelineAnalytics>(`/api/admin/audit/analytics/timeline?days=${days}`),
      ]);
      setUserStats(users);
      setModelStats(models);
      setToolStats(tools);
      setContentStats(content);
      setTimeline(time);
      if ([users, models, tools, content, time].some((item) => item === null)) {
        setError("部分分析数据加载失败，已展示可用数据。");
      }
    } catch (error) {
      console.error("加载分析数据失败:", error);
      setError("分析数据加载失败。");
    } finally {
      setLoading(false);
    }
  }

  async function exportData(endpoint: string, filename: string) {
    try {
      const response = await fetch(endpoint, {
        headers: { "X-FPI-Session": token },
      });
      if (!response.ok) throw new Error(await response.text());
      const blob = await response.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    } catch (error) {
      alert("导出失败: " + error);
    }
  }

  if (loading) {
    return <div className="card"><p className="muted">加载中...</p></div>;
  }

  const totalCost = userStats?.user_list.reduce((sum, u) => sum + u.total_cost, 0) || 0;
  const totalTokens = userStats?.user_list.reduce((sum, u) => sum + u.total_tokens, 0) || 0;

  return (
    <div className="analytics-container">
      {/* 时间范围选择 */}
      <div className="card">
        <div className="toolbar">
          <label>
            统计周期：
            <select value={days} onChange={(e) => setDays(Number(e.target.value))} className="input">
              <option value={7}>最近 7 天</option>
              <option value={30}>最近 30 天</option>
              <option value={60}>最近 60 天</option>
              <option value={90}>最近 90 天</option>
            </select>
          </label>
          <div style={{ marginLeft: "auto", display: "flex", gap: "8px" }}>
            <button
              className="button outline"
              onClick={() => exportData(`/api/admin/audit/export/users?days=${days}`, `用户统计_${days}天.csv`)}
            >
              导出用户统计
            </button>
            <button
              className="button outline"
              onClick={() => exportData(`/api/admin/audit/export/sessions?days=${days}`, `会话列表_${days}天.csv`)}
            >
              导出会话列表
            </button>
            <button
              className="button"
              onClick={() => exportData(`/api/admin/audit/export/conversations?days=${days}`, `对话内容_${days}天.csv`)}
            >
              导出对话内容
            </button>
          </div>
        </div>
        {error && <p className="error">{error}</p>}
      </div>

      {/* 总览卡片 */}
      <div className="stats-grid">
        <div className="stat-card">
          <h3>总用户数</h3>
          <div className="stat-value">{userStats?.total_users || 0}</div>
          <div className="stat-label">活跃用户</div>
        </div>
        <div className="stat-card">
          <h3>总 Token 消耗</h3>
          <div className="stat-value">{formatNumber(totalTokens)}</div>
          <div className="stat-label">{days} 天累计</div>
        </div>
        <div className="stat-card">
          <h3>总成本</h3>
          <div className="stat-value">${totalCost.toFixed(2)}</div>
          <div className="stat-label">{days} 天累计</div>
        </div>
        <div className="stat-card">
          <h3>工具调用</h3>
          <div className="stat-value">{formatNumber(toolStats?.total_calls || 0)}</div>
          <div className="stat-label">总调用次数</div>
        </div>
      </div>

      {/* 时间趋势图 */}
      <div className="card">
        <h2>趋势分析</h2>
        {timeline && timeline.timeline.length > 0 && (
          <div className="timeline-chart">
            <table className="table">
              <thead>
                <tr>
                  <th>日期</th>
                  <th>会话数</th>
                  <th>活跃用户</th>
                  <th>Token 消耗</th>
                  <th>成本</th>
                </tr>
              </thead>
              <tbody>
                {timeline.timeline.slice(-14).map((item) => (
                  <tr key={item.date}>
                    <td>{item.date}</td>
                    <td>{item.session_count}</td>
                    <td>{item.active_users}</td>
                    <td>{formatNumber(item.total_tokens)}</td>
                    <td>${item.total_cost.toFixed(2)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>

      {/* 用户分析 */}
      <div className="card">
        <h2>用户分析 - TOP 20</h2>
        <table className="table">
          <thead>
            <tr>
              <th>排名</th>
              <th>用户</th>
              <th>会话数</th>
              <th>消息数</th>
              <th>Token 消耗</th>
              <th>成本</th>
              <th>平均每会话</th>
            </tr>
          </thead>
          <tbody>
            {userStats?.user_list.slice(0, 20).map((user, index) => (
              <tr key={user.user_id}>
                <td>{index + 1}</td>
                <td>
                  <strong>{user.user_display_name}</strong>
                  <div className="muted">{user.user_email}</div>
                </td>
                <td>{user.session_count}</td>
                <td>{user.message_count}</td>
                <td>{formatNumber(user.total_tokens)}</td>
                <td>${user.total_cost.toFixed(2)}</td>
                <td>{formatNumber(user.avg_tokens_per_session)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 模型分析 */}
      <div className="card">
        <h2>模型使用分析</h2>
        <table className="table">
          <thead>
            <tr>
              <th>模型</th>
              <th>供应商</th>
              <th>会话数</th>
              <th>消息数</th>
              <th>总 Token</th>
              <th>输入 Token</th>
              <th>输出 Token</th>
              <th>总成本</th>
              <th>平均成本</th>
            </tr>
          </thead>
          <tbody>
            {modelStats?.model_list.map((model) => (
              <tr key={`${model.provider_id}-${model.model_id}`}>
                <td><strong>{model.model_id}</strong></td>
                <td>{model.provider_id}</td>
                <td>{model.session_count}</td>
                <td>{model.message_count}</td>
                <td>{formatNumber(model.total_tokens)}</td>
                <td>{formatNumber(model.input_tokens)}</td>
                <td>{formatNumber(model.output_tokens)}</td>
                <td>${model.total_cost.toFixed(2)}</td>
                <td>${model.avg_cost_per_session.toFixed(3)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 工具调用分析 */}
      <div className="card">
        <h2>工具调用分析</h2>
        <table className="table">
          <thead>
            <tr>
              <th>工具名称</th>
              <th>调用次数</th>
              <th>成功次数</th>
              <th>失败次数</th>
              <th>成功率</th>
            </tr>
          </thead>
          <tbody>
            {toolStats?.tool_list.map((tool) => (
              <tr key={tool.tool_name}>
                <td><strong>{tool.tool_name}</strong></td>
                <td>{formatNumber(tool.call_count)}</td>
                <td>{formatNumber(tool.success_count)}</td>
                <td>{formatNumber(tool.error_count)}</td>
                <td>
                  <span className={tool.success_rate >= 95 ? "pill success" : tool.success_rate >= 80 ? "pill warning" : "pill error"}>
                    {tool.success_rate.toFixed(1)}%
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* 内容分析 */}
      <div className="card">
        <h2>内容统计</h2>
        <div className="content-stats">
          <div>
            <h3>消息角色分布</h3>
            <table className="table">
              <tbody>
                {contentStats && Object.entries(contentStats.messages_by_role).map(([role, count]) => (
                  <tr key={role}>
                    <td><strong>{role}</strong></td>
                    <td>{formatNumber(count)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <div>
            <h3>会话消息数分布</h3>
            <table className="table">
              <tbody>
                {contentStats && Object.entries(contentStats.session_message_distribution).map(([bucket, count]) => (
                  <tr key={bucket}>
                    <td><strong>{bucket} 条消息</strong></td>
                    <td>{count} 个会话</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      {/* 文件类型分析 */}
      <div className="card">
        <h2>文件类型分析</h2>
        <table className="table">
          <thead>
            <tr>
              <th>文件类型</th>
              <th>数量</th>
              <th>总大小</th>
            </tr>
          </thead>
          <tbody>
            {contentStats?.files_by_type.map((file) => (
              <tr key={file.mime_type}>
                <td><strong>{file.mime_type}</strong></td>
                <td>{formatNumber(file.count)}</td>
                <td>{file.total_size_mb.toFixed(2)} MB</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
