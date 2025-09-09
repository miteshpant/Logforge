# Admin User Story: Admin User Management

## Story
**As a** Logforge super administrator  
**I want to** manage admin user accounts and their permissions  
**So that** I can control platform access and maintain security for administrative operations

## User Journey

### 1. Access Admin User Management
- Super admin logs into Admin UI (`http://localhost:3002`)
- Navigates to Admin Users section (`/admin-users`)
- Views list of current admin users:
  - Sarah Johnson (Super Admin) - Last login: 2 hours ago
  - Mike Chen (Admin) - Last login: Yesterday
  - Emily Rodriguez (Support Admin) - Last login: 3 days ago
  - David Park (Billing Admin) - Last login: 1 week ago

### 2. Create New Admin User
- Super admin clicks "Add New Admin User"
- Fills out user creation form:
  - Full Name: "Jessica Thompson"
  - Email: "jessica@logforge.com"
  - Role: "Support Admin"
  - Department: "Customer Success"
  - Phone: "+1-555-0123"
- System validates email uniqueness
- Calls `POST /v1/admin/users` to create account

### 3. User Account Setup
- System generates secure temporary password
- Sends welcome email with login instructions
- New user must change password on first login
- Account is marked as "Pending Activation"
- Super admin receives confirmation notification

### 4. Role and Permission Management
- Super admin reviews role definitions:

**Super Admin**
- Full platform access
- User management
- Billing and financial data
- System configuration

**Admin**
- Tenant management
- Usage analytics
- Support operations
- No billing access

**Support Admin**
- Tenant support
- User account assistance
- Read-only access to usage data
- No configuration changes

**Billing Admin**
- Usage analytics
- Billing reports
- Financial data
- No tenant management

### 5. Update User Permissions
- Customer escalates security issue
- Super admin promotes Support Admin to full Admin
- Updates user via `PUT /v1/admin/users/{id}/role`
- System immediately applies new permissions
- User receives notification of role change
- Activity is logged in audit trail

### 6. User Account Monitoring
- Super admin reviews login activity
- Checks last login times for all users
- Identifies inactive accounts:
  - David Park: No login for 30+ days
- Reviews failed login attempts
- Monitors suspicious access patterns

### 7. Account Deactivation
- Employee David Park leaves company
- Super admin deactivates account
- System calls `PUT /v1/admin/users/{id}/status`
- All active sessions are terminated
- Account marked as "Deactivated"
- API keys are revoked
- Audit log entry created

### 8. Security Compliance
- Super admin runs quarterly access review
- Exports user access report
- Reviews role assignments against job functions
- Identifies over-privileged accounts
- Updates permissions to follow least privilege principle
- Documents changes for compliance audit

## API Endpoints Used
- `GET /v1/admin/users` - List all admin users
- `POST /v1/admin/users` - Create new admin user
- `GET /v1/admin/users/{user_id}` - Get admin user details
- `PUT /v1/admin/users/{user_id}` - Update admin user
- `DELETE /v1/admin/users/{user_id}` - Delete admin user
- `POST /v1/users/{user_id}/roles` - Assign user roles
- `GET /v1/users/{user_id}/roles` - Get user roles
- `POST /v1/auth/password/reset` - Reset password

## Success Criteria
- Admin users can be created and managed efficiently
- Role-based access control is enforced
- Inactive accounts are identified and managed
- Security compliance requirements are met
- Audit trail is maintained for all changes
- User activity can be monitored and reviewed

## Technical Implementation
- **Authentication**: JWT tokens with role claims
- **Authorization**: Role-based permission middleware
- **Security**: Password policies, session management
- **Audit**: Comprehensive logging of admin actions
- **Compliance**: Regular access reviews and reporting
- **UI**: Intuitive admin user management interface