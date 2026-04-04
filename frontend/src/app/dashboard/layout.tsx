'use client'

import { useEffect, type ReactNode } from 'react'
import { useRouter } from 'next/navigation'
import { getToken } from '@/lib/auth'
import { useAuth } from '@/contexts/AuthContext'
import DashboardNavbar from '@/components/dashboard/DashboardNavbar'

export default function DashboardLayout({ children }: { children: ReactNode }) {
  const router = useRouter()
  const { loading } = useAuth()

  useEffect(() => {
    if (!loading && !getToken()) {
      router.replace('/auth/login')
    }
  }, [loading, router])

  if (loading) {
    return <div className="min-h-screen bg-[#111]" />
  }

  return (
    <div className="min-h-screen bg-[#111] text-[#E8E8E8] font-sans">
      <DashboardNavbar />
      <main className="pt-14">
        {children}
      </main>
    </div>
  )
}
