"use client";

import { Eye, EyeOff } from 'lucide-react';
import { strings } from '@/lib/strings';
import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { useAuth } from "@/contexts/AuthContext";
import Logo from "@/components/brand/Logo";
import { FilmstripBackground } from "@/components/ui/FilmstripBackground";
import { trackEvent, trackGA } from "@/components/TrackingScripts";
import { TurnstileWidget } from "@/components/auth/TurnstileWidget";

const PWD_CRITERIA = [
  (p: string) => p.length >= 8,
  (p: string) => /[A-Z]/.test(p),
  (p: string) => /\d/.test(p),
  (p: string) => p.length >= 12 || /[^A-Za-z0-9]/.test(p),
];
const STRENGTH = [
  { label: "", color: "" },
  { label: "Fraca", color: "#ef4444" },
  { label: "Média", color: "#f59e0b" },
  { label: "Boa", color: "#3b82f6" },
  { label: "Forte", color: "#22c55e" },
];

function PasswordStrength({ password }: { password: string }) {
  if (!password) {
    return <p className="text-xs text-slate-400 mt-1.5">Minimo 8 caracteres, 1 maiuscula e 1 numero.</p>;
  }
  const score = PWD_CRITERIA.filter((test) => test(password)).length;
  const { label, color } = STRENGTH[score];
  return (
    <div className="mt-2">
      <div className="flex gap-1" aria-hidden="true">
        {[0, 1, 2, 3].map((i) => (
          <span
            key={i}
            className="h-1 flex-1 rounded-full transition-colors duration-300"
            style={{ background: i < score ? color : "rgba(255,255,255,0.1)" }}
          />
        ))}
      </div>
      <p className="text-xs mt-1.5 font-medium" style={{ color: color || undefined }}>
        Força da senha: {label}
      </p>
    </div>
  );
}

export default function RegisterPage() {
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [showPwd, setShowPwd] = useState(false);
  const [captchaToken, setCaptchaToken] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError("");
    if (password.length < 8) {
      setError("Senha deve ter no minimo 8 caracteres");
      return;
    }
    if (!/[A-Z]/.test(password)) {
      setError("Senha deve conter pelo menos 1 letra maiuscula");
      return;
    }
    if (!/\d/.test(password)) {
      setError("Senha deve conter pelo menos 1 numero");
      return;
    }
    setLoading(true);
    try {
      await register(email, name, password, captchaToken);
      trackEvent("CompleteRegistration");
      trackGA("sign_up", { method: "email" });
      router.push(`/auth/verify?email=${encodeURIComponent(email)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao criar conta");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4 relative overflow-hidden bg-[#08090f]">
      <FilmstripBackground speed={35} opacity={0.05} />
      <div className="absolute top-1/3 right-1/4 w-72 h-72 sm:w-[500px] sm:h-[500px] bg-coral/20 blur-[150px] rounded-full pointer-events-none"></div>

      <div className="card w-full max-w-md p-8 relative z-10 bg-[#11141d]/80 backdrop-blur-xl border border-white/10 shadow-2xl">
        <div className="flex justify-center mb-6">
          <Logo size="lg" />
        </div>
        <h1 className="text-xl sm:text-2xl font-bold text-center mb-2 text-white tracking-tight">
          {strings.auth.register.title}
        </h1>
        <p className="text-slate-400 text-center text-sm mb-8">
          {strings.auth.register.subtitle}
        </p>

        <form onSubmit={handleSubmit} className="space-y-5">
          {error && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-xl p-4 text-red-400 text-sm font-medium">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="name" className="block text-sm font-medium text-slate-300 mb-1.5">
              {strings.auth.register.name}
            </label>
            <input
              id="name"
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              autoFocus
              className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-500 focus:outline-none focus:border-coral/50 focus:bg-white/10 transition-colors"
              placeholder="Seu nome"
            />
          </div>

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
              className="w-full px-4 py-3 rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-500 focus:outline-none focus:border-coral/50 focus:bg-white/10 transition-colors"
              placeholder="seu@email.com"
            />
          </div>

          <div>
            <label htmlFor="password" className="block text-sm font-medium text-slate-300 mb-1.5">
              {strings.auth.login.password}
            </label>
            <div className="relative">
              <input
                id="password"
                type={showPwd ? "text" : "password"}
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                required
                minLength={8}
                className="w-full px-4 py-3 pr-12 rounded-xl bg-white/5 border border-white/10 text-white placeholder-slate-500 focus:outline-none focus:border-coral/50 focus:bg-white/10 transition-colors"
                placeholder="Minimo 8 caracteres"
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
            <PasswordStrength password={password} />
          </div>

          <TurnstileWidget onToken={setCaptchaToken} />

          <button
            type="submit"
            disabled={loading}
            className="w-full py-3.5 rounded-xl bg-gradient-to-r from-coral to-azure text-white font-bold disabled:opacity-50 hover:opacity-90 transition shadow-lg shadow-coral/25 mt-2"
          >
            {loading ? strings.auth.register.loading : strings.auth.register.submit}
          </button>
        </form>

        <p className="text-center text-sm text-slate-400 mt-8">
          {strings.auth.register.hasAccount}{" "}
          <Link href="/auth/login" className="text-white font-semibold hover:text-coral transition border-b border-white/20 pb-0.5">
            {strings.auth.login.submit}
          </Link>
        </p>
      </div>
    </div>
  );
}
