import { Metadata } from 'next'
import DashboardLayoutClient from './DashboardLayoutClient'

export const metadata: Metadata = {
  title: 'Dashboard | ClipIA',
  description: 'Gere e gerencie seus vídeos curtos com IA.',
}

export default function DashboardLayout({ children }: { children: React.ReactNode }) {
  return <DashboardLayoutClient>{children}</DashboardLayoutClient>
}
