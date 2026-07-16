import { ApiError, fetchJson, normalizeNetworkError, readApiError } from "@/lib/http";
import { buildAuthHeaders } from "@/lib/session";
import {
  canManagePublicShare,
  publishPublicShare,
  revokePublicShare as executeRevokePublicShare,
} from "@/lib/public-share-actions";

export { canManagePublicShare };

const API_PATH = "/api/v1";

export interface PublicShareCreated {
  token: string;
  url: string;
  title: string;
  active: boolean;
}

export interface PublicShareMetadata {
  title: string;
  video_url: string;
  active: boolean;
  published_at: string;
}

export interface QualifiedViewPayload {
  anonymous_session_id: string;
  dwell_ms: number;
  page_visible: boolean;
}

export interface QualifiedViewResult {
  qualified: boolean;
  rewarded: boolean;
}

function apiBase(): string {
  if (typeof window !== "undefined") return API_PATH;
  const origin = process.env.LOCAL_API_URL || process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8005";
  return `${origin.replace(/\/$/, "")}${API_PATH}`;
}

export async function createPublicShare(jobId: string): Promise<PublicShareCreated> {
  return publishPublicShare(jobId, ({ path, method }) =>
    fetchJson<PublicShareCreated>(
      `${apiBase()}${path}`,
      {
        method,
        headers: buildAuthHeaders(method),
      },
      "Não foi possível publicar o link",
    ),
  );
}

export async function revokePublicShare(jobId: string): Promise<void> {
  return executeRevokePublicShare(jobId, async ({ path, method }) => {
    try {
      const response = await fetch(`${apiBase()}${path}`, {
        method,
        credentials: "include",
        headers: buildAuthHeaders(method),
      });
      if (!response.ok) {
        throw new ApiError(response.status, await readApiError(response, "Não foi possível revogar o link"));
      }
    } catch (error) {
      if (error instanceof TypeError) {
        throw new Error("Sem conexão. Verifique sua internet e tente novamente.");
      }
      throw normalizeNetworkError(error);
    }
  });
}

export async function getPublicShare(token: string): Promise<PublicShareMetadata> {
  const encodedToken = encodeURIComponent(token);
  return fetchJson<PublicShareMetadata>(
    `${apiBase()}/public-shares/${encodedToken}`,
    { cache: "no-store" },
    "Vídeo público não encontrado",
  );
}

export async function qualifyPublicShareView(
  token: string,
  payload: QualifiedViewPayload,
): Promise<QualifiedViewResult> {
  const encodedToken = encodeURIComponent(token);
  return fetchJson<QualifiedViewResult>(
    `${apiBase()}/public-shares/${encodedToken}/qualified-view`,
    {
      method: "POST",
      headers: buildAuthHeaders("POST"),
      body: JSON.stringify(payload),
      keepalive: true,
    },
    "Não foi possível registrar a visualização",
  );
}
