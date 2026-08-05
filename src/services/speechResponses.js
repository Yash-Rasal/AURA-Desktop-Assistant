export function clearConversation(
    setTranscript,
    callback
  ) {
    setTranscript("");
  
    if (callback) {
      callback();
    }
  }
  
  export function resetAfterError(setState, setTranscript) {
    setState("idle");
    setTranscript("");
  }