'use client'

import type { ReactNode } from 'react'

export function AdminTable({ columns, rows, emptyText = 'Nenhum registro.' }: {
  columns: string[]
  rows: ReactNode[][]
  emptyText?: string
}) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full min-w-[40rem] text-left">
        <thead>
          <tr>
            {columns.map((column) => (
              <th
                key={column}
                className="pb-3 pr-3 text-xs uppercase tracking-[0.16em] whitespace-nowrap"
                style={{ color: 'var(--text-tertiary)' }}
              >
                {column}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.length === 0 ? (
            <tr>
              <td colSpan={columns.length} className="py-4 text-sm" style={{ color: 'var(--text-secondary)' }}>
                {emptyText}
              </td>
            </tr>
          ) : (
            rows.map((row, rowIndex) => (
              <tr key={rowIndex} style={{ borderTop: '1px solid var(--border-subtle)' }}>
                {row.map((cell, cellIndex) => (
                  <td key={cellIndex} className="py-3 pr-3 align-top text-xs sm:text-sm">
                    {cell}
                  </td>
                ))}
              </tr>
            ))
          )}
        </tbody>
      </table>
    </div>
  )
}

export function AdminPager({ page, pageSize, total, onPage }: {
  page: number
  pageSize: number
  total: number
  onPage: (page: number) => void
}) {
  const lastPage = Math.max(1, Math.ceil(total / pageSize))
  const from = total === 0 ? 0 : (page - 1) * pageSize + 1
  const to = Math.min(total, page * pageSize)

  return (
    <div className="mt-4 flex items-center justify-between gap-3 text-sm" style={{ color: 'var(--text-secondary)' }}>
      <span>
        {from}–{to} de {total}
      </span>
      <div className="flex gap-2">
        <button onClick={() => onPage(page - 1)} disabled={page <= 1} className="btn-outline px-3 py-1.5 text-sm disabled:opacity-40">
          Anterior
        </button>
        <button onClick={() => onPage(page + 1)} disabled={page >= lastPage} className="btn-outline px-3 py-1.5 text-sm disabled:opacity-40">
          Próxima
        </button>
      </div>
    </div>
  )
}

export function StatusPill({ value }: { value: string }) {
  const tones: Record<string, string> = {
    approved: '#4ade80',
    completed: '#4ade80',
    editable: '#38bdf8',
    pending: '#f59e0b',
    queued: '#f59e0b',
    processing: '#f59e0b',
    rendering: '#f59e0b',
    refunded: '#f87171',
    failed: '#f87171',
  }
  const tone = tones[value] ?? 'var(--text-secondary)'
  return (
    <span
      className="inline-block rounded-full px-2 py-0.5 text-xs font-medium uppercase"
      style={{ color: tone, background: 'rgba(255,255,255,0.05)', border: '1px solid var(--border-subtle)' }}
    >
      {value}
    </span>
  )
}

export function formatAdminDateTime(value: string | null): string {
  if (!value) return '-'
  return new Intl.DateTimeFormat('pt-BR', {
    day: '2-digit',
    month: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }).format(new Date(value))
}
