# Cross-Region Inference (CRIS)

Cross-Region Inference Service (CRIS) allows you to use Bedrock models across AWS regions without deploying in each region individually.

## Profile Types

| Type | Prefix | Description | Example |
|------|--------|-------------|---------|
| **US** | `us.` | Routes within US regions | `us.anthropic.claude-sonnet-4-20250514-v1:0` |
| **EU** | `eu.` | Routes within European regions | `eu.anthropic.claude-sonnet-4-20250514-v1:0` |
| **APAC** | `apac.` | Routes within Asia-Pacific regions | `apac.anthropic.claude-sonnet-4-20250514-v1:0` |
| **GLOBAL** | `global.` | Routes to any commercial region | `global.anthropic.claude-sonnet-4-20250514-v1:0` |

## How It Works

Instead of calling a model directly with its model ID, you use the CRIS profile ID:

```python
# Direct (single region)
response = bedrock.invoke_model(modelId="anthropic.claude-sonnet-4-20250514-v1:0")

# CRIS US (routes to any US region)
response = bedrock.invoke_model(modelId="us.anthropic.claude-sonnet-4-20250514-v1:0")

# CRIS Global (routes to any region worldwide)
response = bedrock.invoke_model(modelId="global.anthropic.claude-sonnet-4-20250514-v1:0")
```

## Data Collection

CRIS profiles are collected from the `/inference-profiles` endpoint in each region. Since different regions return different profiles, the collector **merges profiles across all regions** to get the complete picture.

For example, `us-east-1` returns US profiles, `eu-west-1` returns EU profiles, and `ap-northeast-1` returns APAC profiles.

## Pricing Impact

CRIS pricing is often different from direct on-demand:

| Tier | Relative Cost | Use Case |
|------|--------------|----------|
| CRIS Global | Varies | Maximum throughput, no geographic constraints |
| CRIS Geo (US/EU/APAC) | Often lower than direct | Higher throughput within a geography |
| Direct On-Demand | Base price | Single-region, data residency requirements |

The API's headline `inputTokenPrice`/`outputTokenPrice` prefers CRIS Global > CRIS Regional > Standard, reflecting what most users actually pay.

## Current Coverage

- **50 models** have CRIS profiles
- **US**: 48 profiles
- **EU**: 20 profiles
- **APAC**: 11 profiles
- **GLOBAL**: 14 profiles
