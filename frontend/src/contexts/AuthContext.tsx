"use client";

import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  type User,
  type RegisterPayload,
  getMe,
  login as authLogin,
  register as authRegister,
  setToken,
  clearToken,
  getToken,
} from "@/lib/auth";
import { getStoredUTM, clearStoredUTM } from "@/hooks/useUTM";
import { useToast } from "@/components/ui/feedback";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, name: string, password: string) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<void>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const { info } = useToast();

  useEffect(() => {
    const token = getToken();
    if (!token) {
      setLoading(false);
      return;
    }
    getMe()
      .then(setUser)
      .catch(() => clearToken())
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    function handleSessionExpired() {
      setUser(null);
      info("Sessão expirada", "Faça login novamente para continuar.");
      if (!pathname.startsWith("/auth")) {
        router.replace("/auth/login");
      }
    }

    window.addEventListener("clipia:session-expired", handleSessionExpired);
    return () => window.removeEventListener("clipia:session-expired", handleSessionExpired);
  }, [info, pathname, router]);

  useEffect(() => {
    const token = getToken();
    if (!token) return;

    const interval = window.setInterval(() => {
      getMe()
        .then(setUser)
        .catch(() => {
          clearToken();
          setUser(null);
        });
    }, 5 * 60 * 1000);

    return () => window.clearInterval(interval);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await authLogin(email, password);
    setToken(res.access_token);
    const me = await getMe();
    setUser(me);
  }, []);

  const register = useCallback(async (email: string, name: string, password: string) => {
    const utm = getStoredUTM();
    const res = await authRegister(email, name, password, utm);
    clearStoredUTM();
    setToken(res.access_token);
    const me = await getMe();
    setUser(me);
  }, []);

  const logout = useCallback(() => {
    clearToken();
    setUser(null);
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      const me = await getMe();
      setUser(me);
    } catch { /* silent */ }
  }, []);

  return (
    <AuthContext value={{ user, loading, login, register, logout, refreshUser }}>
      {children}
    </AuthContext>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
