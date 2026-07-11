"use client";

import { strings } from '@/lib/strings';
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import Logo from "@/components/brand/Logo";
import { forgotPassword } from "@/lib/auth";

export default function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(false);
  const router = useRouter();

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const normalizedEmail = email.trim().toLowerCase();
    setError("");
    setLoading(true);
    try {
      await forgotPassword(normalizedEmail);
      router.push(`/auth/reset-password?email=${encodeURIComponent(normalizedEmail)}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Erro ao enviar codigo");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center px-4">
      <div className="card w-full max-w-md p-8">
        <div className="flex justify-center mb-4">
          <Logo size="lg" />
        </div>
        <h1 className="font-display text-2xl font-extrabold text-center mb-2 text-white tracking-tight">
          {strings.auth.login.forgotPassword}
        </h1>
        <p className="text-slate-400 text-center text-sm mb-8">
          Enviaremos um código de 6 dígitos para redefinir sua senha
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <div className="bg-red-500/10 border border-red-500/20 rounded-lg p-3 text-red-400 text-sm">
              {error}
            </div>
          )}

          <div>
            <label htmlFor="email" className="block text-sm text-slate-300 mb-1">
              {strings.auth.login.email}
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              autoFocus
              className="w-full px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-white placeholder-slate-500 focus:outline-none focus:border-coral/50"
              placeholder="seu@email.com"
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="btn-primary w-full py-2.5 rounded-lg font-semibold disabled:opacity-50"
          >
            {loading ? "Enviando..." : "Enviar codigo"}
          </button>
        </form>

        <p className="text-center text-sm text-slate-400 mt-6">
          <Link href="/auth/login" className="text-coral hover:text-coral">
            Voltar para o login
          </Link>
        </p>
      </div>
    </div>
  );
}
