# Storage Router Quick Reference

## Endpoint Summary

| Endpoint | Method | Auth | Purpose |
|----------|--------|------|---------|
| `/v1/storage/retention/{customer_id}` | POST | Tenant | Create retention policy |
| `/v1/storage/retention/{customer_id}` | GET | Tenant | Get retention policy |
| `/v1/storage/retention/{customer_id}` | PUT | Tenant | Update retention policy |
| `/v1/storage/cleanup` | POST | Tenant | Manual cleanup |
| `/v1/storage/archive/{customer_id}` | POST | Tenant | Archive old data |
| `/v1/storage/health/infrastructure` | GET | **Admin** | System health |
| `/v1/storage/health` | GET | Tenant | Customer health |
| `/v1/storage/health/{target_customer_id}` | GET | Admin | Cross-tenant health |
| `/v1/storage/quota/sync` | POST | Tenant | Sync customer quota |
| `/v1/storage/quota/sync/all` | POST | **Admin** | Sync all quotas |
| `/v1/storage/archives/{customer_id}` | GET | Tenant | List archives |
| `/v1/storage/archive/{archive_key}` | GET | Tenant | Archive metadata |
| `/v1/storage/archive/{archive_key}/download` | POST | Tenant | Download archive |
| `/v1/storage/query-archive` | POST | Tenant | Query archives |

## Authentication Types

- **Tenant**: Regular JWT + X-Customer-ID header
- **Admin**: Platform admin JWT + X-Customer-ID header

## Common Troubleshooting

### 403 Errors
```bash
# Cross-tenant access
{"detail": "Access denied"}
→ Check customer_id matches X-Customer-ID

# Admin required
{"detail": "User context not found"}
→ Use admin login (admin@mrlogsec.com)
```

### 404 Errors
```bash
# Archive not found
{"detail": "Archive not found"}
→ Use archive_key from list API, not id
→ Verify archive belongs to customer
```

### Archive Key Format
```
❌ Wrong: 8de44692-63bc-4340-b310-9eb70deb2fdb
✅ Correct: archived_logs/tenant-123/2025/10/10/logs_batch_1760154276.parquet
```

## Database Tables

- `retention_policies_mt` - TTL policies
- `archive_metadata_mt` - Archive files
- `archive_access_log_mt` - Access audit
- `storage_operations_mt` - Operations history
- `tenant_quotas_mt` - Storage quotas

## Quick Commands

### List Archives
```bash
GET /v1/storage/archives/{customer_id}?limit=10&offset=0
```

### Get Archive Metadata
```bash
GET /v1/storage/archive/archived_logs/{customer_id}/2025/10/10/logs_batch_1760154276.parquet
```

### Download Archive
```bash
POST /v1/storage/archive/archived_logs/{customer_id}/2025/10/10/logs_batch_1760154276.parquet/download
```

### Check Health
```bash
# Customer health
GET /v1/storage/health

# System health (admin)
GET /v1/storage/health/infrastructure
```

### Manual Operations
```bash
# Cleanup
POST /v1/storage/cleanup

# Archive
POST /v1/storage/archive/{customer_id}

# Sync quotas
POST /v1/storage/quota/sync
```