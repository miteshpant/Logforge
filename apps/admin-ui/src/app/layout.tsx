import type { Metadata } from 'next'
import './globals.css'
import AuthGuard from '@/components/AuthGuard'
import AdminLayout from '@/components/AdminLayout'

export const metadata: Metadata = {
  title: 'MrLogSec Admin Dashboard',
  description: 'Administrative interface for MrLogSec platform management',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className="min-h-screen bg-gray-50">
        <AuthGuard>
          <AdminLayout>
            {children}
          </AdminLayout>
        </AuthGuard>
      </body>
    </html>
  )
}