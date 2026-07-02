//! Native application menu — File, Edit, View, Window, Help.

use tauri::{
    menu::{Menu, MenuItem, PredefinedMenuItem, Submenu},
    AppHandle, Emitter, Manager,
};

pub fn create_menu(app: &AppHandle) -> tauri::Result<Menu<tauri::Wry>> {
    // File menu
    let new_chat = MenuItem::with_id(app, "menu_new_chat", "新建对话", true, Some("CmdOrCtrl+N"))?;
    let settings = MenuItem::with_id(app, "menu_settings", "设置", true, Some("CmdOrCtrl+,"))?;
    let file_menu = Submenu::with_items(
        app,
        "文件",
        true,
        &[
            &new_chat,
            &PredefinedMenuItem::separator(app)?,
            &settings,
            &PredefinedMenuItem::separator(app)?,
            &PredefinedMenuItem::quit(app, Some("退出"))?,
        ],
    )?;

    // Edit menu
    let edit_menu = Submenu::with_items(
        app,
        "编辑",
        true,
        &[
            &PredefinedMenuItem::undo(app, Some("撤销"))?,
            &PredefinedMenuItem::redo(app, Some("重做"))?,
            &PredefinedMenuItem::separator(app)?,
            &PredefinedMenuItem::cut(app, Some("剪切"))?,
            &PredefinedMenuItem::copy(app, Some("复制"))?,
            &PredefinedMenuItem::paste(app, Some("粘贴"))?,
            &PredefinedMenuItem::select_all(app, Some("全选"))?,
        ],
    )?;

    // View menu
    let toggle_sidebar = MenuItem::with_id(
        app,
        "menu_toggle_sidebar",
        "显示/隐藏侧边栏",
        true,
        Some("CmdOrCtrl+Shift+S"),
    )?;
    let reload = MenuItem::with_id(app, "menu_reload", "重新加载", true, Some("CmdOrCtrl+R"))?;
    let dev_tools = MenuItem::with_id(
        app,
        "menu_dev_tools",
        "开发者工具",
        true,
        Some("CmdOrCtrl+Shift+I"),
    )?;
    let view_menu = Submenu::with_items(
        app,
        "视图",
        true,
        &[
            &toggle_sidebar,
            &PredefinedMenuItem::separator(app)?,
            &reload,
            &dev_tools,
        ],
    )?;

    // Window menu
    let minimize = PredefinedMenuItem::minimize(app, Some("最小化"))?;
    let zoom = PredefinedMenuItem::maximize(app, Some("最大化"))?;
    let fullscreen = PredefinedMenuItem::fullscreen(app, Some("全屏"))?;
    let window_menu = Submenu::with_items(
        app,
        "窗口",
        true,
        &[
            &minimize,
            &zoom,
            &PredefinedMenuItem::separator(app)?,
            &fullscreen,
        ],
    )?;

    // Help menu
    let check_updates =
        MenuItem::with_id(app, "menu_check_updates", "检查更新…", true, None::<&str>)?;
    let about = PredefinedMenuItem::about(app, Some("关于聚光办公助理"), None)?;
    let help_menu = Submenu::with_items(
        app,
        "帮助",
        true,
        &[&check_updates, &PredefinedMenuItem::separator(app)?, &about],
    )?;

    let menu = Menu::with_items(
        app,
        &[&file_menu, &edit_menu, &view_menu, &window_menu, &help_menu],
    )?;

    Ok(menu)
}

/// Handle menu events.
pub fn handle_menu_event(app: &AppHandle, event_id: &str) {
    let Some(window) = app.get_webview_window("main") else {
        return;
    };

    match event_id {
        "menu_new_chat" => {
            let _ = window.emit("navigate", "/c/new");
        }
        "menu_settings" => {
            let _ = window.emit("navigate", "/settings");
        }
        "menu_toggle_sidebar" => {
            let _ = window.emit("toggle-sidebar", ());
        }
        "menu_reload" => {
            let _ = window.eval("window.location.reload()");
        }
        "menu_dev_tools" => {
            if window.is_devtools_open() {
                window.close_devtools();
            } else {
                window.open_devtools();
            }
        }
        "menu_check_updates" => {
            let _ = window.emit("check-for-updates", ());
        }
        _ => {}
    }
}
