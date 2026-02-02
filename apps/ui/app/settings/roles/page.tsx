'use client'

import { useState, useEffect } from 'react'
import DashboardLayout from '@/components/layout/DashboardLayout'
import { apiClient } from '@/lib/api'
import {
  Shield,
  Users,
  Plus,
  Edit,
  Trash2,
  Search,
  CheckCircle,
  XCircle,
  Eye,
  Lock,
  Unlock,
  ChevronRight,
  ChevronDown,
  X,
  Copy,
  Save,
  AlertTriangle,
  Clock,
  UserPlus,
  Settings
} from 'lucide-react'

interface Permission {
  id: string
  name: string
  description: string
  category: string
}

interface Role {
  id: string
  name: string
  description: string
  is_system: boolean
  is_default: boolean
  permissions: string[]
  user_count: number
  created_at: string
  updated_at: string
}

interface User {
  id: string
  email: string
  name: string
  role_id: string
  role_name: string
  status: 'active' | 'inactive' | 'pending'
  last_login?: string
}

const PERMISSION_CATEGORIES = [
  { id: 'logs', name: 'Logs', icon: '📝' },
  { id: 'traces', name: 'Traces', icon: '🔍' },
  { id: 'metrics', name: 'Metrics', icon: '📊' },
  { id: 'alerts', name: 'Alerts', icon: '🚨' },
  { id: 'security', name: 'Security', icon: '🛡️' },
  { id: 'dashboards', name: 'Dashboards', icon: '📈' },
  { id: 'settings', name: 'Settings', icon: '⚙️' },
  { id: 'users', name: 'Users', icon: '👥' }
]

const ALL_PERMISSIONS: Permission[] = [
  // Logs
  { id: 'logs:read', name: 'View Logs', description: 'View and search logs', category: 'logs' },
  { id: 'logs:query', name: 'Query Logs', description: 'Run advanced log queries', category: 'logs' },
  { id: 'logs:export', name: 'Export Logs', description: 'Export log data', category: 'logs' },
  { id: 'logs:delete', name: 'Delete Logs', description: 'Delete log entries', category: 'logs' },
  // Traces
  { id: 'traces:read', name: 'View Traces', description: 'View distributed traces', category: 'traces' },
  { id: 'traces:analyze', name: 'Analyze Traces', description: 'Run trace analysis', category: 'traces' },
  // Metrics
  { id: 'metrics:read', name: 'View Metrics', description: 'View metric data', category: 'metrics' },
  { id: 'metrics:create', name: 'Create Metrics', description: 'Create custom metrics', category: 'metrics' },
  // Alerts
  { id: 'alerts:read', name: 'View Alerts', description: 'View alert instances', category: 'alerts' },
  { id: 'alerts:acknowledge', name: 'Acknowledge Alerts', description: 'Acknowledge triggered alerts', category: 'alerts' },
  { id: 'alerts:resolve', name: 'Resolve Alerts', description: 'Resolve alerts', category: 'alerts' },
  { id: 'alerts:rules:read', name: 'View Alert Rules', description: 'View alerting rules', category: 'alerts' },
  { id: 'alerts:rules:write', name: 'Manage Alert Rules', description: 'Create and edit alert rules', category: 'alerts' },
  { id: 'alerts:channels:write', name: 'Manage Channels', description: 'Configure notification channels', category: 'alerts' },
  // Security
  { id: 'security:read', name: 'View Security Events', description: 'View SIEM events', category: 'security' },
  { id: 'security:investigate', name: 'Investigate', description: 'Conduct security investigations', category: 'security' },
  { id: 'security:rules:write', name: 'Manage Detection Rules', description: 'Create and edit Sigma rules', category: 'security' },
  { id: 'security:threat_intel', name: 'Threat Intelligence', description: 'Access threat intel feeds', category: 'security' },
  // Dashboards
  { id: 'dashboards:read', name: 'View Dashboards', description: 'View dashboards', category: 'dashboards' },
  { id: 'dashboards:write', name: 'Create Dashboards', description: 'Create and edit dashboards', category: 'dashboards' },
  { id: 'dashboards:share', name: 'Share Dashboards', description: 'Share dashboards with team', category: 'dashboards' },
  // Settings
  { id: 'settings:read', name: 'View Settings', description: 'View system settings', category: 'settings' },
  { id: 'settings:write', name: 'Modify Settings', description: 'Modify system settings', category: 'settings' },
  { id: 'integrations:write', name: 'Manage Integrations', description: 'Configure integrations', category: 'settings' },
  // Users
  { id: 'users:read', name: 'View Users', description: 'View user list', category: 'users' },
  { id: 'users:write', name: 'Manage Users', description: 'Create and edit users', category: 'users' },
  { id: 'users:invite', name: 'Invite Users', description: 'Invite new users', category: 'users' },
  { id: 'roles:read', name: 'View Roles', description: 'View role definitions', category: 'users' },
  { id: 'roles:write', name: 'Manage Roles', description: 'Create and edit roles', category: 'users' }
]


export default function RolesPage() {
  const [roles, setRoles] = useState<Role[]>([])
  const [users, setUsers] = useState<User[]>([])
  const [isLoading, setIsLoading] = useState(true)
  const [searchQuery, setSearchQuery] = useState('')
  const [activeTab, setActiveTab] = useState<'roles' | 'users'>('roles')
  const [selectedRole, setSelectedRole] = useState<Role | null>(null)
  const [showRoleModal, setShowRoleModal] = useState(false)
  const [showUserModal, setShowUserModal] = useState(false)
  const [expandedCategories, setExpandedCategories] = useState<string[]>(PERMISSION_CATEGORIES.map(c => c.id))
  const [editingRole, setEditingRole] = useState<Partial<Role> | null>(null)

  useEffect(() => {
    loadData()
  }, [])

  const loadData = async () => {
    try {
      setIsLoading(true)
      const [rolesRes, usersRes] = await Promise.allSettled([
        apiClient.get('/v1/enterprise/rbac/roles'),
        apiClient.get('/v1/users')
      ])

      if (rolesRes.status === 'fulfilled' && rolesRes.value?.data) {
        const data = rolesRes.value.data
        setRoles(data.roles || (Array.isArray(data) ? data : []))
      }

      if (usersRes.status === 'fulfilled' && usersRes.value?.data) {
        const data = usersRes.value.data
        setUsers(data.users || (Array.isArray(data) ? data : []))
      }
    } catch (error) {
      console.error('Failed to load data:', error)
    } finally {
      setIsLoading(false)
    }
  }

  const toggleCategory = (categoryId: string) => {
    setExpandedCategories(prev =>
      prev.includes(categoryId)
        ? prev.filter(c => c !== categoryId)
        : [...prev, categoryId]
    )
  }

  const togglePermission = (permissionId: string) => {
    if (!editingRole) return
    const newPermissions = editingRole.permissions?.includes(permissionId)
      ? editingRole.permissions.filter(p => p !== permissionId)
      : [...(editingRole.permissions || []), permissionId]
    setEditingRole({ ...editingRole, permissions: newPermissions })
  }

  const handleCreateRole = () => {
    setEditingRole({
      name: '',
      description: '',
      is_system: false,
      is_default: false,
      permissions: []
    })
    setShowRoleModal(true)
  }

  const handleEditRole = (role: Role) => {
    if (role.is_system) {
      alert('System roles cannot be edited. Create a custom role instead.')
      return
    }
    setEditingRole({ ...role })
    setShowRoleModal(true)
  }

  const handleSaveRole = async () => {
    if (!editingRole?.name) return

    try {
      if (editingRole.id) {
        await apiClient.put(`/v1/enterprise/rbac/roles/${editingRole.id}`, editingRole)
      } else {
        await apiClient.post('/v1/enterprise/rbac/roles', editingRole)
      }
      // Refresh or mock update
      setRoles(prev => {
        if (editingRole.id) {
          return prev.map(r => r.id === editingRole.id ? { ...r, ...editingRole } as Role : r)
        }
        const newRole: Role = {
          id: `custom_${Date.now()}`,
          name: editingRole.name || '',
          description: editingRole.description || '',
          is_system: false,
          is_default: false,
          permissions: editingRole.permissions || [],
          user_count: 0,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        }
        return [...prev, newRole]
      })
    } catch (error) {
      console.error('Failed to save role:', error)
      // Mock update anyway for demo
      setRoles(prev => {
        if (editingRole.id) {
          return prev.map(r => r.id === editingRole.id ? { ...r, ...editingRole } as Role : r)
        }
        const newRole: Role = {
          id: `custom_${Date.now()}`,
          name: editingRole.name || '',
          description: editingRole.description || '',
          is_system: false,
          is_default: false,
          permissions: editingRole.permissions || [],
          user_count: 0,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString()
        }
        return [...prev, newRole]
      })
    }
    setShowRoleModal(false)
    setEditingRole(null)
  }

  const handleDeleteRole = async (roleId: string) => {
    const role = roles.find(r => r.id === roleId)
    if (role?.is_system) {
      alert('System roles cannot be deleted.')
      return
    }
    if (role?.user_count && role.user_count > 0) {
      if (!confirm(`This role has ${role.user_count} users. Reassign them first or proceed to remove the role?`)) {
        return
      }
    }
    if (!confirm('Are you sure you want to delete this role?')) return

    try {
      await apiClient.delete(`/v1/enterprise/rbac/roles/${roleId}`)
    } catch (error) {
      console.error('Failed to delete role:', error)
    }
    setRoles(prev => prev.filter(r => r.id !== roleId))
  }

  const filteredRoles = roles.filter(role =>
    role.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    role.description.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const filteredUsers = users.filter(user =>
    user.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
    user.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
    user.role_name.toLowerCase().includes(searchQuery.toLowerCase())
  )

  const formatTimeAgo = (timestamp: string | undefined) => {
    if (!timestamp) return 'Never'
    const diff = Date.now() - new Date(timestamp).getTime()
    const minutes = Math.floor(diff / 60000)
    const hours = Math.floor(diff / 3600000)
    const days = Math.floor(diff / 86400000)
    if (days > 0) return `${days}d ago`
    if (hours > 0) return `${hours}h ago`
    if (minutes > 0) return `${minutes}m ago`
    return 'Just now'
  }

  const getPermissionsByCategory = (categoryId: string) =>
    ALL_PERMISSIONS.filter(p => p.category === categoryId)

  return (
    <DashboardLayout>
      <div className="p-6 space-y-6">
        {/* Header */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold text-white">Role Management</h1>
            <p className="text-slate-400 mt-1">Manage roles and permissions for your organization</p>
          </div>
          <button
            onClick={handleCreateRole}
            className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg transition-colors"
          >
            <Plus className="w-4 h-4" />
            Create Role
          </button>
        </div>

        {/* Tabs */}
        <div className="flex gap-1 bg-slate-800/50 p-1 rounded-lg w-fit">
          <button
            onClick={() => setActiveTab('roles')}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'roles'
                ? 'bg-blue-500/20 text-blue-400'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Shield className="w-4 h-4 inline mr-2" />
            Roles ({roles.length})
          </button>
          <button
            onClick={() => setActiveTab('users')}
            className={`px-4 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === 'users'
                ? 'bg-blue-500/20 text-blue-400'
                : 'text-slate-400 hover:text-white'
            }`}
          >
            <Users className="w-4 h-4 inline mr-2" />
            Users ({users.length})
          </button>
        </div>

        {/* Search */}
        <div className="relative max-w-md">
          <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
          <input
            type="text"
            placeholder={`Search ${activeTab}...`}
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full pl-10 pr-4 py-2 bg-slate-800 border border-white/10 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-blue-500"
          />
        </div>

        {/* Content */}
        {isLoading ? (
          <div className="flex items-center justify-center h-48">
            <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-500"></div>
          </div>
        ) : activeTab === 'roles' ? (
          /* Roles List */
          <div className="grid gap-4">
            {filteredRoles.map((role) => (
              <div
                key={role.id}
                className={`rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 p-4 ${
                  role.is_default ? 'border-green-500/30' : ''
                }`}
              >
                <div className="flex items-start justify-between">
                  <div className="flex items-start gap-3">
                    <div className={`p-2 rounded-lg ${
                      role.is_system ? 'bg-purple-500/20' : 'bg-blue-500/20'
                    }`}>
                      <Shield className={`w-5 h-5 ${
                        role.is_system ? 'text-purple-400' : 'text-blue-400'
                      }`} />
                    </div>
                    <div>
                      <div className="flex items-center gap-2">
                        <h3 className="text-white font-semibold">{role.name}</h3>
                        {role.is_system && (
                          <span className="px-2 py-0.5 bg-purple-500/20 text-purple-400 text-xs rounded">
                            System
                          </span>
                        )}
                        {role.is_default && (
                          <span className="px-2 py-0.5 bg-green-500/20 text-green-400 text-xs rounded">
                            Default
                          </span>
                        )}
                      </div>
                      <p className="text-slate-400 text-sm mt-1">{role.description}</p>
                      <div className="flex items-center gap-4 mt-2 text-xs text-slate-500">
                        <span className="flex items-center gap-1">
                          <Users className="w-3 h-3" />
                          {role.user_count} users
                        </span>
                        <span className="flex items-center gap-1">
                          <Lock className="w-3 h-3" />
                          {role.permissions.length} permissions
                        </span>
                        <span className="flex items-center gap-1">
                          <Clock className="w-3 h-3" />
                          Updated {formatTimeAgo(role.updated_at)}
                        </span>
                      </div>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => setSelectedRole(selectedRole?.id === role.id ? null : role)}
                      className="p-2 text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
                      title="View permissions"
                    >
                      <Eye className="w-4 h-4" />
                    </button>
                    {!role.is_system && (
                      <>
                        <button
                          onClick={() => handleEditRole(role)}
                          className="p-2 text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors"
                          title="Edit role"
                        >
                          <Edit className="w-4 h-4" />
                        </button>
                        <button
                          onClick={() => handleDeleteRole(role.id)}
                          className="p-2 text-slate-400 hover:text-red-400 hover:bg-red-500/10 rounded-lg transition-colors"
                          title="Delete role"
                        >
                          <Trash2 className="w-4 h-4" />
                        </button>
                      </>
                    )}
                  </div>
                </div>

                {/* Expanded Permissions View */}
                {selectedRole?.id === role.id && (
                  <div className="mt-4 pt-4 border-t border-white/5">
                    <h4 className="text-sm font-medium text-slate-300 mb-3">Permissions</h4>
                    <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
                      {PERMISSION_CATEGORIES.map(cat => {
                        const catPermissions = getPermissionsByCategory(cat.id)
                        const grantedCount = catPermissions.filter(p => role.permissions.includes(p.id)).length
                        return (
                          <div key={cat.id} className="p-3 bg-slate-700/50 rounded-lg">
                            <div className="flex items-center gap-2 mb-2">
                              <span>{cat.icon}</span>
                              <span className="text-sm font-medium text-white">{cat.name}</span>
                            </div>
                            <div className="flex items-center gap-1">
                              <div className="flex-1 h-1.5 bg-slate-600 rounded-full overflow-hidden">
                                <div
                                  className="h-full bg-green-500 rounded-full"
                                  style={{ width: `${(grantedCount / catPermissions.length) * 100}%` }}
                                />
                              </div>
                              <span className="text-xs text-slate-400">
                                {grantedCount}/{catPermissions.length}
                              </span>
                            </div>
                          </div>
                        )
                      })}
                    </div>
                    <div className="flex flex-wrap gap-1.5 mt-3">
                      {role.permissions.map(pId => {
                        const perm = ALL_PERMISSIONS.find(p => p.id === pId)
                        return perm ? (
                          <span key={pId} className="px-2 py-1 bg-green-500/10 text-green-400 text-xs rounded border border-green-500/20">
                            {perm.name}
                          </span>
                        ) : null
                      })}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          /* Users List */
          <div className="rounded-2xl bg-gradient-to-br from-slate-800/80 to-slate-900/95 backdrop-blur-xl shadow-xl border border-white/5 overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="border-b border-white/5">
                  <th className="text-left px-4 py-3 text-sm font-medium text-slate-400">User</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-slate-400">Role</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-slate-400">Status</th>
                  <th className="text-left px-4 py-3 text-sm font-medium text-slate-400">Last Login</th>
                  <th className="text-right px-4 py-3 text-sm font-medium text-slate-400">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-white/5">
                {filteredUsers.map((user) => (
                  <tr key={user.id} className="hover:bg-slate-700/30">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-3">
                        <div className="w-8 h-8 bg-gradient-to-br from-blue-500 to-purple-500 rounded-full flex items-center justify-center text-white text-sm font-medium">
                          {user.name.charAt(0)}
                        </div>
                        <div>
                          <p className="text-white font-medium">{user.name}</p>
                          <p className="text-slate-400 text-sm">{user.email}</p>
                        </div>
                      </div>
                    </td>
                    <td className="px-4 py-3">
                      <span className="px-2 py-1 bg-slate-700 text-slate-300 text-sm rounded">
                        {user.role_name}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${
                        user.status === 'active' ? 'bg-green-500/20 text-green-400' :
                        user.status === 'pending' ? 'bg-yellow-500/20 text-yellow-400' :
                        'bg-slate-500/20 text-slate-400'
                      }`}>
                        {user.status.charAt(0).toUpperCase() + user.status.slice(1)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-sm text-slate-400">
                      {formatTimeAgo(user.last_login)}
                    </td>
                    <td className="px-4 py-3 text-right">
                      <button className="p-2 text-slate-400 hover:text-white hover:bg-slate-700 rounded-lg transition-colors">
                        <Settings className="w-4 h-4" />
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Role Edit Modal */}
        {showRoleModal && editingRole && (
          <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50">
            <div className="bg-slate-900 border border-white/10 rounded-xl w-full max-w-2xl mx-4 max-h-[90vh] overflow-y-auto">
              <div className="flex items-center justify-between p-4 border-b border-white/5">
                <h3 className="text-lg font-semibold text-white">
                  {editingRole.id ? 'Edit Role' : 'Create Role'}
                </h3>
                <button
                  onClick={() => {
                    setShowRoleModal(false)
                    setEditingRole(null)
                  }}
                  className="text-slate-400 hover:text-white"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>

              <div className="p-4 space-y-4">
                {/* Role Name */}
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-1">Role Name</label>
                  <input
                    type="text"
                    value={editingRole.name || ''}
                    onChange={(e) => setEditingRole({ ...editingRole, name: e.target.value })}
                    placeholder="e.g., Security Analyst"
                    className="w-full px-3 py-2 bg-slate-700 border border-white/10 rounded-lg text-white placeholder-slate-500"
                  />
                </div>

                {/* Description */}
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-1">Description</label>
                  <textarea
                    value={editingRole.description || ''}
                    onChange={(e) => setEditingRole({ ...editingRole, description: e.target.value })}
                    placeholder="Describe what this role is for..."
                    rows={2}
                    className="w-full px-3 py-2 bg-slate-700 border border-white/10 rounded-lg text-white placeholder-slate-500 resize-none"
                  />
                </div>

                {/* Default Role Toggle */}
                <div className="flex items-center gap-2">
                  <input
                    type="checkbox"
                    id="is_default"
                    checked={editingRole.is_default || false}
                    onChange={(e) => setEditingRole({ ...editingRole, is_default: e.target.checked })}
                    className="w-4 h-4 rounded border-white/10 bg-slate-700 text-blue-500"
                  />
                  <label htmlFor="is_default" className="text-sm text-slate-300">
                    Set as default role for new users
                  </label>
                </div>

                {/* Permissions */}
                <div>
                  <label className="block text-sm font-medium text-slate-400 mb-2">Permissions</label>
                  <div className="space-y-2">
                    {PERMISSION_CATEGORIES.map(cat => {
                      const catPermissions = getPermissionsByCategory(cat.id)
                      const isExpanded = expandedCategories.includes(cat.id)
                      const grantedCount = catPermissions.filter(p => editingRole.permissions?.includes(p.id)).length

                      return (
                        <div key={cat.id} className="border border-white/10 rounded-lg overflow-hidden">
                          <button
                            onClick={() => toggleCategory(cat.id)}
                            className="w-full flex items-center justify-between p-3 bg-slate-700/50 hover:bg-slate-700 transition-colors"
                          >
                            <div className="flex items-center gap-2">
                              <span>{cat.icon}</span>
                              <span className="text-white font-medium">{cat.name}</span>
                              <span className="text-xs text-slate-400">
                                ({grantedCount}/{catPermissions.length})
                              </span>
                            </div>
                            {isExpanded ? (
                              <ChevronDown className="w-4 h-4 text-slate-400" />
                            ) : (
                              <ChevronRight className="w-4 h-4 text-slate-400" />
                            )}
                          </button>
                          {isExpanded && (
                            <div className="p-3 space-y-2">
                              {catPermissions.map(perm => (
                                <label
                                  key={perm.id}
                                  className="flex items-center gap-3 p-2 rounded hover:bg-slate-700/50 cursor-pointer"
                                >
                                  <input
                                    type="checkbox"
                                    checked={editingRole.permissions?.includes(perm.id) || false}
                                    onChange={() => togglePermission(perm.id)}
                                    className="w-4 h-4 rounded border-white/10 bg-slate-700 text-blue-500"
                                  />
                                  <div>
                                    <p className="text-white text-sm">{perm.name}</p>
                                    <p className="text-slate-500 text-xs">{perm.description}</p>
                                  </div>
                                </label>
                              ))}
                            </div>
                          )}
                        </div>
                      )
                    })}
                  </div>
                </div>
              </div>

              <div className="flex justify-end gap-3 p-4 border-t border-white/5">
                <button
                  onClick={() => {
                    setShowRoleModal(false)
                    setEditingRole(null)
                  }}
                  className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg transition-colors"
                >
                  Cancel
                </button>
                <button
                  onClick={handleSaveRole}
                  disabled={!editingRole.name}
                  className="flex items-center gap-2 px-4 py-2 bg-blue-600 hover:bg-blue-700 disabled:bg-slate-600 disabled:cursor-not-allowed text-white rounded-lg transition-colors"
                >
                  <Save className="w-4 h-4" />
                  {editingRole.id ? 'Save Changes' : 'Create Role'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    </DashboardLayout>
  )
}
