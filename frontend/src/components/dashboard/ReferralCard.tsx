"use client";

import { useState } from "react";
import { Gift, Copy, Check } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { trackProductEvent } from "@/lib/analytics";

export default function ReferralCard() {
  const { user } = useAuth();
  const [copied, setCopied] = useState(false);

  if (!user?.referral_code) return null;

  const referralLink = `https://clipia.com.br/auth/register?ref=${user.referral_code}`;

  async function handleCopy() {
    await navigator.clipboard.writeText(referralLink);
    trackProductEvent("referral_shared", { channel: "copy_link", placement: "dashboard" });
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="rounded-2xl bg-gradient-to-br from-coral/10 to-azure/10 border border-coral/20 p-6 backdrop-blur-md">
      <div className="flex items-center gap-3 mb-3">
        <div className="w-10 h-10 rounded-xl bg-coral/20 flex items-center justify-center text-coral">
          <Gift className="w-5 h-5" />
        </div>
        <div>
          <h3 className="text-white font-bold text-lg">Convide amigos</h3>
          <p className="text-slate-400 text-sm">
            Você ganha +18 créditos quando a pessoa convidada verificar o e-mail e concluir o primeiro vídeo.
          </p>
        </div>
      </div>

      <div className="flex flex-col sm:flex-row gap-2 mt-4">
        <input
          readOnly
          value={referralLink}
          className="w-full px-4 py-2.5 rounded-xl bg-white/5 border border-white/10 text-slate-300 text-sm font-mono truncate"
        />
        <button
          onClick={handleCopy}
          className={`w-full sm:w-auto sm:shrink-0 inline-flex items-center justify-center gap-2 px-5 py-2.5 rounded-xl font-semibold text-sm transition-all ${
            copied
              ? "bg-green-500/20 text-green-300 border border-green-500/30"
              : "bg-coral text-white hover:bg-coral shadow-lg shadow-coral/25"
          }`}
        >
          {copied ? <Check className="w-4 h-4" /> : <Copy className="w-4 h-4" />}
          {copied ? "Copiado!" : "Copiar"}
        </button>
      </div>
    </div>
  );
}
