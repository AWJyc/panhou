"use client";

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  ReactNode,
} from "react";

export interface AuthUser {
  email: string;
  email_verified: boolean;
}

interface AuthState {
  user: AuthUser | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string) => Promise<void>;
  logout: () => Promise<void>;
  refresh: () => Promise<void>;
  verifyEmail: (code: string) => Promise<void>;
  resendVerifyCode: () => Promise<void>;
  forgotPassword: (email: string) => Promise<void>;
  resetPassword: (
    email: string,
    code: string,
    newPassword: string
  ) => Promise<void>;
}

const Ctx = createContext<AuthState>({
  user: null,
  loading: true,
  login: async () => {},
  register: async () => {},
  logout: async () => {},
  refresh: async () => {},
  verifyEmail: async () => {},
  resendVerifyCode: async () => {},
  forgotPassword: async () => {},
  resetPassword: async () => {},
});

async function postJSON(url: string, body?: unknown): Promise<unknown> {
  const res = await fetch(url, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    body: body ? JSON.stringify(body) : undefined,
    credentials: "include",
  });
  if (!res.ok) {
    let detail = await res.text();
    try {
      detail = JSON.parse(detail).detail ?? detail;
    } catch {
      /* keep */
    }
    throw new Error(detail || `${res.status}`);
  }
  return res.json().catch(() => ({}));
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null);
  const [loading, setLoading] = useState(true);

  const refresh = useCallback(async () => {
    try {
      const res = await fetch("/api/auth/me", { credentials: "include" });
      if (res.ok) {
        const u = (await res.json()) as AuthUser;
        setUser(u);
      } else {
        setUser(null);
      }
    } catch {
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  const login = useCallback(async (email: string, password: string) => {
    const u = (await postJSON("/api/auth/login", { email, password })) as AuthUser;
    setUser(u);
  }, []);

  const register = useCallback(async (email: string, password: string) => {
    const u = (await postJSON("/api/auth/register", {
      email,
      password,
    })) as AuthUser;
    setUser(u);
  }, []);

  const logout = useCallback(async () => {
    await postJSON("/api/auth/logout");
    setUser(null);
  }, []);

  const verifyEmail = useCallback(async (code: string) => {
    const u = (await postJSON("/api/auth/verify-email", { code })) as AuthUser;
    setUser(u);
  }, []);

  const resendVerifyCode = useCallback(async () => {
    await postJSON("/api/auth/resend-verify-code");
  }, []);

  const forgotPassword = useCallback(async (email: string) => {
    await postJSON("/api/auth/forgot-password", { email });
  }, []);

  const resetPassword = useCallback(
    async (email: string, code: string, newPassword: string) => {
      await postJSON("/api/auth/reset-password", {
        email,
        code,
        new_password: newPassword,
      });
    },
    []
  );

  return (
    <Ctx.Provider
      value={{
        user,
        loading,
        login,
        register,
        logout,
        refresh,
        verifyEmail,
        resendVerifyCode,
        forgotPassword,
        resetPassword,
      }}
    >
      {children}
    </Ctx.Provider>
  );
}

export function useAuth() {
  return useContext(Ctx);
}
