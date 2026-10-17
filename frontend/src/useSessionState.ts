import { useEffect, useState } from "react";

// Like useState, but the value is also kept in sessionStorage.
//
// Why: switching tabs unmounts a component, and its useState values are thrown away
// (that's why the form and result used to disappear). sessionStorage survives tab
// switches AND page reloads, but is private to this browser tab and gone when it closes.
// It is cleared on logout so the next person on this browser sees nothing.

const PREFIX = "fakehire:";

export function useSessionState<T>(key: string, initial: T) {
  const [value, setValue] = useState<T>(() => {
    try {
      const saved = sessionStorage.getItem(PREFIX + key);
      return saved ? (JSON.parse(saved) as T) : initial;
    } catch {
      return initial;
    }
  });

  useEffect(() => {
    try {
      sessionStorage.setItem(PREFIX + key, JSON.stringify(value));
    } catch {
      /* storage full or blocked: keep working in memory */
    }
  }, [key, value]);

  return [value, setValue] as const;
}

export function clearSessionState() {
  try {
    Object.keys(sessionStorage)
      .filter((k) => k.startsWith(PREFIX))
      .forEach((k) => sessionStorage.removeItem(k));
  } catch {
    /* nothing to clear */
  }
}
