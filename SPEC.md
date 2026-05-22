# Bedrock Model Metadata API

## Overview

AWS Bedrock의 공식 SDK(`ListFoundationModels`, `GetFoundationModel`)는 콘솔에 표시되는 모델 메타데이터의 상당 부분을 리턴하지 않는다. 그러나 **같은 API 엔드포인트**(`GET /foundation-models`)가 실제로는 이 데이터를 모두 리턴하고 있으며, SDK의 botocore service model에 shape가 정의되지 않아 deserialization 단계에서 drop되고 있을 뿐이다.

이 프로젝트는 SigV4로 직접 서명하여 raw HTTP 호출을 수행하고, SDK가 버리는 숨겨진 필드(특히 `consoleIDEMetadata`)를 포함한 전체 메타데이터를 수집하여 정적 JSON으로 서빙하는 경량 서비스다.

## Problem Statement

NextWorld라는 ISV 고객이 Bedrock 모델을 자사 플랫폼에 통합하면서, 모델 선택 시 메타데이터(capabilities, max tokens, categories, supported languages 등)를 API로 자동 수집하길 원한다. 현재 공식 SDK로는 이 정보가 불완전하게 리턴되어, 수동 입력이 필요한 상황.

## Discovery Summary

### 2026-03-02 발견 사항

1. **공식 SDK 응답** (`aws bedrock list-foundation-models`):
   - `modelId`, `modelName`, `providerName`
   - `inputModalities`, `outputModalities`
   - `responseStreamingSupported`
   - `customizationsSupported`
   - `inferenceTypesSupported`
   - `modelLifecycle.status`

2. **Raw HTTP 응답** (SigV4 직접 서명, `GET /foundation-models`):
   - SDK 응답의 모든 필드 +
   - `consoleIDEMetadata` (JSON string, 핵심!)
   - `converse` (maxTokensDefault, maxTokensMaximum, reasoningSupported, userImageTypesSupported 등)
   - `description` (fullDescription, shortDescription, releaseDate, maxContextWindow, modelAttributes, supportedLanguages, supportedUseCases 등)
   - `modelFamily`
   - `modelLifecycle.startOfLifeTime` (release date)
   - `explicitPromptCaching`
   - `guardrailsSupported`
   - `batchSupported`
   - `latencyOptimizationSupported`
   - `intelligentPromptRouting`
   - `featuresSupported`

3. **`consoleIDEMetadata` 필드 구조** (JSON string, parse 필요):

```json
{
  "converse": {
    "additionalRequestFieldsSchema": "...",
    "invokeChatFeatures": {
      "chatHistorySupported": true,
      "citationsSupported": true,
      "documentsSupported": true,
      "functionToolStreamSupported": true,
      "functionToolSupported": true,
      "reasoningSupported": { "embedded": false },
      "systemRoleSupported": true,
      "userImageTypesSupported": ["jpeg", "png", "gif", "webp"],
      "userPassthroughDocumentTypesSupported": ["pdf"],
      "userVideoTypesSupported": []
    },
    "mappingConfig": { "mappingId": "...", "version": 4 },
    "maxTokensDefault": 32000,
    "maxTokensMaximum": 64000,
    "stopSequencesDefault": []
  },
  "description": {
    "fullDescription": "Claude Sonnet 4.6 delivers frontier intelligence...",
    "shortDescription": "Claude Sonnet 4.6 delivers frontier intelligence at scale...",
    "invokeExample": "{...}",
    "maxContextWindow": "1M (beta)",
    "modelAttributes": "Hybrid reasoning, adaptive thinking, efficient code generation, enhanced text generation, agentic search, efficient research, computer use, tool use, real-time support, task efficiency, text and image inputs, steering, memory",
    "releaseDate": 1.7713512E9,
    "supportedLanguages": "English, French, Modern Standard Arabic, Mandarin Chinese, Hindi, Spanish, Portuguese, Korean, Japanese, German, Russian, Polish, other languages.",
    "supportedUseCases": "Complex agentic systems, multi-agent orchestration, ai agents...",
    "supportedFormats": "<placeholder>",
    "unsupportedUseCases": "<placeholder>",
    "policy": "https://aws.amazon.com/legal/bedrock/third-party-models/",
    "version": "v1"
  },
  "featureSupport": {
    "agent": { "isStreamingSupported": true, "isSupported": true },
    "batchInference": {
      "baseModelSupported": false,
      "crossRegionSupported": true,
      "customModelSupported": false,
      "tokenizerSupported": true
    },
    "explicitPromptCaching": { "isSupported": true },
    "flow": { "isSupported": true },
    "guardrails": { "isSupported": true },
    "intelligentPromptRouting": { "isSupported": false },
    "knowledgeBase": {
      "isExternalSourcesSupported": true,
      "isParsingSupported": false,
      "isSupported": true
    },
    "latencyOptimized": { "isSupported": false },
    "modelEvaluation": { "isSupported": true },
    "prompt": { "isSupported": true },
    "systemTool": {
      "supportedSystemTools": [{ "name": "web_search" }]
    }
  },
  "modelFamily": "Claude Sonnet",
  "productId": "prod-ffvjxvh4ltq64",
  "schemaVersion": "v1"
}
```

### 콘솔 표시 항목 → API 매핑

| Console UI Field | Source | Path |
|---|---|---|
| Categories | consoleIDEMetadata | `description.modelAttributes` |
| Max input tokens | consoleIDEMetadata | `description.maxContextWindow` |
| Supported Languages | consoleIDEMetadata | `description.supportedLanguages` |
| Release date | consoleIDEMetadata | `description.releaseDate` (epoch) |
| Full description | consoleIDEMetadata | `description.fullDescription` |
| Short description | consoleIDEMetadata | `description.shortDescription` |
| Supported use cases | consoleIDEMetadata | `description.supportedUseCases` |
| Invoke example | consoleIDEMetadata | `description.invokeExample` |
| Version | consoleIDEMetadata | `description.version` |
| Model family | consoleIDEMetadata | `modelFamily` |
| Agent support | consoleIDEMetadata | `featureSupport.agent` |
| Knowledge Base support | consoleIDEMetadata | `featureSupport.knowledgeBase` |
| Batch inference | consoleIDEMetadata | `featureSupport.batchInference` |
| System tools (web_search) | consoleIDEMetadata | `featureSupport.systemTool.supportedSystemTools` |
| Max output tokens | top-level | `converse.maxTokensMaximum` |
| Reasoning support | top-level | `converse.reasoningSupported` |
| Image types supported | top-level | `converse.userImageTypesSupported` |
| Document types supported | top-level | `converse.userDocumentTypesSupported` |
| Video types supported | top-level | `converse.userVideoTypesSupported` |
| Prompt caching | top-level | `explicitPromptCaching.isSupported` |
| Guardrails | top-level | `guardrailsSupported` |
| Batch support | top-level | `batchSupported` |
| Latency optimization | top-level | `latencyOptimizationSupported` |
| Intelligent prompt routing | top-level | `intelligentPromptRouting.isSupported` |
| Input modalities | top-level | `inputModalities` |
| Output modalities | top-level | `outputModalities` |
| Model lifecycle | top-level | `modelLifecycle` |
| Start of life (release) | top-level | `modelLifecycle.startOfLifeTime` |
| Customizations | top-level | `customizationsSupported` |
| Inference types | top-level | `inferenceTypesSupported` |

### 중요: SDK가 데이터를 버리는 이유

AWS SDK(boto3, JS SDK 등)는 botocore/smithy service model에 정의된 shape만 deserialization한다. `consoleIDEMetadata`, `converse`, `description` 등의 필드가 service model shape에 없으므로 SDK가 자동으로 drop한다. 따라서 **SDK를 사용하지 않고 SigV4 직접 서명으로 raw HTTP 호출**해야 이 데이터를 가져올 수 있다.

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                   EventBridge Rule                       │
│              cron(0 6 * * ? *)  (daily 6AM UTC)          │
└──────────────────────┬──────────────────────────────────┘
                       │ trigger
                       ▼
┌─────────────────────────────────────────────────────────┐
│                    Lambda Function                       │
│                                                         │
│  1. SigV4 sign + GET /foundation-models (raw HTTP)      │
│     - Target: bedrock.{region}.amazonaws.com             │
│     - Regions: us-east-1, us-west-2, eu-west-1, etc.   │
│                                                         │
│  2. SigV4 sign + GET /inference-profiles (raw HTTP)     │
│     - Cross-region inference profile data               │
│                                                         │
│  3. Parse consoleIDEMetadata (JSON string → object)     │
│                                                         │
│  4. Merge & normalize into clean JSON schema            │
│                                                         │
│  5. Upload to S3                                        │
│     - models.json (full catalog)                        │
│     - models/{modelId}.json (per-model detail)          │
│     - inference-profiles.json                           │
│     - metadata.json (last updated, model count, etc.)   │
└──────────────────────┬──────────────────────────────────┘
                       │ s3:PutObject
                       ▼
┌─────────────────────────────────────────────────────────┐
│                      S3 Bucket                           │
│                                                         │
│  /v1/models                                             │
│  /v1/models/{modelId}                                   │
│  /v1/inference-profiles                                 │
│  /v1/metadata                                           │
└──────────────────────┬──────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────┐
│                   CloudFront Distribution                │
│                                                         │
│  https://bedrock-models.example.com/v1/models            │
│                                                         │
│  - Cache TTL: 24h (matches update frequency)            │
│  - CORS: Allow all origins                              │
│  - Gzip compression enabled                             │
└─────────────────────────────────────────────────────────┘
```

## API Endpoints to Call

### 1. List Foundation Models (Primary)

```
GET https://bedrock.{region}.amazonaws.com/foundation-models
```

- **Authentication**: SigV4 (service: `bedrock`, region: target region)
- **Required Headers**:
  - `x-amz-date`
  - `x-amz-security-token` (if using temporary credentials)
  - `authorization` (SigV4 signature)
  - `x-amz-content-sha256`: `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` (empty body SHA256)
- **Response**: JSON with `modelSummaries` array
- **Critical**: Do NOT use SDK. Use raw HTTP with SigV4 to preserve all fields including `consoleIDEMetadata`.

### 2. List Inference Profiles (Cross-Region Info)

```
GET https://bedrock.{region}.amazonaws.com/inference-profiles
```

- **Authentication**: Same SigV4
- **Response**: JSON with `inferenceProfileSummaries` array
- **Contains**: Which models support cross-region inference, which regions are included, US vs Global prefix

### 3. (Optional) Get Foundation Model (Per-Model Detail)

```
GET https://bedrock.{region}.amazonaws.com/foundation-models/{modelId}
```

- **Note**: The list endpoint already returns full detail for all models, so this is only needed if you want to verify individual model data.

## Target Regions

Primary collection from:
- `us-east-1` (most comprehensive model catalog)
- `us-west-2` (secondary, good overlap)

Optional expansion:
- `eu-west-1` (EU availability check)
- `ap-northeast-1` (APAC availability check)

## Output JSON Schema

### models.json (Full Catalog)

```json
{
  "lastUpdated": "2026-03-02T06:00:00Z",
  "region": "us-west-2",
  "totalModels": 102,
  "models": [
    {
      "modelId": "anthropic.claude-sonnet-4-6",
      "modelName": "Claude Sonnet 4.6",
      "providerName": "Anthropic",
      "modelFamily": "Claude Sonnet",

      "modalities": {
        "input": ["TEXT", "IMAGE"],
        "output": ["TEXT"]
      },

      "context": {
        "maxInputTokens": "1M (beta)",
        "maxOutputTokens": 128000,
        "maxOutputTokensDefault": 128000
      },

      "capabilities": {
        "categories": "Hybrid reasoning, adaptive thinking, efficient code generation, enhanced text generation, agentic search, efficient research, computer use, tool use, real-time support, task efficiency, text and image inputs, steering, memory",
        "reasoning": { "supported": true, "embedded": false },
        "promptCaching": true,
        "guardrails": true,
        "streaming": true,
        "batchInference": { "baseModel": false, "crossRegion": true },
        "agent": { "supported": true, "streaming": true },
        "knowledgeBase": { "supported": true, "externalSources": true, "parsing": false },
        "flow": true,
        "promptOptimization": true,
        "latencyOptimization": false,
        "intelligentPromptRouting": false,
        "systemTools": ["web_search"]
      },

      "mediaSupport": {
        "inputImages": ["jpeg", "png", "gif", "webp"],
        "inputDocuments": ["pdf"],
        "inputVideos": [],
        "inputAudio": []
      },

      "description": {
        "short": "Claude Sonnet 4.6 delivers frontier intelligence at scale...",
        "full": "Claude Sonnet 4.6 delivers frontier intelligence at scale—built for coding, agents, and enterprise workflows...",
        "useCases": "Complex agentic systems, multi-agent orchestration...",
        "invokeExample": "{...}"
      },

      "metadata": {
        "releaseDate": "2026-02-17T18:00:00Z",
        "startOfLifeTime": "2026-02-17T18:00:00Z",
        "version": "v1",
        "lifecycle": "ACTIVE",
        "supportedLanguages": "English, French, Modern Standard Arabic, Mandarin Chinese, Hindi, Spanish, Portuguese, Korean, Japanese, German, Russian, Polish, other languages.",
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
          },
          {
            "profileId": "global.anthropic.claude-sonnet-4-6",
            "name": "Global Anthropic Claude Sonnet 4.6",
            "type": "GLOBAL",
            "regions": ["all supported"]
          }
        ]
      }
    }
  ]
}
```

## Implementation Details

### Lambda Runtime

- **Runtime**: Python 3.12 or Node.js 20.x
- **Memory**: 512MB (JSON processing can be large)
- **Timeout**: 60 seconds
- **IAM Permissions**:
  - `bedrock:ListFoundationModels`
  - `bedrock:ListInferenceProfiles`
  - `s3:PutObject` on target bucket
  - CloudWatch Logs

### SigV4 Signing (Python Example)

```python
import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
import requests
import json

def get_raw_foundation_models(region: str) -> dict:
    """
    Call GET /foundation-models with SigV4 signing,
    bypassing SDK deserialization to preserve hidden fields.
    """
    session = boto3.Session()
    credentials = session.get_credentials().get_frozen_credentials()

    url = f"https://bedrock.{region}.amazonaws.com/foundation-models"

    request = AWSRequest(method="GET", url=url, headers={
        "Content-Type": "application/json",
    })

    SigV4Auth(credentials, "bedrock", region).add_auth(request)

    response = requests.get(
        url,
        headers=dict(request.headers),
    )

    return response.json()
```

### consoleIDEMetadata Parsing

```python
import json

def parse_model(raw_model: dict) -> dict:
    """Parse a raw model entry including consoleIDEMetadata."""

    # consoleIDEMetadata is a JSON string, needs double-parse
    console_meta = {}
    if raw_model.get("consoleIDEMetadata"):
        console_meta = json.loads(raw_model["consoleIDEMetadata"])

    desc = console_meta.get("description", {})
    feature = console_meta.get("featureSupport", {})
    converse_meta = console_meta.get("converse", {})

    # Top-level converse (different from consoleIDEMetadata.converse)
    converse_top = raw_model.get("converse", {}) or {}

    # Merge release date from multiple sources
    release_date = None
    if desc.get("releaseDate"):
        # consoleIDEMetadata has epoch float (e.g., 1.7713512E9)
        import datetime
        release_date = datetime.datetime.fromtimestamp(
            desc["releaseDate"], tz=datetime.timezone.utc
        ).isoformat()
    elif raw_model.get("modelLifecycle", {}).get("startOfLifeTime"):
        release_date = raw_model["modelLifecycle"]["startOfLifeTime"]

    return {
        "modelId": raw_model["modelId"],
        "modelName": raw_model["modelName"],
        "providerName": raw_model["providerName"],
        "modelFamily": console_meta.get("modelFamily") or raw_model.get("modelFamily"),
        "modalities": {
            "input": raw_model.get("inputModalities", []),
            "output": raw_model.get("outputModalities", []),
        },
        "context": {
            "maxInputTokens": desc.get("maxContextWindow"),
            "maxOutputTokens": converse_top.get("maxTokensMaximum"),
            "maxOutputTokensDefault": converse_top.get("maxTokensDefault"),
        },
        "capabilities": {
            "categories": desc.get("modelAttributes"),
            "reasoning": converse_top.get("reasoningSupported"),
            "promptCaching": raw_model.get("explicitPromptCaching", {}).get("isSupported", False),
            "guardrails": raw_model.get("guardrailsSupported", False),
            "streaming": raw_model.get("responseStreamingSupported", False),
            "agent": feature.get("agent"),
            "knowledgeBase": feature.get("knowledgeBase"),
            "batchInference": raw_model.get("batchSupported"),
            "flow": feature.get("flow", {}).get("isSupported", False),
            "promptOptimization": raw_model.get("featuresSupported", {}).get("promptOptimization", False),
            "latencyOptimization": raw_model.get("latencyOptimizationSupported", False),
            "intelligentPromptRouting": raw_model.get("intelligentPromptRouting", {}).get("isSupported", False),
            "systemTools": [t["name"] for t in feature.get("systemTool", {}).get("supportedSystemTools", [])],
        },
        "mediaSupport": {
            "inputImages": converse_top.get("userImageTypesSupported", []),
            "inputDocuments": converse_top.get("userDocumentTypesSupported", []),
            "inputVideos": converse_top.get("userVideoTypesSupported", []),
        },
        "description": {
            "short": desc.get("shortDescription"),
            "full": desc.get("fullDescription"),
            "useCases": desc.get("supportedUseCases"),
            "invokeExample": desc.get("invokeExample"),
        },
        "metadata": {
            "releaseDate": release_date,
            "version": desc.get("version"),
            "lifecycle": raw_model.get("modelLifecycle", {}).get("status"),
            "supportedLanguages": desc.get("supportedLanguages"),
            "customizations": raw_model.get("customizationsSupported", []),
            "inferenceTypes": raw_model.get("inferenceTypesSupported", []),
        },
    }
```

## Update Frequency

- **Daily at 06:00 UTC** (EventBridge cron)
- 이유: 새 모델 런칭은 보통 business hours(PST 기준 오전)에 발생. UTC 06:00 = PST 22:00(전날 밤)이므로, 당일 아침에는 최신 데이터 보장.
- 긴급 업데이트 필요 시 Lambda 수동 invoke 가능.

## Deployment

- **IaC**: Terraform (>= 1.5.0, AWS Provider ~> 5.0)
- **Stack components**:
  - S3 Bucket (versioning enabled, AES256 encryption, public access blocked)
  - CloudFront Distribution (OAC, security headers, HTTP/2+3, Brotli/Gzip)
  - WAF v2 (rate limiting, AWS Managed Rules, read-only method enforcement)
  - Lambda Function (Python 3.12, X-Ray tracing, reserved concurrency=1)
  - EventBridge Rule (daily cron)
  - IAM Role (least privilege, scoped to specific resources)
  - CloudWatch Log Group (30-day retention)
  - S3 Access Logs Bucket (30-day lifecycle)

## Security Considerations

- **WAF v2**: CloudFront에 WAF 연동 (rate limiting 1000 req/5min, AWS Managed Rules: Common, Bad Inputs, IP Reputation, read-only method enforcement)
- **CloudFront OAC**: S3 직접 접근 차단, CloudFront OAC를 통한 서명된 요청만 허용
- **S3 보안**: Public access 완전 차단, AES256 서버사이드 암호화, 버전 관리 활성화
- **Security Headers**: HSTS (preload), X-Content-Type-Options, X-Frame-Options: DENY, CSP: default-src 'none', Referrer-Policy
- **TLS**: HTTPS 강제 리다이렉트, TLSv1.2 최소 버전 (커스텀 도메인 시)
- **Lambda IAM**: 최소 권한 원칙 (`bedrock:List*` + `s3:PutObject` on `/v1/*` only)
- **Lambda 보안**: Reserved concurrency=1 (동시 실행 방지), X-Ray 트레이싱 활성화
- **로깅**: CloudFront access logs + CloudWatch Lambda logs (30일 보존)
- **응답 데이터**: 민감 정보 없음 (모두 공개 모델 메타데이터)

## Open Questions / Future Enhancements

1. **Pricing 데이터 포함 여부**: 콘솔 pricing 페이지도 별도 API 있을 수 있음. 추후 조사.
2. **Multi-region diff**: 리전별 모델 가용성 차이를 하나의 JSON에 표현하는 스키마
3. **Webhook/SNS**: 새 모델 감지 시 알림
4. **Versioning**: 이전 스냅샷 보존하여 모델 카탈로그 변경 이력 추적
5. **PFR 제출**: Bedrock 서비스팀에 `ListFoundationModels` API shape 확장 요청 (공식적으로 이 데이터를 SDK에서도 제공하도록)

## Customer Deliverable

NextWorld 고객에게는:
1. CloudFront URL 하나 공유
2. 고객이 daily polling으로 최신 모델 메타데이터 수집
3. 기존 `ListFoundationModels` 호출을 이 API로 대체하면 모든 메타데이터 확보 가능
