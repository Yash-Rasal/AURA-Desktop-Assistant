export function isSleepCommand(text) {
    const lower = text.toLowerCase();
  
    return (
      lower.includes("stop listening") ||
      lower.includes("go to sleep") ||
      lower.includes("sleep") ||
      lower.includes("stop aura")
    );
  }
  
  export function isScreenCommand(text) {
    const lower = text.toLowerCase();
  
    return (
      lower.includes("check my screen") ||
      lower.includes("what is on my screen")
    );
  }