'use client'

import { useRouter } from 'next/navigation'
import { authService } from '@/lib/auth'
import { Button } from '@/components/ui/button'
import { LogOut, User, Home } from 'lucide-react'
import Link from 'next/link'

export default function AdminHeader() {
  const router = useRouter()
  const currentUser = authService.getCurrentUser()

  const handleLogout = () => {
    authService.logout()
    router.push('/login')
  }

  return (
    <header className="bg-white shadow-sm border-b border-gray-200">
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8">
        <div className="flex justify-between items-center h-16">
          {/* Left side - Logo and Navigation */}
          <div className="flex items-center space-x-4">
            <Link 
              href="/" 
              className="flex items-center space-x-2 text-gray-900 hover:text-blue-600 transition-colors"
            >
              <Home className="h-5 w-5" />
              <span className="font-semibold text-lg">Logforge Admin</span>
            </Link>
          </div>

          {/* Right side - User info and Logout */}
          <div className="flex items-center space-x-4">
            {/* User info */}
            <div className="flex items-center space-x-2 text-sm text-gray-600">
              <User className="h-4 w-4" />
              <span className="hidden sm:inline">
                {currentUser?.name || currentUser?.email || 'Admin User'}
              </span>
            </div>

            {/* Logout button */}
            <Button 
              onClick={handleLogout} 
              variant="outline" 
              size="sm"
              className="flex items-center space-x-2 hover:bg-red-50 hover:border-red-200 hover:text-red-600 transition-colors"
            >
              <LogOut className="h-4 w-4" />
              <span className="hidden sm:inline">Logout</span>
            </Button>
          </div>
        </div>
      </div>
    </header>
  )
}