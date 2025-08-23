# Logforge Multi-Cloud Storage Architecture

## Overview

Logforge supports flexible, multi-cloud storage architectures to accommodate different customer requirements, compliance needs, and deployment models. This document describes the various storage options and how to configure them.

## Deployment Models

### 1. Shared Storage (Default)
**Use Case**: Most customers, cost-effective shared infrastructure
- **Storage**: Logforge-managed S3/GCS/Azure buckets
- **Isolation**: Customer data isolated by namespace/prefix
- **Credentials**: Managed by Logforge
- **Cost**: Lowest cost, shared infrastructure economies

```yaml
storage:
  deployment:
    type: "shared"
  cold:
    backend: "s3"
    backends:
      s3:
        shared:
          enabled: true
          bucket_prefix: "logforge-shared"
```

### 2. Dedicated Storage (Enterprise)
**Use Case**: Enterprise customers requiring dedicated infrastructure
- **Storage**: Customer-dedicated buckets/containers
- **Isolation**: Separate storage containers per customer
- **Credentials**: Customer-provided or Logforge cross-account access
- **Cost**: Higher cost, dedicated resources

```yaml
storage:
  deployment:
    type: "dedicated"
  cold:
    backend: "s3"
    backends:
      s3:
        dedicated:
          enabled: true
          bucket: "customer-logforge-cold"
          role_arn: "arn:aws:iam::123456789012:role/LogforgeAccess"
```

### 3. FedRAMP/Government Cloud
**Use Case**: US Government agencies, compliance requirements
- **Storage**: Government-specific cloud regions (AWS GovCloud, Azure Government)
- **Isolation**: Complete environment isolation
- **Credentials**: Government-provided, high-security authentication
- **Compliance**: FedRAMP High, FISMA compliance

```yaml
storage:
  deployment:
    type: "fedramp"
    region: "us-gov-east-1"
    compliance_tier: "fedramp"
  cold:
    backend: "s3"
    backends:
      s3:
        fedramp:
          enabled: true
          bucket: "gov-agency-logforge"
          endpoint: "https://s3.us-gov-east-1.amazonaws.com"
```

### 4. On-Premises/Air-Gapped
**Use Case**: Highly regulated industries, air-gapped networks
- **Storage**: Customer-operated MinIO clusters
- **Isolation**: Complete physical isolation
- **Credentials**: Customer-managed, on-premises keys
- **Network**: Air-gapped or VPN-only connectivity

```yaml
storage:
  deployment:
    type: "private"
  cold:
    backend: "minio"
    backends:
      minio:
        enabled: true
        endpoint: "https://minio.internal.company.com:9000"
        bucket: "logforge-cold-storage"
```

## Supported Storage Backends

### AWS S3
- **Regions**: All AWS regions including GovCloud
- **Features**: Cross-region replication, lifecycle policies, KMS encryption
- **Authentication**: IAM roles, access keys, cross-account access
- **Compliance**: FedRAMP High, HIPAA, SOC2, PCI DSS

### Google Cloud Storage (GCS)
- **Regions**: All GCP regions
- **Features**: Multi-regional storage, lifecycle management, CMEK
- **Authentication**: Service accounts, workload identity
- **Compliance**: HIPAA, SOC2, PCI DSS

### Microsoft Azure Blob Storage  
- **Regions**: All Azure regions including Government
- **Features**: Hot/cool/archive tiers, geo-redundancy
- **Authentication**: Service principals, managed identities
- **Compliance**: FedRAMP High, HIPAA, SOC2

### MinIO (On-Premises)
- **Deployment**: Customer-managed clusters
- **Features**: S3-compatible API, erasure coding, versioning
- **Authentication**: Access keys, LDAP integration
- **Use Cases**: Air-gapped environments, data sovereignty

## Configuration Examples

### Shared AWS S3 (Most Customers)
```yaml
# config/deployments/shared-s3.yaml
storage:
  deployment:
    type: "shared"
    region: "us-east-1"
  cold:
    backend: "s3"
    backends:
      s3:
        shared:
          enabled: true
          bucket_prefix: "logforge-shared"
          # Uses Logforge AWS credentials
  lifecycle:
    hot_to_cold_days: 7
    delete_after_days: 365
```

### Enterprise Dedicated GCS
```yaml
# config/deployments/enterprise-gcs.yaml
storage:
  deployment:
    type: "dedicated"
    region: "us-east1"
    compliance_tier: "hipaa"
  cold:
    backend: "gcs"
    backends:
      gcs:
        dedicated:
          enabled: true
          bucket: "healthcare-customer-logforge"
          project_id: "customer-gcp-project"
          service_account_key: "${GCS_SERVICE_ACCOUNT_KEY}"
  encryption:
    customer_keys:
      enabled: true
      kms_key_id: "projects/customer/locations/us-east1/keyRings/logforge/cryptoKeys/cold-storage"
```

### FedRAMP AWS GovCloud
```yaml
# config/deployments/fedramp-govcloud.yaml
storage:
  deployment:
    type: "fedramp"
    region: "us-gov-east-1"
    compliance_tier: "fedramp"
  cold:
    backend: "s3"
    backends:
      s3:
        fedramp:
          enabled: true
          bucket: "agency-logforge-fedramp"
          endpoint: "https://s3.us-gov-east-1.amazonaws.com"
          access_key: "${FEDRAMP_S3_ACCESS_KEY}"
          secret_key: "${FEDRAMP_S3_SECRET_KEY}"
  encryption:
    customer_keys:
      enabled: true
      hsm_partition: "${FEDRAMP_HSM_PARTITION}"
```

## Security and Compliance Features

### Encryption
- **At Rest**: AES-256 encryption for all storage backends
- **In Transit**: TLS 1.3 for all data transfers  
- **Key Management**: Logforge-managed, customer-managed, or HSM-based keys

### Access Controls
- **Authentication**: Multi-factor authentication required for high-security deployments
- **Authorization**: Role-based access control (RBAC)
- **Audit**: Complete audit trails for all data access

### Compliance Certifications
- **FedRAMP High**: For US Government agencies
- **HIPAA**: For healthcare organizations
- **SOC 2 Type II**: For enterprise customers
- **PCI DSS**: For payment processing environments

## Cost Optimization

### Storage Tiers
- **Hot Storage (ClickHouse)**: 7-30 days, high-performance queries
- **Cold Storage (Cloud)**: 30-365 days, cost-effective long-term storage
- **Archive Storage**: 365+ days, lowest cost for compliance retention

### Cost Comparison by Deployment Type

| Deployment Model | Relative Cost | Use Case |
|------------------|---------------|----------|
| Shared S3        | 1x (baseline) | Most customers |
| Dedicated S3     | 2-3x         | Enterprise isolation |
| FedRAMP GovCloud | 3-5x         | Government compliance |
| On-Premises      | Variable     | Air-gapped, data sovereignty |

## Migration and Setup

### Customer Onboarding Process

1. **Requirements Assessment**
   - Compliance needs (FedRAMP, HIPAA, etc.)
   - Data sovereignty requirements
   - Expected data volume and retention

2. **Deployment Type Selection**
   - Shared: Most cost-effective
   - Dedicated: Enhanced isolation
   - FedRAMP: Government compliance
   - Private: Maximum control

3. **Storage Backend Configuration**
   - Cloud provider preference
   - Region selection for performance/compliance
   - Credential setup and testing

4. **Security Configuration**
   - Encryption key management
   - Access control setup
   - Audit logging configuration

### Migration from Other Platforms

**From Splunk**:
- Export data using Splunk REST API
- Convert to Logforge format using migration tools
- Parallel ingestion during transition period

**From ELK Stack**:
- Use Logstash output plugin for dual-shipping
- Elasticsearch export/import for historical data
- Kibana dashboard conversion to Logforge

## Monitoring and Operations

### Health Monitoring
- Storage backend connectivity
- Data lifecycle policy execution
- Cost monitoring and alerting
- Performance metrics (ingestion rate, query latency)

### Disaster Recovery
- Cross-region replication for critical deployments
- Point-in-time recovery capabilities
- Automated backup validation
- Recovery time objectives (RTO) < 4 hours

## API and Integration

### Storage Configuration API
```python
from logforge.storage import StorageConfigManager

# Initialize storage manager
storage = StorageConfigManager()

# Get storage endpoint for customer
endpoint = storage.get_storage_endpoint(customer_id="enterprise_customer")

# Get storage client
client = storage.get_storage_client(customer_id="enterprise_customer")
```

### Dynamic Configuration
- Hot-reloading of storage configurations
- Customer-specific overrides
- Runtime switching between backends (for migrations)

This flexible architecture ensures Logforge can meet diverse customer requirements while maintaining security, compliance, and cost-effectiveness.