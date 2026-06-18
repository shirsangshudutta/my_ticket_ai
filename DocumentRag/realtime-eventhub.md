# Pattern: Real-time API → Event Hub

## When to use
- Source is REST API, IoT device, POS terminal, webhook
- Data is continuous or near-continuous
- Volume is high (thousands of events per minute)
- Consumers need live data (dashboards, alerts)
- Losing occasional event is acceptable (telemetry, analytics)

## Flow
REST API / IoT / POS → Ingestion MS → Routing MS → Event Hub → Consumer(s)

## AKS Microservices
- **Ingestion MS**: authenticate, rate-limit, validate, log
- **Routing MS**: assign partition key, route to correct Event Hub namespace
- **Transform MS**: SKIPPED or minimal inline — speed is priority

## Azure Services
- Azure Event Hub: partitioned, high-throughput streaming (up to millions/sec)
- Azure Stream Analytics: real-time aggregation before consumers
- Azure Monitor: throughput and lag alerting

## Consumers
- Power BI: live sales dashboard
- Azure Data Lake: raw event archival (Event Hub Capture)
- Azure Functions: lightweight real-time alerting
- Multiple consumer groups reading same stream independently

## SLA
- Latency: milliseconds to seconds
- Retention: 1–7 days (replay possible)
- Partitions: scale by volume

## Example Retail Use Cases
- Live POS transactions → Power BI dashboard
- IoT shelf sensors → inventory alerting
- Customer clickstream → personalisation engine
- Loyalty point events → notification service
