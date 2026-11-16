import type { Metadata } from 'next'
import './globals.css'
import AuthGuard from '@/components/AuthGuard'
import AdminLayout from '@/components/AdminLayout'

export const metadata: Metadata = {
  title: 'Logforge Admin',
  description: 'Administrative interface for Logforge platform administration',
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