# V2 API Reference

The V2 API is the recommended version. It includes pricing data, all regions, and CRIS profiles.

## Base URL

All endpoints return `Content-Type: application/json`. No authentication required. Data is refreshed daily at 06:00 UTC.

## Endpoints

### GET /v2/metadata

Returns API status and collection metadata.

```bash
curl https://BASE_URL/v2/metadata.json
```

**Response:**

```json
{
  "lastUpdated": "2026-04-06T06:00:00.000000+00:00",
  "regions": ["us-east-1", "us-east-2", "..."],
  "totalRegions": 33,
  "totalModels": 146,
  "totalInferenceProfiles": 80,
  "version": "2.0.0",
  "features": ["pricing", "all-regions", "parallel-collection"]
}
```

| Field | Type | Description |
|-------|------|-------------|
| `lastUpdated` | `string` | ISO 8601 timestamp of the last collection run (UTC) |
| `regions` | `string[]` | AWS regions from which data was collected |
| `totalRegions` | `integer` | Total number of regions scanned |
| `totalModels` | `integer` | Total number of models in the catalog |
| `totalInferenceProfiles` | `integer` | Total number of inference profiles |
| `version` | `string` | API schema version (`2.0.0`) |
| `features` | `string[]` | V2 feature flags |

---

### GET /v2/models

Returns the full model catalog with pricing.

```bash
curl https://BASE_URL/v2/models.json
```

**Response:**

```json
{
  "lastUpdated": "2026-04-06T06:00:00.000000+00:00",
  "regions": ["us-east-1", "..."],
  "totalRegions": 33,
  "totalModels": 146,
  "models": [...]
}
```

The `models` array contains [Model objects](/docs/api/model-schema).

---

### GET /v2/models/{modelId}

Returns a single model by ID.

```bash
curl https://BASE_URL/v2/models/anthropic.claude-sonnet-4-20250514-v1_0.json
```

> In `{modelId}`, `/` and `:` characters are replaced with `_`.

**Response:** A single [Model object](/docs/api/model-schema).

---

### GET /v2/inference-profiles

Returns cross-region inference profile data.

```bash
curl https://BASE_URL/v2/inference-profiles.json
```

**Response:**

```json
{
  "lastUpdated": "2026-04-06T06:00:00.000000+00:00",
  "region": "us-east-1",
  "totalProfiles": 80,
  "profiles": [...]
}
```
