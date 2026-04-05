"use client";

import { strings } from '@/lib/strings';
import { useState } from "react";
import { useRouter } from "next/navigation";
import { changePassword, clearToken, deleteAccount, exportAccountData, updateProfile } from "@/lib/auth";
import { useAuth } from "@/contexts/AuthContext";
import { useToast } from "@/components/ui/feedback";

export default function SettingsPage() {
  const router = useRouter();
  const { user, refreshUser, logout } = useAuth();
  const { success, error, info } = useToast();
  const [name, setName] = useState(user?.name ?? "");
  const [profileSaving, setProfileSaving] = useState(false);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [passwordSaving, setPasswordSaving] = useState(false);
  const [deletePassword, setDeletePassword] = useState("");
  const [deleteLoading, setDeleteLoading] = useState(false);

  async function handleProfileSubmit(e: React.FormEvent) {
    e.preventDefault();
    setProfileSaving(true);
    try {
      await updateProfile(name);
      await refreshUser();
      success("Perfil atualizado", "Seu nome foi salvo com sucesso.");
    } catch (err) {
      error("Falha ao atualizar perfil", err instanceof Error ? err.message : "Tente novamente.")
    } finally {
      setProfileSaving(false);
    }
  }

  async function handlePasswordSubmit(e: React.FormEvent) {
    e.preventDefault();
    setPasswordSaving(true);
    try {
      await changePassword(currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      success("Senha alterada", "Use a nova senha no próximo login.");
    } catch (err) {
      error("Falha ao alterar senha", err instanceof Error ? err.message : "Tente novamente.")
    } finally {
      setPasswordSaving(false);
    }
  }

  async function handleExportData() {
    try {
      const payload = await exportAccountData();
      const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = "clipia-export.json";
      link.click();
      URL.revokeObjectURL(url);
      info("Exportação pronta", "O download do seu arquivo foi iniciado.");
    } catch (err) {
      error("Falha ao exportar dados", err instanceof Error ? err.message : "Tente novamente.")
    }
  }

  async function handleDeleteAccount(e: React.FormEvent) {
    e.preventDefault();
    setDeleteLoading(true);
    try {
      await deleteAccount(deletePassword);
      clearToken();
      logout();
      success("Conta excluída", "Seus dados pessoais foram anonimizados.");
      router.replace("/auth/login");
    } catch (err) {
      error("Falha ao excluir conta", err instanceof Error ? err.message : "Tente novamente.")
    } finally {
      setDeleteLoading(false);
    }
  }

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 space-y-8">
      <section className="card p-6">
        <h1 className="text-2xl font-semibold mb-2">Configurações da conta</h1>
        <p className="text-sm text-slate-400 mb-6">
          Atualize seus dados, troque a senha e gerencie sua conta.
        </p>

        <form onSubmit={handleProfileSubmit} className="space-y-4">
          <div>
            <label htmlFor="name" className="block text-sm text-slate-300 mb-1">
              {strings.auth.register.name}
            </label>
            <input
              id="name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
              className="w-full px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-white focus:outline-none focus:border-purple-500/50"
            />
          </div>
          <div>
            <label htmlFor="email" className="block text-sm text-slate-300 mb-1">
              {strings.auth.login.email}
            </label>
            <input
              id="email"
              value={user?.email ?? ""}
              disabled
              className="w-full px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-slate-400"
            />
          </div>
          <button type="submit" disabled={profileSaving} className="btn-primary px-4 py-2 rounded-lg">
            {profileSaving ? strings.editor.saving : "Salvar perfil"}
          </button>
        </form>
      </section>

      <section className="card p-6">
        <h2 className="text-xl font-semibold mb-4">Alterar senha</h2>
        <form onSubmit={handlePasswordSubmit} className="space-y-4">
          <input
            type="password"
            value={currentPassword}
            onChange={(e) => setCurrentPassword(e.target.value)}
            placeholder="Senha atual"
            required
            className="w-full px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-white focus:outline-none focus:border-purple-500/50"
          />
          <input
            type="password"
            value={newPassword}
            onChange={(e) => setNewPassword(e.target.value)}
            placeholder="Nova senha"
            minLength={6}
            required
            className="w-full px-4 py-2.5 rounded-lg bg-white/5 border border-white/10 text-white focus:outline-none focus:border-purple-500/50"
          />
          <button type="submit" disabled={passwordSaving} className="btn-primary px-4 py-2 rounded-lg">
            {passwordSaving ? "Atualizando..." : "Atualizar senha"}
          </button>
        </form>
      </section>

      <section className="card p-6 space-y-4 border border-red-500/20">
        <div>
          <h2 className="text-xl font-semibold text-red-300 mb-2">Zona de perigo</h2>
          <p className="text-sm text-slate-400">
            Exclua sua conta e exporte seus dados pessoais.
          </p>
        </div>

        <button onClick={handleExportData} className="btn-outline px-4 py-2 rounded-lg">
          Exportar meus dados
        </button>

        <form onSubmit={handleDeleteAccount} className="space-y-4">
          <input
            type="password"
            value={deletePassword}
            onChange={(e) => setDeletePassword(e.target.value)}
            placeholder="Confirme sua senha para excluir"
            required
            className="w-full px-4 py-2.5 rounded-lg bg-red-500/10 border border-red-500/20 text-white focus:outline-none focus:border-red-400/60"
          />
          <button
            type="submit"
            disabled={deleteLoading}
            className="px-4 py-2 rounded-lg font-semibold text-white bg-red-600 hover:bg-red-500 disabled:opacity-50"
          >
            {deleteLoading ? "Excluindo..." : "Excluir minha conta"}
          </button>
        </form>
      </section>
    </div>
  );
}
