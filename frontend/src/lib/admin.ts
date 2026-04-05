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
    registered: number
    verified: number
    paying: number
    verification_rate: number
    payer_conversion_rate: number
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

export async function fetchAdminDashboard(range: AdminRange): Promise<AdminDashboardResponse> {
  return fetchJson<AdminDashboardResponse>(
    `${API_BASE}/api/v1/admin/dashboard?range=${range}`,
    { headers: authHeaders() },
    'Nao foi possivel carregar o painel administrativo',
  )
}
