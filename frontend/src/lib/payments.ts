import { getToken } from "@/lib/auth";
import { fetchJson } from "@/lib/http";

const API_BASE = "";

export interface CreditPackage {
  id: string;
  name: string;
  credits: number;
  price_brl: number;
  price_display: string;
}

export interface PurchaseHistoryItem {
  id: string;
  package_name: string;
  credits_amount: number;
  price_brl: number;
  status: string;
  created_at: string;
  paid_at: string | null;
}

function authHeaders(): HeadersInit {
  const token = getToken();
  if (!token) throw new Error("Não autenticado");
  return { Authorization: `Bearer ${token}`, "Content-Type": "application/json" };
}

export async function fetchPackages(): Promise<CreditPackage[]> {
  return fetchJson(`${API_BASE}/api/v1/credits/packages`, {
    headers: authHeaders(),
  }, "Erro ao carregar pacotes");
}

export async function createCheckout(packageId: string): Promise<string> {
  const data = await fetchJson<{ checkout_url: string }>(`${API_BASE}/api/v1/credits/checkout`, {
    method: "POST",
    headers: authHeaders(),
    body: JSON.stringify({ package: packageId }),
  }, "Erro ao criar checkout");
  return data.checkout_url;
}

export async function fetchHistory(): Promise<PurchaseHistoryItem[]> {
  const data = await fetchJson<{ purchases: PurchaseHistoryItem[] }>(`${API_BASE}/api/v1/credits/history`, {
    headers: authHeaders(),
  }, "Erro ao carregar historico");
  return data.purchases;
}
