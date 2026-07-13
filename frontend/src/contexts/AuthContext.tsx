"use client";

import { createContext, useContext, useEffect, useState, useCallback, type ReactNode } from "react";
import { usePathname, useRouter } from "next/navigation";
import {
  type User,
  type RegisterPayload,
  getMe,
  login as authLogin,
  register as authRegister,
  logout as authLogout,
  setToken,
  setCsrfToken,
  clearToken,
  hasSessionCandidate,
  NetworkError,
} from "@/lib/auth";
import type { SelectedPackage } from "@/lib/package-intent";
import { getStoredUTM, clearStoredUTM } from "@/hooks/useUTM";
import { useToast } from "@/components/ui/feedback";

interface AuthContextType {
  user: User | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, name: string, password: string, turnstileToken?: string, consent?: boolean, selectedPackage?: SelectedPackage) => Promise<void>;
  logout: () => void;
  refreshUser: () => Promise<User | null>;
}

const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const { info } = useToast();

  useEffect(() => {
    if (!hasSessionCandidate()) {
      setLoading(false);
      return;
    }
    getMe()
      .then(setUser)
      .catch((err: unknown) => {
        // Erro transitório (502/timeout/rede) NÃO derruba a sessão: mantemos o token,
        // deixamos user=null e liberamos o loading para o usuário entrar no dashboard.
        // O polling de 5 min vai recuperar o usuário assim que o backend voltar.
        // Só 401 (sessão expirada de verdade) apaga o token.
        if (!(err instanceof NetworkError)) clearToken();
      })
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
    if (!hasSessionCandidate()) return;

    const interval = window.setInterval(() => {
      getMe()
        .then(setUser)
        .catch((err: unknown) => {
          // Em erro transitório mantemos o último usuário conhecido e o token.
          // Só agir (apagar token + user) se for sessão expirada real (401).
          if (!(err instanceof NetworkError)) {
            clearToken();
            setUser(null);
          }
        });
    }, 5 * 60 * 1000);

    return () => window.clearInterval(interval);
  }, []);

  const login = useCallback(async (email: string, password: string) => {
    const res = await authLogin(email, password);
    setToken(res.access_token);
    setCsrfToken(res.csrf_token);
    // Erro transitório em /auth/me logo após o login não deve impedir o redirect
    // para o dashboard: o token já foi gravado e o efeito de carregamento inicial
    // vai revalidar. Só repassamos 401 (sessão expirada de verdade).
    try {
      const me = await getMe();
      setUser(me);
    } catch (err) {
      if (err instanceof NetworkError) {
        setUser(null);
        return;
      }
      throw err;
    }
  }, []);

  const register = useCallback(async (email: string, name: string, password: string, turnstileToken?: string, consent?: boolean, selectedPackage?: SelectedPackage) => {
    const utm = getStoredUTM();
    const res = await authRegister(email, name, password, {
      ...utm,
      turnstile_token: turnstileToken,
      consent,
      selected_package: selectedPackage,
    });
    // Intenção de nicho (/criar/[nicho] → utm_campaign=nicho-{slug}): sobrevive ao
    // cadastro para o dashboard aplicar template/estilo/tema recomendados UMA vez
    // após o OTP — quem chega buscando "drama histórico" não cai num form genérico.
    if (utm.utm_campaign?.startsWith("nicho-")) {
      localStorage.setItem("clipia_signup_intent", utm.utm_campaign.slice("nicho-".length));
    }
    clearStoredUTM();
    setToken(res.access_token);
    setCsrfToken(res.csrf_token);
    try {
      const me = await getMe();
      setUser(me);
    } catch (err) {
      if (err instanceof NetworkError) {
        setUser(null);
        return;
      }
      throw err;
    }
  }, []);

  const logout = useCallback(() => {
    void authLogout().catch(() => undefined);
    clearToken();
    setUser(null);
  }, []);

  const refreshUser = useCallback(async () => {
    try {
      const me = await getMe();
      setUser(me);
      return me;
    } catch {
      return null;
    }
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
