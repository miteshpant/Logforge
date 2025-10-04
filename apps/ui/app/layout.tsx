import './globals.css'
import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import { AuthProvider } from '@/contexts/AuthContext'
import { TimeRangeProvider } from '@/contexts/TimeRangeContext'

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
          <TimeRangeProvider defaultRange="24h">
            {children}
          </TimeRangeProvider>
        </AuthProvider>
      </body>
    </html>
  )
}