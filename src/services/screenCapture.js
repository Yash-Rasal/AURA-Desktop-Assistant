import { invoke } from "@tauri-apps/api/core";

/**
 * Captures the primary screen using native OS APIs via Tauri.
 * Returns a Promise that resolves to a JPEG base64 Data URL.
 */
export async function captureScreen() {
  try {
    const dataUrl = await invoke("capture_screen_native");
    return dataUrl;
  } catch (error) {
    console.error("Native screen capture failed:", error);
    throw error;
  }
}
