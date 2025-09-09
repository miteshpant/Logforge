# Tenant User Story: Alert Configuration and Incident Response

## Story
**As a** Site Reliability Engineer (SRE)  
**I want to** configure intelligent alerting rules and receive timely notifications  
**So that** I can respond to incidents quickly and maintain service availability

## User Journey

### 1. Access Alert Management
- SRE logs into Logforge at `http://localhost:3001`
- Navigates to Alerts section
- System calls `GET /v1/alerts/rules` to load existing rules
- Views current alert rules:
  - High Error Rate (Active): >5% errors in 5 minutes
  - Database Connectivity (Active): Connection failures
  - Payment Service Down (Active): Service unavailable
  - Memory Usage High (Inactive): >85% memory usage

### 2. Create Performance Alert Rule
- SRE clicks "Create New Alert Rule"
- Configures threshold-based alert:
  - **Name**: "API Response Time Degradation"
  - **Description**: "Alert when API response time exceeds acceptable limits"
  - **Rule Type**: Threshold
  - **Query**: `service = "web-api" AND level != "DEBUG"`
  - **Metric**: Average response time
  - **Threshold**: > 500ms
  - **Time Window**: 5 minutes
  - **Severity**: HIGH

### 3. Configure Alert Conditions
- Sets advanced conditions:
  - **Evaluation Frequency**: Every 1 minute
  - **Grace Period**: 2 minutes (avoid false positives)
  - **Recovery Condition**: < 300ms for 3 minutes
  - **Escalation**: Promote to CRITICAL after 15 minutes
- System validates rule logic
- Calls `POST /v1/alerts/rules` to create rule

### 4. Set Up Notification Channels
- SRE configures multiple notification channels:

**Slack Integration**
- Channel: #sre-alerts
- Webhook URL: https://hooks.slack.com/services/...
- Message template: Custom format with service details

**Email Notifications**
- Recipients: sre-team@company.com, on-call@company.com
- Escalation: Manager after 30 minutes
- Format: HTML with charts and context

**PagerDuty Integration**
- Service key: Critical incidents only
- Routing: Based on service affected
- Auto-resolve: When alert clears

### 5. Test Alert Configuration
- SRE uses alert testing feature
- System calls `POST /v1/alerts/rules/{id}/test`
- Simulates threshold breach scenario
- Verifies alert fires correctly:
  - Slack message received in #sre-alerts
  - Email sent to team distribution list
  - PagerDuty incident created (TEST mode)
- Confirms notification content and formatting

### 6. Production Alert Triggered
- API response times spike due to database load
- Alert rule evaluates every minute
- Threshold breached: Average 750ms > 500ms
- System calls alert engine to fire notification
- Alert lifecycle begins:
  - Status: FIRING
  - First notification: Slack (immediate)
  - Escalation timer: Started

### 7. Incident Response Workflow
- SRE receives Slack notification:
```
🚨 ALERT: API Response Time Degradation
Service: web-api
Current: 750ms (threshold: 500ms)
Duration: 3 minutes
Severity: HIGH
Dashboard: [View Details]
```
- Clicks dashboard link to investigate
- Reviews real-time metrics and logs
- Identifies database connection pool exhaustion

### 8. Alert Acknowledge and Investigation
- SRE acknowledges alert to stop escalation
- System calls `PUT /v1/alerts/{id}/acknowledge`
- Updates alert status in all channels
- Begins remediation:
  - Scales database connection pool
  - Restarts affected application instances
  - Monitors response time recovery

### 9. Alert Resolution
- Response times return to normal: 180ms average
- Recovery condition met: < 300ms for 3 minutes
- System automatically resolves alert
- Calls `PUT /v1/alerts/{id}/resolve`
- Resolution notifications sent:
  - Slack: "✅ RESOLVED: API Response Time back to normal"
  - Email: Summary with incident duration
  - PagerDuty: Incident auto-resolved

### 10. Post-Incident Analysis
- SRE reviews alert effectiveness
- System calls `GET /v1/alerts/{id}/history`
- Analyzes incident timeline:
  - Detection time: 2 minutes
  - Acknowledgment time: 4 minutes
  - Resolution time: 12 minutes
  - Total duration: 18 minutes
- Updates alert threshold based on learnings

### 11. Advanced Pattern-Based Alert
- SRE creates complex pattern detection rule:
  - **Name**: "Security Login Anomaly"
  - **Type**: Anomaly Detection
  - **Pattern**: Unusual login patterns by user/location
  - **ML Model**: Statistical deviation from baseline
  - **Baseline Period**: 30 days
  - **Sensitivity**: Medium (avoid false positives)
  - **Action**: Create security event + notification

### 12. Alert Performance Review
- Weekly team review of alerting effectiveness
- SRE generates alert report
- System calls `GET /v1/alerts/analytics`
- Reviews metrics:
  - Total alerts fired: 47
  - Mean time to detection: 1.8 minutes
  - Mean time to resolution: 8.5 minutes
  - False positive rate: 3.2%
  - Alert accuracy: 96.8%
- Identifies optimization opportunities

## API Endpoints Used
- `GET /v1/alerts/rules` - List alert rules
- `POST /v1/alerts/rules` - Create alert rule
- `PUT /v1/alerts/rules/{rule_id}` - Update alert rule
- `DELETE /v1/alerts/rules/{rule_id}` - Delete alert rule
- `POST /v1/alerts/rules/{rule_id}/test` - Test alert rule
- `GET /v1/alerts` - List active alerts
- `POST /v1/alerts/{alert_id}/acknowledge` - Acknowledge alert
- `POST /v1/alerts/{alert_id}/resolve` - Resolve alert
- `GET /v1/alerts/{alert_id}` - Get alert details
- `GET /v1/alerts/stats` - Alert statistics
- `GET /v1/alerts/notifications/channels` - List notification channels
- `POST /v1/alerts/notifications/channels` - Create notification channels

## Success Criteria
- Alerts fire within 2 minutes of condition breach
- Notification delivery is reliable across all channels
- False positive rate remains below 5%
- Alert escalation works as configured
- Recovery detection and auto-resolution functions properly
- Alert analytics provide actionable insights
- Complex pattern detection identifies real anomalies
- Integration with external tools (Slack, PagerDuty) works seamlessly

## Technical Implementation
- **Alert Engine**: Rule evaluation with configurable frequency
- **Notification System**: Multi-channel delivery with templates
- **Escalation Logic**: Time-based escalation and recovery
- **Pattern Detection**: ML-based anomaly detection
- **Integration**: Webhook and API integrations
- **Analytics**: Alert performance metrics and reporting
- **UI**: Visual rule builder and alert management interface