# Model Schema

Every model in the catalog follows this schema. Fields that are unavailable for a given model will be `null`.

## Example

```json
{
  "modelId": "anthropic.claude-sonnet-4-20250514-v1:0",
  "modelName": "Claude Sonnet 4",
  "providerName": "Anthropic",
  "modelFamily": "Claude Sonnet",
  "availableRegions": ["us-east-1", "us-west-2", "eu-west-1", "..."],

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
    "categories": "Hybrid reasoning, code generation, ...",
    "reasoning": true,
    "promptCaching": true,
    "guardrails": true,
    "streaming": true,
    "agent": { "isSupported": true },
    "knowledgeBase": { "isSupported": true },
    "batchInference": { "baseModelSupported": false, "crossRegionSupported": true },
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
    "short": "Claude Sonnet 4 delivers frontier intelligence at scale...",
    "full": "Detailed description...",
    "useCases": "Complex agentic systems, multi-agent orchestration, ...",
    "invokeExample": "{...}"
  },

  "metadata": {
    "releaseDate": "2025-05-14T18:00:00+00:00",
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
        "profileId": "us.anthropic.claude-sonnet-4-20250514-v1:0",
        "name": "US Claude Sonnet 4",
        "type": "US",
        "regions": ["us-east-1", "us-east-2", "us-west-2"]
      },
      {
        "profileId": "eu.anthropic.claude-sonnet-4-20250514-v1:0",
        "name": "EU Claude Sonnet 4",
        "type": "EU",
        "regions": ["eu-central-1", "eu-west-1", "eu-west-3"]
      }
    ]
  },

  "pricing": {
    "modelName": "Claude Sonnet 4",
    "inputTokenPrice": 0.003,
    "outputTokenPrice": 0.015,
    "prices": [...],
    "source": "AmazonBedrockFoundationModels"
  }
}
```

## Field Reference

### Top-Level

| Field | Type | Description |
|-------|------|-------------|
| `modelId` | `string` | Unique identifier (e.g., `anthropic.claude-sonnet-4-20250514-v1:0`) |
| `modelName` | `string` | Human-readable name |
| `providerName` | `string` | Provider (e.g., `Anthropic`, `Amazon`, `Meta`) |
| `modelFamily` | `string\|null` | Family grouping (e.g., `Claude Sonnet`) |
| `availableRegions` | `string[]` | Regions where this model is available (sourced from AWS docs) |

### `modalities`

| Field | Type | Description |
|-------|------|-------------|
| `input` | `string[]` | `TEXT`, `IMAGE`, `AUDIO`, `VIDEO` |
| `output` | `string[]` | `TEXT`, `IMAGE`, `AUDIO`, `VIDEO` |

### `context`

| Field | Type | Description |
|-------|------|-------------|
| `maxInputTokens` | `string\|integer\|null` | Max input context (may be string like `"1M (beta)"`) |
| `maxOutputTokens` | `integer\|null` | Max output tokens |
| `maxOutputTokensDefault` | `integer\|null` | Default max output tokens |

### `capabilities`

| Field | Type | Description |
|-------|------|-------------|
| `categories` | `string\|null` | Comma-separated capability tags |
| `reasoning` | `boolean\|null` | Extended thinking / reasoning support |
| `promptCaching` | `boolean` | Explicit prompt caching |
| `guardrails` | `boolean` | Bedrock Guardrails support |
| `streaming` | `boolean` | Response streaming |
| `agent` | `object\|null` | Agent support (`isSupported`, `isStreamingSupported`) |
| `knowledgeBase` | `object\|null` | Knowledge Base support |
| `batchInference` | `object\|null` | Batch inference support |
| `flow` | `boolean` | Bedrock Flows support |
| `promptOptimization` | `boolean` | Prompt optimization |
| `latencyOptimization` | `boolean` | Latency-optimized inference |
| `intelligentPromptRouting` | `boolean` | Intelligent prompt routing |
| `systemTools` | `string[]` | System tools (e.g., `["web_search"]`) |

### `crossRegionInference`

| Field | Type | Description |
|-------|------|-------------|
| `supported` | `boolean` | Whether CRIS is available |
| `profiles[].profileId` | `string` | Profile ID (e.g., `us.anthropic.claude-sonnet-4-20250514-v1:0`) |
| `profiles[].type` | `string` | `US`, `EU`, `APAC`, or `GLOBAL` |
| `profiles[].regions` | `string[]` | Regions in this profile |

### `pricing` (V2 only)

| Field | Type | Description |
|-------|------|-------------|
| `inputTokenPrice` | `number\|null` | Per 1K input tokens (USD). Prefers CRIS > Standard > Flex |
| `outputTokenPrice` | `number\|null` | Per 1K output tokens (USD) |
| `prices` | `object[]` | Detailed tier breakdown entries |
| `prices[].inferenceType` | `string` | e.g., `Input tokens`, `Output tokens flex`, `Batch input tokens` |
| `prices[].pricePerUnit` | `number` | Price per 1K tokens |
| `source` | `string` | `AmazonBedrockFoundationModels`, `AmazonBedrock`, or `fallback` |

#### Pricing Tiers

Entries in the `prices` array are classified into tiers:

| Tier | Contains | Description |
|------|----------|-------------|
| **Standard** | `Input tokens`, `Output tokens` | Base on-demand pricing |
| **Flex** | `*flex*` | Lower cost, flexible SLA |
| **Priority** | `*priority*` | Higher cost, guaranteed throughput |
| **Cache** | `*cache*` | Prompt cache read pricing |
| **Batch** | `*batch*` | Batch inference pricing |
| **Cross-Region** | `*cross-region*` | CRIS-specific pricing |

> **Display convention**: Headline prices (`inputTokenPrice`, `outputTokenPrice`) are stored per 1K tokens. Multiply by 1000 to get per-1M pricing for display.
