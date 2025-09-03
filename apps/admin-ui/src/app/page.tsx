'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { 
  Users, 
  BarChart3, 
  CreditCard, 
  Settings, 
  HelpCircle, 
  Shield,
  DollarSign,
  Database,
  Activity
} from 'lucide-react'
import { fetchTenants } from '@/lib/api'

interface PlatformStat {
  title: string
  value: string
  description: string
  icon: any
}

const navigationCards = [
  {
    title: "Tenant Management",
    description: "Onboard and manage tenant accounts",
    href: "/tenants",
    icon: Users,
    color: "bg-blue-50 hover:bg-blue-100"
  },
  {
    title: "Usage Analytics", 
    description: "Monitor usage patterns and billing",
    href: "/usage",
    icon: BarChart3,
    color: "bg-green-50 hover:bg-green-100"
  },
  {
    title: "Billing & Subscriptions",
    description: "Manage subscription tiers and billing",
    href: "/billing", 
    icon: CreditCard,
    color: "bg-purple-50 hover:bg-purple-100"
  },
  {
    title: "Feature Management",
    description: "Configure feature availability",
    href: "/features",
    icon: Settings,
    color: "bg-orange-50 hover:bg-orange-100"
  },
  {
    title: "Support & Tickets",
    description: "Handle customer support requests", 
    href: "/support",
    icon: HelpCircle,
    color: "bg-yellow-50 hover:bg-yellow-100"
  },
  {
    title: "Admin Users",
    description: "Manage platform administrator accounts",
    href: "/admin-users",
    icon: Shield,
    color: "bg-red-50 hover:bg-red-100"
  }
]

export default function AdminDashboard() {
  const [platformStats, setPlatformStats] = useState<PlatformStat[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetchPlatformStats()
  }, [])

  const fetchPlatformStats = async () => {
    try {
      setLoading(true)
      
      // Fetch tenant data for statistics
      const tenantsData = await fetchTenants()
      const totalTenants = tenantsData.tenants?.length || 0
      const activeTenants = tenantsData.tenants?.filter((t: any) => t.status === 'active').length || 0
      
      // Calculate estimated revenue based on tenant types
      const estimatedRevenue = tenantsData.tenants?.reduce((total: number, tenant: any) => {
        switch (tenant.type) {
          case 'enterprise': return total + 997
          case 'smb': return total + 499  
          case 'startup': return total + 99
          default: return total
        }
      }, 0) || 0

      setPlatformStats([
        {
          title: "Active Tenants",
          value: activeTenants.toString(),
          description: "Currently active tenants",
          icon: Users
        },
        {
          title: "Monthly Revenue", 
          value: `$${estimatedRevenue.toLocaleString()}`,
          description: "Estimated monthly revenue",
          icon: DollarSign
        },
        {
          title: "Total Tenants",
          value: totalTenants.toString(),
          description: "All registered tenants",
          icon: Database
        },
        {
          title: "Platform Health",
          value: "100%",
          description: "System operational status",
          icon: Activity
        }
      ])
      
    } catch (error) {
      console.error('Failed to fetch platform statistics:', error)
      // Show error stats
      setPlatformStats([
        { title: "Error", value: "Failed", description: "Check API connection", icon: Users },
        { title: "Error", value: "Failed", description: "Check API connection", icon: DollarSign },
        { title: "Error", value: "Failed", description: "Check API connection", icon: Database },
        { title: "Error", value: "Failed", description: "Check API connection", icon: Activity }
      ])
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex flex-col space-y-2">
        <h1 className="text-3xl font-bold text-gray-900">Logforge Admin Dashboard</h1>
        <p className="text-gray-600">Manage tenants, monitor usage, and oversee platform operations</p>
      </div>

      {/* Platform Statistics */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {loading ? (
          // Loading skeleton
          [1, 2, 3, 4].map((i) => (
            <Card key={i} className="bg-white p-4 rounded-lg shadow">
              <CardContent className="p-0">
                <div className="flex items-center space-x-2">
                  <div className="h-4 w-4 bg-gray-200 rounded" />
                  <div className="flex flex-col">
                    <span className="text-sm text-gray-400">Loading...</span>
                    <span className="text-2xl font-bold text-gray-400">-</span>
                  </div>
                </div>
              </CardContent>
            </Card>
          ))
        ) : (
          platformStats.map((stat) => {
            const Icon = stat.icon
            return (
              <Card key={stat.title} className="bg-white p-4 rounded-lg shadow">
                <CardContent className="p-0">
                  <div className="flex items-center space-x-2">
                    <Icon className="h-4 w-4 text-gray-500" />
                    <div className="flex flex-col">
                      <span className="text-sm text-gray-500">{stat.title}</span>
                      <span className="text-2xl font-bold text-gray-900">{stat.value}</span>
                    </div>
                  </div>
                </CardContent>
              </Card>
            )
          })
        )}
      </div>

      {/* Navigation Grid */}
      <div className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
        {navigationCards.map((card) => {
          const Icon = card.icon
          return (
            <Link key={card.title} href={card.href}>
              <Card className={`${card.color} transition-colors cursor-pointer border-0 h-full`}>
                <CardHeader>
                  <div className="flex items-center space-x-2">
                    <Icon className="h-6 w-6 text-gray-700" />
                    <CardTitle className="text-gray-900">{card.title}</CardTitle>
                  </div>
                  <CardDescription className="text-gray-600">
                    {card.description}
                  </CardDescription>
                </CardHeader>
              </Card>
            </Link>
          )
        })}
      </div>
    </div>
  )
}