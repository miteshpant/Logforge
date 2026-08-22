# Logforge - Enterprise Observability Platform

Multi-tenant observability and SIEM platform with advanced log management, metrics, traces, and security analytics.

## Table of Contents

- [Quick Start](#quick-start)
- [Architecture](#architecture)
- [Initial Setup](#initial-setup)
- [Admin Functionality](#admin-functionality)
- [Development](#development)
- [Testing](#testing)

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Node.js 18+ (for local UI development)
- Python 3.11+ (for local API development)

### 1. Start the Infrastructure

```bash
# Deploy all services (ClickHouse, MinIO, RedPanda, Redis, API, UI)
./deploy.sh

# Check service status
docker compose -f infra/docker/compose.yml ps
```

**Services:**
- API: http://localhost:7080
- Main UI: http://localhost:3001
- Admin UI: http://localhost:3002
- ClickHouse: http://localhost:8124
- MinIO Console: http://localhost:9004
- RedPanda Console: http://localhost:18081

---

## Initial Setup

### Create First Platform Admin User

After deploying the infrastructure, you need to create the first platform administrator to access the admin UI and manage the platform.

#### Step 1: Generate Setup Token

```bash
curl -X POST http://localhost:7080/v1/auth/setup/init
```

**Response:**
```json
{
  "setup_token": "AbCdEfGhIjKlMnOpQrStUvWxYz1234567890",
  "expires_at": "2025-08-12T10:30:00Z"
}
```

**Note:** The setup token expires in 24 hours and can only be used once.

#### Step 2: Create First Admin User

```bash
curl -X POST http://localhost:7080/v1/auth/setup \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@logforge.com",
    "name": "Platform Admin",
    "password": "YourSecurePassword123!",
    "setup_token": "AbCdEfGhIjKlMnOpQrStUvWxYz1234567890"
  }'
```

**Password Requirements:**
- Minimum 12 characters
- At least 1 uppercase letter
- At least 1 lowercase letter
- At least 1 number
- At least 1 special character (!@#$%^&*(),.?":{}|<>)

**Response:**
```json
{
  "id": "user-uuid-123",
  "email": "admin@logforge.com",
  "name": "Platform Admin",
  "status": "active",
  "created_at": "2025-08-11T10:30:00Z",
  "customer_id": "platform"
}
```

#### Step 3: Login to Admin UI

1. Navigate to Admin UI: http://localhost:3002
2. Login with credentials:
   - Email: `admin@logforge.com`
   - Password: `YourSecurePassword123!`

3. You should now have access to the Admin Dashboard

---

## Admin Functionality

### 1. Admin User Management

**Endpoint:** `/v1/admin/users`

#### Create Additional Admin Users

Via Admin UI:
1. Go to http://localhost:3002/admin-users
2. Click "Add Admin User" button
3. Fill in the form:
   - Full Name
   - Email Address
   - Role (Admin, Super Admin, Support Admin, Billing Admin)
   - Optional: Temporary Password (defaults to `TempPassword123!`)
4. Click "Add User"

Via API:
```bash
# Get your JWT token first by logging in
curl -X POST http://localhost:7080/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin@logforge.com",
    "password": "YourSecurePassword123!"
  }'

# Create new admin user
curl -X POST http://localhost:7080/v1/admin/users \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "admin2@logforge.com",
    "name": "Second Admin",
    "password": "SecondAdminPass123!"
  }'
```

#### List Admin Users

```bash
curl -X GET http://localhost:7080/v1/admin/users?page=1&page_size=50 \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

#### Update Admin User

```bash
curl -X PUT http://localhost:7080/v1/admin/users/{user_id} \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Updated Name",
    "status": "active"
  }'
```

#### Delete Admin User

```bash
curl -X DELETE http://localhost:7080/v1/admin/users/{user_id} \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Safeguards:**
- Cannot delete your own admin account
- Cannot delete the last super_admin (prevents lockout)
- Automatically revokes all sessions for security

---

### 2. Tenant Management

#### Create Tenant

Via Admin UI:
1. Go to http://localhost:3002/tenants
2. Click "Onboard New Tenant" button
3. Fill in tenant details:
   - Organization Name *
   - Domain *
   - Billing Email *
   - **Admin Contact Name*** (will become the tenant admin user)
   - **Admin Contact Email*** (will become the tenant admin login)
   - Subscription Tier * (Startup, SMB, Enterprise, etc.)
   - Industry, Region, Compliance Requirements (optional)
4. Submit

**Important:** When creating a tenant, the system automatically:
- ✅ Creates a tenant record
- ✅ Creates a tenant admin user with the contact email provided
- ✅ Generates a **secure 16-character temporary password**
- ✅ Assigns `tenant_admin` role to the user

#### How to Get the Tenant User's Password

The tenant admin password is auto-generated during creation. Here's how to retrieve it:

**Option 1: Check Browser Console (During Creation)**
1. Open browser DevTools (Press F12)
2. Go to Console tab
3. Look for logs showing: `✅ Admin user created: {...}`
4. The temporary password is logged in the workflow result

**Option 2: Reset Password via API**
```bash
# 1. Find the user by email
curl -X GET "http://localhost:7080/v1/users?email=mitesh.pant@gmail.com" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN"

# 2. Reset the password (creates new password)
curl -X POST "http://localhost:7080/v1/users/{user_id}/reset-password" \
  -H "Authorization: Bearer YOUR_ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "new_password": "NewSecurePassword123!"
  }'
```

**Option 3: Send Password Reset Email** *(Recommended for production)*
```bash
curl -X POST "http://localhost:7080/v1/auth/forgot-password" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "mitesh.pant@gmail.com"
  }'
```

Via API:
```bash
curl -X POST http://localhost:7080/v1/tenants \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Acme Corporation",
    "type": "enterprise",
    "primary_contact_name": "John Doe",
    "primary_contact_email": "john@acme.com",
    "domain": "acme.com",
    "status": "active"
  }'
```

#### List Tenants

```bash
curl -X GET http://localhost:7080/v1/tenants?page=1&page_size=50 \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

### 3. Usage Analytics

View platform-wide usage metrics:
- Total tenants
- Active users
- Data ingestion rates
- Storage usage
- API usage

Access via Admin UI: http://localhost:3002/usage

---

### 4. Billing & Subscriptions

Manage tenant subscriptions, billing, and payments.

Access via Admin UI: http://localhost:3002/billing

---

### 5. Feature Flags

Enable/disable features for specific tenants or platform-wide.

Access via Admin UI: http://localhost:3002/features

---

### 6. Support Management

Manage support tickets and customer inquiries.

Access via Admin UI: http://localhost:3002/support

---

## Architecture

### Technology Stack

**Backend:**
- FastAPI (Python 3.11)
- ClickHouse (columnar database for logs/metrics)
- RedPanda (Kafka-compatible message broker)
- Redis (caching & session management)
- MinIO (S3-compatible object storage)

**Frontend:**
- Next.js 14 (Main UI)
- Next.js 14 (Admin UI)
- TypeScript
- Tailwind CSS
- shadcn/ui components

**Infrastructure:**
- Docker & Docker Compose
- Nginx (reverse proxy)

### Services

| Service | Port | Purpose |
|---------|------|---------|
| API | 7080 | Backend REST API |
| Main UI | 3001 | Tenant-facing dashboard |
| Admin UI | 3002 | Platform admin dashboard |
| ClickHouse | 8124 | Database (HTTP), 9001 (Native) |
| MinIO | 9003 (API), 9004 (Console) | Object storage |
| RedPanda | 19092 (Kafka), 18081 (Schema Registry) | Message broker |
| Redis | 6379 | Cache & sessions |

---

## Development

### Running API Locally

```bash
cd apps/api
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
uvicorn main:app --reload --port 8080
```

### Running Main UI Locally

```bash
cd apps/ui
npm install
npm run dev
# Access at http://localhost:3000
```

### Running Admin UI Locally

```bash
cd apps/admin-ui
npm install
npm run dev
# Access at http://localhost:3002
```

---

## Testing

### API Tests

```bash
cd apps/api
pytest
```

### UI Tests

```bash
cd apps/ui
npm test
```

### Admin UI Tests

```bash
cd apps/admin-ui
npm test
```

---

## Environment Variables

### API

```bash
CLICKHOUSE_HOST=localhost
CLICKHOUSE_PORT=8123
CLICKHOUSE_USER=logforge
CLICKHOUSE_PASSWORD=logforge123
CLICKHOUSE_DATABASE=logforge

KAFKA_BOOTSTRAP_SERVERS=localhost:19092
KAFKA_SECURITY_PROTOCOL=PLAINTEXT

MINIO_ENDPOINT=localhost:9003
MINIO_ACCESS_KEY=minio
MINIO_SECRET_KEY=minio123

REDIS_HOST=localhost
REDIS_PORT=6379
REDIS_DB=0

CORS_ORIGINS=http://localhost:3000,http://localhost:3001,http://localhost:3002
```

### UI

```bash
NEXT_PUBLIC_API_URL=http://localhost:7080
```

### Admin UI

```bash
NEXT_PUBLIC_API_URL=http://localhost:7080
NEXT_PUBLIC_ADMIN_MODE=true
```

---

## Troubleshooting

### Services Not Starting

```bash
# Check service status
docker compose -f infra/docker/compose.yml ps

# View logs
docker compose -f infra/docker/compose.yml logs -f

# Restart services
docker compose -f infra/docker/compose.yml restart
```

### Database Connection Issues

```bash
# Check ClickHouse health
docker exec logforge-clickhouse clickhouse-client --query "SELECT 1"

# List databases
docker exec logforge-clickhouse clickhouse-client --query "SHOW DATABASES"

# List tables
docker exec logforge-clickhouse clickhouse-client --query "SHOW TABLES FROM logforge"
```

### UI Permission Errors (Development Mode)

If running UI in Docker and seeing permission errors:
```bash
# Stop UI container
docker stop logforge-ui

# Run UI locally instead
cd apps/ui
npm install
npm run dev
```

---

## Documentation

- [API Reference](./docs/API_REFERENCE.md)
- [Architecture](./docs/ARCHITECTURE.md)
- [Deployment Guide](./DEPLOYMENT.md)
- [Admin UI Guide](./apps/admin-ui/README.md)

---

## License

Proprietary - All rights reserved

---

## Support

For issues or questions:
- Create an issue in the repository
- Contact: support@logforge.com