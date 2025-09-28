'use client'

import { useState, useEffect } from 'react'
import { useParams, useRouter } from 'next/navigation'
import Link from 'next/link'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Select } from '@/components/ui/select'
import { Badge } from '@/components/ui/badge'
import { ArrowLeft, Save, UserX, Shield, Clock } from 'lucide-react'
import { 
  getAdminUser, 
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

export default function AdminUserEditPage() {
  const params = useParams()
  const router = useRouter()
  const userId = params.id as string

  const [user, setUser] = useState<AdminUser | null>(null)
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [successMessage, setSuccessMessage] = useState<string | null>(null)

  const [formData, setFormData] = useState({
    name: '',
    email: '',
    status: 'active',
    role: 'admin'
  })

  const fetchUser = async () => {
    try {
      setLoading(true)
      setError(null)
      
      const userData = await getAdminUser(userId)
      console.log('User data:', userData)
      
      setUser(userData)
      setFormData({
        name: userData.name || '',
        email: userData.email || '',
        status: userData.status || 'active',
        role: 'admin' // TODO: Get actual role from API
      })
    } catch (error: any) {
      console.error('Failed to fetch user:', error)
      setError(error.message || 'Failed to load user details')
    } finally {
      setLoading(false)
    }
  }

  const handleSave = async () => {
    try {
      setSaving(true)
      setError(null)
      setSuccessMessage(null)

      await updateAdminUser(userId, {
        name: formData.name,
        email: formData.email,
        status: formData.status
      })

      setSuccessMessage('User updated successfully!')
      await fetchUser() // Refresh user data
      
      // Clear success message after 3 seconds
      setTimeout(() => setSuccessMessage(null), 3000)
    } catch (error: any) {
      console.error('Failed to update user:', error)
      setError(error.message || 'Failed to update user')
    } finally {
      setSaving(false)
    }
  }

  const handleDelete = async () => {
    if (!confirm('Are you sure you want to permanently delete this admin user? This action cannot be undone.')) {
      return
    }

    try {
      setSaving(true)
      await deleteAdminUser(userId)
      router.push('/admin-users')
    } catch (error: any) {
      console.error('Failed to delete user:', error)
      setError(error.message || 'Failed to delete user')
      setSaving(false)
    }
  }

  const getRoleColor = (role: string): 'red' | 'blue' | 'green' | 'purple' | 'secondary' => {
    switch (role) {
      case 'super_admin': return 'red'
      case 'admin': return 'blue'
      case 'support_admin': return 'green'
      case 'billing_admin': return 'purple'
      default: return 'secondary'
    }
  }

  const getRoleDisplayName = (role: string): string => {
    switch (role) {
      case 'super_admin': return 'Super Admin'
      case 'admin': return 'Admin'
      case 'support_admin': return 'Support Admin'
      case 'billing_admin': return 'Billing Admin'
      default: return 'User'
    }
  }

  const formatDate = (dateString?: string) => {
    if (!dateString) return 'Never'
    return new Date(dateString).toLocaleDateString() + ' at ' + new Date(dateString).toLocaleTimeString()
  }

  useEffect(() => {
    if (userId) {
      fetchUser()
    }
  }, [userId])

  if (loading) {
    return (
      <div className="space-y-8">
        <div className="flex items-center space-x-4">
          <Link href="/admin-users" className="text-blue-600 hover:text-blue-800 flex items-center">
            <ArrowLeft className="h-4 w-4 mr-1" />
            ← Back to Admin Users
          </Link>
        </div>
        
        <div className="flex flex-col space-y-2">
          <div className="h-8 bg-gray-200 rounded w-64"></div>
          <div className="h-4 bg-gray-200 rounded w-96"></div>
        </div>

        <Card>
          <CardContent className="p-6 space-y-4">
            {[1, 2, 3, 4].map(i => (
              <div key={i} className="space-y-2">
                <div className="h-4 bg-gray-200 rounded w-24"></div>
                <div className="h-10 bg-gray-200 rounded w-full"></div>
              </div>
            ))}
          </CardContent>
        </Card>
      </div>
    )
  }

  if (error && !user) {
    return (
      <div className="space-y-8">
        <div className="flex items-center space-x-4">
          <Link href="/admin-users" className="text-blue-600 hover:text-blue-800 flex items-center">
            <ArrowLeft className="h-4 w-4 mr-1" />
            ← Back to Admin Users
          </Link>
        </div>
        
        <Card className="border-red-200 bg-red-50">
          <CardContent className="p-6">
            <div className="flex items-center">
              <UserX className="h-8 w-8 text-red-600 mr-4" />
              <div>
                <h2 className="text-lg font-semibold text-red-800">User Not Found</h2>
                <p className="text-red-700">{error}</p>
                <Button 
                  onClick={() => fetchUser()}
                  className="mt-4"
                  variant="outline"
                >
                  Try Again
                </Button>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    )
  }

  return (
    <div className="space-y-8">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="flex items-center space-x-4">
          <Link href="/admin-users" className="text-blue-600 hover:text-blue-800 flex items-center">
            <ArrowLeft className="h-4 w-4 mr-1" />
            ← Back to Admin Users
          </Link>
        </div>
        
        <div className="flex space-x-2">
          <Button
            onClick={handleSave}
            disabled={saving}
            className="bg-blue-600 text-white hover:bg-blue-700"
          >
            <Save className="h-4 w-4 mr-2" />
            {saving ? 'Saving...' : 'Save Changes'}
          </Button>
          
          <Button
            onClick={handleDelete}
            disabled={saving}
            variant="outline"
            className="text-red-600 border-red-300 hover:bg-red-50"
          >
            <UserX className="h-4 w-4 mr-2" />
            Delete User
          </Button>
        </div>
      </div>
      
      <div className="flex flex-col space-y-2">
        <h1 className="text-3xl font-bold text-gray-900">Edit Admin User</h1>
        <p className="text-gray-600">Manage admin user account and permissions</p>
      </div>

      {/* Success/Error Messages */}
      {successMessage && (
        <Card className="border-green-200 bg-green-50">
          <CardContent className="p-4">
            <p className="text-green-800">{successMessage}</p>
          </CardContent>
        </Card>
      )}

      {error && (
        <Card className="border-red-200 bg-red-50">
          <CardContent className="p-4">
            <p className="text-red-800">{error}</p>
          </CardContent>
        </Card>
      )}

      <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
        {/* Main Form */}
        <div className="lg:col-span-2">
          <Card>
            <CardHeader>
              <CardTitle>User Information</CardTitle>
            </CardHeader>
            <CardContent className="space-y-6">
              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Full Name *
                </label>
                <Input
                  type="text"
                  value={formData.name}
                  onChange={(e) => setFormData(prev => ({ ...prev, name: e.target.value }))}
                  placeholder="Enter full name"
                  disabled={saving}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Email Address *
                </label>
                <Input
                  type="email"
                  value={formData.email}
                  onChange={(e) => setFormData(prev => ({ ...prev, email: e.target.value }))}
                  placeholder="user@logforge.com"
                  disabled={saving}
                />
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Role *
                </label>
                <Select
                  value={formData.role}
                  onChange={(e) => setFormData(prev => ({ ...prev, role: e.target.value }))}
                  disabled={saving}
                >
                  <option value="admin">Admin</option>
                  <option value="super_admin">Super Admin</option>
                  <option value="support_admin">Support Admin</option>
                  <option value="billing_admin">Billing Admin</option>
                </Select>
              </div>

              <div>
                <label className="block text-sm font-medium text-gray-700 mb-2">
                  Status *
                </label>
                <Select
                  value={formData.status}
                  onChange={(e) => setFormData(prev => ({ ...prev, status: e.target.value }))}
                  disabled={saving}
                >
                  <option value="active">Active</option>
                  <option value="inactive">Inactive</option>
                  <option value="pending">Pending</option>
                </Select>
              </div>
            </CardContent>
          </Card>
        </div>

        {/* Sidebar Info */}
        <div className="space-y-6">
          {/* User Status */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Shield className="h-5 w-5 mr-2" />
                User Status
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Current Role:</span>
                <Badge variant={getRoleColor(formData.role)}>
                  {getRoleDisplayName(formData.role)}
                </Badge>
              </div>
              
              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Status:</span>
                <Badge variant={formData.status === 'active' ? 'green' : 'secondary'}>
                  {formData.status}
                </Badge>
              </div>

              <div className="flex items-center justify-between">
                <span className="text-sm text-gray-600">Email Verified:</span>
                <span className="text-sm text-gray-900">
                  {user?.email_verified_at ? 'Yes' : 'No'}
                </span>
              </div>
            </CardContent>
          </Card>

          {/* Activity Info */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center">
                <Clock className="h-5 w-5 mr-2" />
                Activity
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div>
                <p className="text-sm text-gray-600">Created:</p>
                <p className="text-sm text-gray-900">{formatDate(user?.created_at)}</p>
              </div>
              
              <div>
                <p className="text-sm text-gray-600">Last Updated:</p>
                <p className="text-sm text-gray-900">{formatDate(user?.updated_at)}</p>
              </div>
              
              <div>
                <p className="text-sm text-gray-600">Last Login:</p>
                <p className="text-sm text-gray-900">{formatDate(user?.last_login_at)}</p>
              </div>
            </CardContent>
          </Card>

          {/* Security Actions */}
          <Card>
            <CardHeader>
              <CardTitle>Security Actions</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Button 
                variant="outline" 
                className="w-full"
                disabled={saving}
              >
                Reset Password
              </Button>
              
              <Button 
                variant="outline" 
                className="w-full"
                disabled={saving}
              >
                Revoke Sessions
              </Button>
              
              <Button 
                variant="outline" 
                className="w-full text-red-600 border-red-300 hover:bg-red-50"
                disabled={saving}
              >
                Send Password Reset
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}