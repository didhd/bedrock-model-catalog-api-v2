# Bedrock Model Catalog API

A read-only JSON API that serves the complete metadata of AWS Bedrock foundation models, including fields not available through the official AWS SDK.

The official AWS SDK (`ListFoundationModels`) silently drops a significant portion of model metadata during deserialization. This API captures the full response — including `consoleIDEMetadata`, `converse`, and `description` fields — and serves it as a normalized, publicly accessible JSON API.

> **Unofficial API** — This is not an official AWS service. It leverages undocumented response fields from the AWS Bedrock API. Some fields may change without notice as AWS updates their API.

---

## Base URL

```
https://d3q5s82trr046g.cloudfront.net/v1
```

All responses are `Content-Type: application/json` with Gzip/Brotli compression. No authentication required.

Data is refreshed daily at 06:00 UTC. Cache TTL is 24 hours.

---

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/metadata` | API status and last update time |
| `GET` | `/v1/models` | Full model catalog |
| `GET` | `/v1/models/{modelId}` | Individual model detail |
| `GET` | `/v1/inference-profiles` | Cross-region inference profiles |

---

## Region Support

This is **not a per-region API**. Data is aggregated from multiple AWS regions (`us-east-1`, `us-west-2`) into a single unified catalog. Each model includes an `availableRegions` field indicating which regions it is available in.

## Data Coverage

Not all models have the same level of metadata. The Bedrock API returns rich metadata (`consoleIDEMetadata`) for most models when the `x-console-consumer` header is included. For models where the API does not return this data, curated fallback metadata is used. PT (Provisioned Throughput) variants inherit metadata from their base model.

| Metadata Level | Models | Fields Available |
|----------------|--------|------------------|
| Full metadata (API) | ~110+ models | All fields including `categories`, `description`, `supportedLanguages`, `releaseDate`, `agent`, `knowledgeBase`, `systemTools`, `maxInputTokens`, `maxOutputTokens` |
| Enriched metadata (Fallback) | ~38 models (older Claude 3.x, Llama, Titan, Cohere, etc.) | `categories`, `description`, `supportedLanguages`, `releaseDate`, `maxInputTokens` from curated data |

All 148 models currently have `categories` populated. Fields that are not available for a given model will be `null`. As AWS populates `consoleIDEMetadata` for more models over time, this API will automatically pick up the additional data on the next collection run.

---

### GET /v1/metadata

Returns API status and the last data collection timestamp.

```bash
curl https://d3q5s82trr046g.cloudfront.net/v1/metadata
```

**Response**

```json
{
  "lastUpdated": "2026-03-02T20:50:51.066605+00:00",
  "regions": ["us-east-1", "us-west-2"],
  "totalModels": 148,
  "totalInferenceProfiles": 60,
  "version": "1.0.0"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `lastUpdated` | `string` | ISO 8601 timestamp of the last collection run (UTC) |
| `regions` | `string[]` | AWS regions from which data was collected |
| `totalModels` | `integer` | Total number of models in the catalog |
| `totalInferenceProfiles` | `integer` | Total number of inference profiles |
| `version` | `string` | API schema version |

---

### GET /v1/models

Returns the full model catalog.

```bash
curl https://d3q5s82trr046g.cloudfront.net/v1/models
```

**Response**

```json
{
  "lastUpdated": "2026-03-02T20:50:51.066605+00:00",
  "regions": ["us-east-1", "us-west-2"],
  "totalModels": 148,
  "models": [ ... ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `lastUpdated` | `string` | ISO 8601 timestamp of the last collection run |
| `regions` | `string[]` | Regions from which data was collected |
| `totalModels` | `integer` | Number of models |
| `models` | `Model[]` | Array of Model objects (see Model Schema below) |

---

### GET /v1/models/{modelId}

Returns detailed information for a single model.

```bash
curl https://d3q5s82trr046g.cloudfront.net/v1/models/anthropic.claude-sonnet-4-6
```

**Response:** A single `Model` object (see Model Schema below).

> In `{modelId}`, `/` and `:` characters are replaced with `_`.

---

### GET /v1/inference-profiles

Returns cross-region inference profile data.

```bash
curl https://d3q5s82trr046g.cloudfront.net/v1/inference-profiles
```

**Response**

```json
{
  "lastUpdated": "2026-03-02T20:50:51.066605+00:00",
  "region": "us-east-1",
  "totalProfiles": 60,
  "profiles": [ ... ]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `lastUpdated` | `string` | ISO 8601 timestamp of the last collection run |
| `region` | `string` | Primary region from which profiles were collected |
| `totalProfiles` | `integer` | Number of profiles |
| `profiles` | `object[]` | Raw inference profile objects from the Bedrock API |

---

## Model Schema

Each object in the `models` array (and each individual model endpoint response) follows this schema:

```json
{
  "modelId": "anthropic.claude-sonnet-4-6",
  "modelName": "Claude Sonnet 4.6",
  "providerName": "Anthropic",
  "modelFamily": "Claude Sonnet",
  "availableRegions": ["us-east-1", "us-west-2"],

  "modalities": {
    "input": ["TEXT", "IMAGE"],
    "output": ["TEXT"]
  },

  "context": {
    "maxInputTokens": "1M (beta)",
    "maxOutputTokens": 64000,
    "maxOutputTokensDefault": 32000
  },

  "capabilities": {
    "categories": "Hybrid reasoning, adaptive thinking, code generation, ...",
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
    "supportedLanguages": "English, French, Modern Standard Arabic, Mandarin Chinese, ...",
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
        "regions": ["us-east-1", "us-east-2", "us-west-2"]
      }
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
| `availableRegions` | `string[]` | AWS regions where this model is available |

#### `modalities`

| Field | Type | Description |
|-------|------|-------------|
| `input` | `string[]` | Supported input modalities: `TEXT`, `IMAGE`, `AUDIO`, `VIDEO` |
| `output` | `string[]` | Supported output modalities: `TEXT`, `IMAGE`, `AUDIO`, `VIDEO` |

#### `context`

| Field | Type | Description |
|-------|------|-------------|
| `maxInputTokens` | `string\|integer\|null` | Maximum input context window (may be a string like `"1M (beta)"`) |
| `maxOutputTokens` | `integer\|null` | Maximum output tokens supported |
| `maxOutputTokensDefault` | `integer\|null` | Default max output tokens if not specified |

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
| `profiles[].type` | `string` | Profile type: `US` or `GLOBAL` |
| `profiles[].regions` | `string[]` | Regions included in this profile |

---

## SDK vs This API

The official AWS SDK returns only a subset of the available metadata. The following fields are **only available through this API**:

| Data | SDK | This API | Source |
|------|-----|----------|--------|
| Model ID, name, provider | ✅ | ✅ | SDK fields |
| Input/output modalities | ✅ | ✅ | SDK fields |
| Streaming, customizations, inference types | ✅ | ✅ | SDK fields |
| Model lifecycle status | ✅ | ✅ | SDK fields |
| **Full description** | ❌ | ✅ | `consoleIDEMetadata` |
| **Short description** | ❌ | ✅ | `consoleIDEMetadata` |
| **Supported use cases** | ❌ | ✅ | `consoleIDEMetadata` |
| **Supported languages** | ❌ | ✅ | `consoleIDEMetadata` |
| **Release date** | ❌ | ✅ | `consoleIDEMetadata` |
| **Max context window** | ❌ | ✅ | `consoleIDEMetadata` |
| **Model categories/attributes** | ❌ | ✅ | `consoleIDEMetadata` |
| **Model family** | ❌ | ✅ | `consoleIDEMetadata` |
| **Max output tokens** | ❌ | ✅ | `converse` |
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
| **Cross-region inference profiles** | ❌ | ✅ | `/inference-profiles` |

---

## License

MIT
