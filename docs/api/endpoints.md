# API Endpoints

All endpoints return `application/json`. No authentication required. Data is refreshed daily at 06:00 UTC.

---

## GET /models

Returns the full model catalog with pricing, capabilities, and regional availability.

```bash
curl https://BASE_URL/models.json
```

### Response

```json
{
  "lastUpdated": "2026-04-06T06:00:00+00:00",
  "regions": ["us-east-1", "us-east-2", "..."],
  "totalRegions": 33,
  "totalModels": 146,
  "models": [...]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `lastUpdated` | `string` | ISO 8601 timestamp of the last collection |
| `regions` | `string[]` | Regions from which data was collected |
| `totalRegions` | `integer` | Number of regions scanned |
| `totalModels` | `integer` | Number of models |
| `models` | `Model[]` | Array of [Model objects](/docs/api/model-schema) |

---

## GET /models/{modelId}

Returns a single model by ID.

```bash
curl https://BASE_URL/models/anthropic.claude-sonnet-4-20250514-v1_0.json
```

> `/` and `:` in model IDs are replaced with `_` in the URL path.

Returns a single [Model object](/docs/api/model-schema).

---

## GET /metadata

Returns API status and collection metadata.

```bash
curl https://BASE_URL/metadata.json
```

### Response

```json
{
  "lastUpdated": "2026-04-06T06:00:00+00:00",
  "regions": ["us-east-1", "..."],
  "totalRegions": 33,
  "totalModels": 146,
  "totalInferenceProfiles": 80,
  "version": "1.0.0"
}
```

---

## GET /inference-profiles

Returns cross-region inference (CRIS) profile data from the primary region.

```bash
curl https://BASE_URL/inference-profiles.json
```

### Response

```json
{
  "lastUpdated": "2026-04-06T06:00:00+00:00",
  "region": "us-east-1",
  "totalProfiles": 80,
  "profiles": [...]
}
```

---

## Usage Examples

### Find models by provider

```bash
curl -s BASE_URL/models.json | jq '[.models[] | select(.providerName == "Anthropic") | {id: .modelId, name: .modelName}]'
```

### Get pricing for a model

```bash
curl -s BASE_URL/models.json | jq '
  .models[] | select(.modelName == "Claude Sonnet 4") |
  {name: .modelName, input_1M: (.pricing.inputTokenPrice * 1000), output_1M: (.pricing.outputTokenPrice * 1000)}'
```

### Check availability in a region

```bash
curl -s BASE_URL/models.json | jq '[.models[] | select(.availableRegions | index("ap-northeast-2")) | .modelName]'
```

### Compare model pricing

```bash
curl -s BASE_URL/models.json | jq '
  [.models[] | select(.pricing.inputTokenPrice != null) |
   {name: .modelName, provider: .providerName,
    in: (.pricing.inputTokenPrice * 1000), out: (.pricing.outputTokenPrice * 1000)}] |
  sort_by(.in) | .[:10]'
```
