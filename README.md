# Bedrock Model Catalog API

A read-only JSON API that serves the complete metadata, pricing, and regional availability of AWS Bedrock foundation models — including fields not exposed by the official AWS SDK.

The official AWS SDK (`ListFoundationModels`) silently drops a significant portion of model metadata during deserialization. This API captures the full response — including `consoleIDEMetadata`, `converse`, and `description` fields — merges it with AWS Pricing API data and AWS docs regional availability, and serves the result as a normalized, publicly accessible JSON API.

> **Unofficial API** — This is not an official AWS service. It leverages undocumented response fields from the AWS Bedrock API. Some fields may change without notice as AWS updates their API.

---

## Base URL

```
https://bedrock.sanghwa.people.aws.dev/v2
```

All responses are `Content-Type: application/json` with Gzip/Brotli compression. No authentication required.

Data is refreshed daily at 06:00 UTC. Cache TTL is 24 hours.

---

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v2/metadata.json` | API status, region list, and feature flags |
| `GET` | `/v2/models.json` | Full model catalog with pricing |
| `GET` | `/v2/models/{modelId}.json` | Individual model detail |
| `GET` | `/v2/inference-profiles.json` | Cross-region inference profile data |

> A v1 endpoint set (without pricing) is also served under `/v1/` for backward compatibility, but `/v2/` is recommended for new integrations.

---

## What's New in v2

- **Pricing data** — Per-model `inputTokenPrice` / `outputTokenPrice` (USD per 1K tokens) plus a detailed `prices[]` breakdown covering Standard, Cross-Region (US/EU/JP/Global), Cache, Batch, Flex, and Priority tiers.
- **All AWS regions** — Data collected from 36 regions (vs 2 in v1), including GovCloud and Middle East regions.
- **AWS docs regional availability** — `availableRegions` is merged from the official [AWS regional availability docs](https://docs.aws.amazon.com/bedrock/latest/userguide/models-region-compatibility.html), not just from API responses.
- **Cross-region inference profiles** — Detailed profile-level region lists for `US`, `EU`, `JP`, `APAC`, and `GLOBAL` profile types.
- **Curated metadata fallback** — Context window sizes, max output tokens, and descriptions are corrected against AWS official model card pages where the API returns wrong/hallucinated values.

---

## Endpoint Reference

### GET /v2/metadata.json

Returns API status and the last data collection timestamp.

```bash
curl https://bedrock.sanghwa.people.aws.dev/v2/metadata.json
```

**Response**

```json
{
  "lastUpdated": "2026-05-22T06:00:33.183271+00:00",
  "regions": ["us-east-1", "us-west-2", "..."],
  "totalRegions": 36,
  "totalModels": 152,
  "totalInferenceProfiles": 58,
  "version": "2.0.0",
  "features": ["pricing", "all-regions", "cris-profiles", "aws-docs-regions"]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `lastUpdated` | `string` | ISO 8601 timestamp of the last collection run (UTC) |
| `regions` | `string[]` | AWS regions from which data was collected |
| `totalRegions` | `integer` | Number of regions collected |
| `totalModels` | `integer` | Total number of models in the catalog |
| `totalInferenceProfiles` | `integer` | Total number of inference profiles |
| `version` | `string` | API schema version |
| `features` | `string[]` | Feature flags enabled in this catalog version |

---

### GET /v2/models.json

Returns the full model catalog including pricing.

```bash
curl https://bedrock.sanghwa.people.aws.dev/v2/models.json
```

**Response**

```json
{
  "lastUpdated": "2026-05-22T06:00:33.183271+00:00",
  "regions": ["us-east-1", "us-west-2", "..."],
  "totalRegions": 36,
  "totalModels": 152,
  "models": [ /* Model[] */ ]
}
```

---

### GET /v2/models/{modelId}.json

Returns detailed information for a single model.

```bash
curl https://bedrock.sanghwa.people.aws.dev/v2/models/anthropic.claude-sonnet-4-6.json
```

**Response:** A single `Model` object (see Model Schema below).

> In `{modelId}`, `/` and `:` characters are replaced with `_`. Example: `anthropic.claude-sonnet-4-20250514-v1:0` → `anthropic.claude-sonnet-4-20250514-v1_0.json`

---

### GET /v2/inference-profiles.json

Returns cross-region inference profile data from the primary region (`us-east-1`).

```bash
curl https://bedrock.sanghwa.people.aws.dev/v2/inference-profiles.json
```

**Response**

```json
{
  "lastUpdated": "2026-05-22T06:00:33.183271+00:00",
  "region": "us-east-1",
  "totalProfiles": 58,
  "profiles": [ /* raw inference profile objects */ ]
}
```

---

## Model Schema

Each object in the `models` array (and each individual model endpoint response) follows this schema:

```json
{
  "modelId": "anthropic.claude-sonnet-4-6",
  "modelName": "Claude Sonnet 4.6",
  "providerName": "Anthropic",
  "modelFamily": "Claude Sonnet",
  "availableRegions": ["us-east-1", "us-west-2", "..."],

  "modalities": {
    "input": ["TEXT", "IMAGE"],
    "output": ["TEXT"]
  },

  "context": {
    "maxInputTokens": "1M",
    "maxOutputTokens": 64000,
    "maxOutputTokensDefault": 64000
  },

  "capabilities": {
    "categories": "Hybrid reasoning, adaptive thinking, ...",
    "reasoning": true,
    "promptCaching": true,
    "guardrails": true,
    "streaming": true,
    "agent": { "isSupported": true, "isStreamingSupported": true },
    "knowledgeBase": { "isSupported": true, "isExternalSourcesSupported": true, "isParsingSupported": false },
    "batchInference": { "baseModelSupported": false, "crossRegionSupported": true, "customModelSupported": false, "tokenizerSupported": true },
    "flow": true,
    "promptOptimization": true,
    "latencyOptimization": false,
    "intelligentPromptRouting": false,
    "systemTools": ["web_search"]
  },

  "mediaSupport": {
    "inputImages": ["jpeg", "png", "gif", "webp"],
    "inputDocuments": ["pdf"],
    "inputVideos": []
  },

  "description": {
    "short": "Claude Sonnet 4.6 delivers frontier intelligence at scale...",
    "full": "Claude Sonnet 4.6 delivers frontier intelligence at scale—built for coding, agents, and enterprise workflows...",
    "useCases": "Complex agentic systems, multi-agent orchestration, ...",
    "invokeExample": "{...}"
  },

  "metadata": {
    "releaseDate": "2026-02-17T18:00:00+00:00",
    "version": "v1",
    "lifecycle": "ACTIVE",
    "supportedLanguages": "English, French, ...",
    "customizations": [],
    "inferenceTypes": ["INFERENCE_PROFILE"]
  },

  "crossRegionInference": {
    "supported": true,
    "profiles": [
      {
        "profileId": "us.anthropic.claude-sonnet-4-6",
        "name": "US Anthropic Claude Sonnet 4.6",
        "type": "US",
        "regions": ["us-east-1", "us-east-2", "us-west-2", "..."]
      },
      {
        "profileId": "global.anthropic.claude-sonnet-4-6",
        "name": "Global Anthropic Claude Sonnet 4.6",
        "type": "GLOBAL",
        "regions": ["af-south-1", "ap-east-2", "..."]
      }
    ]
  },

  "pricing": {
    "modelName": "Claude Sonnet 4.6",
    "inputTokenPrice": 0.003,
    "outputTokenPrice": 0.015,
    "prices": [
      { "inferenceType": "Input tokens", "pricePerUnit": 0.0033, "region": "us-east-1" },
      { "inferenceType": "Output tokens", "pricePerUnit": 0.0165, "region": "us-east-1" },
      { "inferenceType": "Cross-region global input tokens", "pricePerUnit": 0.003, "region": "us-east-1" },
      { "inferenceType": "Cross-region global output tokens", "pricePerUnit": 0.015, "region": "us-east-1" },
      { "inferenceType": "Batch input tokens", "pricePerUnit": 0.00165, "region": "us-east-1" },
      { "inferenceType": "Prompt cache read input tokens", "pricePerUnit": 0.00033, "region": "us-east-1" }
    ]
  }
}
```

### Field Reference

#### Top-Level Fields

| Field | Type | Description |
|-------|------|-------------|
| `modelId` | `string` | Unique model identifier (e.g., `anthropic.claude-sonnet-4-6`) |
| `modelName` | `string` | Human-readable model name |
| `providerName` | `string` | Model provider (e.g., `Anthropic`, `Amazon`, `Meta`) |
| `modelFamily` | `string\|null` | Model family grouping (e.g., `Claude Sonnet`, `Nova`) |
| `availableRegions` | `string[]` | AWS regions where this model is available (merged from API + AWS docs) |

#### `modalities`

| Field | Type | Description |
|-------|------|-------------|
| `input` | `string[]` | Supported input modalities: `TEXT`, `IMAGE`, `AUDIO`, `VIDEO` |
| `output` | `string[]` | Supported output modalities: `TEXT`, `IMAGE`, `AUDIO`, `VIDEO` |

#### `context`

| Field | Type | Description |
|-------|------|-------------|
| `maxInputTokens` | `string\|integer\|null` | Maximum input context window (e.g., `"128K"`, `"1M"`) |
| `maxOutputTokens` | `integer\|null` | Maximum output tokens supported |
| `maxOutputTokensDefault` | `integer\|null` | Default max output tokens if not specified by the caller |

#### `capabilities`

| Field | Type | Description |
|-------|------|-------------|
| `categories` | `string\|null` | Comma-separated capability categories |
| `reasoning` | `boolean\|null` | Whether the model supports reasoning/thinking |
| `promptCaching` | `boolean` | Explicit prompt caching support |
| `guardrails` | `boolean` | Amazon Bedrock Guardrails support |
| `streaming` | `boolean` | Response streaming support |
| `agent` | `object\|null` | Agent support details (`isSupported`, `isStreamingSupported`) |
| `knowledgeBase` | `object\|null` | Knowledge Base support details |
| `batchInference` | `object\|null` | Batch inference support details |
| `flow` | `boolean` | Amazon Bedrock Flows support |
| `promptOptimization` | `boolean` | Prompt optimization support |
| `latencyOptimization` | `boolean` | Latency-optimized inference support |
| `intelligentPromptRouting` | `boolean` | Intelligent prompt routing support |
| `systemTools` | `string[]` | Supported system tools (e.g., `["web_search"]`) |

#### `mediaSupport`

| Field | Type | Description |
|-------|------|-------------|
| `inputImages` | `string[]` | Supported input image formats (e.g., `["jpeg", "png", "gif", "webp"]`) |
| `inputDocuments` | `string[]` | Supported input document formats (e.g., `["pdf"]`) |
| `inputVideos` | `string[]` | Supported input video formats |

#### `description`

| Field | Type | Description |
|-------|------|-------------|
| `short` | `string\|null` | Short description of the model |
| `full` | `string\|null` | Full description of the model |
| `useCases` | `string\|null` | Recommended use cases |
| `invokeExample` | `string\|null` | Example invocation payload (JSON string) |

#### `metadata`

| Field | Type | Description |
|-------|------|-------------|
| `releaseDate` | `string\|null` | ISO 8601 release date |
| `version` | `string\|null` | Model version identifier |
| `lifecycle` | `string\|null` | Lifecycle status: `ACTIVE`, `LEGACY`, `EOL` |
| `supportedLanguages` | `string\|null` | Comma-separated list of supported languages |
| `customizations` | `string[]` | Supported customization types (e.g., `["FINE_TUNING"]`) |
| `inferenceTypes` | `string[]` | Supported inference types (e.g., `["ON_DEMAND", "INFERENCE_PROFILE"]`) |

#### `crossRegionInference`

| Field | Type | Description |
|-------|------|-------------|
| `supported` | `boolean` | Whether cross-region inference is available |
| `profiles` | `object[]` | Array of inference profile objects |
| `profiles[].profileId` | `string` | Inference profile ID (e.g., `us.anthropic.claude-sonnet-4-6`) |
| `profiles[].name` | `string` | Human-readable profile name |
| `profiles[].type` | `string` | Profile type: `US`, `EU`, `JP`, `APAC`, or `GLOBAL` |
| `profiles[].regions` | `string[]` | Regions included in this profile |

#### `pricing`

| Field | Type | Description |
|-------|------|-------------|
| `modelName` | `string` | Pricing source's model name (may differ slightly from `modelName`) |
| `inputTokenPrice` | `number\|null` | Headline input price in USD per 1K tokens |
| `outputTokenPrice` | `number\|null` | Headline output price in USD per 1K tokens |
| `prices` | `object[]` | Detailed tier breakdown |
| `prices[].inferenceType` | `string` | Tier name (see below) |
| `prices[].pricePerUnit` | `number` | USD per 1K tokens (or per image/video/second for non-text models) |
| `prices[].region` | `string` | Region this price applies to |

**Pricing tier types** in `prices[].inferenceType`:

- `Input tokens` / `Output tokens` — Standard on-demand
- `Cross-region global input tokens` — Global Cross-Region Inference (CRIS)
- `Cross-region geo input tokens` — Regional CRIS (US/EU/APAC/JP)
- `Batch input tokens` / `Batch output tokens` — Batch inference
- `Prompt cache read input tokens` — Cache hit pricing
- `Flex input tokens` — Flex tier (lower cost, flexible SLA)
- `Priority input tokens` — Priority tier (guaranteed throughput)

The headline `inputTokenPrice` / `outputTokenPrice` use this priority order:
**Global CRIS > Regional CRIS > Standard On-Demand > Flex** (cache, batch, priority excluded).

Multiply by 1000 to display per-1M-token pricing. Some models price by image, video second, or search query rather than tokens — those expose `imagePrice`, `videoPrice`, `videoSecPrice`, or `searchUnitPrice` instead.

---

## SDK vs This API

The official AWS SDK returns only a subset of the available metadata. The following fields are **only available through this API**:

| Data | SDK | This API | Source |
|------|-----|----------|--------|
| Model ID, name, provider | ✅ | ✅ | SDK fields |
| Input/output modalities | ✅ | ✅ | SDK fields |
| Streaming, customizations, inference types | ✅ | ✅ | SDK fields |
| Model lifecycle status | ✅ | ✅ | SDK fields |
| **Pricing (input/output, batch, cache, CRIS)** | ❌ | ✅ | AWS Pricing API |
| **Regional availability (all regions)** | ❌ | ✅ | AWS docs |
| **Cross-region inference profiles** | ❌ | ✅ | `/inference-profiles` |
| **Full description** | ❌ | ✅ | `consoleIDEMetadata` |
| **Short description** | ❌ | ✅ | `consoleIDEMetadata` |
| **Supported use cases** | ❌ | ✅ | `consoleIDEMetadata` |
| **Supported languages** | ❌ | ✅ | `consoleIDEMetadata` |
| **Release date** | ❌ | ✅ | `consoleIDEMetadata` |
| **Max context window** | ❌ | ✅ | `consoleIDEMetadata` + curated fallback |
| **Model categories/attributes** | ❌ | ✅ | `consoleIDEMetadata` |
| **Model family** | ❌ | ✅ | `consoleIDEMetadata` |
| **Max output tokens** | ❌ | ✅ | `converse` + curated fallback |
| **Reasoning support** | ❌ | ✅ | `converse` |
| **Supported image/doc/video types** | ❌ | ✅ | `converse` |
| **Agent support details** | ❌ | ✅ | `consoleIDEMetadata` |
| **Knowledge Base support** | ❌ | ✅ | `consoleIDEMetadata` |
| **Batch inference details** | ❌ | ✅ | `consoleIDEMetadata` |
| **System tools (web_search)** | ❌ | ✅ | `consoleIDEMetadata` |
| **Prompt caching** | ❌ | ✅ | `explicitPromptCaching` |
| **Guardrails support** | ❌ | ✅ | `guardrailsSupported` |
| **Latency optimization** | ❌ | ✅ | `latencyOptimizationSupported` |
| **Intelligent prompt routing** | ❌ | ✅ | `intelligentPromptRouting` |

---

## License

MIT
