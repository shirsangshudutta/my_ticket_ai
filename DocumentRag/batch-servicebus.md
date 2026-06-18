# Pattern: Batch File → Service Bus

## When to use
- Source is SFTP or legacy file system
- Data arrives on a schedule (nightly, hourly)
- Delivery guarantee is critical (finance, orders, inventory)
- Volume is moderate (up to 500k records per batch)

## Flow
SFTP/File → Ingestion MS → Transform MS → Routing MS → Service Bus → Consumer(s)

## AKS Microservices
- **Ingestion MS**: polls SFTP, downloads file, validates schema
- **Transform MS**: CSV/XML → JSON, field mapping, enrichment
- **Routing MS**: assigns topic, handles retry, dead-letter on failure

## Azure Services
- Azure Data Factory (ADF): SFTP polling trigger
- Azure Service Bus: guaranteed delivery, sessions, dead-letter queue
- Azure Key Vault: SFTP credentials storage

## Consumers
- ERP (SAP/Oracle): order and inventory updates
- Azure Data Lake: archival and analytics
- Downstream APIs: via HTTP adapter on Service Bus trigger

## SLA
- Latency tolerance: minutes to hours (batch acceptable)
- Retry: 3 attempts with exponential backoff
- Dead-letter alert: PagerDuty / Azure Monitor

## Example Retail Use Cases
- Nightly POS sales reconciliation → ERP
- Supplier inventory feed → Data Lake
- Daily pricing file → Product catalogue service
