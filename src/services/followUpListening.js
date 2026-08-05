export function followUpListening(
    recognitionRef,
    followUpTimerRef,
    listeningModeRef,
    setState
  ) {
    const recognition = recognitionRef.current;

    if (!recognition) {
      listeningModeRef.current = false;
      setState("idle");
      return false;
    }

    listeningModeRef.current = true;
  
    setState("listening");
  
    try {
      recognition.start();
    } catch {
      listeningModeRef.current = false;
      setState("idle");
      return false;
    }
  
    clearTimeout(followUpTimerRef.current);
  
    followUpTimerRef.current = setTimeout(() => {
      listeningModeRef.current = false;

      try {
        recognition.stop();
      } catch {
        // Recognition may already have stopped.
      }

      setState("idle");
    }, 10000);

    return true;
  }
