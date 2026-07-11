'use client'

import { useCallback, useEffect, useState } from 'react'

import { adjustUserCredits, fetchAdminUsers, type AdminUserItem } from '@/lib/admin'
import { InlineError, useToast } from '@/components/ui/feedback'
import { AdminPager, AdminTable, formatAdminDateTime } from './AdminTable'

const PAGE_SIZE = 50

export default function AdminUsersTab() {
  const { success, error: toastError } = useToast()
  const [search, setSearch] = useState('')
  const [query, setQuery] = useState('')
  const [page, setPage] = useState(1)
  const [total, setTotal] = useState(0)
  const [users, setUsers] = useState<AdminUserItem[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)
  const [adjustingId, setAdjustingId] = useState<string | null>(null)
  const [delta, setDelta] = useState('')
  const [reason, setReason] = useState('')
  const [saving, setSaving] = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const data = await fetchAdminUsers({ search: query, page })
      setUsers(data.users)
      setTotal(data.total)
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Erro ao carregar usuários')
    } finally {
      setLoading(false)
    }
  }, [query, page])

  useEffect(() => {
    void load()
  }, [load])

  async function submitAdjust(user: AdminUserItem) {
    const parsed = Number.parseInt(delta, 10)
    if (!Number.isFinite(parsed) || parsed === 0) {
      toastError('Delta inválido', 'Informe um número de créditos diferente de zero.')
      return
    }
    if (reason.trim().length < 3) {
      toastError('Motivo obrigatório', 'Descreva o motivo do ajuste (mín. 3 caracteres).')
      return
    }
    setSaving(true)
    try {
      const result = await adjustUserCredits(user.id, parsed, reason.trim())
      success('Créditos ajustados', `${user.email}: ${result.previous_balance} → ${result.new_balance}`)
      setAdjustingId(null)
      setDelta('')
      setReason('')
      await load()
    } catch (err) {
      toastError('Falha ao ajustar', err instanceof Error ? err.message : 'Tente novamente.')
    } finally {
      setSaving(false)
    }
  }

  if (error) {
    return <InlineError title="Não foi possível carregar os usuários" description={error} onRetry={() => load()} />
  }

  return (
    <div className="card p-6">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-xl font-semibold">Usuários</h2>
        <form
          onSubmit={(event) => {
            event.preventDefault()
            setPage(1)
            setQuery(search)
          }}
          className="flex gap-2"
        >
          <input
            value={search}
            onChange={(event) => setSearch(event.target.value)}
            placeholder="Buscar por e-mail ou nome"
            className="rounded-xl px-3 py-2 text-sm outline-none"
            style={{
              background: 'rgba(255,255,255,0.04)',
              border: '1px solid var(--border-subtle)',
              color: 'var(--text-primary)',
              minWidth: '16rem',
            }}
          />
          <button type="submit" className="btn-outline px-4 py-2 text-sm">
            Buscar
          </button>
        </form>
      </div>

      <div className="mt-4">
        {loading ? (
          <div className="h-40 animate-pulse rounded-2xl" style={{ background: 'rgba(255,255,255,0.04)' }} />
        ) : (
          <AdminTable
            columns={['Usuário', 'Créditos', 'Plano', 'Status', 'Entrada', 'Ações']}
            rows={users.map((user) => [
              <div key={user.id}>
                <p className="font-medium">{user.name}</p>
                <p className="text-xs" style={{ color: 'var(--text-secondary)' }}>{user.email}</p>
              </div>,
              <span key={`${user.id}-credits`} className="font-semibold" style={{ color: 'var(--accent-primary, #ff5638)' }}>
                {user.credits}
              </span>,
              <span key={`${user.id}-plan`} className="capitalize">{user.plan}</span>,
              <span key={`${user.id}-status`} className="text-xs">
                {user.is_paying ? 'Pagante' : user.email_verified ? 'Verificado' : 'Pendente'}
              </span>,
              <span key={`${user.id}-created`}>{formatAdminDateTime(user.created_at)}</span>,
              <div key={`${user.id}-actions`}>
                {adjustingId === user.id ? (
                  <div className="flex flex-col gap-2 min-w-[14rem]">
                    <input
                      value={delta}
                      onChange={(event) => setDelta(event.target.value)}
                      placeholder="Delta (ex.: 10 ou -5)"
                      inputMode="numeric"
                      className="rounded-lg px-2 py-1.5 text-xs outline-none"
                      style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
                    />
                    <input
                      value={reason}
                      onChange={(event) => setReason(event.target.value)}
                      placeholder="Motivo (obrigatório)"
                      className="rounded-lg px-2 py-1.5 text-xs outline-none"
                      style={{ background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border-subtle)', color: 'var(--text-primary)' }}
                    />
                    <div className="flex gap-2">
                      <button
                        onClick={() => void submitAdjust(user)}
                        disabled={saving}
                        className="rounded-lg px-3 py-1.5 text-xs font-semibold disabled:opacity-50"
                        style={{ background: 'linear-gradient(135deg, #ff5638, #3e9bff)', color: '#fff' }}
                      >
                        {saving ? 'Salvando…' : 'Confirmar'}
                      </button>
                      <button
                        onClick={() => setAdjustingId(null)}
                        className="rounded-lg px-3 py-1.5 text-xs"
                        style={{ border: '1px solid var(--border-subtle)', color: 'var(--text-secondary)' }}
                      >
                        Cancelar
                      </button>
                    </div>
                  </div>
                ) : (
                  <button
                    onClick={() => {
                      setAdjustingId(user.id)
                      setDelta('')
                      setReason('')
                    }}
                    className="rounded-lg px-3 py-1.5 text-xs"
                    style={{ border: '1px solid var(--border-subtle)', color: 'var(--text-secondary)' }}
                  >
                    Ajustar créditos
                  </button>
                )}
              </div>,
            ])}
          />
        )}
      </div>

      <AdminPager page={page} pageSize={PAGE_SIZE} total={total} onPage={setPage} />
    </div>
  )
}
