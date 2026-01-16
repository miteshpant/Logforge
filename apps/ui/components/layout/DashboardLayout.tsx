'use client'

import React, { useState } from 'react'
import { useAuth } from '@/contexts/AuthContext'
import { usePathname } from 'next/navigation'
import Link from 'next/link'
import { Button } from '@/components/ui/button'
import GlobalTimeSelector from '@/components/GlobalTimeSelector'
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu'
import { Badge } from '@/components/ui/badge'
import {
  BarChart3,
  Search,
  Shield,
  Bell,
  Settings,
  Users,
  Database,
  Activity,
  FileText,
  Zap,
  Brain,
  Menu,
  X,
  User,
  LogOut,
  Building2,
  ChevronDown,
  Home,
  GitBranch,
  Clock,
  Gauge,
  Radio,
  ShieldAlert,
  Target,
  Crosshair,
  Globe,
  ScrollText,
  LayoutDashboard,
} from 'lucide-react'
import { TenantSelector } from '@/components/TenantSelector'
import PWASupport from '@/components/PWASupport'

const navigation = [
  {
    name: 'Centrum',
    href: '/centrum',
    icon: Home,
    description: 'Central command center'
  },
  // Observability Section
  {
    name: 'Service Map',
    href: '/observability/service-map',
    icon: GitBranch,
    description: 'Interactive service dependencies'
  },
  {
    name: 'Distributed Tracing',
    href: '/observability/traces',
    icon: Clock,
    description: 'Request traces & waterfall'
  },
  {
    name: 'APM Dashboard',
    href: '/observability/apm',
    icon: Gauge,
    description: 'Application performance metrics'
  },
  {
    name: 'Metrics',
    href: '/observability/metrics',
    icon: Radio,
    description: 'Metrics explorer and visualization'
  },
  {
    name: 'Dashboards',
    href: '/dashboards',
    icon: LayoutDashboard,
    description: 'Custom dashboards and visualizations'
  },
  {
    name: 'Log Explorer',
    href: '/observability/logs',
    icon: ScrollText,
    description: 'Search & analyze logs'
  },
  {
    name: 'Anomaly Detection',
    href: '/anomaly-detection',
    icon: Brain,
    description: 'AI-powered anomaly detection'
  },
  // Security Section
  {
    name: 'SIEM Dashboard',
    href: '/security/siem',
    icon: ShieldAlert,
    description: 'Security operations center',
    badge: 'New'
  },
  {
    name: 'Security Events',
    href: '/security/events',
    icon: Shield,
    description: 'Investigate security incidents'
  },
  {
    name: 'Detection Rules',
    href: '/security/rules',
    icon: FileText,
    description: 'Sigma detection rules'
  },
  {
    name: 'Threat Intel',
    href: '/security/threat-intel',
    icon: Globe,
    description: 'IOC & threat feeds'
  },
  {
    name: 'Threat Hunting',
    href: '/security/threat-hunting',
    icon: Crosshair,
    description: 'Proactive threat hunting'
  },
]

interface DashboardLayoutProps {
  children: React.ReactNode
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { user, tenant, logout, userRole } = useAuth()
  const pathname = usePathname()

  const handleLogout = async () => {
    try {
      await logout()
    } catch (error) {
      console.error('Logout failed:', error)
    }
  }

  return (
    <div className="min-h-screen bg-slate-50 flex">
      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div 
          className="fixed inset-0 z-40 lg:hidden"
          onClick={() => setSidebarOpen(false)}
        >
          <div className="fixed inset-0 bg-slate-600 opacity-75" />
        </div>
      )}

      {/* Sidebar */}
      <div className={`
        fixed inset-y-0 left-0 z-50 w-64 bg-white border-r border-slate-200 transform transition-transform duration-300 ease-in-out lg:translate-x-0
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        <div className="flex flex-col h-full">
          {/* Logo and tenant info */}
          <div className="flex items-center justify-between p-6 border-b border-slate-200">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-blue-700 rounded-lg flex items-center justify-center">
                <BarChart3 className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-slate-900">Logforge</h1>
                <p className="text-xs text-slate-500 flex items-center space-x-1">
                  <Building2 className="w-3 h-3" />
                  <span>{tenant?.name || 'Loading...'}</span>
                </p>
              </div>
            </div>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setSidebarOpen(false)}
              className="lg:hidden"
            >
              <X className="w-5 h-5" />
            </Button>
          </div>

          {/* Navigation */}
          <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto" data-testid="main-navigation">
            {navigation.map((item) => {
              const isActive = pathname === item.href || pathname?.startsWith(item.href + '/')
              return (
                <Link
                  key={item.name}
                  href={item.href}
                  className={`
                    group flex items-center px-3 py-2.5 text-sm font-medium rounded-lg transition-all duration-200
                    ${isActive 
                      ? 'bg-blue-50 text-blue-700 border border-blue-200' 
                      : 'text-slate-600 hover:text-slate-900 hover:bg-slate-50'
                    }
                  `}
                  onClick={() => setSidebarOpen(false)}
                  data-testid={`nav-${item.name.toLowerCase().replace(/\s+/g, '-')}`}
                >
                  <item.icon className={`
                    flex-shrink-0 w-5 h-5 mr-3 transition-colors
                    ${isActive ? 'text-blue-600' : 'text-slate-400 group-hover:text-slate-500'}
                  `} />
                  
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center justify-between">
                      <span className="truncate">{item.name}</span>
                      {item.badge && (
                        <Badge 
                          variant={item.badge === 'New' ? 'default' : 'secondary'}
                          className="ml-2 text-xs"
                          data-testid={`badge-${item.badge.toLowerCase()}`}
                        >
                          {item.badge}
                        </Badge>
                      )}
                    </div>
                    <p className="text-xs text-slate-500 mt-0.5 group-hover:text-slate-600">
                      {item.description}
                    </p>
                  </div>
                </Link>
              )
            })}
          </nav>

          {/* User menu */}
          <div className="p-4 border-t border-slate-200">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="w-full justify-start h-auto p-3" data-testid="user-menu">
                  <div className="flex items-center space-x-3">
                    <div className="w-8 h-8 bg-gradient-to-br from-slate-400 to-slate-500 rounded-full flex items-center justify-center">
                      <User className="w-4 h-4 text-white" />
                    </div>
                    <div className="flex-1 text-left">
                      <p className="text-sm font-medium text-slate-900">
                        {user?.full_name || user?.email || 'Loading...'}
                      </p>
                      <p className="text-xs text-slate-500 capitalize" data-testid="current-tenant">
                        {userRole} • {tenant?.name}
                      </p>
                    </div>
                    <ChevronDown className="w-4 h-4 text-slate-400" />
                  </div>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent 
                align="end" 
                className="w-56 bg-white border border-slate-200 shadow-lg rounded-md p-1 z-50"
                style={{ backdropFilter: 'none' }}
              >
                <DropdownMenuLabel className="px-3 py-2 text-sm font-semibold text-slate-900 bg-slate-50">
                  Account
                </DropdownMenuLabel>
                <DropdownMenuItem 
                  data-testid="profile-settings"
                  className="flex items-center px-3 py-2 text-sm text-slate-700 hover:bg-slate-100 hover:text-slate-900 cursor-pointer rounded-sm"
                >
                  <User className="w-4 h-4 mr-2" />
                  Profile Settings
                </DropdownMenuItem>
                <DropdownMenuItem 
                  data-testid="preferences"
                  className="flex items-center px-3 py-2 text-sm text-slate-700 hover:bg-slate-100 hover:text-slate-900 cursor-pointer rounded-sm"
                >
                  <Settings className="w-4 h-4 mr-2" />
                  Preferences
                </DropdownMenuItem>
                <DropdownMenuSeparator className="my-1 border-slate-200" />
                <DropdownMenuItem 
                  onClick={handleLogout} 
                  data-testid="logout-button"
                  className="flex items-center px-3 py-2 text-sm text-red-600 hover:bg-red-50 hover:text-red-700 cursor-pointer rounded-sm font-medium"
                >
                  <LogOut className="w-4 h-4 mr-2" />
                  Sign Out
                </DropdownMenuItem>
              </DropdownMenuContent>
            </DropdownMenu>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 lg:ml-64">
        {/* Top header */}
        <header className="bg-white border-b border-slate-200 px-4 lg:px-6 py-4">
          <div className="flex items-center justify-between">
            <div className="flex items-center space-x-4">
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setSidebarOpen(true)}
                className="lg:hidden"
              >
                <Menu className="w-5 h-5" />
              </Button>
              
              {/* Breadcrumb or page title can go here */}
              <div className="hidden sm:block">
                <h2 className="text-xl font-semibold text-slate-900">
                  {navigation.find(item => pathname === item.href || pathname?.startsWith(item.href + '/'))?.name || 'Dashboard'}
                </h2>
              </div>
            </div>

            {/* Quick actions */}
            <div className="flex items-center space-x-3">
              {/* Global Time Selector */}
              <GlobalTimeSelector variant="compact" showRefresh={true} />
              
              {/* Tenant Selector */}
              <TenantSelector />
              
              {/* Settings */}
              <Button variant="ghost" size="sm">
                <Settings className="w-5 h-5" />
              </Button>
            </div>
          </div>
        </header>

        {/* Page content */}
        <main className="p-4 lg:p-6">
          {children}
        </main>
      </div>

      {/* PWA Support - World-Class Mobile Experience */}
      <PWASupport />
    </div>
  )
}