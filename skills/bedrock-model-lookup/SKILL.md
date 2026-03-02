---
name: bedrock-model-lookup
description: >
  Look up AWS Bedrock foundation model metadata, pricing, regional availability,
  and capabilities using the Bedrock Model Catalog API. Use this skill when the
  user asks about Bedrock model pricing (e.g., "how much does Claude Sonnet cost
  on Bedrock?"), model availability across AWS regions, model capabilities
  (reasoning, streaming, agent support), cross-region inference (CRIS) profiles,
  or wants to compare Bedrock models. Also use when the user mentions Bedrock
  model IDs, provider names (Anthropic, Amazon Nova, Meta Llama, Mistral, etc.),
  or needs to choose a Bedrock model for their use case.
---

# Bedrock Model Lookup

Query the Bedrock Model Catalog API to get real-time model metadata, pricing,
regional availability, and capabilities for all AWS Bedrock foundation models.

## API Base

```
https://bedrock.sanghwa.people.aws.dev
```

The API serves static JSON. No auth required.

## Quick Lookups

### Get all models

```bash
curl -s https://bedrock.sanghwa.people.aws.dev/v2/models.json | jq '.models | length'
```

### Find a model by name or ID

```bash
# By name (case-insensitive substring)
curl -s https://bedrock.sanghwa.people.aws.dev/v2/models.json | jq '[.models[] | select(.modelName | ascii_downcase | contains("claude sonnet 4"))]'

# By model ID
curl -s https://bedrock.sanghwa.people.aws.dev/v2/models.json | jq '[.models[] | select(.modelId | contains("claude-sonnet-4"))]'

# By provider
curl -s https://bedrock.sanghwa.people.aws.dev/v2/models.json | jq '[.models[] | select(.providerName == "Anthropic")]'
```

### Get pricing for a model

```bash
# Headline pricing (per 1K tokens stored, multiply by 1000 for per-1M display)
curl -s https://bedrock.sanghwa.people.aws.dev/v2/models.json | jq '
  .models[] | select(.modelId | contains("claude-sonnet-4-2")) |
  {
    name: .modelName,
    input_per_1M: ((.pricing.inputTokenPrice // 0) * 1000),
    output_per_1M: ((.pricing.outputTokenPrice // 0) * 1000),
    source: .pricing.source
  }'

# Full pricing tiers breakdown
curl -s https://bedrock.sanghwa.people.aws.dev/v2/models.json | jq '
  .models[] | select(.modelId | contains("claude-sonnet-4-2")) |
  .pricing.prices[] | {type: .inferenceType, per_1K: .pricePerUnit, per_1M: (.pricePerUnit * 1000)}'
```

### Check regional availability

```bash
# Which regions is a model available in?
curl -s https://bedrock.sanghwa.people.aws.dev/v2/models.json | jq '
  .models[] | select(.modelId | contains("claude-sonnet-4-2")) |
  {name: .modelName, regions: (.availableRegions | length), list: .availableRegions}'

# Which models are available in a specific region?
curl -s https://bedrock.sanghwa.people.aws.dev/v2/models.json | jq '
  [.models[] | select(.availableRegions | index("ap-northeast-2")) | .modelName]'
```

### Check CRIS profiles

```bash
curl -s https://bedrock.sanghwa.people.aws.dev/v2/models.json | jq '
  .models[] | select(.modelId | contains("claude-sonnet-4-2")) |
  .crossRegionInference.profiles[] | {type, profileId, regions}'
```

### Compare models

```bash
# Compare pricing across providers
curl -s https://bedrock.sanghwa.people.aws.dev/v2/models.json | jq '
  [.models[] | select(.pricing.inputTokenPrice != null) |
  {name: .modelName, provider: .providerName,
   input: ((.pricing.inputTokenPrice // 0) * 1000),
   output: ((.pricing.outputTokenPrice // 0) * 1000),
   regions: (.availableRegions | length)}] |
  sort_by(.input)'
```

## Data Schema

### Pricing

- `pricing.inputTokenPrice` — USD per 1K input tokens
- `pricing.outputTokenPrice` — USD per 1K output tokens
- Multiply by 1000 to get per-1M pricing for display
- `pricing.prices[]` — Detailed tier breakdown:
  - **Standard**: `Input tokens`, `Output tokens`
  - **Flex**: `*flex*` — lower cost, flexible SLA
  - **Priority**: `*priority*` — higher cost, guaranteed throughput
  - **Cache**: `*cache*` — prompt cache read pricing
  - **Batch**: `*batch*` — batch inference pricing
  - **Cross-Region**: `*cross-region*` — CRIS-specific pricing
- `pricing.source`: `AmazonBedrockFoundationModels`, `AmazonBedrock`, or `fallback`

### Capabilities

- `capabilities.reasoning` — Extended thinking support (boolean)
- `capabilities.streaming` — Response streaming (boolean)
- `capabilities.agent` — Agent support (`{isSupported: true}`)
- `capabilities.knowledgeBase` — Knowledge Base support
- `capabilities.systemTools` — e.g., `["web_search"]`
- `capabilities.promptCaching` — Prompt caching support

### Cross-Region Inference (CRIS)

- `crossRegionInference.profiles[].type`: `US`, `EU`, `APAC`, or `GLOBAL`
- `crossRegionInference.profiles[].profileId`: Use this as `modelId` for CRIS
- `crossRegionInference.profiles[].regions`: Regions in this profile

### Regional Availability

- `availableRegions` — All regions where model is usable (in-region + CRIS)
- Data sourced from official AWS documentation (source of truth)

## Gotchas

- Prices are stored **per 1K tokens**. Always multiply by 1000 when displaying per-1M.
- Headline prices prefer CRIS > Standard > Flex. The actual direct on-demand price may be higher.
- Some models have `pricing.imagePrice` (per image), `pricing.videoPrice` (per video), or `pricing.searchUnitPrice` (per query) instead of token pricing.
- `availableRegions` includes both in-region AND CRIS-reachable regions. A model showing 33 regions doesn't mean it's deployed in 33 regions — many are reachable via CRIS.
- Model IDs with `:` in them use `_` in the per-model API path (e.g., `anthropic.claude-sonnet-4-20250514-v1_0.json`).
- PT variants (e.g., `model:0:24k`) are context-window variants of the base model with the same pricing.
