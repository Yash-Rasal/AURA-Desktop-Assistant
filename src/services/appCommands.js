export async function handleOpenUrl(reply, invoke, speak, onEnd) {
    await invoke("open_url", {
      url: reply.url,
    });
  
    speak("Opening website.", onEnd);
  }
  
  export async function handleOpenApp(reply, invoke, speak, onEnd) {
    await invoke("open_app", {
      appName: reply.app,
    });
  
    speak(`Opening ${reply.app}.`, onEnd);
  }