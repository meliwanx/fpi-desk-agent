"""Static enterprise admin console page."""

from __future__ import annotations


def admin_console_html() -> str:
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>fpi-agent 管理后台</title>
  <style>
    :root {
      color-scheme: light;
      --bg: #f6f7f9;
      --panel: #ffffff;
      --line: #dde2ea;
      --text: #18202a;
      --muted: #6a7380;
      --brand: #1557b0;
      --danger: #b42318;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      background: var(--bg);
      color: var(--text);
    }
    header {
      height: 56px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 24px;
      border-bottom: 1px solid var(--line);
      background: var(--panel);
    }
    h1 { font-size: 17px; margin: 0; }
    main {
      display: grid;
      grid-template-columns: 280px minmax(0, 1fr);
      min-height: calc(100vh - 56px);
    }
    aside {
      border-right: 1px solid var(--line);
      background: #fbfcfd;
      padding: 20px;
    }
    section { padding: 24px; }
    label { display: block; font-size: 12px; color: var(--muted); margin: 12px 0 6px; }
    input, select, textarea {
      width: 100%;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 9px 10px;
      background: #fff;
      color: var(--text);
      font: inherit;
    }
    button {
      border: 1px solid var(--brand);
      border-radius: 6px;
      padding: 8px 12px;
      background: var(--brand);
      color: #fff;
      font: inherit;
      cursor: pointer;
    }
    button.secondary { background: #fff; color: var(--brand); }
    button:disabled { opacity: .55; cursor: default; }
    .tabs { display: flex; gap: 8px; margin-bottom: 18px; }
    .tab { background: #fff; color: var(--text); border-color: var(--line); }
    .tab.active { background: var(--brand); color: #fff; border-color: var(--brand); }
    .row { display: flex; gap: 8px; align-items: center; }
    .split { display: grid; grid-template-columns: 360px minmax(0, 1fr); gap: 16px; }
    .panel {
      background: var(--panel);
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
    }
    .list { display: grid; gap: 8px; }
    .item {
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 10px;
      background: #fff;
      cursor: pointer;
    }
    .item:hover { border-color: #aeb8c5; }
    .muted { color: var(--muted); font-size: 12px; }
    .error { color: var(--danger); min-height: 18px; }
    pre {
      white-space: pre-wrap;
      word-break: break-word;
      background: #f3f5f8;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 12px;
      max-height: 520px;
      overflow: auto;
    }
    .downloads { display: grid; gap: 8px; margin-bottom: 12px; }
    .file-row {
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 12px;
      border: 1px solid var(--line);
      border-radius: 6px;
      padding: 8px 10px;
      background: #fff;
    }
    table { width: 100%; border-collapse: collapse; background: #fff; }
    th, td { border-bottom: 1px solid var(--line); padding: 10px; text-align: left; font-size: 13px; }
    th { color: var(--muted); font-weight: 600; }
    #app[hidden], #login[hidden] { display: none; }
  </style>
</head>
<body>
  <header>
    <h1>fpi-agent 管理后台</h1>
    <div class="row">
      <span id="who" class="muted"></span>
      <button id="logout" class="secondary">退出</button>
    </div>
  </header>

  <main id="login">
    <aside></aside>
    <section>
      <div class="panel" style="max-width: 420px">
        <h2>管理员登录</h2>
        <label>账号</label>
        <input id="loginEmail" value="admin" autocomplete="username" />
        <label>密码</label>
        <input id="loginPassword" value="admin123" type="password" autocomplete="current-password" />
        <div style="height: 14px"></div>
        <button id="loginButton">登录</button>
        <p id="loginError" class="error"></p>
      </div>
    </section>
  </main>

  <main id="app" hidden>
    <aside>
      <div class="tabs">
        <button class="tab active" data-tab="audit">审计</button>
        <button class="tab" data-tab="users">员工</button>
      </div>
      <div id="auditFilters">
        <label>搜索</label>
        <input id="auditSearch" placeholder="员工、标题、工作空间" />
        <div style="height: 10px"></div>
        <button id="refreshAudit">刷新审计</button>
      </div>
    </aside>
    <section id="auditTab">
      <div class="split">
        <div class="panel">
          <h2>会话</h2>
          <div id="auditList" class="list"></div>
        </div>
        <div class="panel">
          <h2>对话记录</h2>
          <div id="fileDownloads" class="downloads"></div>
          <pre id="transcript">选择左侧会话查看详情</pre>
        </div>
      </div>
    </section>
    <section id="usersTab" hidden>
      <div class="panel">
        <h2>新增员工</h2>
        <div class="row">
          <input id="newEmail" placeholder="账号或邮箱" />
          <input id="newName" placeholder="姓名" />
          <input id="newPassword" placeholder="初始密码" />
          <select id="newRole"><option value="user">user</option><option value="admin">admin</option></select>
          <button id="createUser">新增</button>
        </div>
        <p id="userError" class="error"></p>
      </div>
      <div style="height: 16px"></div>
      <div class="panel">
        <h2>员工列表</h2>
        <table>
          <thead><tr><th>账号</th><th>姓名</th><th>角色</th><th>状态</th></tr></thead>
          <tbody id="userRows"></tbody>
        </table>
      </div>
    </section>
  </main>

  <script>
    const key = "fpi-admin-session";
    const state = { token: "", user: null };
    const $ = (id) => document.getElementById(id);

    function readSession() {
      try {
        const raw = localStorage.getItem(key);
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        if (!parsed.token) return null;
        return parsed;
      } catch { return null; }
    }
    function saveSession(payload) {
      localStorage.setItem(key, JSON.stringify(payload));
      state.token = payload.token;
      state.user = payload.user;
      $("who").textContent = payload.user ? `${payload.user.display_name || payload.user.email} (${payload.user.role})` : "";
    }
    async function api(path, options = {}) {
      const headers = new Headers(options.headers || {});
      headers.set("Content-Type", "application/json");
      if (state.token) headers.set("X-FPI-Session", state.token);
      const res = await fetch(path, { ...options, headers });
      if (!res.ok) throw new Error(await res.text());
      return res.status === 204 ? null : res.json();
    }
    function escapeHtml(value) {
      return String(value ?? "").replace(/[&<>"']/g, (ch) => ({
        "&": "&amp;",
        "<": "&lt;",
        ">": "&gt;",
        '"': "&quot;",
        "'": "&#39;",
      }[ch]));
    }
    function showApp() {
      $("login").hidden = true;
      $("app").hidden = false;
      loadAudit();
      loadUsers();
    }
    async function login() {
      $("loginError").textContent = "";
      try {
        const payload = await api("/api/company-auth/login", {
          method: "POST",
          body: JSON.stringify({ email: $("loginEmail").value, password: $("loginPassword").value }),
        });
        saveSession(payload);
        showApp();
      } catch (err) {
        $("loginError").textContent = "登录失败";
      }
    }
    async function loadUsers() {
      try {
        const users = await api("/api/admin/users");
        $("userRows").innerHTML = users.map((u) =>
          `<tr><td>${u.email}</td><td>${u.display_name}</td><td>${u.role}</td><td>${u.is_active ? "启用" : "停用"}</td></tr>`
        ).join("");
      } catch (err) {
        $("userError").textContent = "员工列表加载失败";
      }
    }
    async function createUser() {
      $("userError").textContent = "";
      try {
        await api("/api/admin/users", {
          method: "POST",
          body: JSON.stringify({
            email: $("newEmail").value,
            display_name: $("newName").value,
            password: $("newPassword").value,
            role: $("newRole").value,
          }),
        });
        $("newEmail").value = "";
        $("newName").value = "";
        $("newPassword").value = "";
        await loadUsers();
      } catch (err) {
        $("userError").textContent = "新增员工失败";
      }
    }
    async function loadAudit() {
      const q = encodeURIComponent($("auditSearch").value || "");
      const data = await api(`/api/admin/audit/sessions?q=${q}`);
      $("auditList").innerHTML = data.items.map((s) =>
        `<div class="item" data-session="${s.id}">
          <strong>${s.title || "未命名会话"}</strong>
          <div class="muted">${s.user_display_name || s.user_email} · ${s.workspace || "无工作空间"}</div>
        </div>`
      ).join("") || "<div class='muted'>暂无审计数据</div>";
      document.querySelectorAll("[data-session]").forEach((node) => {
        node.addEventListener("click", () => loadTranscript(node.dataset.session));
      });
    }
    async function loadTranscript(sessionId) {
      const data = await api(`/api/admin/audit/sessions/${sessionId}/messages`);
      const files = data.messages.flatMap((message) =>
        (message.parts || []).filter((part) => part.file).map((part) => ({ partId: part.id, ...part.file }))
      );
      $("fileDownloads").innerHTML = files.map((file) =>
        `<div class="file-row">
          <span><strong>${escapeHtml(file.name || "附件")}</strong><span class="muted"> · ${Number(file.size || 0).toLocaleString()} bytes</span></span>
          ${file.content_uploaded ? `<button class="secondary" data-download="${escapeHtml(file.partId)}">下载</button>` : `<span class="muted">未同步原件</span>`}
        </div>`
      ).join("");
      document.querySelectorAll("[data-download]").forEach((node) => {
        node.addEventListener("click", () => downloadAuditFile(node.dataset.download));
      });
      $("transcript").textContent = JSON.stringify(data.messages, null, 2);
    }
    async function downloadAuditFile(partId) {
      const res = await fetch(`/api/admin/audit/files/${encodeURIComponent(partId)}/download`, {
        headers: { "X-FPI-Session": state.token },
      });
      if (!res.ok) {
        alert("文件下载失败");
        return;
      }
      const blob = await res.blob();
      const disposition = res.headers.get("content-disposition") || "";
      const match = disposition.match(/filename="?([^";]+)"?/i);
      const filename = match ? decodeURIComponent(match[1]) : "attachment";
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();
      a.remove();
      URL.revokeObjectURL(url);
    }
    function switchTab(tab) {
      document.querySelectorAll(".tab").forEach((node) => node.classList.toggle("active", node.dataset.tab === tab));
      $("auditTab").hidden = tab !== "audit";
      $("usersTab").hidden = tab !== "users";
      $("auditFilters").hidden = tab !== "audit";
    }

    $("loginButton").addEventListener("click", login);
    $("createUser").addEventListener("click", createUser);
    $("refreshAudit").addEventListener("click", loadAudit);
    $("logout").addEventListener("click", () => { localStorage.removeItem(key); location.reload(); });
    document.querySelectorAll(".tab").forEach((node) => node.addEventListener("click", () => switchTab(node.dataset.tab)));

    const existing = readSession();
    if (existing) {
      saveSession(existing);
      showApp();
    }
  </script>
</body>
</html>"""
