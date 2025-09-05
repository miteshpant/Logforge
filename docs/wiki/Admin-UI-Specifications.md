# Logforge Admin UI Specifications

## Overview
The Logforge Admin UI is a separate Next.js application designed for platform administrators to manage tenants, monitor usage, handle billing, and oversee platform operations. This interface is distinct from the customer-facing UI and provides comprehensive administrative capabilities.

## Architecture

### Technical Stack
- **Framework**: Next.js 14 with TypeScript
- **Styling**: Tailwind CSS + shadcn/ui components
- **Port**: 3002 (separate from customer UI on 3001)
- **API Integration**: FastAPI backend at localhost:7080
- **Testing**: Playwright for E2E testing
- **Container**: Docker with development mode

### Deployment
- **Development**: Docker Compose service `admin-ui`
- **URL**: `http://localhost:3002`
- **Container Name**: `logforge-admin-ui`
- **Environment Variables**:
  - `NEXT_PUBLIC_API_URL=http://localhost:7080`
  - `NEXT_PUBLIC_ADMIN_MODE=true`

## Core Features

### 1. Dashboard Home (`/`)
**Purpose**: Central hub for admin navigation and platform overview

**Components**:
- Header with "Logforge Admin Dashboard" title
- Platform statistics cards:
  - Active Tenants: 1,247
  - Monthly Revenue: $127,450
  - Total Data Ingested: 15.2TB
  - Platform Uptime: 99.97%
- Navigation grid (3 columns on desktop):
  - Tenant Management
  - Usage Analytics
  - Billing & Subscriptions
  - Feature Management
  - Support & Tickets
  - Admin Users

**Navigation Cards**:
Each card should be clickable and navigate to respective pages with hover effects.

### 2. Tenant Management (`/tenants`)
**Purpose**: Onboard new tenants and manage existing tenant accounts

**API Endpoints**:
- `GET /v1/tenants` - List all tenants
- `POST /v1/tenants` - Create new tenant
- `PUT /v1/tenants/{id}` - Update tenant details
- `DELETE /v1/tenants/{id}` - Remove tenant

**Page Components**:
- **Header**: "Tenant Management" with back navigation
- **Statistics Cards** (4 cards):
  - Total Tenants: 3
  - Active Tenants: 3
  - Monthly Revenue: $1,497
  - Enterprise Customers: 1

- **Action Button**: "+ Onboard New Tenant" (opens modal)

- **Tenant Table**: 
  - **Columns**: Organization, Tenant ID, Subscription, Status, Monthly Usage, Monthly Cost, Actions
  - **Sample Data**:
    - Acme Corp | ace-001 | Enterprise | Active | 850GB | $997 | View Details, Manage Subscription
    - TechStart Inc | tsi-002 | Professional | Active | 250GB | $499 | View Details, Manage Subscription  
    - DevTeam LLC | dtl-003 | Starter | Active | 50GB | $99 | View Details, Manage Subscription

- **Subscription Badges**:
  - Enterprise: Purple background (`bg-purple-100 text-purple-800`)
  - Professional: Blue background (`bg-blue-100 text-blue-800`)
  - Starter: Green background (`bg-green-100 text-green-800`)

**Onboarding Modal**:
- **Fields**:
  - Organization Name (text input, required)
  - Admin Email (email input, required)
  - Subscription Tier (select dropdown)
    - Starter ($99/month)
    - Professional ($499/month)
    - Enterprise (Custom)
- **Buttons**: Cancel, Create Tenant
- **Validation**: Required field validation, proper form submission

### 3. Usage Analytics (`/usage`)
**Purpose**: Monitor tenant usage patterns and generate billing reports

**API Endpoints**:
- `GET /v1/usage/analytics` - Get usage analytics data
- `GET /v1/usage/export` - Export usage reports
- `POST /v1/billing/generate` - Generate bills

**Page Components**:
- **Header**: "Usage Analytics" with back navigation
- **Period Selector**: Dropdown with options:
  - Current Month
  - Last Month  
  - Last 3 Months
  - Custom Range

- **Summary Statistics** (4 cards):
  - Total Revenue: $1,497
  - Total API Calls: 3,750,000
  - Avg Revenue/Tenant: $499
  - Enterprise Accounts: 1

- **Tenant Usage Breakdown Table**:
  - **Columns**: Organization, Data Ingested, API Calls, Monthly Cost, Actions
  - **Sample Data**:
    - Acme Corp | 850GB | 2,500,000 | $997 | Generate Bill →
    - TechStart Inc | 250GB | 1,000,000 | $499 | Generate Bill →
    - DevTeam LLC | 50GB | 250,000 | $99 | Generate Bill →

- **Feature Usage Details**:
  - Per-tenant feature breakdown with usage counts and costs
  - Feature categories: INGESTION, QUERIES, SECURITY, ALERTS
  - Detailed cost attribution per feature

- **Action Buttons**:
  - Export Usage Report
  - Generate All Bills

### 4. Billing & Subscriptions (`/billing`)
**Purpose**: Manage subscription tiers, pricing, and billing configurations

**Components**:
- Subscription tier management
- Pricing configuration
- Invoice generation
- Payment method management
- Billing cycle configuration

### 5. Feature Management (`/features`)
**Purpose**: Configure feature availability per subscription tier

**Components**:
- Feature toggle management
- Subscription tier feature mapping
- Usage limits configuration
- API rate limiting settings

### 6. Support & Tickets (`/support`)
**Purpose**: View and manage customer support tickets

**Components**:
- Support ticket list
- Ticket priority and status management
- Customer communication interface
- Escalation workflows

### 7. Admin Users (`/admin-users`)
**Purpose**: Manage platform administrator accounts

**API Endpoints**:
- `GET /v1/admin/users` - List admin users
- `POST /v1/admin/users` - Create admin user
- `PUT /v1/admin/users/{id}` - Update admin user
- `DELETE /v1/admin/users/{id}` - Remove admin user

**Page Components**:
- **Admin Users Table**:
  - **Columns**: Name, Email, Role, Status, Last Login, Permissions, Actions
  - **Sample Data**:
    - Sarah Johnson | sarah.johnson@logforge.com | Super Admin | Active | 2024-01-15 09:30:00 | All Permissions | Edit, Deactivate
    - Mike Chen | mike.chen@logforge.com | Admin | Active | 2024-01-14 16:45:00 | Tenant Management, Usage Analytics, Billing | Edit, Deactivate

- **Add User Modal**:
  - Full Name (text input)
  - Email Address (email input)
  - Role (select dropdown): Admin, Super Admin, Support Admin, Billing Admin

- **Role Badges**:
  - Super Admin: Red background (`bg-red-100 text-red-800`)
  - Admin: Blue background (`bg-blue-100 text-blue-800`)
  - Support Admin: Green background (`bg-green-100 text-green-800`)
  - Billing Admin: Purple background (`bg-purple-100 text-purple-800`)

## UI/UX Requirements

### Design System
- **Colors**: Professional gray/blue palette
- **Typography**: Clean, readable fonts with proper hierarchy
- **Layout**: Consistent spacing, grid-based layouts
- **Responsive**: Mobile-friendly with breakpoints

### Accessibility
- **Contrast**: Ensure proper color contrast ratios
- **Navigation**: Clear breadcrumbs and back links
- **Forms**: Proper labels, validation messages
- **Interactive Elements**: Clear hover states and button feedback

### Common UI Patterns
- **Back Navigation**: "← Back to Dashboard" on all pages
- **Modal Pattern**: Consistent modal styling for forms
- **Table Pattern**: Consistent table styling with proper headers
- **Badge Pattern**: Consistent color coding for status/subscription tiers
- **Button Pattern**: Primary (blue), secondary (gray), destructive (red)

## Data Integration

### Mock Data Requirements
All pages should initially use mock data that matches the expected API response format:

**Tenant Data**:
```json
{
  "id": "ace-001",
  "name": "Acme Corp",
  "email": "admin@acme.com",
  "subscription_tier": "enterprise",
  "status": "active",
  "monthly_usage_gb": 850,
  "monthly_cost": 997,
  "created_at": "2024-01-01T00:00:00Z"
}
```

**Usage Data**:
```json
{
  "tenant_id": "ace-001",
  "period": "current_month",
  "data_ingested_gb": 850,
  "api_calls": 2500000,
  "monthly_cost": 997,
  "feature_usage": [
    {"feature": "ingestion.basic", "usage_count": 2500000, "cost": 2500.00},
    {"feature": "queries.advanced", "usage_count": 15000, "cost": 750.00}
  ]
}
```

**Admin User Data**:
```json
{
  "id": "au001",
  "name": "Sarah Johnson", 
  "email": "sarah.johnson@logforge.com",
  "role": "super_admin",
  "status": "active",
  "last_login": "2024-01-15T09:30:00Z",
  "permissions": ["all"]
}
```

## Testing Requirements

### Playwright Test Coverage
**File**: `apps/admin-ui/tests/admin-interface.spec.ts`

**Test Suites**:
1. **Dashboard Navigation**: Verify all cards and navigation work
2. **Tenant Management**: Test onboarding modal, table display, form validation
3. **Usage Analytics**: Test period selector, export functionality, data display
4. **Admin Users**: Test user creation, role management, permissions
5. **Responsive Design**: Test mobile and desktop layouts
6. **Form Validation**: Test all form inputs and error handling

### Test Data Requirements
- Tests should use consistent mock data
- All interactive elements must be testable
- Form submissions should be validated
- Navigation between pages should work correctly

## Security Requirements

### Access Control
- Admin-only access (separate from customer UI)
- Role-based permissions within admin interface
- Secure API communication with proper headers

### Data Protection
- No sensitive data exposure in client-side code
- Proper input validation and sanitization
- Secure form handling

## Performance Requirements

### Page Load
- Initial page load < 2 seconds
- Navigation between pages < 1 second
- Modal opening/closing < 500ms

### Data Handling
- Efficient table rendering for large datasets
- Pagination for tables with >100 rows
- Lazy loading for heavy components

## Future Enhancements

### Phase 1 (Immediate)
- Basic CRUD operations for all entities
- Form validation and error handling
- Responsive design implementation

### Phase 2 (Near-term)
- Real-time data updates
- Advanced filtering and search
- Bulk operations support

### Phase 3 (Long-term)
- Advanced analytics and reporting
- Automated billing workflows
- Integration with external systems

## Implementation Notes

### File Structure
```
apps/admin-ui/
├── src/
│   ├── app/
│   │   ├── page.tsx                 # Dashboard home
│   │   ├── tenants/
│   │   │   └── page.tsx            # Tenant management
│   │   ├── usage/
│   │   │   └── page.tsx            # Usage analytics
│   │   ├── billing/
│   │   │   └── page.tsx            # Billing management
│   │   ├── features/
│   │   │   └── page.tsx            # Feature management
│   │   ├── support/
│   │   │   └── page.tsx            # Support tickets
│   │   ├── admin-users/
│   │   │   └── page.tsx            # Admin user management
│   │   ├── layout.tsx              # Root layout
│   │   └── globals.css             # Global styles
│   ├── components/                 # Reusable components
│   └── lib/                        # Utilities
├── tests/
│   └── admin-interface.spec.ts     # Playwright tests
├── package.json
├── next.config.js
├── tailwind.config.js
├── postcss.config.js
└── Dockerfile
```

### Development Workflow
1. **Specs First**: Complete specifications (this document)
2. **Tests First**: Write comprehensive Playwright tests
3. **Implementation**: Build components to pass tests
4. **Integration**: Docker containerization
5. **Validation**: End-to-end testing

This approach ensures we build exactly what's needed without over-engineering or missing requirements.