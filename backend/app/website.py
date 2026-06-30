"""Public product website and desktop package downloads."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse
from starlette.responses import FileResponse

from app.api.app_update import _asset_id_for_platform, _company_store, _policy_value
from app.dependencies import SettingsDep

router = APIRouter(include_in_schema=False)

_PLATFORMS = ("macos", "windows", "linux")
_PLATFORM_LABELS = {
    "macos": "Mac 版本",
    "windows": "Windows 版本",
    "linux": "Linux 版本",
}


@router.get("/", response_class=HTMLResponse)
async def website_home() -> HTMLResponse:
    return HTMLResponse(_website_html())


@router.get("/download-options")
async def website_download_options(request: Request) -> dict[str, Any]:
    store = _company_store(request)
    policy = await store.get_update_policy()
    platforms = {}
    for platform in _PLATFORMS:
        platforms[platform] = await _public_platform_download(request, store, policy, platform)
    return {
        "latest_version": str(_policy_value(policy, "latest_version", "") or ""),
        "release_notes": str(_policy_value(policy, "release_notes", "") or ""),
        "platforms": platforms,
    }


@router.get("/download/{asset_id}", name="website_download_asset")
async def website_download_asset(
    request: Request,
    settings: SettingsDep,
    asset_id: str,
) -> FileResponse:
    store = _company_store(request)
    if not hasattr(store, "get_update_asset"):
        raise HTTPException(status_code=404, detail="Update asset not found")
    asset = await store.get_update_asset(asset_id)
    if asset is None:
        raise HTTPException(status_code=404, detail="Update asset not found")

    storage_dir = Path(settings.update_asset_storage_dir).expanduser()
    file_path = storage_dir / Path(asset.stored_filename).name
    if not file_path.is_file():
        raise HTTPException(status_code=404, detail="Update asset file not found")

    if hasattr(store, "increment_update_asset_download_count"):
        await store.increment_update_asset_download_count(asset.id)

    return FileResponse(
        file_path,
        media_type=asset.mime_type or "application/octet-stream",
        filename=asset.original_filename or file_path.name,
    )


@router.get("/website-assets/juguang-logo.png")
async def website_logo() -> FileResponse:
    logo_path = _find_logo_path()
    if logo_path is None:
        raise HTTPException(status_code=404, detail="Logo not found")
    return FileResponse(logo_path, media_type="image/png")


async def _public_platform_download(request: Request, store: Any, policy: Any, platform: str) -> dict[str, Any]:
    asset_id = _asset_id_for_platform(policy, platform)
    asset = await store.get_update_asset(asset_id) if asset_id and hasattr(store, "get_update_asset") else None
    if asset is None:
        return {
            "platform": platform,
            "label": _PLATFORM_LABELS[platform],
            "available": False,
            "download_url": "",
            "filename": "",
            "version": str(_policy_value(policy, "latest_version", "") or ""),
            "size_bytes": 0,
            "sha256": "",
        }
    return {
        "platform": platform,
        "label": _PLATFORM_LABELS[platform],
        "available": True,
        "download_url": str(request.url_for("website_download_asset", asset_id=asset.id)),
        "filename": asset.original_filename or "",
        "version": asset.version or str(_policy_value(policy, "latest_version", "") or ""),
        "size_bytes": int(asset.size_bytes or 0),
        "sha256": asset.sha256 or "",
    }


def _find_logo_path() -> Path | None:
    candidates = [
        Path(__file__).parent / "website_static" / "juguang-logo.png",
        Path(__file__).parent.parent.parent / "frontend" / "public" / "juguang-logo.png",
    ]
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _website_html() -> str:
    return """<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>聚光智能办公助手</title>
  <meta name="description" content="聚光智能办公助手，面向团队的桌面 AI 办公助手，支持安全私有部署、资料整理、智能问答和自动更新。" />
  <style>
    :root {
      color-scheme: light;
      --blue: #1768e8;
      --blue-dark: #0d3f9f;
      --ink: #152033;
      --muted: #5d6a7c;
      --line: #d9e1ee;
      --panel: #ffffff;
      --soft: #f4f7fb;
      --green: #138a62;
      --amber: #ad6b00;
      --violet: #6d5bd0;
      --teal: #0f7b8a;
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      color: var(--ink);
      background: #f8fafd;
      letter-spacing: 0;
    }
    a { color: inherit; text-decoration: none; }
    .page-shell { min-height: 100vh; }
    .site-header {
      position: sticky;
      top: 0;
      z-index: 20;
      border-bottom: 1px solid rgba(21, 32, 51, 0.08);
      background: rgba(255, 255, 255, 0.92);
      backdrop-filter: blur(14px);
    }
    .nav {
      max-width: 1160px;
      margin: 0 auto;
      padding: 14px 24px;
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 24px;
    }
    .brand {
      display: flex;
      align-items: center;
      gap: 10px;
      font-weight: 700;
      white-space: nowrap;
    }
    .brand img {
      width: 34px;
      height: 34px;
      border-radius: 8px;
      box-shadow: 0 8px 20px rgba(23, 104, 232, 0.18);
    }
    .nav-links {
      display: flex;
      align-items: center;
      gap: 22px;
      color: var(--muted);
      font-size: 14px;
    }
    .support-link {
      display: inline-flex;
      align-items: center;
      min-height: 30px;
      padding: 0 10px;
      border: 1px solid #d7e1ef;
      border-radius: 999px;
      color: #41516b;
      background: #f8fbff;
      font-weight: 700;
    }
    .hero {
      max-width: 1160px;
      margin: 0 auto;
      padding: 68px 24px 54px;
      display: grid;
      grid-template-columns: minmax(0, 0.96fr) minmax(420px, 1.04fr);
      gap: 52px;
      align-items: center;
    }
    .eyebrow {
      display: inline-flex;
      align-items: center;
      gap: 8px;
      color: var(--blue-dark);
      background: #eaf2ff;
      border: 1px solid #cfe0ff;
      padding: 7px 10px;
      border-radius: 999px;
      font-size: 13px;
      font-weight: 700;
    }
    .eyebrow::before {
      content: "";
      width: 7px;
      height: 7px;
      border-radius: 999px;
      background: var(--green);
    }
    h1 {
      margin: 22px 0 18px;
      font-size: 56px;
      line-height: 1.05;
      letter-spacing: 0;
    }
    .hero-copy {
      margin: 0;
      max-width: 660px;
      color: var(--muted);
      font-size: 18px;
      line-height: 1.8;
    }
    .hero-meta {
      margin-top: 20px;
      display: flex;
      flex-wrap: wrap;
      gap: 10px;
    }
    .meta-pill {
      display: inline-flex;
      align-items: center;
      min-height: 32px;
      padding: 0 11px;
      border: 1px solid #d7e1ef;
      border-radius: 999px;
      background: #fff;
      color: #3c4a60;
      font-size: 13px;
      font-weight: 700;
    }
    .download-panel {
      margin-top: 32px;
      padding: 18px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: var(--panel);
      box-shadow: 0 18px 48px rgba(30, 49, 80, 0.10);
    }
    .download-row {
      display: flex;
      gap: 12px;
      align-items: center;
      flex-wrap: wrap;
    }
    .download-button {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-height: 48px;
      padding: 0 22px;
      border-radius: 8px;
      border: 1px solid var(--blue);
      background: var(--blue);
      color: #fff;
      font-weight: 800;
      white-space: nowrap;
    }
    .download-button[aria-disabled="true"] {
      pointer-events: none;
      border-color: #a7b3c5;
      background: #a7b3c5;
    }
    .version-text {
      color: var(--muted);
      font-size: 14px;
      line-height: 1.5;
    }
    .segmented {
      margin-top: 16px;
      display: inline-grid;
      grid-template-columns: repeat(3, minmax(86px, 1fr));
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
      background: #f7f9fc;
    }
    .segmented button {
      appearance: none;
      border: 0;
      border-right: 1px solid var(--line);
      background: transparent;
      color: var(--muted);
      min-height: 38px;
      padding: 0 12px;
      font: inherit;
      font-size: 14px;
      font-weight: 700;
      cursor: pointer;
    }
    .segmented button:last-child { border-right: 0; }
    .segmented button.active {
      color: var(--blue-dark);
      background: #eaf2ff;
    }
    .segmented button.unavailable {
      color: #9aa6b6;
      background: #f1f4f8;
    }
    .release-note {
      margin: 14px 0 0;
      color: var(--muted);
      font-size: 13px;
      line-height: 1.6;
    }
    .product-visual {
      border: 1px solid #cdd7e6;
      border-radius: 8px;
      background: #ffffff;
      box-shadow: 0 24px 70px rgba(34, 47, 72, 0.16);
      overflow: hidden;
    }
    .window-bar {
      height: 42px;
      border-bottom: 1px solid var(--line);
      display: flex;
      align-items: center;
      justify-content: space-between;
      padding: 0 16px;
      color: #718096;
      font-size: 13px;
      background: #f5f7fb;
    }
    .traffic {
      display: flex;
      gap: 7px;
    }
    .traffic i {
      width: 10px;
      height: 10px;
      border-radius: 50%;
      display: block;
    }
    .traffic i:nth-child(1) { background: #ff6259; }
    .traffic i:nth-child(2) { background: #ffbd2e; }
    .traffic i:nth-child(3) { background: #28c840; }
    .visual-body {
      display: grid;
      grid-template-columns: 164px minmax(0, 1fr);
      min-height: 430px;
    }
    .mock-sidebar {
      border-right: 1px solid var(--line);
      background: #f7f9fc;
      padding: 18px 14px;
    }
    .mock-logo {
      display: flex;
      align-items: center;
      gap: 8px;
      font-weight: 800;
      font-size: 14px;
    }
    .mock-logo img {
      width: 26px;
      height: 26px;
      border-radius: 7px;
    }
    .mock-nav {
      margin-top: 22px;
      display: grid;
      gap: 9px;
    }
    .mock-nav span {
      display: block;
      height: 32px;
      border-radius: 8px;
      background: #eef3fa;
    }
    .mock-nav span:first-child {
      background: #dfeaff;
      border: 1px solid #c9dcff;
    }
    .mock-main {
      padding: 20px;
      display: grid;
      gap: 16px;
      align-content: start;
    }
    .assistant-card {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 16px;
      background: #ffffff;
    }
    .assistant-card h2 {
      margin: 0 0 10px;
      font-size: 18px;
      letter-spacing: 0;
    }
    .assistant-card p {
      margin: 0;
      color: var(--muted);
      line-height: 1.7;
      font-size: 14px;
    }
    .chips {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-top: 14px;
    }
    .chips span {
      display: inline-flex;
      align-items: center;
      min-height: 28px;
      padding: 0 9px;
      border-radius: 999px;
      background: #eef6f2;
      color: var(--green);
      font-size: 12px;
      font-weight: 700;
    }
    .ops-row {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
    }
    .ops-card {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: #fbfcfe;
    }
    .ops-card b {
      display: block;
      margin-bottom: 6px;
      color: #26344a;
      font-size: 13px;
    }
    .ops-card span {
      color: var(--muted);
      font-size: 12px;
      line-height: 1.5;
    }
    .task-grid {
      display: grid;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      gap: 12px;
    }
    .task {
      min-height: 92px;
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: #fbfcfe;
    }
    .task strong {
      display: block;
      margin-bottom: 8px;
      font-size: 14px;
    }
    .bar {
      display: block;
      height: 8px;
      margin-top: 7px;
      border-radius: 999px;
      background: #dde6f2;
    }
    .bar.short { width: 58%; }
    .bar.mid { width: 76%; }
    .bar.long { width: 92%; }
    .sections {
      border-top: 1px solid rgba(21, 32, 51, 0.08);
      background: #ffffff;
    }
    .section-inner {
      max-width: 1160px;
      margin: 0 auto;
      padding: 58px 24px;
    }
    .section-heading {
      margin: 0 0 26px;
      font-size: 32px;
      line-height: 1.2;
      letter-spacing: 0;
    }
    .feature-grid {
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 16px;
    }
    .section-kicker {
      margin: 0 0 10px;
      color: var(--teal);
      font-size: 13px;
      font-weight: 800;
    }
    .feature {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 20px;
      background: #fbfcfe;
    }
    .feature .icon {
      width: 34px;
      height: 34px;
      border-radius: 8px;
      display: grid;
      place-items: center;
      background: #eaf2ff;
      color: var(--blue-dark);
      font-weight: 900;
      margin-bottom: 16px;
    }
    .feature h3 {
      margin: 0 0 10px;
      font-size: 18px;
      letter-spacing: 0;
    }
    .feature p {
      margin: 0;
      color: var(--muted);
      line-height: 1.7;
      font-size: 14px;
    }
    .analysis-band {
      border-top: 1px solid rgba(21, 32, 51, 0.08);
      background: #f7fafc;
    }
    .analysis-layout {
      display: grid;
      grid-template-columns: 0.92fr 1.08fr;
      gap: 28px;
      align-items: stretch;
    }
    .analysis-list {
      display: grid;
      gap: 12px;
      margin-top: 24px;
    }
    .analysis-item {
      display: grid;
      grid-template-columns: 38px minmax(0, 1fr);
      gap: 12px;
      align-items: start;
      padding: 15px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fff;
    }
    .analysis-item b {
      display: grid;
      place-items: center;
      width: 38px;
      height: 38px;
      border-radius: 8px;
      background: #edf7f8;
      color: var(--teal);
      font-size: 15px;
    }
    .analysis-item h3 {
      margin: 0 0 6px;
      font-size: 16px;
      letter-spacing: 0;
    }
    .analysis-item p {
      margin: 0;
      color: var(--muted);
      font-size: 14px;
      line-height: 1.7;
    }
    .analysis-preview {
      border: 1px solid #cdd7e6;
      border-radius: 8px;
      background: #fff;
      box-shadow: 0 22px 58px rgba(34, 47, 72, 0.12);
      overflow: hidden;
    }
    .analysis-toolbar {
      min-height: 48px;
      border-bottom: 1px solid var(--line);
      display: flex;
      align-items: center;
      justify-content: space-between;
      gap: 14px;
      padding: 0 16px;
      background: #f5f7fb;
      color: #3f4d64;
      font-size: 13px;
      font-weight: 800;
    }
    .analysis-body {
      padding: 18px;
      display: grid;
      gap: 16px;
    }
    .kpi-row {
      display: grid;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      gap: 10px;
    }
    .kpi {
      border: 1px solid var(--line);
      border-radius: 8px;
      padding: 12px;
      background: #fbfcfe;
    }
    .kpi strong {
      display: block;
      color: var(--ink);
      font-size: 20px;
      margin-bottom: 4px;
    }
    .kpi span {
      color: var(--muted);
      font-size: 12px;
    }
    .sheet {
      border: 1px solid var(--line);
      border-radius: 8px;
      overflow: hidden;
    }
    .sheet-row {
      display: grid;
      grid-template-columns: 1.1fr 0.8fr 1fr 0.9fr;
      min-height: 34px;
      border-bottom: 1px solid #e7edf5;
      background: #fff;
    }
    .sheet-row:last-child { border-bottom: 0; }
    .sheet-row.header {
      min-height: 36px;
      background: #eef4fb;
      color: #40506a;
      font-weight: 800;
    }
    .sheet-row span {
      display: flex;
      align-items: center;
      padding: 0 10px;
      border-right: 1px solid #e7edf5;
      color: #4a5870;
      font-size: 13px;
    }
    .sheet-row span:last-child { border-right: 0; }
    .cell-bar {
      width: 100%;
      height: 8px;
      border-radius: 999px;
      background: #dfe7f2;
      overflow: hidden;
    }
    .cell-bar i {
      display: block;
      height: 100%;
      border-radius: inherit;
      background: var(--blue);
    }
    .chart-strip {
      display: grid;
      grid-template-columns: repeat(8, 1fr);
      gap: 8px;
      align-items: end;
      min-height: 118px;
      padding: 16px;
      border: 1px solid var(--line);
      border-radius: 8px;
      background: #fbfcfe;
    }
    .chart-strip i {
      display: block;
      border-radius: 6px 6px 0 0;
      background: #1768e8;
      min-height: 24px;
    }
    .chart-strip i:nth-child(2n) { background: var(--teal); }
    .chart-strip i:nth-child(3n) { background: var(--violet); }
    footer {
      max-width: 1160px;
      margin: 0 auto;
      padding: 24px;
      color: var(--muted);
      font-size: 13px;
      display: flex;
      justify-content: space-between;
      gap: 16px;
      flex-wrap: wrap;
    }
    @media (max-width: 920px) {
      .nav-links { display: none; }
      .hero {
        grid-template-columns: 1fr;
        padding-top: 44px;
      }
      h1 { font-size: 42px; }
      .visual-body { grid-template-columns: 1fr; min-height: auto; }
      .mock-sidebar { display: none; }
      .feature-grid, .analysis-layout { grid-template-columns: 1fr; }
      .ops-row { grid-template-columns: 1fr; }
    }
    @media (max-width: 560px) {
      .hero { padding: 30px 18px 42px; gap: 28px; }
      .nav { padding: 12px 18px; }
      h1 { font-size: 34px; }
      .hero-copy { font-size: 16px; }
      .download-button { width: 100%; }
      .segmented { width: 100%; }
      .task-grid, .kpi-row { grid-template-columns: 1fr; }
      .section-inner { padding: 42px 18px; }
      .sheet-row { grid-template-columns: 1fr; }
      .sheet-row span {
        min-height: 32px;
        border-right: 0;
        border-bottom: 1px solid #e7edf5;
      }
      .sheet-row span:last-child { border-bottom: 0; }
    }
  </style>
</head>
<body>
  <div class="page-shell">
    <header class="site-header">
      <nav class="nav" aria-label="主导航">
        <a class="brand" href="/">
          <img src="/website-assets/juguang-logo.png" alt="" onerror="this.style.display='none'" />
          <span>聚光智能办公助手</span>
        </a>
        <div class="nav-links">
          <a href="#features">能力</a>
          <a href="#analysis">数据分析</a>
          <span class="support-link">可视化发展部提供技术支持</span>
        </div>
      </nav>
    </header>

    <main>
      <section class="hero">
        <div>
          <span class="eyebrow">内部办公助手 · 企业统一托管</span>
          <h1>聚光智能办公助手</h1>
          <p class="hero-copy">为聚光同事准备的桌面 AI 工作台，把资料理解、任务推进、问题反馈和版本更新放到同一个入口。少切工具、少找文件，让日常办公更快落到结果。</p>
          <div class="hero-meta">
            <span class="meta-pill">公司账号登录</span>
            <span class="meta-pill">安装包服务器托管</span>
            <span class="meta-pill">问题反馈闭环</span>
            <span class="meta-pill">Excel 数据分析</span>
          </div>

          <div id="download" class="download-panel">
            <div class="download-row">
              <a id="downloadButton" class="download-button" href="#" aria-disabled="true">正在获取下载版本</a>
              <div class="version-text">
                <div id="versionText">检测当前系统中...</div>
                <div id="fileText">你也可以手动切换下载版本</div>
              </div>
            </div>
            <div class="segmented" role="tablist" aria-label="选择下载版本">
              <button type="button" data-platform="macos">Mac</button>
              <button type="button" data-platform="windows">Windows</button>
              <button type="button" data-platform="linux">Linux</button>
            </div>
            <p id="releaseNote" class="release-note"></p>
          </div>
        </div>

        <div class="product-visual" aria-label="产品界面预览">
          <div class="window-bar">
            <div class="traffic"><i></i><i></i><i></i></div>
            <span>内部工作台</span>
          </div>
          <div class="visual-body">
            <aside class="mock-sidebar">
              <div class="mock-logo">
                <img src="/website-assets/juguang-logo.png" alt="" onerror="this.style.display='none'" />
                <span>聚光</span>
              </div>
              <div class="mock-nav"><span></span><span></span><span></span><span></span></div>
            </aside>
            <div class="mock-main">
              <div class="assistant-card">
                <h2>今天的办公线索已经归拢</h2>
                <p>自动整理会议纪要、客户资料、Excel 表格和待办事项，同事可以继续追问、生成文档、提交反馈或跟进版本更新。</p>
                <div class="chips"><span>资料问答</span><span>Excel 分析</span><span>报告生成</span><span>问题反馈</span><span>版本更新</span></div>
              </div>
              <div class="ops-row">
                <div class="ops-card"><b>使用状态</b><span>管理员可查看日活、在线设备与版本覆盖情况。</span></div>
                <div class="ops-card"><b>安全边界</b><span>公司账号登录，员工端和后台管理分离。</span></div>
                <div class="ops-card"><b>支持闭环</b><span>反馈附图直接进服务器文件服务，后台在线预览。</span></div>
              </div>
              <div class="task-grid">
                <div class="task"><strong>合同要点提取</strong><span class="bar long"></span><span class="bar mid"></span><span class="bar short"></span></div>
                <div class="task"><strong>会议纪要生成</strong><span class="bar mid"></span><span class="bar long"></span><span class="bar short"></span></div>
                <div class="task"><strong>Excel 趋势分析</strong><span class="bar long"></span><span class="bar mid"></span><span class="bar mid"></span></div>
                <div class="task"><strong>问题反馈追踪</strong><span class="bar mid"></span><span class="bar short"></span><span class="bar long"></span></div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <section id="features" class="sections">
        <div class="section-inner">
          <p class="section-kicker">给内部团队使用，而不是做一张漂亮下载页</p>
          <h2 class="section-heading">把高频办公动作收进一个桌面工作台</h2>
          <div class="feature-grid">
            <article class="feature"><div class="icon">问</div><h3>资料理解与问答</h3><p>把日常文档、会议记录、客户资料集中处理，快速得到摘要、结论和下一步动作。</p></article>
            <article class="feature"><div class="icon">写</div><h3>报告和纪要生成</h3><p>围绕已有上下文生成可继续编辑的文档内容，让同事把时间放在判断和复核上。</p></article>
            <article class="feature"><div class="icon">数</div><h3>Excel 数据分析</h3><p>对表格做清洗、汇总、趋势解释和异常定位，帮助同事更快看懂业务数据。</p></article>
            <article class="feature"><div class="icon">管</div><h3>版本和反馈管控</h3><p>管理员统一上传安装包、设置版本号、查看反馈附图和下载次数，客户端保持一致版本节奏。</p></article>
          </div>
        </div>
      </section>

      <section id="analysis" class="analysis-band">
        <div class="section-inner analysis-layout">
          <div>
            <p class="section-kicker">Excel、CSV 和经营明细先交给助手整理</p>
            <h2 class="section-heading">数据分析更像一个可复用的办公流程</h2>
            <p class="hero-copy">同事把表格文件放进工作台后，可以让助手先做字段理解、数据清洗、指标汇总和趋势解释，再把结果整理成报告、图表或下一步排查清单。</p>
            <div class="analysis-list">
              <article class="analysis-item"><b>清</b><div><h3>表格清洗与合并</h3><p>识别空值、重复项、异常格式和多表字段差异，减少手工整理时间。</p></div></article>
              <article class="analysis-item"><b>算</b><div><h3>指标汇总与口径说明</h3><p>围绕部门关注的销量、成本、交付、回款等指标生成清晰口径和汇总结果。</p></div></article>
              <article class="analysis-item"><b>看</b><div><h3>趋势解读与异常定位</h3><p>把 Excel 中难以直接看出的波动、环比变化和异常点转成可讨论的结论。</p></div></article>
            </div>
          </div>
          <div class="analysis-preview" aria-label="数据分析预览">
            <div class="analysis-toolbar"><span>Excel 数据分析</span><span>自动汇总 · 趋势解释</span></div>
            <div class="analysis-body">
              <div class="kpi-row">
                <div class="kpi"><strong>12.8%</strong><span>本月效率提升</span></div>
                <div class="kpi"><strong>3 项</strong><span>异常指标待复核</span></div>
                <div class="kpi"><strong>8 张</strong><span>表格已归并</span></div>
              </div>
              <div class="sheet">
                <div class="sheet-row header"><span>部门</span><span>指标</span><span>进度</span><span>建议</span></div>
                <div class="sheet-row"><span>生产</span><span>交付达成</span><span><span class="cell-bar"><i style="width: 82%"></i></span></span><span>关注延迟批次</span></div>
                <div class="sheet-row"><span>销售</span><span>回款跟进</span><span><span class="cell-bar"><i style="width: 64%"></i></span></span><span>补充客户分层</span></div>
                <div class="sheet-row"><span>运营</span><span>成本波动</span><span><span class="cell-bar"><i style="width: 73%"></i></span></span><span>复核异常项</span></div>
              </div>
              <div class="chart-strip" aria-hidden="true">
                <i style="height: 36px"></i><i style="height: 58px"></i><i style="height: 44px"></i><i style="height: 76px"></i>
                <i style="height: 62px"></i><i style="height: 88px"></i><i style="height: 70px"></i><i style="height: 98px"></i>
              </div>
            </div>
          </div>
        </div>
      </section>

    </main>
    <footer><span>© 聚光智能办公助手</span><span>可视化发展部提供技术支持</span></footer>
  </div>

  <script>
    const labels = { macos: "Mac 版本", windows: "Windows 版本", linux: "Linux 版本" };
    const shortLabels = { macos: "Mac", windows: "Windows", linux: "Linux" };
    let downloadOptions = { platforms: {} };
    let selectedPlatform = "macos";

    function detectPlatform() {
      const source = [
        navigator.userAgentData && navigator.userAgentData.platform,
        navigator.platform,
        navigator.userAgent
      ].filter(Boolean).join(" ").toLowerCase();
      if (source.includes("win")) return "windows";
      if (source.includes("mac") || source.includes("darwin")) return "macos";
      if (source.includes("linux")) return "linux";
      return "macos";
    }

    function formatBytes(value) {
      if (!value) return "";
      const units = ["B", "KB", "MB", "GB"];
      let size = Number(value);
      let index = 0;
      while (size >= 1024 && index < units.length - 1) {
        size = size / 1024;
        index += 1;
      }
      return `${size.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
    }

    function firstAvailablePlatform(preferred) {
      if (downloadOptions.platforms[preferred]?.available) return preferred;
      return ["macos", "windows", "linux"].find((key) => downloadOptions.platforms[key]?.available) || preferred;
    }

    function selectPlatform(platform) {
      selectedPlatform = platform;
      const item = downloadOptions.platforms[platform] || {};
      document.querySelectorAll("[data-platform]").forEach((button) => {
        const key = button.dataset.platform;
        button.classList.toggle("active", key === platform);
        button.classList.toggle("unavailable", downloadOptions.platforms[key] && !downloadOptions.platforms[key].available);
      });

      const button = document.getElementById("downloadButton");
      const versionText = document.getElementById("versionText");
      const fileText = document.getElementById("fileText");
      const releaseNote = document.getElementById("releaseNote");
      const version = item.version || downloadOptions.latest_version || "";
      const size = formatBytes(item.size_bytes);

      if (item.available && item.download_url) {
        button.href = item.download_url;
        button.removeAttribute("aria-disabled");
        button.textContent = `下载${labels[platform]}`;
        versionText.textContent = version ? `最新版 v${String(version).replace(/^v/i, "")}` : "已配置下载包";
        fileText.textContent = [item.filename, size].filter(Boolean).join(" · ");
      } else {
        button.href = "#download";
        button.setAttribute("aria-disabled", "true");
        button.textContent = `${labels[platform]}暂未配置`;
        versionText.textContent = "当前版本暂未开放下载";
        fileText.textContent = "请在后台上传安装包后再访问官网";
      }
      releaseNote.textContent = downloadOptions.release_notes ? `更新说明：${downloadOptions.release_notes}` : "";
    }

    async function loadDownloadOptions() {
      const preferred = detectPlatform();
      selectedPlatform = preferred;
      try {
        const response = await fetch("/download-options", { cache: "no-store" });
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        downloadOptions = await response.json();
      } catch (error) {
        downloadOptions = { platforms: {} };
      }
      selectPlatform(firstAvailablePlatform(preferred));
    }

    document.querySelectorAll("[data-platform]").forEach((button) => {
      button.addEventListener("click", () => selectPlatform(button.dataset.platform));
    });
    loadDownloadOptions();
  </script>
</body>
</html>"""
