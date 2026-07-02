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
  | "connectors"
  | "announcements"
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

interface ConnectorPolicyEntry {
  connector_id: string;
  name: string;
  description: string;
  category: string;
  icon_url: string;
  enabled: boolean;
  status: string;
  allowed_user_ids: string[];
}

interface ConnectorPolicy {
  connectors: ConnectorPolicyEntry[];
  users: UserInfo[];
}

interface AnnouncementPolicy {
  id: string;
  enabled: boolean;
  content: string;
  target_user_ids: string[];
  published_by_user_id: string;
  published_by_email: string;
  published_by_display_name: string;
  time_created: string;
  time_updated: string;
  users: UserInfo[];
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
  time_created?: string;
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
  name: string;
  version: string;
  original_filename: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
  md5: string;
  signature: string;
  uploaded_by_user_id: string;
  uploaded_by_email: string;
  uploaded_by_display_name: string;
  download_count: number;
  time_created: string;
  time_updated: string;
}

interface UpdateAssetList {
  items: UpdateAsset[];
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
  const fileSource = part.data?.source === "generated" ? "AI 生成文件" : "用户上传文件";
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
            <div className="muted">{fileSource} · {part.file.mime_type || "文件"} · {formatNumber(part.file.size)} bytes</div>
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

interface TranscriptTurn {
  id: string;
  user: TranscriptMessage | null;
  assistants: TranscriptMessage[];
}

function buildTranscriptTurns(messages: TranscriptMessage[]): TranscriptTurn[] {
  const turns: TranscriptTurn[] = [];
  let current: TranscriptTurn | null = null;
  for (const message of messages) {
    if (message.role === "user") {
      current = { id: message.id, user: message, assistants: [] };
      turns.push(current);
      continue;
    }
    if (!current) {
      current = { id: `orphan-${message.id}`, user: null, assistants: [] };
      turns.push(current);
    }
    current.assistants.push(message);
  }
  return turns;
}

function AuditChatMessage({ message, token }: { message: TranscriptMessage; token: string }) {
  const isUser = message.role === "user";
  return (
    <article className={`admin-chat-message ${isUser ? "user" : "assistant"}`}>
      <div className="admin-chat-avatar">{isUser ? "用" : "AI"}</div>
      <div className="admin-chat-bubble">
        <div className="admin-chat-head">
          <span className={`role-badge ${message.role}`}>{roleLabel(message.role)}</span>
          {modelLabel(message.model_id, message.provider_id) && (
            <span className="model-badge">模型：{modelLabel(message.model_id, message.provider_id)}</span>
          )}
          {message.time_created && <span className="muted">{compactDate(message.time_created)}</span>}
        </div>
        <div className="admin-chat-parts">
          {message.parts.map((part) => (
            <AuditPartView key={part.id} part={part} token={token} />
          ))}
        </div>
      </div>
    </article>
  );
}

function AuditChatTranscript({ messages, token }: { messages: TranscriptMessage[]; token: string }) {
  const turns = buildTranscriptTurns(messages).slice().reverse();
  return (
    <div className="admin-chat-scroll">
      <div className="admin-chat-thread">
        {turns.map((turn) => (
          <section className="admin-chat-turn" key={turn.id}>
            {turn.user && <AuditChatMessage message={turn.user} token={token} />}
            {turn.assistants.map((message) => (
              <AuditChatMessage key={message.id} message={message} token={token} />
            ))}
          </section>
        ))}
      </div>
    </div>
  );
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

const NAV_GROUPS: Array<{
  title: string;
  items: Array<{ key: Tab; label: string; marker: string }>;
}> = [
  {
    title: "运营概览",
    items: [
      { key: "overview", label: "总览", marker: "总" },
      { key: "analytics", label: "数据分析", marker: "析" },
    ],
  },
  {
    title: "审计追踪",
    items: [
      { key: "sessions", label: "会话审计", marker: "会" },
      { key: "allInfo", label: "全部信息", marker: "全" },
      { key: "risks", label: "风险发现", marker: "险" },
      { key: "tools", label: "工具调用", marker: "工" },
      { key: "feedback", label: "问题反馈", marker: "馈" },
    ],
  },
  {
    title: "企业管控",
    items: [
      { key: "users", label: "员工管理", marker: "员" },
      { key: "actions", label: "管控日志", marker: "志" },
      { key: "models", label: "模型管控", marker: "模" },
      { key: "connectors", label: "连接器管控", marker: "连" },
      { key: "announcements", label: "通知公告", marker: "告" },
      { key: "updates", label: "版本更新", marker: "版" },
    ],
  },
];

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
          {NAV_GROUPS.map((group) => (
            <div className="nav-group" key={group.title}>
              <div className="nav-group-title">{group.title}</div>
              {group.items.map((item) => (
                <button
                  key={item.key}
                  className={`nav-item ${tab === item.key ? "active" : ""}`}
                  onClick={() => setTab(item.key)}
                >
                  <span className="nav-marker">{item.marker}</span>
                  <span>{item.label}</span>
                </button>
              ))}
            </div>
          ))}
        </nav>
        <div className="sidebar-footer">
          <div className="sidebar-user">
            <span>{(session.user.display_name || session.user.email || "A").slice(0, 1).toUpperCase()}</span>
            <div>
              <strong>{session.user.display_name || session.user.email}</strong>
              <small>{session.user.role || "admin"}</small>
            </div>
          </div>
          <button className="button ghost full" onClick={logout}>退出登录</button>
        </div>
      </aside>

      <main className="content">
        <header className="page-header">
          <div className="page-title-block">
            <span className="page-kicker">FPI Agent Console</span>
            <h1>{tabTitle(tab)}</h1>
            <p>{tabSubtitle(tab)}</p>
          </div>
          <div className="header-actions">
            <span className="user-chip">{session.user.display_name || session.user.email}</span>
            <button className="button outline" onClick={() => window.location.reload()}>刷新</button>
          </div>
        </header>

        {tab === "overview" && <Overview api={api} />}
        {tab === "sessions" && <Sessions api={api} token={token} />}
        {tab === "allInfo" && <AllAuditInfo api={api} token={token} />}
        {tab === "analytics" && <Analytics api={api} token={token} />}
        {tab === "risks" && <Risks api={api} />}
        {tab === "tools" && <ToolCalls api={api} />}
        {tab === "feedback" && <FeedbackPanel api={api} token={token} />}
        {tab === "users" && <Users api={api} currentUserId={session.user.id} />}
        {tab === "actions" && <AdminActions api={api} />}
        {tab === "models" && <ModelPolicyPanel api={api} />}
        {tab === "connectors" && <ConnectorPolicyPanel api={api} />}
        {tab === "announcements" && <AnnouncementPanel api={api} />}
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
    connectors: "连接器管控",
    announcements: "通知公告",
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
    connectors: "按员工开放连接器能力，未授权员工客户端不可见也不可启用。",
    announcements: "发布客户端顶部公告，可选择全员或指定员工展示。",
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
          <AuditChatTranscript messages={messages} token={token} />
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

function Users({ api, currentUserId }: { api: ReturnType<typeof useApi>; currentUserId: string }) {
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

  async function deleteUser(user: UserInfo) {
    if (user.id === currentUserId) {
      setError("不能删除当前登录账号");
      return;
    }
    const name = user.display_name || user.email;
    if (!confirm(`确认删除员工「${name}」？删除后该账号无法登录，并会踢下线所有设备。`)) return;

    setError("");
    setMessage("");
    try {
      await api(`/api/admin/users/${encodeURIComponent(user.id)}`, {
        method: "DELETE",
      });
      setSelectedSessionIds([]);
      setMessage(`已删除员工：${name}`);
      await loadAll();
    } catch (error) {
      setError(error instanceof Error ? error.message : "删除员工失败");
    }
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
                  <div className="table-actions">
                    <button className="button ghost danger-text" onClick={() => void revokeUserSessions(user.id)}>踢全部设备</button>
                    <button
                      className="button ghost danger-text"
                      disabled={user.id === currentUserId}
                      onClick={() => void deleteUser(user)}
                    >
                      删除员工
                    </button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </section>
    </div>
  );
}

function ConnectorPolicyPanel({ api }: { api: ReturnType<typeof useApi> }) {
  const [policy, setPolicy] = useState<ConnectorPolicy | null>(null);
  const [message, setMessage] = useState("");

  async function loadPolicy() {
    const data = await api<ConnectorPolicy>("/api/admin/connector-policy");
    setPolicy(data);
  }

  useEffect(() => {
    void loadPolicy();
  }, []);

  function toggleUser(connectorId: string, userId: string, checked: boolean) {
    if (!policy) return;
    setPolicy({
      ...policy,
      connectors: policy.connectors.map((connector) => {
        if (connector.connector_id !== connectorId) return connector;
        const current = new Set(connector.allowed_user_ids);
        if (checked) {
          current.add(userId);
        } else {
          current.delete(userId);
        }
        return {
          ...connector,
          allowed_user_ids: Array.from(current),
        };
      }),
    });
  }

  async function savePolicy() {
    if (!policy) return;
    setMessage("");
    try {
      const saved = await api<ConnectorPolicy>("/api/admin/connector-policy", {
        method: "PUT",
        body: JSON.stringify({
          connectors: policy.connectors.map((connector) => ({
            connector_id: connector.connector_id,
            allowed_user_ids: connector.allowed_user_ids,
          })),
        }),
      });
      setPolicy(saved);
      setMessage("已保存，员工客户端刷新连接器列表后生效");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存失败");
    }
  }

  if (!policy) return <section className="card muted">加载中...</section>;

  return (
    <section className="card">
      <div className="toolbar">
        <div>
          <h2>连接器开放范围</h2>
          <p className="muted">默认不开放。勾选员工后，该员工才能在客户端看到并手动启用对应连接器。</p>
        </div>
        <button className="button outline" onClick={() => void loadPolicy()}>刷新</button>
        <button className="button" onClick={() => void savePolicy()}>保存策略</button>
      </div>

      <div className="table-scroll">
        <table>
          <thead>
            <tr>
              <th>连接器</th>
              <th>状态</th>
              <th>开放员工</th>
            </tr>
          </thead>
          <tbody>
            {policy.connectors.map((connector) => (
              <tr key={connector.connector_id}>
                <td>
                  <div className="connector-policy-name">
                    {connector.icon_url && <img src={connector.icon_url} alt="" />}
                    <div>
                      <strong>{connector.name || connector.connector_id}</strong>
                      <span>{connector.description || connector.connector_id}</span>
                    </div>
                  </div>
                </td>
                <td>
                  <span className={`pill ${connector.enabled ? "success" : "muted-pill"}`}>
                    {connector.enabled ? "已启用" : "默认关闭"}
                  </span>
                </td>
                <td>
                  <div className="connector-user-grid">
                    {policy.users.map((user) => (
                      <label className="connector-user-choice" key={`${connector.connector_id}-${user.id}`}>
                        <input
                          type="checkbox"
                          checked={connector.allowed_user_ids.includes(user.id)}
                          disabled={user.is_active === false}
                          onChange={(event) => toggleUser(connector.connector_id, user.id, event.target.checked)}
                        />
                        <span>{user.display_name || user.email}</span>
                      </label>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
            {policy.connectors.length === 0 && (
              <tr>
                <td colSpan={3} className="muted">当前没有可管控的连接器</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {message && <p className={message.startsWith("已保存") ? "success" : "error"}>{message}</p>}
    </section>
  );
}

function AnnouncementPanel({ api }: { api: ReturnType<typeof useApi> }) {
  const [policy, setPolicy] = useState<AnnouncementPolicy | null>(null);
  const [scope, setScope] = useState<"all" | "selected">("all");
  const [message, setMessage] = useState("");

  async function loadPolicy() {
    const data = await api<AnnouncementPolicy>("/api/admin/announcement");
    setPolicy(data);
    setScope(data.target_user_ids.length > 0 ? "selected" : "all");
  }

  useEffect(() => {
    void loadPolicy();
  }, []);

  function updateContent(content: string) {
    if (!policy) return;
    setPolicy({ ...policy, content });
  }

  function toggleTargetUser(userId: string, checked: boolean) {
    if (!policy) return;
    const current = new Set(policy.target_user_ids);
    if (checked) {
      current.add(userId);
    } else {
      current.delete(userId);
    }
    setPolicy({ ...policy, target_user_ids: Array.from(current) });
  }

  async function saveAnnouncement(enabled: boolean) {
    if (!policy) return;
    const target_user_ids = scope === "all" ? [] : policy.target_user_ids;
    if (enabled && !policy.content.trim()) {
      setMessage("请先填写公告内容");
      return;
    }
    if (enabled && scope === "selected" && target_user_ids.length === 0) {
      setMessage("请选择至少一名员工，或切换为全员公告");
      return;
    }

    setMessage("");
    try {
      const saved = await api<AnnouncementPolicy>("/api/admin/announcement", {
        method: "PUT",
        body: JSON.stringify({
          enabled,
          content: policy.content,
          target_user_ids,
        }),
      });
      setPolicy(saved);
      setScope(saved.target_user_ids.length > 0 ? "selected" : "all");
      setMessage(enabled ? "公告已发布，员工客户端将在下一次轮询时显示" : "公告已停用");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存失败");
    }
  }

  if (!policy) return <section className="card muted">加载中...</section>;

  return (
    <div className="stack">
      <section className="card">
        <div className="toolbar">
          <div>
            <h2>发布公告</h2>
            <p className="muted">员工端每 30 秒检查一次新公告。每次发布都会生成新的公告版本。</p>
          </div>
          <button className="button outline" onClick={() => void loadPolicy()}>刷新</button>
          <button className="button outline" onClick={() => void saveAnnouncement(false)} disabled={!policy.enabled}>
            停用公告
          </button>
          <button className="button" onClick={() => void saveAnnouncement(true)}>发布公告</button>
        </div>

        <div className="form-grid announcement-form">
          <label className="model-field model-field-wide">
            <span>公告内容（支持 Markdown）</span>
            <textarea
              className="input textarea announcement-textarea"
              placeholder="请输入需要展示给员工的通知公告，例如：[下载地址](https://example.com)"
              value={policy.content}
              onChange={(event) => updateContent(event.target.value)}
            />
            <small className="muted">支持加粗、列表和链接；链接会在员工客户端中直接点击打开。</small>
          </label>

          <div className="model-field model-field-wide">
            <span>展示范围</span>
            <div className="announcement-scope-row">
              <label className="connector-user-choice">
                <input
                  type="radio"
                  checked={scope === "all"}
                  onChange={() => setScope("all")}
                />
                <span>全员</span>
              </label>
              <label className="connector-user-choice">
                <input
                  type="radio"
                  checked={scope === "selected"}
                  onChange={() => setScope("selected")}
                />
                <span>指定员工</span>
              </label>
            </div>
          </div>

          {scope === "selected" && (
            <div className="model-field model-field-wide">
              <span>选择员工</span>
              <div className="connector-user-grid announcement-user-grid">
                {policy.users.map((user) => (
                  <label className="connector-user-choice" key={`announcement-${user.id}`}>
                    <input
                      type="checkbox"
                      checked={policy.target_user_ids.includes(user.id)}
                      disabled={user.is_active === false}
                      onChange={(event) => toggleTargetUser(user.id, event.target.checked)}
                    />
                    <span>{user.display_name || user.email}</span>
                  </label>
                ))}
              </div>
            </div>
          )}
        </div>

        {message && <p className={message.startsWith("公告已") ? "success" : "error"}>{message}</p>}
      </section>

      <section className="card">
        <div className="toolbar">
          <div>
            <h2>当前公告</h2>
            <p className="muted">
              {policy.enabled ? "启用中" : "未启用"}
              {policy.id ? ` · ${compactDate(policy.time_updated)}` : ""}
            </p>
          </div>
          <span className={`pill ${policy.enabled ? "success" : "muted-pill"}`}>
            {policy.enabled ? "展示中" : "已关闭"}
          </span>
        </div>
        {policy.content ? (
          <div className="announcement-preview">
            <p>{policy.content}</p>
            <span>
              范围：
              {policy.target_user_ids.length === 0
                ? "全员"
                : `指定员工 ${policy.target_user_ids.length} 人`}
            </span>
            <span>发布人：{policy.published_by_display_name || policy.published_by_email || "-"}</span>
          </div>
        ) : (
          <p className="muted">暂无公告内容</p>
        )}
      </section>
    </div>
  );
}

function ModelPolicyPanel({ api }: { api: ReturnType<typeof useApi> }) {
  const [policy, setPolicy] = useState<ModelPolicy | null>(null);
  const [message, setMessage] = useState("");
  const [dialog, setDialog] = useState<{
    mode: "create" | "edit";
    index: number | null;
    model: ModelEntry;
  } | null>(null);

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

  function openCreateDialog() {
    setDialog({
      mode: "create",
      index: null,
      model: {
        provider_id: `custom_${Math.random().toString(36).slice(2, 8)}`,
        id: "",
        name: "",
        protocol: DEFAULT_MODEL_PROTOCOL,
        base_url: "https://",
        enabled: true,
        api_key: "",
      },
    });
  }

  function openEditDialog(index: number) {
    if (!policy) return;
    setDialog({
      mode: "edit",
      index,
      model: { ...policy.models[index], api_key: "" },
    });
  }

  function applyDialogModel(model: ModelEntry) {
    if (!policy || !dialog) return;
    if (dialog.mode === "create") {
      setPolicy(addModelToPolicy(policy, model));
    } else if (dialog.index !== null) {
      setPolicy(updateModelInPolicy(policy, dialog.index, model));
    }
    setDialog(null);
    setMessage("模型配置已更新，请点击保存策略使员工客户端生效");
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
        <button className="button outline" onClick={openCreateDialog}>新增模型</button>
        <button className="button" onClick={() => void savePolicy()}>保存策略</button>
      </div>
      <div className="table-scroll">
        <table className="model-policy-table">
          <thead>
            <tr>
              <th>默认</th>
              <th>状态</th>
              <th>协议</th>
              <th>供应商 ID</th>
              <th>模型 ID</th>
              <th>显示名称</th>
              <th>Base URL</th>
              <th>Key</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {policy.models.map((model, index) => {
              const enabled = model.enabled !== false;
              const isDefault = model.provider_id === policy.default_provider_id && model.id === policy.default_model_id;
              return (
                <tr className={enabled ? "" : "is-disabled"} key={`${index}-${model.provider_id}-${model.id}`}>
                  <td>
                    <label className="default-model-choice compact">
                      <input
                        type="radio"
                        name="default-model"
                        checked={isDefault}
                        disabled={!enabled || !model.provider_id.trim() || !model.id.trim()}
                        onChange={() => setPolicy(setDefaultModelInPolicy(policy, index))}
                      />
                      <span>{isDefault ? "当前" : "设为默认"}</span>
                    </label>
                  </td>
                  <td>
                    <span className={`pill ${enabled ? "success" : "muted-pill"}`}>{enabled ? "启用" : "禁用"}</span>
                  </td>
                  <td>{model.protocol === "anthropic" ? "Anthropic" : "OpenAI 兼容"}</td>
                  <td className="mono">{model.provider_id || "-"}</td>
                  <td className="mono">{model.id || "-"}</td>
                  <td>{model.name || "-"}</td>
                  <td className="mono">{model.protocol === "anthropic" ? "-" : model.base_url || "-"}</td>
                  <td>{model.masked_key || (model.api_key ? "待保存新 Key" : "-")}</td>
                  <td>
                    <div className="table-actions">
                      <button className="button ghost" onClick={() => openEditDialog(index)}>编辑</button>
                      <button
                        className={`button ghost ${enabled ? "danger-text" : ""}`}
                        onClick={() => updateModel(index, { enabled: !enabled })}
                      >
                        {enabled ? "禁用" : "启用"}
                      </button>
                    </div>
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {message && <p className={message.startsWith("已保存") ? "success" : "error"}>{message}</p>}
      {dialog && (
        <ModelPolicyDialog
          api={api}
          mode={dialog.mode}
          model={dialog.model}
          onClose={() => setDialog(null)}
          onSave={applyDialogModel}
        />
      )}
    </section>
  );
}

interface ModelPolicyTestResponse {
  ok: boolean;
  message: string;
  test_token: string;
}

function ModelPolicyDialog({
  api,
  mode,
  model,
  onClose,
  onSave,
}: {
  api: ReturnType<typeof useApi>;
  mode: "create" | "edit";
  model: ModelEntry;
  onClose: () => void;
  onSave: (model: ModelEntry) => void;
}) {
  const [draft, setDraft] = useState<ModelEntry>(model);
  const [testState, setTestState] = useState<{
    status: "idle" | "testing" | "passed" | "failed";
    message: string;
  }>({ status: "idle", message: "保存前必须测试通过。" });

  function patchDraft(patch: Partial<ModelEntry>) {
    setDraft((prev) => ({ ...prev, ...patch, test_token: "" }));
    setTestState({ status: "idle", message: "配置已变更，请重新测试。" });
  }

  async function testModel() {
    setTestState({ status: "testing", message: "正在测试模型连通性..." });
    try {
      const result = await api<ModelPolicyTestResponse>("/api/admin/model-policy/test", {
        method: "POST",
        body: JSON.stringify(draft),
      });
      setDraft((prev) => ({ ...prev, test_token: result.test_token }));
      setTestState({
        status: result.ok ? "passed" : "failed",
        message: result.message || (result.ok ? "测试通过" : "测试失败"),
      });
    } catch (error) {
      setDraft((prev) => ({ ...prev, test_token: "" }));
      setTestState({
        status: "failed",
        message: error instanceof Error ? error.message : "模型测试失败",
      });
    }
  }

  const canSave = testState.status === "passed" && !!draft.test_token;
  const isAnthropic = draft.protocol === "anthropic";

  return (
    <div className="modal-backdrop" role="presentation">
      <section className="modal-card" role="dialog" aria-modal="true" aria-label={mode === "create" ? "新增模型" : "编辑模型"}>
        <div className="modal-header">
          <div>
            <h2>{mode === "create" ? "新增模型" : "编辑模型"}</h2>
            <p>新增或更改模型必须测试通过后才能保存。</p>
          </div>
          <button className="button ghost" onClick={onClose}>关闭</button>
        </div>

        <div className="modal-grid">
          <label className="model-field">
            <span>协议</span>
            <select className="input" value={draft.protocol || DEFAULT_MODEL_PROTOCOL} onChange={(event) => patchDraft({ protocol: event.target.value, base_url: event.target.value === "anthropic" ? "" : draft.base_url })}>
              <option value="openai_compatible">OpenAI 兼容</option>
              <option value="anthropic">Anthropic</option>
            </select>
          </label>
          <label className="model-field">
            <span>供应商 ID</span>
            <input className="input" placeholder="custom_provider" value={draft.provider_id} onChange={(event) => patchDraft({ provider_id: event.target.value })} />
          </label>
          <label className="model-field">
            <span>模型 ID</span>
            <input className="input" placeholder="gpt-5.5" value={draft.id} onChange={(event) => patchDraft({ id: event.target.value })} />
          </label>
          <label className="model-field">
            <span>显示名称</span>
            <input className="input" placeholder="GPT-5.5" value={draft.name} onChange={(event) => patchDraft({ name: event.target.value })} />
          </label>
          <label className="model-field model-field-wide">
            <span>Base URL</span>
            <input
              className="input"
              disabled={isAnthropic}
              placeholder={isAnthropic ? "Anthropic 不需要填写" : "https://example.com/v1"}
              value={isAnthropic ? "" : draft.base_url}
              onChange={(event) => patchDraft({ base_url: event.target.value })}
            />
          </label>
          <label className="model-field model-field-wide">
            <span>API Key</span>
            <input
              className="input"
              type="password"
              placeholder={draft.masked_key ? `已保存 ${draft.masked_key}，留空沿用旧 Key` : "sk-..."}
              value={draft.api_key || ""}
              onChange={(event) => patchDraft({ api_key: event.target.value })}
            />
          </label>
        </div>

        <p className={testState.status === "passed" ? "success" : testState.status === "failed" ? "error" : "muted"}>
          {testState.message}
        </p>

        <div className="modal-actions">
          <button className="button outline" disabled={testState.status === "testing"} onClick={() => void testModel()}>
            {testState.status === "testing" ? "测试中..." : "测试连接"}
          </button>
          <button
            className="button"
            disabled={testState.status !== "passed" || !canSave}
            onClick={() => onSave({ ...draft, enabled: draft.enabled !== false })}
          >
            保存模型
          </button>
        </div>
      </section>
    </div>
  );
}

function UpdatePolicyPanel({ api }: { api: ReturnType<typeof useApi> }) {
  const [policy, setPolicy] = useState<UpdatePolicy | null>(null);
  const [assets, setAssets] = useState<UpdateAsset[]>([]);
  const [message, setMessage] = useState("");
  const [uploadingSlot, setUploadingSlot] = useState<string | null>(null);
  const [packageName, setPackageName] = useState<Record<string, string>>({});
  const [assetVersions, setAssetVersions] = useState<Record<string, string>>({});
  const [assetSignatures, setAssetSignatures] = useState<Record<string, string>>({});

  async function loadPolicy() {
    const [policyData, assetData] = await Promise.all([
      api<UpdatePolicy>("/api/admin/update-policy"),
      api<UpdateAssetList>("/api/admin/update-assets").catch(() => ({ items: [] })),
    ]);
    setPolicy(policyData);
    setAssets(assetData.items || []);
  }

  useEffect(() => {
    void loadPolicy();
  }, []);

  function updatePolicy(patch: Partial<UpdatePolicy>) {
    if (!policy) return;
    setPolicy({ ...policy, ...patch });
  }

  async function savePolicy(nextPolicy = policy) {
    if (!nextPolicy) return;
    setMessage("");
    try {
      const saved = await api<UpdatePolicy>("/api/admin/update-policy", {
        method: "PUT",
        body: JSON.stringify({
          enabled: nextPolicy.enabled,
          latest_version: nextPolicy.latest_version,
          min_supported_version: nextPolicy.min_supported_version,
          force_update: nextPolicy.force_update,
          release_notes: nextPolicy.release_notes,
          macos_asset_id: nextPolicy.macos_asset_id,
          windows_asset_id: nextPolicy.windows_asset_id,
          linux_asset_id: nextPolicy.linux_asset_id,
          default_asset_id: nextPolicy.default_asset_id,
          macos_download_url: nextPolicy.macos_download_url,
          windows_download_url: nextPolicy.windows_download_url,
          linux_download_url: nextPolicy.linux_download_url,
          default_download_url: nextPolicy.default_download_url,
        }),
      });
      setPolicy(saved);
      setMessage("已保存，员工客户端启动或下次检查更新时生效");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "保存失败");
    }
  }

  function slotForPlatform(platform: string) {
    return UPDATE_ASSET_SLOTS.find((slot) => slot.platform === platform) || UPDATE_ASSET_SLOTS[3];
  }

  function setLatestAsset(slot: (typeof UPDATE_ASSET_SLOTS)[number], asset: UpdateAsset) {
    if (!policy) return;
    setPolicy({
      ...policy,
      latest_version: asset.version,
      [slot.assetIdKey]: asset.id,
      [slot.assetKey]: asset,
    });
    setMessage(`${slot.label} 已选择 ${asset.name || asset.original_filename}，保存策略后生效`);
  }

  async function deleteAsset(asset: UpdateAsset, isLatest: boolean) {
    if (isLatest) return;
    const displayName = asset.name || asset.original_filename;
    if (!window.confirm(`确认删除历史包「${displayName}」吗？删除后服务器文件也会移除。`)) {
      return;
    }
    setMessage("");
    try {
      await api<{ success: boolean }>(`/api/admin/update-assets/${asset.id}`, {
        method: "DELETE",
      });
      setAssets((items) => items.filter((item) => item.id !== asset.id));
      setMessage(`历史包「${displayName}」已删除`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "删除失败");
    }
  }

  async function uploadAsset(slot: (typeof UPDATE_ASSET_SLOTS)[number], file: File | null) {
    if (!policy || !file) return;
    const version = (assetVersions[slot.platform] || policy.latest_version || "").trim();
    if (!version) {
      setMessage("请先填写这个安装包的版本号，再上传安装包");
      return;
    }
    const name = (packageName[slot.platform] || `${slot.label} ${version}`).trim();

    const form = new FormData();
    form.set("platform", slot.platform);
    form.set("name", name);
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
      setAssets((items) => [asset, ...items.filter((item) => item.id !== asset.id)]);
      setPackageName({ ...packageName, [slot.platform]: "" });
      setMessage(`${slot.label} 安装包已上传，已进入历史列表，可手动设为最新包`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "上传失败");
    } finally {
      setUploadingSlot(null);
    }
  }

  if (!policy) return <section className="card muted">加载中...</section>;

  const latestVersion = policy.latest_version.trim();
  const mismatchedSlots = UPDATE_ASSET_SLOTS.filter((slot) => {
    const asset = policy[slot.assetKey];
    return asset !== null && latestVersion !== "" && asset.version.trim() !== latestVersion;
  });

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
          版本号用于展示和发布记录；员工端是否需要更新以当前安装包 SHA-256 是否等于所选最新包为准。上传的历史包都会保留，需要手动选择某个平台的最新包。
        </div>
        {mismatchedSlots.length > 0 && (
          <p className="error">
            警告：{mismatchedSlots.map((slot) => `${slot.label}（v${policy[slot.assetKey]?.version}）`).join("、")}
            安装包版本与最新版号 v{latestVersion} 不一致。员工端会以对应平台安装包的版本为准判断是否有更新，
            版本号旧于 v{latestVersion} 的安装包不会推送给用户。请先填写新版号，再重新上传对应平台的新版安装包。
          </p>
        )}
        <div className="form-grid update-form">
          <label className="model-field model-field-wide">
            <span>更新说明</span>
            <textarea
              className="input textarea"
              placeholder="本次更新修复了..."
              value={policy.release_notes}
              onChange={(event) => updatePolicy({ release_notes: event.target.value })}
            />
          </label>
          <label className="model-field model-field-wide">
            <span>兼容旧客户端的最低版本</span>
            <input
              className="input"
              placeholder="1.3.0"
              value={policy.min_supported_version}
              onChange={(event) => updatePolicy({ min_supported_version: event.target.value })}
            />
          </label>
          <div className="model-field model-field-wide">
            <span>上传新安装包</span>
            <div className="update-asset-grid">
              {UPDATE_ASSET_SLOTS.map((slot) => {
                const asset = policy[slot.assetKey];
                const isUploading = uploadingSlot === slot.platform;
                return (
                  <div className="update-asset-panel" key={slot.platform}>
                    <div className="update-asset-head">
                      <strong>{slot.label}</strong>
                      <span>
                        {asset ? `v${asset.version}` : "未上传"}
                        {asset && latestVersion !== "" && asset.version.trim() !== latestVersion && " ⚠️ 与最新版号不一致"}
                      </span>
                    </div>
                    {asset ? (
                      <div className="update-asset-meta">
                        <b>{asset.name || asset.original_filename}</b>
                        <span>文件：{asset.original_filename}</span>
                        <span>{asset.mime_type || "文件"} · {formatNumber(asset.size_bytes)} bytes</span>
                        <span>上传人：{asset.uploaded_by_display_name || asset.uploaded_by_email || "-"}</span>
                        <span>上传时间：{compactDate(asset.time_created)}</span>
                        <span>下载次数：{formatNumber(asset.download_count)}</span>
                        <span>SHA-256：{asset.sha256.slice(0, 16)}...</span>
                        <span>MD5：{asset.md5 ? `${asset.md5.slice(0, 16)}...` : "-"}</span>
                        <span>应用内更新签名：{asset.signature ? `${asset.signature.slice(0, 18)}...` : "未配置"}</span>
                      </div>
                    ) : (
                      <p className="muted">员工端匹配不到该平台包时会使用默认包。</p>
                    )}
                    <input
                      className="input"
                      placeholder={`${slot.label} 包名，例如：${slot.label} 1.4.1 正式包`}
                      value={packageName[slot.platform] || ""}
                      onChange={(event) =>
                        setPackageName({
                          ...packageName,
                          [slot.platform]: event.target.value,
                        })
                      }
                    />
                    <input
                      className="input"
                      placeholder="版本号，例如：1.4.1"
                      value={assetVersions[slot.platform] || ""}
                      onChange={(event) =>
                        setAssetVersions({
                          ...assetVersions,
                          [slot.platform]: event.target.value,
                        })
                      }
                    />
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
                      {isUploading ? "上传中..." : "上传为历史包"}
                    </label>
                  </div>
                );
              })}
            </div>
          </div>
        </div>
        {message && (
          <p className={/(已保存|已选择|已上传|已删除)/.test(message) ? "success" : "error"}>
            {message}
          </p>
        )}
      </section>
      <section className="card">
        <div className="section-title">
          <h3>版本包历史</h3>
          <span>共 {formatNumber(assets.length)} 个包</span>
        </div>
        <div className="table-scroll">
          <table className="table update-history-table">
            <thead>
              <tr>
                <th>状态</th>
                <th>包名</th>
                <th>平台</th>
                <th>版本</th>
                <th>文件</th>
                <th>Hash</th>
                <th>上传</th>
                <th>下载</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              {assets.length === 0 ? (
                <tr>
                  <td colSpan={9} className="muted">暂无上传记录</td>
                </tr>
              ) : (
                assets.map((asset) => {
                  const slot = slotForPlatform(asset.platform);
                  const isLatest = policy[slot.assetIdKey] === asset.id;
                  return (
                    <tr key={asset.id}>
                      <td>{isLatest ? <span className="pill success">最新</span> : <span className="muted">历史</span>}</td>
                      <td>
                        <strong>{asset.name || asset.original_filename}</strong>
                        <span className="muted block">ID：{asset.id}</span>
                      </td>
                      <td>{slot.label}</td>
                      <td>v{asset.version}</td>
                      <td>
                        <span>{asset.original_filename}</span>
                        <span className="muted block">{formatNumber(asset.size_bytes)} bytes</span>
                      </td>
                      <td>
                        <code>SHA：{asset.sha256.slice(0, 18)}...</code>
                        <code>MD5：{asset.md5 ? `${asset.md5.slice(0, 18)}...` : "-"}</code>
                      </td>
                      <td>
                        <span>{asset.uploaded_by_display_name || asset.uploaded_by_email || "-"}</span>
                        <span className="muted block">{compactDate(asset.time_created)}</span>
                      </td>
                      <td>{formatNumber(asset.download_count)}</td>
                      <td>
                        <div className="table-actions">
                          <button
                            className="button outline"
                            disabled={isLatest}
                            onClick={() => setLatestAsset(slot, asset)}
                          >
                            {isLatest ? "已是最新" : "设为最新"}
                          </button>
                          <button
                            className="button ghost danger-text"
                            disabled={isLatest}
                            onClick={() => void deleteAsset(asset, isLatest)}
                          >
                            删除
                          </button>
                        </div>
                      </td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
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
    reasoning_tokens: number;
    cache_read_tokens: number;
    cache_write_tokens: number;
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

interface UserDailyTokenAnalytics {
  period_days: number;
  items: Array<{
    date: string;
    user_id: string;
    user_email: string;
    user_display_name: string;
    input_tokens: number;
    output_tokens: number;
    reasoning_tokens: number;
    cache_read_tokens: number;
    cache_write_tokens: number;
    total_tokens: number;
    total_cost: number;
    conversation_count: number;
    conversations: Array<{
      session_id: string;
      title: string;
      workspace: string;
      total_tokens: number;
      total_cost: number;
    }>;
    models: Array<{
      provider_id: string | null;
      model_id: string | null;
      input_tokens: number;
      output_tokens: number;
      reasoning_tokens: number;
      total_tokens: number;
      total_cost: number;
    }>;
  }>;
}

function ActiveUsersLineChart({ timeline }: { timeline: TimelineAnalytics | null }) {
  const points = timeline?.timeline || [];
  if (points.length === 0) {
    return <div className="active-users-chart empty">暂无趋势数据</div>;
  }
  const width = 720;
  const height = 180;
  const padX = 34;
  const padY = 22;
  const maxActive = Math.max(1, ...points.map((item) => item.active_users));
  const maxTokens = Math.max(1, ...points.map((item) => item.total_tokens));
  const xFor = (index: number) => padX + (index * (width - padX * 2)) / Math.max(points.length - 1, 1);
  const yForActive = (value: number) => height - padY - (value / maxActive) * (height - padY * 2);
  const yForTokens = (value: number) => height - padY - (value / maxTokens) * (height - padY * 2);
  const activeLine = points.map((item, index) => `${xFor(index)},${yForActive(item.active_users)}`).join(" ");
  const tokenLine = points.map((item, index) => `${xFor(index)},${yForTokens(item.total_tokens)}`).join(" ");

  return (
    <div className="active-users-chart">
      <svg viewBox={`0 0 ${width} ${height}`} role="img" aria-label="活跃人数和 Token 趋势折线图">
        <line x1={padX} y1={height - padY} x2={width - padX} y2={height - padY} className="chart-axis" />
        <line x1={padX} y1={padY} x2={padX} y2={height - padY} className="chart-axis" />
        <polyline points={activeLine} className="chart-line active" />
        <polyline points={tokenLine} className="chart-line tokens" />
        {points.map((item, index) => (
          <g key={item.date}>
            <circle cx={xFor(index)} cy={yForActive(item.active_users)} r="3" className="chart-dot active" />
            <text x={xFor(index)} y={height - 4} textAnchor="middle" className="chart-label">
              {item.date.slice(5)}
            </text>
          </g>
        ))}
      </svg>
      <div className="chart-legend">
        <span><i className="legend-active" />活跃人数</span>
        <span><i className="legend-tokens" />Token 趋势</span>
      </div>
    </div>
  );
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
  const [userDailyTokens, setUserDailyTokens] = useState<UserDailyTokenAnalytics | null>(null);

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

      const [users, models, tools, content, time, userDaily] = await Promise.all([
        loadOne<UserAnalytics>(`/api/admin/audit/analytics/users?days=${days}`),
        loadOne<ModelAnalytics>(`/api/admin/audit/analytics/models?days=${days}`),
        loadOne<ToolAnalytics>(`/api/admin/audit/analytics/tools?days=${days}`),
        loadOne<ContentAnalytics>(`/api/admin/audit/analytics/content?days=${days}`),
        loadOne<TimelineAnalytics>(`/api/admin/audit/analytics/timeline?days=${days}`),
        loadOne<UserDailyTokenAnalytics>(`/api/admin/audit/analytics/user-daily-tokens?days=${days}`),
      ]);
      setUserStats(users);
      setModelStats(models);
      setToolStats(tools);
      setContentStats(content);
      setTimeline(time);
      setUserDailyTokens(userDaily);
      if ([users, models, tools, content, time, userDaily].some((item) => item === null)) {
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
        <ActiveUsersLineChart timeline={timeline} />
        {timeline && timeline.timeline.length > 0 && (
          <table className="table compact-table">
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
              {timeline.timeline.slice(-7).map((item) => (
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

      <div className="card">
        <h2>用户每日 Token</h2>
        <table className="table">
          <thead>
            <tr>
              <th>日期</th>
              <th>用户</th>
              <th>总 Token</th>
              <th>输入 / 输出 / 推理</th>
              <th>成本</th>
              <th>模型</th>
              <th>对话内容</th>
            </tr>
          </thead>
          <tbody>
            {userDailyTokens?.items.slice(0, 30).map((item) => (
              <tr key={`${item.user_id}-${item.date}`}>
                <td>{item.date}</td>
                <td>
                  <strong>{item.user_display_name || item.user_email}</strong>
                  <div className="muted">{item.user_email}</div>
                </td>
                <td>{formatNumber(item.total_tokens)}</td>
                <td>
                  {formatNumber(item.input_tokens)} / {formatNumber(item.output_tokens)} / {formatNumber(item.reasoning_tokens)}
                </td>
                <td>${item.total_cost.toFixed(2)}</td>
                <td>
                  {item.models.slice(0, 2).map((model) => (
                    <div className="muted" key={`${model.provider_id}-${model.model_id}`}>
                      {modelLabel(model.model_id, model.provider_id)} · {formatNumber(model.total_tokens)}
                    </div>
                  ))}
                </td>
                <td>
                  <div className="conversation-links">
                    {item.conversations.slice(0, 3).map((conversation) => (
                      <button
                        className="link-button"
                        key={conversation.session_id}
                        onClick={() => {
                          window.location.hash = `audit-session=${encodeURIComponent(conversation.session_id)}`;
                        }}
                      >
                        {conversation.title || conversation.session_id}
                      </button>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
            {(!userDailyTokens || userDailyTokens.items.length === 0) && (
              <tr>
                <td colSpan={7} className="muted">暂无用户每日 Token 数据</td>
              </tr>
            )}
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
              <th>推理 Token</th>
              <th>缓存读/写</th>
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
                <td>{formatNumber(model.reasoning_tokens)}</td>
                <td>{formatNumber(model.cache_read_tokens)} / {formatNumber(model.cache_write_tokens)}</td>
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
