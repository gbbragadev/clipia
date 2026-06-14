"use client";

import { useState } from "react";
import { useAuth } from "@/contexts/AuthContext";

export default function ReferralCard() {
  const { user } = useAuth();
  const [copied, setCopied] = useState(false);

  if (!user?.referral_code) return null;

  const referralLink = `https://clipia.com.br/auth/register?ref=${user.referral_code}`;

  async function handleCopy() {
    await navigator.clipboard.writeText(referralLink);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <div className="rounded-2xl bg-gradient-to-br from-purple-600/10 to-blue-600/10 border border-purple-500/20 p-6 backdrop-blur-md">
      <div className="flex items-center gap-3 mb-3">
        <div className="w-10 h-10 rounded-xl bg-purple-500/20 flex items-center justify-center text-xl">
          🎁
        </div>
        <div>
          <h3 className="text-white font-bold text-lg">Convide amigos</h3>
          <p className="text-slate-400 text-sm">Vocês dois ganham 2 créditos extras</p>
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
          className={`w-full sm:w-auto sm:shrink-0 px-5 py-2.5 rounded-xl font-semibold text-sm transition-all ${
            copied
              ? "bg-green-500/20 text-green-300 border border-green-500/30"
              : "bg-purple-600 text-white hover:bg-purple-500 shadow-lg shadow-purple-500/25"
          }`}
        >
          {copied ? "Copiado!" : "Copiar"}
        </button>
      </div>
    </div>
  );
}
