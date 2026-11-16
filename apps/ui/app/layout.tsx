import './globals.css'
import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import { AuthProvider } from '@/contexts/AuthContext'
import { TimeRangeProvider } from '@/contexts/TimeRangeContext'
import { AuthGate } from '@/components/auth/AuthGate'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Logforge - Enterprise Observability Platform',
  description: 'Advanced log analytics, security operations, and observability platform built for enterprise scale',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <AuthProvider>
          <AuthGate>
            <TimeRangeProvider defaultRange="24h">
              {children}
            </TimeRangeProvider>
          </AuthGate>
        </AuthProvider>
      </body>
    </html>
  )
}