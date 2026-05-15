"use client";

import {
  createContext,
  useContext,
  useEffect,
  useState,
  useCallback,
  ReactNode,
} from "react";

interface PinCtxValue {
  pinned: string | null;
  setPinned: (s: string | null) => void;
}

const PinCtx = createContext<PinCtxValue>({
  pinned: null,
  setPinned: () => {},
});

export function PinProvider({ children }: { children: ReactNode }) {
  const [pinned, setPinnedState] = useState<string | null>(null);

  const setPinned = useCallback((s: string | null) => {
    setPinnedState(s);
    if (s) {
      // 滚到对应的涨停股行
      requestAnimationFrame(() => {
        const el = document.getElementById(`stock-${s}`);
        if (el)
          el.scrollIntoView({ behavior: "smooth", block: "center" });
      });
    }
  }, []);

  // Esc 取消
  useEffect(() => {
    if (!pinned) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setPinnedState(null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [pinned]);

  return (
    <PinCtx.Provider value={{ pinned, setPinned }}>{children}</PinCtx.Provider>
  );
}

export function usePin() {
  return useContext(PinCtx);
}
