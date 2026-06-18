# Pattern: Master Data → Service Bus Pub/Sub (Topics)

## When to use
- Source is a master data system (MDM, product catalogue, customer DB)
- Same data must reach MULTIPLE consumers reliably
- Each consumer needs its own independent copy (fan-out)
- Data changes are event-driven (record created/updated/deleted)

## Flow
MDM / Source API → Ingestion MS → Transform MS → Routing MS → Service Bus Topic → Multiple Subscriptions → Consumers

## AKS Microservices
- **Ingestion MS**: listen to DB change events (CDC) or API webhooks
- **Transform MS**: full transformation — canonical data model enforced
- **Routing MS**: publishes to topic, each consumer has own subscription filter

## Azure Services
- Azure Service Bus Topics: one message → N subscriptions (fan-out)
- Azure Service Bus Subscriptions: per-consumer, filtered, independent
- Azure API Management: if source is external API

## Consumers
- ERP: customer master updates
- eCommerce platform: product catalogue sync
- Data Lake: MDM history tracking
- Loyalty system: customer profile updates

## SLA
- Latency tolerance: seconds to minutes
- Every consumer MUST receive every message (no data loss)
- Dead-letter per subscription — each consumer handles its own failures

## Example Retail Use Cases
- Product price change → eCommerce + ERP + Data Lake simultaneously
- New customer registration → CRM + Loyalty + Marketing platform
- Store master update → all regional systems
