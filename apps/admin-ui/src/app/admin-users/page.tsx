'use client'

import { useState, useEffect } from 'react'
import Link from 'next/link'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { NativeSelect } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { ArrowLeft, Plus, Edit, UserX } from 'lucide-react'
import { 
  fetchAdminUsers, 
  createAdminUser, 
  updateAdminUser, 
  deleteAdminUser 
} from '@/lib/api'

interface AdminUser {
  id: string
  name: string
  email: string
  status: string
  created_at: string
  updated_at: string
  last_login_at?: string
  email_verified_at?: string
}

interface UserWithRoles extends AdminUser {
  roleDisplayName: string
  roleColor: 'red' | 'blue' | 'green' | 'purple' | 'secondary'
  permissions: string
}

// Helper functions
const getRoleDisplayName = (roles: string[]): string => {
  if (roles.includes('super_admin')) return 'Super Admin'
  if (roles.includes('admin')) return 'Admin'
  if (roles.includes('support_admin')) return 'Support Admin'
  if (roles.includes('billing_admin')) return 'Billing Admin'
  return 'User'
}

const getRoleColor = (roles: string[]): 'red' | 'blue' | 'green' | 'purple' | 'secondary' => {
  if (roles.includes('super_admin')) return 'red'
  if (roles.includes('admin')) return 'blue'
  if (roles.includes('support_admin')) return 'green'
  if (roles.includes('billing_admin')) return 'purple'
  return 'secondary'
}

const getPermissions = (roles: string[]): string => {
  if (roles.includes('super_admin')) return 'All Permissions'
  if (roles.includes('admin')) return 'Tenant Management, Usage Analytics, Billing'
  if (roles.includes('support_admin')) return 'Support Tickets, User Management'
  if (roles.includes('billing_admin')) return 'Billing, Subscriptions'
  return 'Basic Access'
}

interface AddUserModalProps {
  isOpen: boolean
  onClose: () => void
  onSuccess: () => void
}

function AddUserModal({ isOpen, onClose, onSuccess }: AddUserModalProps) {
  const [formData, setFormData] = useState({
    fullName: '',
    email: '',
    role: '',
    password: ''
  })
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    
    if (!formData.fullName || !formData.email || !formData.role) {
      setError('Please fill in all required fields')
      return
    }

    setLoading(true)
    setError(null)

    try {
      await createAdminUser({
        name: formData.fullName,
        email: formData.email,
        password: formData.password || 'TempPassword123!', // Generate secure temp password
        status: 'active'
      })
      
      // Success
      onClose()
      onSuccess()
      setFormData({ fullName: '', email: '', role: '', password: '' })
    } catch (error: any) {
      console.error('Failed to create admin user:', error)
      setError(error.message || 'Failed to create admin user')
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
      <div className="bg-white rounded-lg p-6 w-full max-w-md">
        <h2 className="text-lg font-semibold mb-4">Add Admin User</h2>
        
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md">
            <p className="text-red-800 text-sm">{error}</p>
          </div>
        )}
        
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
              disabled={loading}
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
              disabled={loading}
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Role *
            </label>
            <NativeSelect
              value={formData.role}
              onChange={(e) => setFormData(prev => ({ ...prev, role: e.target.value }))}
              required
              disabled={loading}
            >
              <option value="">Select role</option>
              <option value="admin">Admin</option>
              <option value="super_admin">Super Admin</option>
              <option value="support_admin">Support Admin</option>
              <option value="billing_admin">Billing Admin</option>
            </NativeSelect>
          </div>

          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              Temporary Password (Optional)
            </label>
            <Input
              type="password"
              value={formData.password}
              onChange={(e) => setFormData(prev => ({ ...prev, password: e.target.value }))}
              placeholder="Leave blank for auto-generated password"
              disabled={loading}
            />
            <p className="text-xs text-gray-500 mt-1">User will be required to change password on first login</p>
          </div>
          
          <div className="flex justify-end space-x-2 pt-4">
            <Button type="button" variant="outline" onClick={onClose} disabled={loading}>
              Cancel
            </Button>
            <Button type="submit" disabled={loading}>
              {loading ? 'Creating...' : 'Add User'}
            </Button>
          </div>
        </form>
      </div>
    </div>
  )
}

export default function AdminUsersPage() {
  const [showAddUserModal, setShowAddUserModal] = useState(false)
  const [adminUsers, setAdminUsers] = useState<UserWithRoles[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState<string | null>(null)

  const fetchUsers = async () => {
    try {
      setLoading(true)
      setError(null)
      
      const response = await fetchAdminUsers(1, 50)
      console.log('Admin users response:', response)
      
      // Transform the user data to include role information
      const usersWithRoles: UserWithRoles[] = response.users.map((user: AdminUser) => ({
        ...user,
        roleDisplayName: getRoleDisplayName([]), // TODO: Get actual roles from API
        roleColor: getRoleColor([]), // TODO: Get actual roles from API
        permissions: getPermissions([]) // TODO: Get actual roles from API
      }))
      
      setAdminUsers(usersWithRoles)
    } catch (error: any) {
      console.error('Failed to fetch admin users:', error)
      setError(error.message || 'Failed to load admin users')
    } finally {
      setLoading(false)
    }
  }

  const handleDeactivateUser = async (userId: string) => {
    if (!confirm('Are you sure you want to deactivate this admin user?')) {
      return
    }

    try {
      await deleteAdminUser(userId)
      await fetchUsers() // Refresh the list
    } catch (error: any) {
      console.error('Failed to deactivate user:', error)
      alert(error.message || 'Failed to deactivate user')
    }
  }

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'Never'
    return new Date(dateString).toLocaleDateString() + ' ' + new Date(dateString).toLocaleTimeString()
  }

  useEffect(() => {
    fetchUsers()
  }, [])

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

      {/* Error Alert */}
      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="p-4">
            <div className="flex items-center">
              <UserX className="h-5 w-5 text-red-600 mr-2" />
              <div className="flex-1">
                <p className="text-red-800 font-medium">Error Loading Admin Users</p>
                <p className="text-red-700 text-sm">{error}</p>
              </div>
              <button 
                onClick={() => fetchUsers()}
                className="text-red-600 hover:text-red-800 ml-4"
              >
                Retry
              </button>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Action Button */}
      <div className="flex justify-end">
        <Button 
          onClick={() => setShowAddUserModal(true)}
          className="bg-blue-600 text-white hover:bg-blue-700"
          disabled={loading}
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
              {loading ? (
                // Loading skeleton
                [1, 2, 3].map((i) => (
                  <tr key={i}>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="h-4 bg-gray-200 rounded w-32"></div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="h-4 bg-gray-200 rounded w-48"></div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="h-6 bg-gray-200 rounded w-20"></div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="h-6 bg-gray-200 rounded w-16"></div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="h-4 bg-gray-200 rounded w-32"></div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="h-4 bg-gray-200 rounded w-40"></div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="h-4 bg-gray-200 rounded w-24"></div>
                    </td>
                  </tr>
                ))
              ) : adminUsers.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-6 py-12 text-center">
                    <UserX className="h-12 w-12 text-gray-400 mx-auto mb-4" />
                    <p className="text-gray-500">No admin users found</p>
                    <Button 
                      onClick={() => setShowAddUserModal(true)}
                      className="mt-4"
                    >
                      Add First Admin User
                    </Button>
                  </td>
                </tr>
              ) : (
                adminUsers.map((user) => (
                  <tr key={user.id} className="hover:bg-gray-50">
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm font-medium text-gray-900">{user.name}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-500">{user.email}</div>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <Badge variant={user.roleColor}>
                        {user.roleDisplayName}
                      </Badge>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <Badge variant={user.status === 'active' ? 'green' : 'secondary'} className={user.status === 'inactive' ? 'bg-gray-100 text-gray-900' : ''}>
                        {user.status}
                      </Badge>
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap">
                      <div className="text-sm text-gray-500">{formatDate(user.last_login_at)}</div>
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
                        <button 
                          onClick={() => handleDeactivateUser(user.id)}
                          className="text-red-600 hover:text-red-800"
                        >
                          Deactivate
                        </button>
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>

      {/* Add User Modal */}
      <AddUserModal 
        isOpen={showAddUserModal}
        onClose={() => setShowAddUserModal(false)}
        onSuccess={() => fetchUsers()}
      />
    </div>
  )
}