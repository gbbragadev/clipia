"use client";

import { Eye, EyeOff } from 'lucide-react';
import { strings } from '@/lib/strings';
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import Logo from "@/components/brand/Logo";
import { FilmstripBackground } from "@/components/ui/FilmstripBackground";

export default function LoginPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { login } = useAuth();
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    setLoading(true);
    try {
      await login(email, password);
      router.push("/dashboard");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao entrar");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 relative overflow-hidden bg-[#08090f]">
      <FilmstripBackground speed={30} opacity={0.05} />
      <div className="absolute top-1/4 left-1/4 w-64 h-64 sm:w-96 sm:h-96 bg-coral/20 blur-[120px] rounded-full pointer-events-none"></div>
      <div className="absolute bottom-1/4 right-1/4 w-64 h-64 sm:w-96 sm:h-96 bg-azure/10 blur-[120px] rounded-full pointer-events-none"></div>

      <div className="card w-full max-w-md p-8 relative z-10 bg-[#11141d]/80 backdrop-blur-xl border border-white/10 shadow-2xl">
        <div className="flex justify-center mb-6">
          <Logo size="lg" />
        </div>
        <h1 className="font-display text-2xl sm:text-3xl font-extrabold text-center mb-2 text-white tracking-tight">
          Bem-vindo de volta
        </h1>
        <p className="text-slate-400 text-center text-sm mb-8">
          Pronto para criar vídeos incríveis?
        </p>

        <form onSubmit={handleSubmit} className="space-y-5">
          {error && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-red-400 text-sm font-medium">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="email" className="block text-sm font-medium text-slate-300 mb-1.5">
              {strings.auth.login.email}
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
              className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-500 focus:outline-none focus:border-coral/50 focus:bg-white/10 transition-colors"
              placeholder="seu@email.com"
            />
          </div>

          <div>
            <div className="flex items-center justify-between mb-1.5">
              <label htmlFor="password" className="block text-sm font-medium text-slate-300">
                {strings.auth.login.password}
              </label>
              <Link href="/auth/forgot-password" className="text-xs text-coral hover:text-coral font-medium">
                {strings.auth.login.forgotPassword}
              </Link>
            </div>
            <div className="relative">
              <input
                id="password"
                type={showPwd ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                className="w-full px-4 py-3 pr-12 rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-500 focus:outline-none focus:border-coral/50 focus:bg-white/10 transition-colors"
                placeholder="••••••••"
              />
              <button
                type="button"
                onClick={() => setShowPwd((v) => !v)}
                aria-label={showPwd ? "Ocultar senha" : "Mostrar senha"}
                className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-white transition"
              >
                {showPwd ? <EyeOff className="w-5 h-5" /> : <Eye className="w-5 h-5" />}
              </button>
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3.5 rounded-xl bg-gradient-to-r from-coral to-azure text-white font-bold disabled:opacity-50 hover:opacity-90 transition shadow-lg shadow-coral/25 mt-2"
          >
            {loading ? strings.auth.login.loading : strings.auth.login.submit}
          </button>
        </form>

        <p className="text-center text-sm text-slate-400 mt-8">
          {strings.auth.login.noAccount}{" "}
          <Link href="/auth/register" className="text-white font-semibold hover:text-coral transition border-b border-white/20 pb-0.5">
            {strings.auth.login.register}
          </Link>
        </p>
      </div>
    </div>
  );
}
