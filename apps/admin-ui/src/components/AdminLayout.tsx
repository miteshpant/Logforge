'use client'

import { usePathname } from 'next/navigation'
import AdminHeader from '@/components/AdminHeader'

interface AdminLayoutProps {
  children: React.ReactNode
}

export default function AdminLayout({ children }: AdminLayoutProps) {
  const pathname = usePathname()
  
  // Don't show header on login page
  const isLoginPage = pathname === '/login'

  if (isLoginPage) {
    return (
      <div className="min-h-screen">
        {children}
      </div>
    )
  }

  return (
    <div className="min-h-screen flex flex-col">
      <AdminHeader />
      <main className="flex-1">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
          {children}
        </div>
      </main>
    </div>
  )
}