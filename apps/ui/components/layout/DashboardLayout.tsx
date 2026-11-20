'use client'

import React, { useState, useMemo } from 'react'
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
  ChevronRight,
  Home,
  GitBranch,
  Package,
  Bot,
  Clock,
  Gauge,
  Radio,
  ShieldAlert,
  Target,
  Crosshair,
  Globe,
  ScrollText,
  LayoutDashboard,
  AlertTriangle,
  BellRing,
  Puzzle,
  UserCog,
  DollarSign,
  ClipboardCheck,
  Eye,
  Siren,
  Sparkles,
  Link2,
  TrendingUp,
  MessageSquare,
  Key, Briefcase , HardDrive, Workflow, FileBarChart } from 'lucide-react'
import { TenantSelector } from '@/components/TenantSelector'
import PWASupport from '@/components/PWASupport'

interface NavItem {
  name: string
  href: string
  icon: React.ComponentType<{ className?: string }>
  badge?: string
}

interface NavSection {
  id: string
  label: string
  icon: React.ComponentType<{ className?: string }>
  items: NavItem[]
}

const navSections: NavSection[] = [
  {
    id: 'observe',
    label: 'Observability',
    icon: Eye,
    items: [
      { name: 'Service Map', href: '/observability/service-map', icon: GitBranch },
      { name: 'Tracing', href: '/observability/traces', icon: Clock },
      { name: 'APM', href: '/observability/apm', icon: Gauge },
      { name: 'Metrics', href: '/observability/metrics', icon: Radio },
      { name: 'Log Explorer', href: '/observability/logs', icon: ScrollText },
      { name: 'Dashboards', href: '/dashboards', icon: LayoutDashboard },
      { name: 'System Intelligence', href: '/dashboards/system', icon: Database },
      { name: 'Anomaly Detection', href: '/anomaly-detection', icon: Brain },
    ],
  },
  {
    id: 'alerts',
    label: 'Alerts',
    icon: BellRing,
    items: [
      { name: 'Alert Rules', href: '/alerts/rules', icon: AlertTriangle },
      { name: 'Alert Instances', href: '/alerts/instances', icon: BellRing },
      { name: 'Channels', href: '/alerts/channels', icon: Bell },
    ],
  },
  {
    id: 'security',
    label: 'Security',
    icon: ShieldAlert,
    items: [
      { name: 'SIEM Dashboard', href: '/security/siem', icon: ShieldAlert },
      { name: 'Cases', href: '/security/cases', icon: Briefcase },
      { name: 'Events', href: '/security/events', icon: Shield },
      { name: 'Entities', href: '/security/entities', icon: Users },
      { name: 'Detection Rules', href: '/security/rules', icon: FileText },
      { name: 'Threat Intel', href: '/security/threat-intel', icon: Globe },
      { name: 'Threat Hunting', href: '/security/threat-hunting', icon: Crosshair },
      { name: 'Playbooks', href: '/security/playbooks', icon: Workflow },
      { name: 'Reports', href: '/security/reports', icon: FileBarChart },
    ],
  },
  {
    id: 'ai',
    label: 'AI & Analytics',
    icon: Sparkles,
    items: [
      { name: 'Alert Correlation', href: '/ai/alert-correlation', icon: Link2 },
      { name: 'Predictive Analytics', href: '/ai/predictive-analytics', icon: TrendingUp },
      { name: 'Investigations', href: '/ai/investigations', icon: MessageSquare },
      { name: 'ML Models', href: '/ai/ml-models', icon: Brain },
    ],
  },
  {
    id: 'settings',
    label: 'Settings',
    icon: Settings,
    items: [
      { name: 'Authentication', href: '/settings/authentication', icon: Key },
      { name: 'Integrations', href: '/settings/integrations', icon: Puzzle },
      { name: 'Ingest Pipelines', href: '/settings/pipelines', icon: GitBranch },
      { name: 'Content Packs', href: '/settings/packs', icon: Package },
      { name: 'AI', href: '/settings/ai', icon: Bot },
      { name: 'Roles & Access', href: '/settings/roles', icon: UserCog },
      { name: 'Storage & Retention', href: '/settings/storage', icon: HardDrive },
      { name: 'Cost Analytics', href: '/settings/costs', icon: DollarSign },
      { name: 'Compliance', href: '/settings/compliance', icon: ClipboardCheck },
    ],
  },
]

// Flat list for header title resolution
const allNavItems = [
  { name: 'Centrum', href: '/centrum' },
  ...navSections.flatMap(s => s.items),
]

interface DashboardLayoutProps {
  children: React.ReactNode
}

export default function DashboardLayout({ children }: DashboardLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const { user, tenant, logout, userRole } = useAuth()
  const pathname = usePathname()

  // Auto-expand sections that contain the active page
  const initialExpanded = useMemo(() => {
    const expanded: string[] = []
    for (const section of navSections) {
      if (section.items.some(item => pathname === item.href || pathname?.startsWith(item.href + '/'))) {
        expanded.push(section.id)
      }
    }
    return expanded
  }, [pathname])

  const [expandedSections, setExpandedSections] = useState<string[]>(initialExpanded)

  const toggleSection = (sectionId: string) => {
    setExpandedSections(prev =>
      prev.includes(sectionId)
        ? prev.filter(id => id !== sectionId)
        : [...prev, sectionId]
    )
  }

  const handleLogout = async () => {
    try {
      await logout()
    } catch (error) {
      console.error('Logout failed:', error)
    }
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-950 via-slate-900 to-slate-950 flex">
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
        fixed inset-y-0 left-0 z-50 w-64 bg-slate-900 border-r border-white/5 transform transition-transform duration-300 ease-in-out lg:translate-x-0
        ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'}
      `}>
        <div className="flex flex-col h-full">
          {/* Logo and tenant info */}
          <div className="flex items-center justify-between p-6 border-b border-white/5">
            <div className="flex items-center space-x-3">
              <div className="w-10 h-10 bg-gradient-to-br from-blue-600 to-blue-700 rounded-lg flex items-center justify-center">
                <BarChart3 className="w-6 h-6 text-white" />
              </div>
              <div>
                <h1 className="text-xl font-bold text-white">Logforge</h1>
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
          <nav className="flex-1 px-3 py-4 overflow-y-auto" data-testid="main-navigation">
            {/* Centrum - always visible at top */}
            <Link
              href="/centrum"
              className={`
                group flex items-center px-3 py-2 text-sm font-medium rounded-lg transition-all duration-200 mb-3
                ${pathname === '/centrum'
                  ? 'bg-blue-500/10 text-blue-400 border border-blue-500/20'
                  : 'text-slate-400 hover:text-white hover:bg-white/5'
                }
              `}
              onClick={() => setSidebarOpen(false)}
              data-testid="nav-centrum"
            >
              <Home className={`flex-shrink-0 w-5 h-5 mr-3 ${pathname === '/centrum' ? 'text-blue-400' : 'text-slate-500'}`} />
              <span>Centrum</span>
            </Link>

            {/* Grouped sections */}
            <div className="space-y-1">
              {navSections.map((section) => {
                const isExpanded = expandedSections.includes(section.id)
                const hasActiveChild = section.items.some(
                  item => pathname === item.href || pathname?.startsWith(item.href + '/')
                )

                return (
                  <div key={section.id}>
                    {/* Section header */}
                    <button
                      onClick={() => toggleSection(section.id)}
                      className={`
                        w-full flex items-center justify-between px-3 py-2 text-sm font-medium rounded-lg transition-all duration-200
                        ${hasActiveChild
                          ? 'text-blue-400 bg-blue-500/10'
                          : 'text-slate-400 hover:text-white hover:bg-white/5'
                        }
                      `}
                      data-testid={`nav-section-${section.id}`}
                    >
                      <div className="flex items-center">
                        <section.icon className={`flex-shrink-0 w-4 h-4 mr-2.5 ${hasActiveChild ? 'text-blue-600' : 'text-slate-400'}`} />
                        <span>{section.label}</span>
                      </div>
                      {isExpanded
                        ? <ChevronDown className="w-4 h-4 text-slate-400" />
                        : <ChevronRight className="w-4 h-4 text-slate-400" />
                      }
                    </button>

                    {/* Section items */}
                    {isExpanded && (
                      <div className="ml-4 pl-3 border-l border-white/10 mt-1 mb-2 space-y-0.5">
                        {section.items.map((item) => {
                          const isActive = pathname === item.href || pathname?.startsWith(item.href + '/')
                          return (
                            <Link
                              key={item.name}
                              href={item.href}
                              className={`
                                group flex items-center px-3 py-1.5 text-sm rounded-lg transition-all duration-200
                                ${isActive
                                  ? 'bg-blue-500/10 text-blue-400 font-medium'
                                  : 'text-slate-400 hover:text-white hover:bg-white/5'
                                }
                              `}
                              onClick={() => setSidebarOpen(false)}
                              data-testid={`nav-${item.name.toLowerCase().replace(/\s+/g, '-')}`}
                            >
                              <item.icon className={`flex-shrink-0 w-4 h-4 mr-2.5 ${isActive ? 'text-blue-400' : 'text-slate-500 group-hover:text-slate-400'}`} />
                              <span className="truncate">{item.name}</span>
                              {item.badge && (
                                <Badge
                                  variant={item.badge === 'New' ? 'default' : 'secondary'}
                                  className="ml-auto text-[10px] px-1.5 py-0"
                                  data-testid={`badge-${item.badge.toLowerCase()}`}
                                >
                                  {item.badge}
                                </Badge>
                              )}
                            </Link>
                          )
                        })}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>
          </nav>

          {/* User menu */}
          <div className="p-4 border-t border-white/5">
            <DropdownMenu>
              <DropdownMenuTrigger asChild>
                <Button variant="ghost" className="w-full justify-start h-auto p-3" data-testid="user-menu">
                  <div className="flex items-center space-x-3">
                    <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-blue-700 rounded-full flex items-center justify-center">
                      <User className="w-4 h-4 text-white" />
                    </div>
                    <div className="flex-1 text-left">
                      <p className="text-sm font-medium text-white">
                        {user?.name || user?.email || 'Loading...'}
                      </p>
                      <p className="text-xs text-slate-400 capitalize" data-testid="current-tenant">
                        {userRole} • {tenant?.name}
                      </p>
                    </div>
                    <ChevronDown className="w-4 h-4 text-slate-400" />
                  </div>
                </Button>
              </DropdownMenuTrigger>
              <DropdownMenuContent
                align="end"
                className="w-56 bg-slate-800 border border-white/10 shadow-lg rounded-md p-1 z-50"
                style={{ backdropFilter: 'none' }}
              >
                <DropdownMenuLabel className="px-3 py-2 text-sm font-semibold text-white bg-slate-700/50">
                  Account
                </DropdownMenuLabel>
                <DropdownMenuItem asChild
                  data-testid="profile-settings"
                  className="flex items-center px-3 py-2 text-sm text-slate-300 hover:bg-white/5 hover:text-white cursor-pointer rounded-sm"
                >
                  <Link href="/account"><User className="w-4 h-4 mr-2" />Profile Settings</Link>
                </DropdownMenuItem>
                <DropdownMenuItem
                  data-testid="preferences"
                  className="flex items-center px-3 py-2 text-sm text-slate-300 hover:bg-white/5 hover:text-white cursor-pointer rounded-sm"
                >
                  <Settings className="w-4 h-4 mr-2" />
                  Preferences
                </DropdownMenuItem>
                <DropdownMenuSeparator className="my-1 border-white/10" />
                <DropdownMenuItem
                  onClick={handleLogout}
                  data-testid="logout-button"
                  className="flex items-center px-3 py-2 text-sm text-red-400 hover:bg-red-500/10 hover:text-red-300 cursor-pointer rounded-sm font-medium"
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
      {/* min-w-0: a flex item defaults to min-width:auto, so wide page content
          (e.g. the 14-tactic MITRE row on SIEM) stretched this column past the
          viewport and cut off headers and actions on the right. */}
      <div className="flex-1 min-w-0 lg:ml-64">
        {/* Top header */}
        <header className="sticky top-0 z-40 bg-slate-900/80 backdrop-blur-xl border-b border-white/5 px-4 lg:px-6 py-4">
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
                <h2 className="text-xl font-semibold text-white">
                  {allNavItems.find(item => pathname === item.href || pathname?.startsWith(item.href + '/'))?.name || 'Dashboard'}
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
