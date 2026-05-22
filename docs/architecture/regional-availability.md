# Regional Availability

## Source of Truth

Regional availability data is sourced from the **official AWS documentation**:

```
https://docs.aws.amazon.com/bedrock/latest/userguide/models-region-compatibility.html
```

This is more accurate than querying individual region APIs because:
1. Some models are deployed but not yet reflected in the API
2. The docs include CRIS availability (Geo + Global), not just in-region
3. The docs cover all 33+ regions; local collection may only query a subset

## How It Works

The AWS docs page contains one HTML table per model with columns:
- **Region** (e.g., `us-east-1 (N. Virginia)`)
- **In-Region** (model is directly available)
- **Geo** (available via geographic CRIS)
- **Global** (available via global CRIS)

Availability is indicated by `<img alt="Yes">` or `<img alt="No">` tags.

## Merge Strategy

```
availableRegions = API_collected_regions ∪ AWS_docs_regions
```

The collector first queries regions via the Bedrock API (for metadata), then merges the AWS docs data to ensure completeness. The union means a model shows as available if *either* source reports it.

## Covered Regions

| Geo | Regions |
|-----|---------|
| **NAMER** | us-east-1, us-east-2, us-west-2, us-west-1, ca-central-1, ca-west-1 |
| **EMEA** | eu-west-1, eu-west-2, eu-west-3, eu-central-1, eu-central-2, eu-north-1, eu-south-1, eu-south-2, af-south-1, il-central-1 |
| **APAC** | ap-northeast-1, ap-northeast-2, ap-northeast-3, ap-southeast-1~7, ap-south-1, ap-south-2, ap-east-2 |
| **LATAM** | sa-east-1, mx-central-1 |
| **MEA** | me-west-1, me-central-1, me-south-1 |
| **GovCloud** | us-gov-west-1, us-gov-east-1 |

## Name Mapping

Some models have different names in the AWS docs vs the Bedrock API. These are mapped via aliases:

| AWS Docs Name | API Name |
|--------------|----------|
| Claude 3.5 Sonnet V2:0 | Claude 3.5 Sonnet v2 |
| Mistral Large | Mistral Large (24.07) |
| NVIDIA Nemotron 3 Super 120B | NVIDIA Nemotron 3 Super 120B A12B |
| Sd3.5 Large | Stable Diffusion 3.5 Large |
| Stable Image Core V1:1 | Stable Image Core 1.0 |
