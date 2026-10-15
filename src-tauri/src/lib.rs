// Learn more about Tauri commands at https://tauri.app/develop/calling-rust/

use enigo::{Direction, Enigo, Key, Keyboard, Settings};
use std::process::Command;
use std::time::Duration;
use tauri::Manager;
use tauri_plugin_sql::{Migration, MigrationKind};

fn open_in_brave(url: &str) -> bool {
    let mut candidates = vec![std::path::PathBuf::from("brave.exe")];

    for variable in ["LOCALAPPDATA", "PROGRAMFILES", "PROGRAMFILES(X86)"] {
        if let Some(directory) = std::env::var_os(variable) {
            candidates.push(
                std::path::PathBuf::from(directory)
                    .join("BraveSoftware")
                    .join("Brave-Browser")
                    .join("Application")
                    .join("brave.exe"),
            );
        }
    }

    candidates
        .into_iter()
        .any(|executable| Command::new(executable).arg(url).spawn().is_ok())
}

#[tauri::command]
fn greet(name: &str) -> String {
    format!("Hello, {}! You've been greeted from Rust!", name)
}

#[tauri::command]
async fn open_url(url: String) -> Result<(), String> {
    if !open_in_brave(&url) {
        // Explorer delegates URL handling to the user's Windows default browser.
        Command::new("explorer.exe")
            .arg(&url)
            .spawn()
            .map_err(|e| e.to_string())?;
    }

    Ok(())
}

#[tauri::command]
async fn open_app(app_name: String) -> Result<(), String> {
    let mut enigo = Enigo::new(&Settings::default()).map_err(|e| e.to_string())?;

    // Open Windows Search
    enigo
        .key(Key::Meta, Direction::Click)
        .map_err(|e| e.to_string())?;

    tokio::time::sleep(Duration::from_millis(500)).await;

    // Type app name
    enigo.text(&app_name).map_err(|e| e.to_string())?;

    tokio::time::sleep(Duration::from_millis(300)).await;

    // Press Enter
    enigo
        .key(Key::Return, Direction::Click)
        .map_err(|e| e.to_string())?;

    Ok(())
}

#[tauri::command]
async fn capture_screen_native() -> Result<String, String> {
    use screenshots::Screen;
    use base64::{Engine as _, engine::general_purpose};
    use std::io::Cursor;

    // Capture the primary screen (first screen)
    let screens = Screen::all().map_err(|e| e.to_string())?;
    let screen = screens.first().ok_or_else(|| "No screens found".to_string())?;
    let image = screen.capture().map_err(|e| e.to_string())?;

    // Convert raw pixels to dynamic image
    let img_buffer = image::ImageBuffer::<image::Rgba<u8>, Vec<u8>>::from_raw(
        image.width(),
        image.height(),
        image.into_raw(),
    ).ok_or_else(|| "Failed to create image buffer".to_string())?;

    let dynamic_img = image::DynamicImage::ImageRgba8(img_buffer);
    
    // Resize for speed and payload reduction
    let resized = dynamic_img.resize(1280, 720, image::imageops::FilterType::Triangle);

    let mut jpeg_bytes = Vec::new();
    let mut cursor = Cursor::new(&mut jpeg_bytes);
    resized
        .write_to(&mut cursor, image::ImageFormat::Jpeg)
        .map_err(|e| e.to_string())?;

    let base64_str = general_purpose::STANDARD.encode(&jpeg_bytes);
    Ok(format!("data:image/jpeg;base64,{}", base64_str))
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .setup(|app| {
            let window = app.get_webview_window("main").unwrap();

            window.set_always_on_top(true).unwrap();

            Ok(())
        })
        .plugin(
            tauri_plugin_sql::Builder::default()
                .add_migrations(
                    "sqlite:aura.db",
                    vec![Migration {
                        version: 1,
                        description: "create_memory_table",
                        sql: "
                        CREATE TABLE IF NOT EXISTS memory(
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            role TEXT NOT NULL,
                            content TEXT NOT NULL,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                        );
                        ",
                        kind: MigrationKind::Up,
                    }, Migration {
                        version: 2,
                        description: "create_user_facts_table",
                        sql: "
                        CREATE TABLE IF NOT EXISTS user_facts(
                            id INTEGER PRIMARY KEY AUTOINCREMENT,
                            category TEXT NOT NULL,
                            fact TEXT NOT NULL,
                            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                            updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                        );
                        CREATE INDEX IF NOT EXISTS idx_user_facts_category ON user_facts(category);
                        ",
                        kind: MigrationKind::Up,
                    }],
                )
                .build(),
        )
        .plugin(tauri_plugin_opener::init())
        .invoke_handler(tauri::generate_handler![
            greet,
            open_app,
            open_url,
            capture_screen_native
        ])
        .run(tauri::generate_context!())
        .expect("error while running tauri application");
}

