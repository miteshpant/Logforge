'use client'

import { useState } from 'react'
import { usePathname } from 'next/navigation'
import AdminHeader from '@/components/AdminHeader'
import AdminActivityLog from '@/components/AdminActivityLog'
import { Button } from '@/components/ui/button'
import { Activity } from 'lucide-react'

interface AdminLayoutProps {
  children: React.ReactNode
}

export default function AdminLayout({ children }: AdminLayoutProps) {
  const pathname = usePathname()
  const [isActivityLogOpen, setIsActivityLogOpen] = useState(false)
  
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
      
      {/* Floating Activity Log Trigger */}
      <div className="fixed bottom-6 right-6 z-50" style={{ zIndex: 9999 }}>
        <Button
          onClick={() => {
            console.log('🔍 Activity log button clicked!')
            setIsActivityLogOpen(true)
          }}
          className="rounded-full w-16 h-16 bg-red-600 hover:bg-red-700 shadow-2xl border-4 border-white"
          title="View Admin Activity Log"
        >
          <Activity className="h-8 w-8 text-white" />
        </Button>
      </div>

      {/* Admin Activity Log Component */}
      <AdminActivityLog 
        isOpen={isActivityLogOpen} 
        onClose={() => setIsActivityLogOpen(false)} 
      />
    </div>
  )
}