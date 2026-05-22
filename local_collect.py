"""
Local data collector - Lambda handler와 동일 로직으로 실제 AWS 데이터 수집.
결과를 frontend/public/v2/ 에 저장하여 로컬 미리보기 가능.

Regional availability는 AWS 공식 문서를 source of truth로 사용:
https://docs.aws.amazon.com/bedrock/latest/userguide/models-region-compatibility.html
"""
import json
import os
import re
import sys

# Lambda handler를 직접 import
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "lambda"))
from handler import (
    ALL_BEDROCK_REGIONS,
    collect_region_data,
    fetch_pricing,
    parse_model,
    FALLBACK_METADATA,
)
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "frontend", "public")

AWS_DOCS_URL = "https://docs.aws.amazon.com/bedrock/latest/userguide/models-region-compatibility.html"


def fetch_aws_docs_regions() -> dict[str, dict]:
    """AWS 공식 문서에서 모델별 리전 가용성을 파싱한다.

    Returns: {modelName: {in_region: [...], geo_cris: [...], global_cris: [...], all_regions: [...]}}
    """
    import requests as _req
    print(f"  Fetching {AWS_DOCS_URL}")
    resp = _req.get(AWS_DOCS_URL, timeout=30)
    resp.raise_for_status()
    html = resp.text
    print(f"  Got {len(html)} bytes")

    # Each model table: <table><caption><a href="...model-card-*">ModelName</a></caption>...
    tables = re.findall(
        r'<table[^>]*>\s*<caption>(.*?)</caption>(.*?)</table>',
        html, re.DOTALL,
    )

    result = {}
    for caption_html, table_body in tables:
        name_match = re.search(r'>([^<]+)</a>', caption_html)
        if not name_match:
            name_match = re.search(r'([^<]+)', caption_html)
        model_name = name_match.group(1).strip() if name_match else ""
        if not model_name:
            continue

        rows = re.findall(r'<tr>(.*?)</tr>', table_body, re.DOTALL)
        in_region, geo_cris, global_cris = [], [], []

        for row in rows:
            if '<th' in row:
                continue
            code_match = re.search(r'<code[^>]*>([^<]+)</code>', row)
            if not code_match:
                continue
            region_code = code_match.group(1).strip()
            alts = re.findall(r'alt="(Yes|No)"', row)

            if len(alts) >= 1 and alts[0] == 'Yes':
                in_region.append(region_code)
            if len(alts) >= 2 and alts[1] == 'Yes':
                geo_cris.append(region_code)
            if len(alts) >= 3 and alts[2] == 'Yes':
                global_cris.append(region_code)

        result[model_name] = {
            'in_region': sorted(in_region),
            'geo_cris': sorted(geo_cris),
            'global_cris': sorted(global_cris),
            'all_regions': sorted(set(in_region + geo_cris + global_cris)),
        }

    print(f"  Parsed {len(result)} models from AWS docs")
    return result


# Docs model name -> API model name (where they differ)
DOCS_NAME_ALIASES = {
    "Claude 3.5 Sonnet V2:0": "Claude 3.5 Sonnet v2",
    "Mistral Large": "Mistral Large (24.07)",
    "Mistral Large 2407": "Mistral Large (24.02)",
    "Mistral Small": "Mistral Small (24.02)",
    "NVIDIA Nemotron 3 Super 120B": "NVIDIA Nemotron 3 Super 120B A12B",
    "Palmyra Vision 7B": "Writer Palmyra Vision 7B",
    "Pixtral Large": "Pixtral Large (25.02)",
    "Qwen3 32B": "Qwen3 32B (dense)",
    "Ray V2:0": "Ray v2",
    "Rerank": "Rerank 1.0",
    "Sd3.5 Large": "Stable Diffusion 3.5 Large",
    "Stable Image Core V1:1": "Stable Image Core 1.0",
    "Stable Image Ultra V1:1": "Stable Image Ultra 1.0",
}

# 주요 리전만 먼저 빠르게 (전체 33개는 시간 오래 걸림)
QUICK_REGIONS = [
    "us-east-1", "us-west-2", "eu-west-1", "eu-central-1",
    "ap-northeast-1", "ap-southeast-1", "ap-northeast-2",
    "ca-central-1", "sa-east-1",
]

def main():
    use_all = "--all" in sys.argv
    regions = ALL_BEDROCK_REGIONS if use_all else QUICK_REGIONS
    print(f"Collecting from {len(regions)} regions: {', '.join(regions)}")

    now = datetime.now(timezone.utc).isoformat()

    # Fetch pricing
    print("\n[1/3] Fetching pricing data...")
    pricing_data = {}
    try:
        pricing_data = fetch_pricing()
        print(f"  Got pricing for {len(pricing_data)} model IDs")
    except Exception as e:
        print(f"  Pricing fetch failed (non-blocking): {e}")

    # Collect from regions in parallel
    # Fetch AWS docs regional availability (source of truth)
    print("\n[1.5/3] Fetching AWS docs regional availability...")
    docs_regions = {}
    try:
        docs_regions = fetch_aws_docs_regions()
    except Exception as e:
        print(f"  AWS docs fetch failed (non-blocking): {e}")

    print(f"\n[2/3] Collecting models from {len(regions)} regions (parallel)...")
    all_models = {}
    all_inference_profiles = {}

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(collect_region_data, r): r for r in regions}
        for future in as_completed(futures):
            region, raw_models, profiles = future.result()
            if raw_models:
                print(f"  {region}: {len(raw_models)} models, {len(profiles)} profiles")
                all_inference_profiles[region] = profiles
                for raw in raw_models:
                    model_id = raw.get("modelId", "")
                    if model_id not in all_models:
                        all_models[model_id] = parse_model(raw, profiles)
                        all_models[model_id]["availableRegions"] = [region]
                    else:
                        if region not in all_models[model_id].get("availableRegions", []):
                            all_models[model_id]["availableRegions"].append(region)
                        # Merge CRIS profiles from this region
                        existing_profiles = {p["profileId"]: p for p in all_models[model_id]["crossRegionInference"]["profiles"]}
                        new_parsed = parse_model(raw, profiles)
                        for p in new_parsed["crossRegionInference"]["profiles"]:
                            if p["profileId"] not in existing_profiles:
                                all_models[model_id]["crossRegionInference"]["profiles"].append(p)
                                all_models[model_id]["crossRegionInference"]["supported"] = True
                            else:
                                ep = existing_profiles[p["profileId"]]
                                ep["regions"] = sorted(set(ep["regions"]) | set(p["regions"]))
            else:
                print(f"  {region}: skipped (no data or error)")

    models_list = sorted(all_models.values(), key=lambda m: m.get("modelId", ""))

    # PT variant inheritance
    for model in models_list:
        mid = model["modelId"]
        if mid.count(":") >= 2 and not model["capabilities"]["categories"]:
            base_id = ":".join(mid.split(":")[:2])
            base = all_models.get(base_id)
            if not base:
                base_id = mid.split(":")[0]
                base = all_models.get(base_id)
            if base and base["capabilities"]["categories"]:
                model["capabilities"]["categories"] = base["capabilities"]["categories"]
                if not model["description"]["full"]:
                    model["description"] = base["description"].copy()
                if not model["metadata"]["supportedLanguages"]:
                    model["metadata"]["supportedLanguages"] = base["metadata"]["supportedLanguages"]

    # Merge AWS docs regions into availableRegions (docs = source of truth)
    if docs_regions:
        # Build modelName -> model mapping
        by_name = {}
        for model in models_list:
            n = model.get("modelName", "")
            if n and n not in by_name:
                by_name[n] = model

        docs_matched = 0
        docs_added_regions = 0
        for doc_name, doc_data in docs_regions.items():
            # Try direct name match, then alias
            api_name = DOCS_NAME_ALIASES.get(doc_name, doc_name)
            model = by_name.get(api_name)
            if not model:
                continue

            docs_matched += 1
            # Merge: docs all_regions (in-region + geo + global) as the complete set
            doc_all = set(doc_data['all_regions'])
            api_existing = set(model.get("availableRegions", []))
            new_regions = doc_all - api_existing
            if new_regions:
                docs_added_regions += len(new_regions)
                model["availableRegions"] = sorted(api_existing | doc_all)

        print(f"\n  AWS docs merge: matched {docs_matched}/{len(docs_regions)} models, added {docs_added_regions} regions")

    # Load fallback pricing for models not in AWS Pricing API
    import os as _os
    _fallback_pricing_path = _os.path.join(_os.path.dirname(__file__), "lambda", "fallback_pricing.json")
    with open(_fallback_pricing_path) as _fp:
        _fallback_prices = json.load(_fp)
    # Remove comment key
    _fallback_prices.pop("_comment", None)

    # Hard-coded: pricing display name -> catalog modelName
    PRICING_TO_CATALOG = {
        "Nova 2.0 Lite": "Nova 2 Lite",
        "Nova 2.0 Pro": "Nova 2 Pro Preview",
        "Nova Sonic 2.0": "Nova 2 Sonic",
        "R1": "DeepSeek-R1",
        "Magistral Small 1.2": "Magistral Small 2509",
        "Ministral 8B 3.0": "Ministral 3 8B",
        "Pixtral Large 25.02": "Pixtral Large (25.02)",
        "NVIDIA Nemotron Nano 2": "NVIDIA Nemotron Nano 9B v2",
        "NVIDIA Nemotron Nano 2 VL": "NVIDIA Nemotron Nano 12B v2 VL BF16",
        "Voxtral Mini 1.0": "Voxtral Mini 3B 2507",
        "Voxtral Small 1.0": "Voxtral Small 24B 2507",
        "Mistral Large 2407": "Mistral Large (24.07)",
    }
    # Build reverse: catalog name -> pricing data
    hardcoded = {}
    for pricing_name, catalog_name in PRICING_TO_CATALOG.items():
        if pricing_name in pricing_data:
            hardcoded[catalog_name] = pricing_data[pricing_name]

    # Enrich with pricing (fuzzy match by modelName)
    def _normalize(s):
        return s.lower().replace("-", " ").replace(".", " ").replace("_", " ").strip()

    pricing_by_norm = {_normalize(k): v for k, v in pricing_data.items()}

    def _match_pricing(model_name):
        if not model_name:
            return None
        # 0. Hard-coded mapping
        if model_name in hardcoded:
            return hardcoded[model_name]
        # 1. Exact match
        if model_name in pricing_data:
            return pricing_data[model_name]
        # 2. Normalized
        norm = _normalize(model_name)
        if norm in pricing_by_norm:
            return pricing_by_norm[norm]
        # 3. Prefix match
        for pname, pdata in pricing_data.items():
            pnorm = _normalize(pname)
            if norm.startswith(pnorm) or pnorm.startswith(norm):
                return pdata
        # 4. Substring
        for pname, pdata in pricing_data.items():
            pnorm = _normalize(pname)
            if len(pnorm) >= 3 and pnorm in norm:
                return pdata
        return None

    models_list_v2 = []
    matched_pricing = 0
    for model in models_list:
        model_v2 = model.copy()
        model_name = model_v2.get("modelName") or ""
        model_pricing = _match_pricing(model_name)
        # Check if matched pricing has any useful data
        def _has_useful_price(p):
            if not p: return False
            return any(p.get(k) is not None for k in [
                'inputTokenPrice', 'outputTokenPrice', 'imagePrice',
                'videoPrice', 'videoSecPrice', 'searchUnitPrice',
            ])
        # Fallback: use fallback_pricing.json if API match has no useful price
        if (not _has_useful_price(model_pricing)) and model_name in _fallback_prices:
            fb = _fallback_prices[model_name]
            model_pricing = {
                "modelName": model_name,
                "prices": [],
                "source": "fallback",
                **{k: v for k, v in fb.items()},
            }
        if model_pricing:
            matched_pricing += 1
        model_v2["pricing"] = model_pricing
        models_list_v2.append(model_v2)

    # Data cleanup before output
    cleaned_empty = 0
    cleaned_dups = 0
    cleaned_nl = 0
    for model in models_list_v2:
        # 1. Clean literal \n in descriptions
        desc = model.get("description") or {}
        for field in ("short", "full", "useCases"):
            val = desc.get(field)
            if val and "\\n" in val:
                desc[field] = val.replace("\\n", "\n")
                cleaned_nl += 1

        # 2. Clean pricing: remove empty inferenceType, deduplicate
        p = model.get("pricing")
        if p and p.get("prices"):
            before = len(p["prices"])
            # Filter empty inferenceType
            p["prices"] = [e for e in p["prices"] if (e.get("inferenceType") or "").strip()]
            cleaned_empty += before - len(p["prices"])
            # Deduplicate by (inferenceType, pricePerUnit)
            seen = set()
            deduped = []
            for e in p["prices"]:
                key = (e["inferenceType"], round(e.get("pricePerUnit", 0), 8))
                if key not in seen:
                    seen.add(key)
                    deduped.append(e)
            cleaned_dups += len(p["prices"]) - len(deduped)
            p["prices"] = deduped

    print(f"\n  Cleanup: removed {cleaned_empty} empty types, {cleaned_dups} dups, fixed {cleaned_nl} \\n in descriptions")

    print(f"\n[3/3] Writing output files...")
    print(f"  Total models: {len(models_list_v2)}")
    print(f"  Models with pricing: {matched_pricing}")
    print(f"  Regions collected: {len(regions)}")

    # Write v2 files
    v2_dir = os.path.join(OUTPUT_DIR, "v2")
    os.makedirs(v2_dir, exist_ok=True)

    catalog = {
        "lastUpdated": now,
        "regions": regions,
        "totalRegions": len(regions),
        "totalModels": len(models_list_v2),
        "models": models_list_v2,
    }
    with open(os.path.join(v2_dir, "models.json"), "w") as f:
        json.dump(catalog, f, ensure_ascii=False, indent=2, default=str)

    primary_profiles = all_inference_profiles.get("us-east-1", [])
    metadata = {
        "lastUpdated": now,
        "regions": regions,
        "totalRegions": len(regions),
        "totalModels": len(models_list_v2),
        "totalInferenceProfiles": len(primary_profiles),
        "version": "2.0.0",
        "features": ["pricing", "all-regions", "parallel-collection"],
    }
    with open(os.path.join(v2_dir, "metadata.json"), "w") as f:
        json.dump(metadata, f, ensure_ascii=False, indent=2, default=str)

    # Also write v1 for backward compat
    v1_dir = os.path.join(OUTPUT_DIR, "v1")
    os.makedirs(v1_dir, exist_ok=True)
    catalog_v1 = {
        "lastUpdated": now,
        "regions": regions,
        "totalModels": len(models_list),
        "models": models_list,
    }
    with open(os.path.join(v1_dir, "models.json"), "w") as f:
        json.dump(catalog_v1, f, ensure_ascii=False, indent=2, default=str)
    with open(os.path.join(v1_dir, "metadata.json"), "w") as f:
        json.dump({
            "lastUpdated": now,
            "regions": regions,
            "totalModels": len(models_list),
            "totalInferenceProfiles": len(primary_profiles),
            "version": "1.0.0",
        }, f, ensure_ascii=False, indent=2, default=str)

    print(f"\nDone! Files saved to:")
    print(f"  {v2_dir}/models.json")
    print(f"  {v2_dir}/metadata.json")
    print(f"  {v1_dir}/models.json")
    print(f"  {v1_dir}/metadata.json")
    print(f"\nRun local server:")
    print(f"  cd {OUTPUT_DIR} && python3 -m http.server 8080")


if __name__ == "__main__":
    main()
