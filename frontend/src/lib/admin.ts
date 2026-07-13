import { fetchJson } from './http'
import { getToken } from './auth'

const API_BASE = ''

function authHeaders(): Record<string, string> {
  const token = getToken()
  const headers: Record<string, string> = { 'Content-Type': 'application/json' }
  if (token) headers.Authorization = `Bearer ${token}`
  return headers
}

export type AdminRange = '7d' | '30d' | '90d'

export interface AdminSeriesPoint {
  date: string
  value: number
}

export interface AdminDashboardResponse {
  range: AdminRange
  window_start: string
  window_end: string
  summary: {
    paid_gross_revenue_brl: number
    refunded_value_brl: number
    net_revenue_brl: number
    approved_revenue_brl: number
    pending_revenue_brl: number
    approved_orders: number
    pending_orders: number
    average_ticket_brl: number
    new_users: number
    verified_users: number
    paying_users: number
    active_jobs: number
    credits_sold: number
    credits_consumed: number
  }
  timeseries: {
    revenue_by_day: AdminSeriesPoint[]
    new_users_by_day: AdminSeriesPoint[]
    jobs_by_day: AdminSeriesPoint[]
    approved_orders_by_day: AdminSeriesPoint[]
  }
  funnel: {
    visited: number
    cta_clicked: number
    registered: number
    verified: number
    first_generation: number
    exported: number
    checkout_started: number
    paying: number
    second_generation: number
    verification_rate: number
    payer_conversion_rate: number
    cta_registration_rate: number
    activation_rate: number
    export_payment_rate: number
    second_generation_rate: number
    analytics_enabled: boolean
    analytics_frontend_enabled: boolean
    collection_flags_aligned: boolean
    baseline_started_at: string | null
    baseline_days: number
    onboarding_gate_ready: boolean
  }
  cohorts: {
    weekly: AdminCohortRow[]
    source: AdminCohortRow[]
    niche: AdminCohortRow[]
    device: AdminCohortRow[]
  }
  operations: {
    queued_jobs: number
    processing_jobs: number
    completed_jobs: number
    failed_jobs: number
    success_rate: number
    avg_pending_credits: number
    jobs_dir_size_gb: number
    output_dir_size_gb: number
    total_jobs: number
    failed_jobs_total?: number
    orphan_dirs: number
    oldest_job_days: number
  }
  package_mix: Array<{
    package_name: string
    orders: number
    paid_gross_revenue_brl: number
    refunded_value_brl: number
    net_revenue_brl: number
    approved_revenue_brl: number
    credits_sold: number
  }>
  recent_activity: {
    recent_users: Array<{
      id: string
      email: string
      name: string
      plan: string
      email_verified: boolean
      created_at: string | null
      is_paying: boolean
    }>
    recent_purchases: Array<{
      id: string
      user_id: string
      package_name: string
      price_brl: number
      credits_amount: number
      status: string
      created_at: string | null
      paid_at: string | null
    }>
    recent_failed_jobs: Array<{
      id: string
      user_id: string
      topic: string
      status: string
      error: string | null
      created_at: string | null
    }>
  }
}

export interface AdminCohortRow {
  key: string
  registered: number
  verified: number
  first_generation: number
  exported: number
  checkout_started: number
  paying: number
  second_generation: number
  verification_rate: number
  activation_rate: number
  payer_conversion_rate: number
}

export async function fetchAdminDashboard(range: AdminRange): Promise<AdminDashboardResponse> {
  return fetchJson<AdminDashboardResponse>(
    `${API_BASE}/api/v1/admin/dashboard?range=${range}`,
    { headers: authHeaders() },
    'Não foi possível carregar o painel administrativo',
  )
}

export interface AdminUserItem {
  id: string
  email: string
  name: string
  credits: number
  plan: string
  email_verified: boolean
  created_at: string | null
  is_paying: boolean
}

export interface AdminPurchaseItem {
  id: string
  user_email: string
  package_name: string
  credits_amount: number
  bonus_credits: number
  price_brl: number
  provider: string
  status: string
  created_at: string | null
  paid_at: string | null
}

export interface AdminJobItem {
  id: string
  user_email: string
  topic: string
  template_id: string
  status: string
  credit_cost: number
  created_at: string | null
  error: string | null
}

interface AdminPage {
  total: number
  page: number
  page_size: number
}

function adminQuery(params: Record<string, string | number | undefined>): string {
  const search = new URLSearchParams()
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== '') search.set(key, String(value))
  }
  const qs = search.toString()
  return qs ? `?${qs}` : ''
}

export async function fetchAdminUsers(params: { search?: string; page?: number }) {
  return fetchJson<AdminPage & { users: AdminUserItem[] }>(
    `${API_BASE}/api/v1/admin/users${adminQuery(params)}`,
    { headers: authHeaders() },
    'Não foi possível carregar os usuarios',
  )
}

export async function fetchAdminPurchases(params: { status?: string; page?: number }) {
  return fetchJson<AdminPage & { purchases: AdminPurchaseItem[] }>(
    `${API_BASE}/api/v1/admin/purchases${adminQuery(params)}`,
    { headers: authHeaders() },
    'Não foi possível carregar as compras',
  )
}

export async function fetchAdminJobs(params: { status?: string; page?: number }) {
  return fetchJson<AdminPage & { jobs: AdminJobItem[] }>(
    `${API_BASE}/api/v1/admin/jobs${adminQuery(params)}`,
    { headers: authHeaders() },
    'Não foi possível carregar os videos',
  )
}

// ── Economia por job (telemetria consolidada no finalize) ──────────────────

export interface AdminEconomyJob {
  job_id: string
  template_id: string
  voice_provider: string
  created_at: string | null
  total_seconds: number | null
  steps: Record<string, number>
  api_cost_usd_est: number
  credit_cost: number
  rerenders: number
  rerender_seconds: number
}

export interface AdminEconomyTemplateAgg {
  count: number
  api_cost_usd_est: number
  credits: number
  total_seconds: number
  avg_cost_usd: number
  avg_seconds: number
}

export interface AdminEconomyResponse {
  jobs: AdminEconomyJob[]
  by_template: Record<string, AdminEconomyTemplateAgg>
}

export async function fetchAdminEconomy() {
  return fetchJson<AdminEconomyResponse>(
    `${API_BASE}/api/v1/admin/economy`,
    { headers: authHeaders() },
    'Não foi possível carregar a economia',
  )
}

export interface AdminFeedbackItem {
  id: string
  user_email: string
  kind: 'widget' | 'post_video'
  rating: number | null
  comment: string | null
  job_id: string | null
  job_topic: string | null
  source_url: string | null
  created_at: string | null
}

export async function fetchAdminFeedbacks(params: { kind?: string; page?: number }) {
  return fetchJson<AdminPage & { feedbacks: AdminFeedbackItem[] }>(
    `${API_BASE}/api/v1/admin/feedbacks${adminQuery(params)}`,
    { headers: authHeaders() },
    'Não foi possível carregar os feedbacks',
  )
}

export async function adjustUserCredits(userId: string, delta: number, reason: string) {
  return fetchJson<{ user_id: string; delta: number; previous_balance: number; new_balance: number }>(
    `${API_BASE}/api/v1/admin/users/${userId}/adjust-credits`,
    { method: 'POST', headers: authHeaders(), body: JSON.stringify({ delta, reason }) },
    'Não foi possível ajustar os creditos',
  )
}
