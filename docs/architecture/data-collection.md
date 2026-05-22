# Data Collection

The data collection pipeline aggregates model metadata from multiple AWS sources into a unified catalog.

## Pipeline Overview

```
┌─────────────────────────────────────────────┐
│              Data Collection                 │
│                                              │
│  1. AWS Price List API (2 service codes)     │
│  2. AWS Docs (region availability)           │
│  3. Bedrock API (33 regions, parallel)       │
│  4. Merge CRIS profiles across regions       │
│  5. Merge AWS docs regions                   │
│  6. Match pricing to models (fuzzy)          │
│  7. Cleanup (dedup, normalize)               │
│  8. Write v1 + v2 JSON files                 │
└─────────────────────────────────────────────┘
```

## Step 1: Pricing Collection

Two AWS Pricing API service codes are queried in parallel:

### `AmazonBedrockFoundationModels`
- Covers: Claude, Cohere, AI21 Labs, Writer
- Price unit: **per 1M tokens** (converted to per 1K for storage)
- Includes: Standard, CRIS Global, CRIS Regional, Batch, Cache tiers
- Identified by `servicename` containing `(Amazon Bedrock Edition)`

### `AmazonBedrock`
- Covers: Nova, DeepSeek, Llama, Mistral, Google, OpenAI, etc.
- Price unit: **per 1K tokens** (stored as-is)
- Tiers identified by `inferenceType` field

### Pricing Priority
```
CRIS Global > CRIS Regional (APAC/EU) > Standard On-Demand > Flex
```

Cache and batch prices are excluded from headline pricing but included in the `prices` breakdown array.

## Step 2: AWS Docs Region Availability

The official AWS documentation page is the **source of truth** for regional availability:

```
https://docs.aws.amazon.com/bedrock/latest/userguide/models-region-compatibility.html
```

The HTML is parsed to extract per-model availability across three categories:
- **In-Region**: Model is directly available
- **Geo CRIS**: Available via geographic cross-region inference
- **Global CRIS**: Available via global cross-region inference

All three categories are merged into `availableRegions`.

## Step 3: Bedrock API Collection

Each region's `/foundation-models` and `/inference-profiles` endpoints are queried using SigV4-signed requests with the `x-console-consumer: true` header. This header unlocks the `consoleIDEMetadata` field that the SDK normally drops.

Regions are queried in parallel (10 workers).

## Step 4: Pricing Matching

Models are matched to pricing entries by `modelName` using a multi-step fuzzy matcher:

1. **Hard-coded mapping** (for known name mismatches)
2. **Exact match** by display name
3. **Normalized match** (lowercase, remove hyphens/dots)
4. **Prefix match** (pricing name starts with model name or vice versa)
5. **Substring match** (for short pricing names like "R1")
6. **Fallback pricing** from `fallback_pricing.json`

## Local vs Lambda

| Feature | `local_collect.py` | `lambda/handler.py` |
|---------|-------------------|---------------------|
| AWS Docs scraper | Yes | No (Lambda has all regions) |
| Hard-coded pricing aliases | Yes | No |
| Fallback pricing enrichment | Yes (with `_has_useful_price` check) | Basic |
| Output | `frontend/public/v1/` + `v2/` | S3 bucket |
| Default regions | 9 quick regions | All 33+ |
