# Tenant User Story: Team User Management and Access Control

## Story
**As a** Team Lead/Administrator  
**I want to** manage user accounts and access permissions for my team  
**So that** I can control who has access to our logs and maintain security compliance

## User Journey

### 1. Access User Management
- Team lead logs into Logforge at `http://localhost:3001`
- Authenticates with admin role via `POST /v1/auth/login`
- Navigates to Team Management section
- System calls `GET /v1/users` to load current team members
- Views team roster:
  - Alice Johnson (Admin) - Last login: 2 hours ago
  - Bob Smith (Analyst) - Last login: Yesterday
  - Carol Davis (Viewer) - Last login: 1 week ago
  - David Wilson (Inactive) - Last login: 30+ days ago

### 2. Invite New Team Member
- New developer joining the team
- Team lead clicks "Invite User"
- Fills out invitation form:
  - **Full Name**: "Emma Thompson"
  - **Email**: "emma@company.com"
  - **Role**: "Developer" (query and dashboard access)
  - **Department**: "Engineering"
  - **Access Level**: "Standard"
- System validates email format and domain
- Calls `POST /v1/users` to create user account

### 3. Configure Role-Based Permissions
- Team lead defines role permissions:

**Admin Role**
- Full platform access
- User management
- Alert configuration
- Dashboard creation
- Security analytics
- Export capabilities

**Developer Role**
- Log querying and analysis
- Dashboard viewing
- Alert viewing (no configuration)
- Limited export (JSON only)
- No user management

**Analyst Role**
- Advanced querying
- Dashboard creation
- Security event analysis
- Custom rule creation
- Full export capabilities

**Viewer Role**
- Read-only dashboard access
- Basic log searching
- No configuration changes
- No export capabilities

### 4. Send User Invitation
- System generates secure invitation link
- Sends welcome email to emma@company.com:
```
Welcome to Logforge!

You've been invited to join the Company Engineering team.

Click here to set up your account: [Secure Link]
This link expires in 48 hours.

Your role: Developer
Platform: https://logforge.company.com

Questions? Contact your team lead.
```
- Team lead receives confirmation notification

### 5. New User Account Setup
- Emma receives email and clicks setup link
- Redirected to account creation page
- Sets up account credentials:
  - Password (meets security requirements)
  - Multi-factor authentication setup
  - Profile information
- System calls `PUT /v1/users/{id}/setup`
- Account activated and ready for use

### 6. User Permission Management
- Security audit requires permission review
- Team lead reviews user access:
  - Carol Davis: Viewer role but needs Analyst access
  - David Wilson: Inactive for 30+ days
- Updates Carol's permissions:
  - System calls `PUT /v1/users/{id}/role`
  - Role changed from "Viewer" to "Analyst"
  - Carol receives notification of permission change

### 7. Manage Inactive Users
- Team lead addresses inactive account (David Wilson)
- Options available:
  - Suspend account temporarily
  - Deactivate account permanently
  - Reset password and force re-authentication
- Chooses to suspend account:
  - System calls `PUT /v1/users/{id}/status`
  - Account marked as "Suspended"
  - All active sessions terminated
  - API access revoked

### 8. Team Access Audit
- Monthly security compliance requirement
- Team lead generates access report
- System calls `GET /v1/users/audit-report`
- Reviews detailed access information:
  - User login frequency
  - Permission changes history
  - Data access patterns
  - Failed login attempts
- Exports report for compliance documentation

### 9. Handle User Account Issues
- Bob Smith reports login problems
- Team lead investigates user account status
- Checks account details via `GET /v1/users/{id}`
- Identifies issues:
  - Password expired (90-day policy)
  - MFA device lost/reset required
- Resets Bob's account:
  - Forces password reset
  - Resets MFA enrollment
  - Sends recovery instructions

### 10. Configure Team-Wide Policies
- Team lead implements security policies:
  - **Password Policy**: 90-day expiration, complexity requirements
  - **Session Policy**: 8-hour timeout, single session per user
  - **MFA Policy**: Required for all users with Admin/Analyst roles
  - **Access Policy**: Automatic suspension after 45 days inactivity
- System enforces policies for all team members

### 11. Emergency Access Management
- Critical production incident during off-hours
- Need to grant temporary elevated access
- Team lead grants emergency permissions:
  - Promotes Developer to temporary Admin role
  - Sets automatic role reversion (24 hours)
  - Enables emergency access logging
  - Notifies security team of temporary escalation

### 12. User Activity Monitoring
- Team lead monitors user activity for security
- Reviews activity dashboard:
  - Login patterns and locations
  - Query activity and data access
  - Export operations and file downloads
  - Failed authentication attempts
- Identifies unusual activity:
  - Alice: Login from new country (traveling)
  - Emma: High query volume (legitimate - new project)
- Takes appropriate action (verify travel, no action needed)

### 13. Team Onboarding Automation
- Multiple new hires starting next week
- Team lead uses bulk user creation:
  - Uploads CSV with user details
  - System calls `POST /v1/users/bulk-create`
  - Generates multiple invitation emails
  - Sets consistent role assignments
  - Creates team-specific dashboard access

## API Endpoints Used
- `GET /v1/users` - List team users
- `POST /v1/users` - Create new user
- `GET /v1/users/{user_id}` - Get user details
- `PUT /v1/users/{user_id}` - Update user information
- `DELETE /v1/users/{user_id}` - Delete user
- `POST /v1/users/{user_id}/roles` - Assign user roles
- `GET /v1/users/{user_id}/roles` - Get user roles
- `DELETE /v1/users/{user_id}/roles/{role_id}` - Remove user role
- `POST /v1/auth/invite` - Send user invitation
- `POST /v1/auth/accept-invite` - Accept invitation
- `POST /v1/auth/password/reset` - Reset password
- `POST /v1/enterprise/auth/mfa/setup` - Setup MFA

## Success Criteria
- User accounts can be created and managed efficiently
- Role-based access control is enforced correctly
- Invitation process is secure and user-friendly
- Audit trails are comprehensive and exportable
- Inactive accounts are identified and managed
- Emergency access procedures work smoothly
- Security policies are enforced automatically
- Team onboarding scales with organization growth

## Technical Implementation
- **Authentication**: JWT-based with role claims
- **Authorization**: Role-based permission middleware
- **Security**: Password policies, MFA enforcement
- **Audit**: Comprehensive user activity logging
- **Compliance**: Automated reporting and policy enforcement
- **UI**: Intuitive user management interface
- **Integration**: Email notifications and SSO support