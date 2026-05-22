# V1 API Reference (Legacy)

The V1 API provides the same model catalog without pricing data. It is maintained for backward compatibility.

## Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/metadata.json` | API status and last update time |
| `GET` | `/v1/models.json` | Full model catalog (no pricing) |
| `GET` | `/v1/models/{modelId}.json` | Individual model detail (no pricing) |
| `GET` | `/v1/inference-profiles.json` | Cross-region inference profiles |

## Differences from V2

| Feature | V1 | V2 |
|---------|----|----|
| Pricing data | No | Yes |
| `totalRegions` in metadata | No | Yes |
| `features` array | No | Yes |
| Model schema | Same (minus `pricing`) | Full |

## Migration

Replace `/v1/` with `/v2/` in your API calls. The model schema is identical except V2 adds the `pricing` field. If `pricing` is `null`, the model has no pricing data available.
