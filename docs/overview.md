# Bedrock Model Catalog API

A read-only JSON API that serves the complete metadata of AWS Bedrock foundation models, including fields not available through the official AWS SDK.

## Why This Exists

The official AWS SDK (`ListFoundationModels`) silently drops a significant portion of model metadata during deserialization. This API captures the full response — including `consoleIDEMetadata`, `converse`, and `description` fields — and serves it as a normalized, publicly accessible JSON API.

> **Unofficial API** — This is not an official AWS service. It leverages undocumented response fields from the AWS Bedrock API. Some fields may change without notice as AWS updates their API.

## What's Included

- **200+ models** from 18+ providers (Anthropic, Amazon, Meta, Mistral, Google, DeepSeek, OpenAI, etc.)
- **33+ AWS regions** with availability data sourced from official AWS documentation
- **Pricing data** from AWS Price List API with tier breakdowns (Standard, Flex, Priority, Batch, Cache)
- **Cross-Region Inference (CRIS)** profiles — US, EU, APAC, and Global
- **Rich metadata** not available via SDK: descriptions, use cases, supported languages, release dates, capability flags

## Architecture

```
AWS Bedrock API (33 regions)
        │
        ▼
   Lambda / local_collect.py
   ├── SigV4 signed requests (x-console-consumer header)
   ├── AWS Price List API (2 service codes)
   ├── AWS Docs scraper (region availability)
   └── Fallback metadata + pricing
        │
        ▼
   S3 / Static JSON files
   ├── /v1/models.json (no pricing)
   ├── /v2/models.json (with pricing)
   └── /v2/metadata.json
        │
        ▼
   React Frontend (Vite + Tailwind)
   ├── Model Explorer (cards + list view)
   ├── Regional Availability (matrix)
   └── Documentation
```

## Data Sources

| Source | What It Provides |
|--------|-----------------|
| Bedrock API (`/foundation-models`) | Model metadata, capabilities, modalities, lifecycle |
| Bedrock API (`/inference-profiles`) | CRIS profiles and regions |
| `consoleIDEMetadata` field | Descriptions, categories, languages, release dates, agent/KB support |
| `converse` field | Max tokens, reasoning support, media types |
| AWS Price List API (`AmazonBedrockFoundationModels`) | Claude, Cohere, AI21 pricing |
| AWS Price List API (`AmazonBedrock`) | Nova, DeepSeek, Llama, Mistral pricing |
| AWS Docs (region compatibility page) | Authoritative region availability data |
| `fallback_metadata.json` | Curated data for models missing `consoleIDEMetadata` |
| `fallback_pricing.json` | Pricing for models not in Price List API (image, video, embedding) |

## API Versions

| Version | Description |
|---------|-------------|
| **V2** (recommended) | Full catalog with pricing, all regions, CRIS profiles |
| V1 (legacy) | Same models, no pricing data |
