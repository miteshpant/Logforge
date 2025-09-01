# Logforge Subscription & Pricing Model

## Overview
Logforge offers a flexible, feature-based subscription model that allows organizations to pay only for the capabilities they need. Our hybrid subscription system combines the simplicity of tiered plans with the flexibility of à la carte feature selection.

## 🏷️ Subscription Tiers

### **STARTER** - $99/month
Perfect for small teams and development environments
- **Basic Log Ingestion** (`ingestion.basic`) - JSON, Syslog, Text formats
- **Hot Storage** (`storage.hot`) - ClickHouse real-time queries  
- **Basic Search** (`queries.basic`) - Simple log search and filtering

**Ideal for:** Small development teams, staging environments, proof-of-concepts

### **PROFESSIONAL** - $499/month  
Comprehensive observability for growing organizations
- **All Ingestion Features** (`ingestion.*`) - JSON, Syslog, OTLP, CEF, Nginx, bulk processing
- **All Storage Options** (`storage.*`) - Hot + cold storage with automated TTL
- **Advanced Analytics** (`queries.*`) - Complex queries, aggregations, time-series analysis
- **Basic Alerting** (`alerts.basic`) - Rule-based alerts with email/Slack notifications
- **Dashboard Access** (`dashboards.readonly`) - 6 pre-built enterprise dashboards
- **Data Export** (`export.basic`) - JSON/CSV export capabilities

**Ideal for:** Growing companies, production environments, DevOps teams

### **ENTERPRISE** - Custom Pricing
Complete security and observability platform for large organizations
- **Universal Access** (`*`) - All current and future features included
- **Advanced Security Analytics** (`security.*`) - Full SIEM capabilities with Sigma rules
- **Distributed Tracing** (`observability.*`) - APM, service mapping, performance monitoring  
- **AI-Powered Assistant** (`ai_assistant.*`) - Natural language queries, root cause analysis
- **Enterprise Features** (`enterprise.*`) - SSO/OIDC, advanced RBAC, compliance automation
- **Priority Support** - Dedicated customer success manager
- **Custom Integrations** - Tailored connectors and data pipelines

**Ideal for:** Large enterprises, security-focused organizations, compliance-heavy industries

## 💰 Pricing Models

### **Per-Unit Pricing**
Pay based on actual usage volume
- **Log Ingestion**: $0.001 - $0.002 per log (tier-dependent)
- **Query Execution**: $0.01 - $0.05 per query
- **Security Events**: $0.03 - $0.05 per event processed

### **Fixed Monthly**  
Predictable monthly costs for core features
- **Basic Alerting**: $9.99 - $49.99/month (tier-dependent)
- **Dashboard Access**: $19.99/month (Professional+)
- **Compliance Reporting**: $99.99/month (Enterprise)

### **Tiered Pricing**
Volume discounts for high-usage features
- **1-1,000 events**: $0.05 per event
- **1,001-10,000 events**: $0.04 per event  
- **10,001+ events**: $0.03 per event

## 🎯 Feature Categories

### **Ingestion** (`ingestion.*`)
- `ingestion.basic` - JSON, Syslog, Text log formats
- `ingestion.batch` - High-volume batch processing
- `ingestion.bulk` - Bulk upload capabilities
- `ingestion.enterprise` - OTLP, CEF, custom parsers

### **Queries & Analytics** (`queries.*`)
- `queries.basic` - Simple log search and filtering
- `queries.advanced` - Complex aggregations, time-series analysis

### **Alerting** (`alerts.*`) 
- `alerts.basic` - Email, Slack, webhook notifications
- `alerts.advanced` - PagerDuty, Opsgenie, custom integrations

### **Security Analytics** (`security.*`)
- `security.events` - Security event detection and correlation
- `security.rules` - Custom Sigma rule creation and management
- `security.hunting` - Proactive threat hunting campaigns
- `security.intelligence` - Threat intelligence integration
- `security.mitre` - MITRE ATT&CK technique mapping

### **Observability** (`observability.*`)
- `observability.basic` - Infrastructure monitoring dashboards
- `observability.traces` - Distributed tracing and APM
- `observability.metrics` - Custom metrics collection
- `observability.apm` - Application performance monitoring

### **AI Assistant** (`ai_assistant.*`)
- `ai_assistant.basic` - Natural language log queries
- `ai_assistant.rca` - AI-powered root cause analysis
- `ai_assistant.anomaly` - ML-based anomaly detection
- `ai_assistant.predictions` - Predictive analytics

### **Enterprise** (`enterprise.*`)
- `enterprise.sso` - OIDC/SAML single sign-on
- `enterprise.rbac` - Advanced role-based access control
- `enterprise.audit` - Comprehensive audit logging
- `enterprise.compliance` - SOX, HIPAA, GDPR automation

## 📈 Cost Optimization

### **Intelligent Tiering**
- **Hot Storage** (ClickHouse) - Last 30 days for real-time queries
- **Cold Storage** (S3/GCS/Azure) - Long-term retention at 90% lower cost
- **Automated TTL** - Configurable data lifecycle policies

### **Consumption-Based Billing**  
- Only pay for features you actively use
- Real-time usage tracking and cost visibility
- Monthly spend limits with overage protection
- Detailed billing breakdowns by feature and tenant

### **Competitive Pricing**
- **60-80% cost reduction** vs. Splunk, Elastic, Datadog
- **No vendor lock-in** - multi-cloud architecture
- **Transparent pricing** - no hidden fees or surprise charges

## 🔒 Access Control & Enforcement

### **Feature-Based Access Control**
- HTTP 403 responses for unauthorized feature access
- Real-time subscription validation on every API call
- Graceful error messages with upgrade suggestions

### **Wildcard Support**
- **Namespace wildcards** (`ingestion.*`) - Access to all features in category
- **Universal access** (`*`) - Enterprise-tier unlimited access
- **Mixed subscriptions** - Combine specific features with wildcards

### **Usage Tracking**
- Real-time feature usage monitoring
- Detailed analytics for cost optimization
- Billing integration with usage-based pricing

## 🚀 Getting Started

### **1. Choose Your Plan**
Start with STARTER for basic log management, upgrade to PROFESSIONAL for comprehensive observability, or contact sales for ENTERPRISE pricing.

### **2. Feature Customization**
Mix and match features based on your specific needs:
```json
{
  "subscribed_features": [
    "ingestion.*",           // All ingestion capabilities
    "queries.basic",         // Basic search only  
    "security.events",       // Security event detection
    "alerts.basic"           // Basic alerting
  ]
}
```

### **3. Admin Configuration**
- Configure individual feature rates through admin APIs
- Set up billing cycles and spend limits
- Monitor usage and costs in real-time

### **4. Seamless Upgrades**
- Add new features instantly via API
- Upgrade subscription tiers without downtime
- Automatic billing adjustments

## 📞 Contact & Support

### **Sales Team**
- **Email**: sales@logforge.com
- **Enterprise Consultation**: Custom pricing and deployment options
- **Proof of Concept**: 30-day enterprise trial available

### **Technical Support**
- **STARTER**: Community forums and documentation
- **PROFESSIONAL**: Email support with 24-hour response SLA  
- **ENTERPRISE**: Dedicated support with 4-hour response SLA

### **Upgrade Information**
Current customers can upgrade their subscription at any time through:
- **API**: `PUT /v1/tenants/{tenant-id}/subscription/upgrade`
- **UI**: Account settings dashboard
- **Sales Contact**: For enterprise or custom requirements

## 🎯 Why Choose Logforge?

### **Cost-Effective**
- 60-80% lower costs than traditional SIEM/observability platforms
- Pay only for features you use
- No surprise charges or hidden fees

### **Enterprise-Ready**
- Multi-tenant architecture with customer isolation
- SOC 2, HIPAA, GDPR compliance built-in
- Horizontal scaling for any volume

### **Developer-Friendly**
- Modern APIs with comprehensive documentation
- SDK support for popular languages
- Extensive integration ecosystem

### **Security-First**
- Advanced threat detection with Sigma rules
- MITRE ATT&CK framework integration
- Real-time security event correlation

---

*Ready to get started? Contact our sales team at sales@logforge.com or visit our [documentation](https://docs.logforge.com) for technical details.*