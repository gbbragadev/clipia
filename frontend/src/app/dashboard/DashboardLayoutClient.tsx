'use client'

import { useEffect, type ReactNode } from 'react'
import { useRouter } from 'next/navigation'
import { getToken } from '@/lib/auth'
import { useAuth } from '@/contexts/AuthContext'
import DashboardNavbar from '@/components/dashboard/DashboardNavbar'
import { MobileBottomNav } from '@/components/dashboard/MobileBottomNav'
import FeedbackWidget from '@/components/ui/FeedbackWidget'
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
      {/* pb-20 em mobile compensa a bottom-nav fixa; lg:pb-12 volta ao normal no desktop. */}
      <main className="pt-14 pb-20 md:pb-12">
        {children}
      </main>
      <MobileBottomNav />
      <FeedbackWidget />
    </div>
  )
}
