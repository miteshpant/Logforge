import './globals.css'
import type { Metadata } from 'next'
import { Inter } from 'next/font/google'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Logforge - Open Observability + SIEM',
  description: 'Open, cloud-native platform for logs, security analytics and observability',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <nav className="bg-gray-900 text-white p-4">
          <div className="container mx-auto flex justify-between items-center">
            <h1 className="text-2xl font-bold">🔍 Logforge</h1>
            <div className="space-x-4">
              <a href="/" className="hover:text-gray-300">Dashboard</a>
              <a href="/logs" className="hover:text-gray-300">Logs</a>
              <a href="/security" className="hover:text-gray-300 bg-red-600 px-3 py-1 rounded">Security Analytics</a>
              <a href="/observability" className="hover:text-gray-300 bg-green-600 px-3 py-1 rounded">Observability & APM</a>
              <a href="/test-runner" className="hover:text-gray-300 bg-blue-600 px-3 py-1 rounded">Test Runner</a>
              <a href="/health" className="hover:text-gray-300">Health</a>
            </div>
          </div>
        </nav>
        <main className="container mx-auto p-4">
          {children}
        </main>
      </body>
    </html>
  )
}