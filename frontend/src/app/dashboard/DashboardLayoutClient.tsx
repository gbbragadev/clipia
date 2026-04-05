'use client'

import { useEffect, type ReactNode } from 'react'
import { useRouter } from 'next/navigation'
import { getToken } from '@/lib/auth'
import { useAuth } from '@/contexts/AuthContext'
import DashboardNavbar from '@/components/dashboard/DashboardNavbar'
import { DashboardLoadingSkeleton } from '@/components/ui/skeletons'

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const router = useRouter()
  const { loading } = useAuth()

  useEffect(() => {
    if (!loading && !getToken()) {
      router.replace('/auth/login')
    }
  }, [loading, router])

  if (loading) {
    return <div className="min-h-screen" style={{ background: 'var(--bg-raised)' }}><DashboardLoadingSkeleton /></div>
  }

  return (
    <div className="min-h-screen font-sans" style={{ background: 'var(--bg-raised)', color: 'var(--text-primary)' }}>
      <DashboardNavbar />
      <main className="pt-14">
        {children}
      </main>
    </div>
  )
}
