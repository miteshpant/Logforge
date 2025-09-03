'use client'

import { useState } from 'react'
import Link from 'next/link'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { ArrowLeft, Plus, Edit, UserX } from 'lucide-react'

const mockAdminUsers = [
  {
    id: "au001",
    name: "Sarah Johnson",
    email: "sarah.johnson@logforge.com", 
    role: "Super Admin",
    status: "Active",
    lastLogin: "2024-01-15 09:30:00",
    permissions: "All Permissions",
    roleColor: "red" as const
  },
  {
    id: "au002",
    name: "Mike Chen",
    email: "mike.chen@logforge.com",
    role: "Admin", 
    status: "Active",
    lastLogin: "2024-01-14 16:45:00",
    permissions: "Tenant Management, Usage Analytics, Billing",
    roleColor: "blue" as const
  },
  {
    id: "au003",
    name: "Emily Rodriguez",
    email: "emily.rodriguez@logforge.com",
    role: "Support Admin",
    status: "Active", 
    lastLogin: "2024-01-13 11:20:00",
    permissions: "Support Tickets, User Management",
    roleColor: "green" as const
  },
  {
    id: "au004",
    name: "David Park",
    email: "david.park@logforge.com",
    role: "Billing Admin",
    status: "Inactive",
    lastLogin: "2024-01-10 14:15:00", 
    permissions: "Billing, Subscriptions",
    roleColor: "purple" as const
  }
]

interface AddUserModalProps {
  isOpen: boolean
  onClose: () => void
}

function AddUserModal({ isOpen, onClose }: AddUserModalProps) {
  const [formData, setFormData] = useState({
    fullName: '',
    email: '',
    role: ''
  })

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!formData.fullName || !formData.email || !formData.role) {
      return
    }

    try {
      const response = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/v1/admin/users`, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: formData.fullName,
          email: formData.email,
          role: formData.role
        })
      })
      
      if (response.ok) {
        onClose()
        setFormData({ fullName: '', email: '', role: '' })
        window.location.reload()
      }
    } catch (error) {
      console.error('Failed to create admin user:', error)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md">
        <h2 className="text-lg font-semibold mb-4">Add Admin User</h2>
        
        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Full Name *
            </label>
            <Input
              type="text"
              value={formData.fullName}
              onChange={(e) => setFormData(prev => ({ ...prev, fullName: e.target.value }))}
              placeholder="Enter full name"
              required
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Email Address *
            </label>
            <Input
              type="email"
              value={formData.email}
              onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
              placeholder="user@logforge.com"
              required
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Role *
            </label>
            <Select
              value={formData.role}
              onChange={(e) => setFormData(prev => ({ ...prev, role: e.target.value }))}
              required
            >
              <option value="">Select role</option>
              <option value="admin">Admin</option>
              <option value="super_admin">Super Admin</option>
              <option value="support_admin">Support Admin</option>
              <option value="billing_admin">Billing Admin</option>
            </Select>
          </div>
          
          <div className="flex justify-end space-x-2 pt-4">
            <Button type="button" variant="outline" onClick={onClose}>
              Cancel
            </Button>
            <Button type="submit">
              Add User
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function AdminUsersPage() {
  const [showAddUserModal, setShowAddUserModal] = useState(false)

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Link href="/" className="text-blue-600 hover:text-blue-800 flex items-center">
            <ArrowLeft className="h-4 w-4 mr-1" />
            ← Back to Dashboard
          </Link>
        </div>
      </div>
      
      <div className="flex flex-col space-y-2">
        <h1 className="text-3xl font-bold text-gray-900">Admin User Management</h1>
        <p className="text-gray-600">Manage platform administrator accounts and permissions</p>
      </div>

      {/* Action Button */}
      <div className="flex justify-end">
        <Button 
          onClick={() => setShowAddUserModal(true)}
          className="bg-blue-600 text-white hover:bg-blue-700"
        >
          <Plus className="h-4 w-4 mr-2" />
          Add Admin User
        </Button>
      </div>

      {/* Admin Users Table */}
      <Card className="bg-white rounded-lg shadow">
        <div className="overflow-x-auto">
          <table className="min-w-full">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Name
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Email
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Role
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Status
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Last Login
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Permissions
                </th>
                <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Actions
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {mockAdminUsers.map((user) => (
                <tr key={user.id} className="hover:bg-gray-50">
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm font-medium text-gray-900">{user.name}</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm text-gray-500">{user.email}</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <Badge variant={user.roleColor}>
                      {user.role}
                    </Badge>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <Badge variant={user.status === 'Active' ? 'green' : 'secondary'} className={user.status === 'Inactive' ? 'bg-gray-100 text-gray-900' : ''}>
                      {user.status}
                    </Badge>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap">
                    <div className="text-sm text-gray-500">{user.lastLogin}</div>
                  </td>
                  <td className="px-6 py-4">
                    <div className="text-sm text-gray-500 max-w-xs truncate">{user.permissions}</div>
                  </td>
                  <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                    <div className="flex space-x-2">
                      <Link href={`/admin-users/${user.id}`} className="text-blue-600 hover:text-blue-800">
                        Edit
                      </Link>
                      <span className="text-gray-300">|</span>
                      <button className="text-red-600 hover:text-red-800">
                        Deactivate
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Add User Modal */}
      <AddUserModal 
        isOpen={showAddUserModal}
        onClose={() => setShowAddUserModal(false)}
      />
    </div>
  )
}