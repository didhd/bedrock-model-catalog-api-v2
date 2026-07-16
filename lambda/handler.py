"""
Bedrock Model Metadata Collector Lambda

SigV4로 직접 서명하여 raw HTTP 호출을 수행하고,
SDK가 버리는 숨겨진 필드(consoleIDEMetadata 등)를 포함한
전체 메타데이터를 수집하여 S3에 정적 JSON으로 서빙한다.

v2: Pricing, CRIS profiles (US/EU/APAC/GLOBAL), AWS docs region availability.
"""

import json
import logging
import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from typing import Any

import boto3
import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

logger = logging.getLogger()
logger.setLevel(logging.INFO)

S3_BUCKET = os.environ["S3_BUCKET"]

ALL_BEDROCK_REGIONS = [
    "us-east-1", "us-east-2", "us-west-2", "us-west-1", "ca-central-1", "ca-west-1",
    "eu-west-1", "eu-west-2", "eu-west-3", "eu-central-1", "eu-central-2", "eu-north-1", "eu-south-1", "eu-south-2", "af-south-1", "il-central-1",
    "ap-northeast-1", "ap-northeast-2", "ap-northeast-3", "ap-southeast-1", "ap-southeast-2", "ap-southeast-3", "ap-southeast-4", "ap-southeast-5", "ap-southeast-6", "ap-southeast-7", "ap-south-1", "ap-south-2", "ap-east-2",
    "sa-east-1", "mx-central-1",
    "me-west-1", "me-central-1", "me-south-1",
    "us-gov-west-1", "us-gov-east-1",
]

_regions_env = json.loads(os.environ.get("REGIONS", "[]"))
REGIONS = _regions_env if _regions_env else ALL_BEDROCK_REGIONS
PRIMARY_REGION = os.environ.get("PRIMARY_REGION", "us-east-1")

# Mantle (bedrock-mantle) endpoint regions — OpenAI Responses / Chat Completions API.
# Source: https://docs.aws.amazon.com/bedrock/latest/userguide/inference-responses.html
# us-gov-west-1 requires GovCloud creds (returns 401 from commercial), so it is
# collected best-effort and simply skipped if unauthorized.
MANTLE_REGIONS = [
    "us-east-1", "us-east-2", "us-west-2",
    "ap-southeast-3", "ap-south-1", "ap-southeast-2", "ap-northeast-1",
    "eu-central-1", "eu-west-1", "eu-west-2", "eu-south-1", "eu-north-1",
    "sa-east-1", "us-gov-west-1",
]

_fallback_path = os.path.join(os.path.dirname(__file__), "fallback_metadata.json")
with open(_fallback_path, "r") as _f:
    FALLBACK_METADATA = json.load(_f)

_fallback_pricing_path = os.path.join(os.path.dirname(__file__), "fallback_pricing.json")
with open(_fallback_pricing_path, "r") as _f:
    FALLBACK_PRICING = json.load(_f)
    FALLBACK_PRICING.pop("_comment", None)
    FALLBACK_PRICING.pop("_source", None)

AWS_DOCS_URL = "https://docs.aws.amazon.com/bedrock/latest/userguide/models-region-compatibility.html"

# Pricing display name -> catalog modelName (where they differ)
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


def sigv4_request(url: str, region: str, service: str = "bedrock") -> dict:
    session = boto3.Session()
    creds = session.get_credentials().get_frozen_credentials()
    req = AWSRequest(method="GET", url=url, headers={"Content-Type": "application/json", "x-console-consumer": "true"})
    SigV4Auth(creds, service, region).add_auth(req)
    resp = requests.get(url, headers=dict(req.headers), timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_foundation_models(region: str) -> list[dict]:
    return sigv4_request(f"https://bedrock.{region}.amazonaws.com/foundation-models", region).get("modelSummaries", [])


def fetch_inference_profiles(region: str) -> list[dict]:
    return sigv4_request(f"https://bedrock.{region}.amazonaws.com/inference-profiles?maxResults=1000", region).get("inferenceProfileSummaries", [])


def collect_region_data(region: str) -> tuple[str, list[dict], list[dict]]:
    try:
        models = fetch_foundation_models(region)
        profiles = fetch_inference_profiles(region)
        logger.info(f"  {region}: {len(models)} models, {len(profiles)} profiles")
        return region, models, profiles
    except Exception as e:
        logger.warning(f"Failed {region}: {e}")
        return region, [], []


# ── Mantle (bedrock-mantle endpoint) ───────────────────────────

def _mantle_norm(model_id: str) -> str:
    """Normalize a mantle/classic model id so equivalent models collide.

    Collapses provider aliases, version tails (-v1:0), -instruct suffix, dated
    snapshots (-2026-03-05 / -20251001), and trailing build numbers (only in the
    -N:0 form, e.g. gpt-oss-120b-1:0) to a bare alphanumeric key.

    IMPORTANT: minor version tails like -4-8 (opus 4.8) or -5 (sonnet 5) are NOT
    stripped — they distinguish distinct models. Verified against the live classic
    + mantle catalogs to produce zero cross-family collisions.
    """
    s = model_id.split(":")[0]
    s = s.replace("moonshotai.", "moonshot.")
    s = re.sub(r"-v\d+$", "", s)               # -v1
    s = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", s)  # dated snapshot -2026-03-05
    s = re.sub(r"-\d{8}$", "", s)              # 8-digit date -20251001
    s = re.sub(r"-instruct$", "", s)
    # Strip a trailing build number only when the original id carried it as "-N:"
    # (e.g. openai.gpt-oss-120b-1:0). This never touches minor-version tails.
    bm = re.search(r"-(\d+):", model_id)
    if bm and s.endswith("-" + bm.group(1)):
        s = s[: -(len(bm.group(1)) + 1)]
    return re.sub(r"[^a-z0-9]", "", s.lower())


def fetch_mantle_models() -> dict[str, list[str]]:
    """Return {mantle_model_id: [regions...]} across all Mantle regions.

    Uses SigV4 against the OpenAI-compatible /v1/models endpoint. Regions that
    return non-200 (e.g. GovCloud without matching creds) are skipped.
    """
    def _one(region: str) -> tuple[str, list[str]]:
        url = f"https://bedrock-mantle.{region}.api.aws/v1/models"
        try:
            data = sigv4_request(url, region, service="bedrock")
            return region, [m.get("id", "") for m in data.get("data", []) if m.get("id")]
        except Exception as e:
            logger.warning(f"Mantle {region} failed: {e}")
            return region, []

    id_regions: dict[str, list[str]] = {}
    with ThreadPoolExecutor(max_workers=14) as ex:
        for region, ids in ex.map(_one, MANTLE_REGIONS):
            for mid in ids:
                id_regions.setdefault(mid, [])
                if region not in id_regions[mid]:
                    id_regions[mid].append(region)
    logger.info(f"Mantle: {len(id_regions)} models across {len(MANTLE_REGIONS)} regions")
    return id_regions


# ── AWS model cards (authoritative metadata source) ────────────

_CARD_BASE = "https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-"
_CARD_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}
# Known model-id -> card slug overrides where the derived candidates don't match
# the AWS docs slug (e.g. docs renamed the SKU).
CARD_SLUG_ALIASES = {
    "google.gemma-3-27b-it": "google-gemma-3-27b-pt",
    "nvidia.nemotron-nano-12b-v2": "nvidia-nvidia-nemotron-nano-12b-v2-vl-bf16",
    "nvidia.nemotron-nano-9b-v2": "nvidia-nvidia-nemotron-nano-9b-v2",
}


def _card_slug_candidates(model_id: str) -> list[str]:
    """Candidate AWS-docs card slugs for a model id (best-effort, no network)."""
    if model_id in CARD_SLUG_ALIASES:
        return [CARD_SLUG_ALIASES[model_id]]
    prov, rest = (model_id.split(".", 1) + [""])[:2] if "." in model_id else (model_id, "")
    rest = re.sub(r"-\d{4}-\d{2}-\d{2}$", "", rest)  # drop dated snapshot
    variants: list[str] = []
    seen = set()
    for base in (rest, rest.replace("-instruct", "")):
        for form in (base.replace(".", "-").replace("_", "-"),
                     base.replace(".", "").replace("_", "-")):
            for cand in (f"{prov}-{form}", f"{prov}-{prov}-{form}"):
                if cand not in seen:
                    seen.add(cand); variants.append(cand)
            if prov == "moonshotai":
                for cand in (f"moonshot-{form}", f"moonshotai-{form}"):
                    if cand not in seen:
                        seen.add(cand); variants.append(cand)
    return variants


def _parse_card_date(raw: str) -> str | None:
    m = re.match(r"([A-Za-z]+)\.?\s+(\d{1,2}),\s+(\d{4})", raw.strip())
    if not m:
        return None
    mon = _CARD_MONTHS.get(m.group(1)[:3].lower())
    if not mon:
        return None
    try:
        return datetime(int(m.group(3)), mon, int(m.group(2)), tzinfo=timezone.utc).isoformat()
    except ValueError:
        return None


def _parse_model_card(md: str) -> dict:
    """Parse an AWS model-card markdown into a metadata dict."""
    out: dict = {}
    # Description: the paragraph right after the "## Model Details" anchor, before
    # the "+ **..." bullet list. Drop the trailing "For more information...card" note.
    dm = re.search(r"## Model Details\s*\n<a name=\"[^\"]*\"></a>\s*\n+(.+?)(?:\n\+ \*\*|\n\n)", md, re.DOTALL)
    if dm:
        desc = dm.group(1).strip()
        desc = re.sub(r"\s*For more information about model development[^\n]*", "", desc).strip()
        # Strip any remaining markdown links -> keep link text only
        desc = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", desc)
        if desc:
            out["description"] = desc
    m = re.search(r"\*\*Model launch date:\*\*\s*([^\n+|]+)", md)
    if m:
        rd = _parse_card_date(m.group(1))
        if rd:
            out["releaseDate"] = rd
    m = re.search(r"\*\*Context window:\*\*\s*([^\n+|]+)", md)
    if m:
        out["maxContextWindow"] = m.group(1).strip().replace(" tokens", "").strip()
    m = re.search(r"\*\*Model lifecycle:\*\*\s*([^\n+|]+)", md)
    if m:
        out["lifecycle"] = m.group(1).strip().upper()

    # Modality + endpoint table: 4 columns (Input | Output | APIs | Endpoints).
    # Each cell is "![...icon-(yes|no)...](url) Label".
    def _cell(cell: str) -> tuple[str | None, str | None]:
        icon = re.search(r"icon-(yes|no)", cell)
        # label is the trailing word(s) after the image markdown
        label = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", cell).strip()
        return (icon.group(1) if icon else None), (label or None)

    tbl = re.search(r"\|\s*\*\*Input Modalities\*\*.*?\n\|[-\s|]+\n(.*?)(?:\n\n|\n#)", md, re.DOTALL)
    inp, outp, eps = [], [], {}
    if tbl:
        for row in tbl.group(1).split("\n"):
            if not row.strip().startswith("|"):
                continue
            cells = [c for c in row.split("|")][1:-1]  # drop outer empties
            if len(cells) >= 2:
                iy, ilabel = _cell(cells[0])
                oy, olabel = _cell(cells[1])
                if iy == "yes" and ilabel:
                    inp.append(ilabel.upper())
                if oy == "yes" and olabel:
                    outp.append(olabel.upper())
            if len(cells) >= 4:
                ey, elabel = _cell(cells[3])
                if elabel in ("bedrock-runtime", "bedrock-mantle"):
                    eps[elabel] = (ey == "yes")
    # Preserve doc order but keep TEXT first for readability
    def _order(mods):
        pref = ["TEXT", "IMAGE", "AUDIO", "VIDEO", "SPEECH", "EMBEDDING"]
        return sorted(set(mods), key=lambda x: pref.index(x) if x in pref else 99)
    if inp:
        out["inputModalities"] = _order(inp)
    if outp:
        out["outputModalities"] = _order(outp)
    if eps:
        out["endpoints"] = eps

    # Service tiers (Standard | Priority | Flex | Reserved)
    st = re.search(r"## Service Tiers.*?\|\s*\*\*Standard\*\*.*?\n\|[-\s|]+\n\|(.*?)\|\s*\n", md, re.DOTALL)
    if st:
        cells = st.group(1).split("|")
        labels = ["Standard", "Priority", "Flex", "Reserved"]
        tiers = [labels[i] for i, c in enumerate(cells) if i < len(labels) and "icon-yes" in c]
        if tiers:
            out["serviceTiers"] = tiers

    # Regional availability (In-Region / Geo / Global columns per region row)
    ra = re.search(r"## Regional Availability(.*?)(?:## Quotas|## Sample|\Z)", md, re.DOTALL)
    if ra:
        regions = re.findall(r"\|\s*([a-z]{2}-[a-z]+-\d+)\s*\(", ra.group(1))
        if regions:
            out["cardRegions"] = sorted(set(regions))
    return out


def fetch_model_card(model_id: str, _cache: dict = {}) -> dict:
    """Fetch + parse the AWS model card for a model id. Returns {} if none found.

    Tries candidate slugs against the docs site; caches results (including misses)
    per process so repeated lookups are cheap.
    """
    if model_id in _cache:
        return _cache[model_id]
    result: dict = {}
    for slug in _card_slug_candidates(model_id):
        if slug in _cache.get("_slug_miss", set()):
            continue
        try:
            resp = requests.get(f"{_CARD_BASE}{slug}.md", timeout=15)
        except Exception:
            continue
        if resp.status_code == 200 and "Model launch date" in resp.text:
            result = _parse_model_card(resp.text)
            result["_slug"] = slug
            break
        _cache.setdefault("_slug_miss", set()).add(slug)
    _cache[model_id] = result
    return result


def fetch_model_cards(model_ids: list[str]) -> dict[str, dict]:
    """Fetch model cards for many ids in parallel. Returns {id: parsed_card}."""
    cards: dict[str, dict] = {}
    with ThreadPoolExecutor(max_workers=8) as ex:
        futs = {ex.submit(fetch_model_card, mid): mid for mid in model_ids}
        for fut in as_completed(futs):
            mid = futs[fut]
            try:
                c = fut.result()
                if c:
                    cards[mid] = c
            except Exception as e:
                logger.warning(f"Card {mid} failed: {e}")
    logger.info(f"Model cards: {len(cards)}/{len(model_ids)} resolved")
    return cards


def _split_usagetype(usagetype: str) -> tuple[str | None, str]:
    """Extract (mantle_core_id, remainder) from a pricing usagetype.

    e.g. 'USW2-zai.glm5-mantle-input-tokens-priority' -> ('zai.glm5', 'input-tokens-priority')
         'USE1-xai.grok-4.3-mantle-output-tokens-standard' -> ('xai.grok-4.3', 'output-tokens-standard')
    Returns (None, "") if the usagetype does not embed a provider.model id.
    """
    m = re.match(r"^[A-Z0-9]+-(.+)", usagetype)
    if not m:
        return None, ""
    rest = m.group(1)
    parts = re.split(r"-(?:mantle-)?(input|output|cache|batch)", rest, maxsplit=1)
    core = parts[0]
    remainder = "-".join(parts[1:]) if len(parts) > 1 else ""
    if "." not in core:
        return None, ""
    return core, remainder.lower()


def fetch_mantle_pricing() -> dict[str, dict]:
    """Build {mantle_core_id: pricing dict} from the AmazonBedrock price list.

    Links pricing to mantle model ids via the usagetype (no hardcoded prices).
    Normalizes per-1K vs per-1M units to the catalog's per-1K storage convention.
    Headline input/output prices use Standard on-demand (lowest, excluding
    flex/priority/cache/batch); the full breakdown is kept in prices[].
    """
    client = boto3.client("pricing", region_name="us-east-1")
    paginator = client.get_paginator("get_products")
    raw: dict[str, list[dict]] = {}
    provider: dict[str, str] = {}
    for page in paginator.paginate(ServiceCode="AmazonBedrock",
                                   Filters=[{"Type": "TERM_MATCH", "Field": "regionCode", "Value": "us-east-1"}],
                                   MaxResults=100):
        for item_json in page["PriceList"]:
            item = json.loads(item_json) if isinstance(item_json, str) else item_json
            attrs = item["product"]["attributes"]
            ut = attrs.get("usagetype", "")
            core, remainder = _split_usagetype(ut)
            if not core:
                continue
            provider.setdefault(core, attrs.get("provider", ""))
            for tv in item.get("terms", {}).get("OnDemand", {}).values():
                for dv in tv.get("priceDimensions", {}).values():
                    ppu = float(dv.get("pricePerUnit", {}).get("USD", "0"))
                    if ppu <= 0:
                        continue
                    unit = (dv.get("unit") or "").lower()
                    per_k = ppu / 1000 if "1m" in unit else ppu  # normalize to per-1K
                    low = ut.lower()
                    direction = "Input" if "input" in low else "Output" if "output" in low else None
                    if direction is None:
                        continue
                    tier_parts = []
                    if "cache" in low: tier_parts.append("Prompt cache read")
                    if "batch" in low: tier_parts.append("Batch")
                    if "priority" in low: tier_parts.append("Priority")
                    elif "flex" in low: tier_parts.append("Flex")
                    itype = " ".join(tier_parts + [f"{direction} tokens"]).strip()
                    raw.setdefault(core, []).append(
                        {"inferenceType": itype, "pricePerUnit": per_k, "region": "us-east-1"})

    result = {}
    for core, entries in raw.items():
        std_in = std_out = None
        for e in entries:
            t = e["inferenceType"].lower()
            if any(k in t for k in ("cache", "batch", "priority", "flex")):
                continue
            if "input" in t:
                std_in = e["pricePerUnit"] if std_in is None else min(std_in, e["pricePerUnit"])
            elif "output" in t:
                std_out = e["pricePerUnit"] if std_out is None else min(std_out, e["pricePerUnit"])
        result[core] = {
            "inputTokenPrice": std_in, "outputTokenPrice": std_out,
            "prices": entries, "provider": provider.get(core, ""),
            "source": "AmazonBedrock-mantle",
        }
    logger.info(f"Mantle pricing: {len(result)} models")
    return result


# ── Pricing ────────────────────────────────────────────────────

def _fetch_pricing_foundation_models() -> dict:
    client = boto3.client('pricing', region_name='us-east-1')
    paginator = client.get_paginator('get_products')
    pages = paginator.paginate(ServiceCode='AmazonBedrockFoundationModels',
                               Filters=[{'Type': 'TERM_MATCH', 'Field': 'regionCode', 'Value': 'us-east-1'}], MaxResults=100)
    global_p, regional_p, direct_p = {}, {}, {}
    raw_entries: dict[str, list] = {}
    for page in pages:
        for item_json in page['PriceList']:
            item = json.loads(item_json) if isinstance(item_json, str) else item_json
            attrs = item['product']['attributes']
            svc, ut = attrs.get('servicename', ''), attrs.get('usagetype', '')
            if '(Amazon Bedrock Edition)' not in svc:
                continue
            name = svc.replace(' (Amazon Bedrock Edition)', '')
            for tv in item.get('terms', {}).get('OnDemand', {}).values():
                for dv in tv.get('priceDimensions', {}).values():
                    ppm = float(dv.get('pricePerUnit', {}).get('USD', '0'))
                    if ppm <= 0:
                        continue
                    utl = ut.lower().replace('_', '')
                    if 'reserved' in utl or 'lctx' in utl:
                        continue
                    price = ppm / 1000
                    d = 'Input tokens' if 'inputtoken' in utl else 'Output tokens' if 'outputtoken' in utl else ut
                    parts = []
                    if 'cache' in utl: parts.append('Prompt cache read')
                    if 'global' in utl: parts.append('cross-region global')
                    elif any(k in utl for k in ('apac', 'eu-cris', 'eu.')): parts.append('cross-region geo')
                    if 'batch' in utl: parts.append('batch')
                    itype = f"{' '.join(parts + [d])}".strip().capitalize()
                    raw_entries.setdefault(name, []).append({'inferenceType': itype, 'pricePerUnit': price, 'region': 'us-east-1'})
                    if 'batch' in utl or 'cache' in utl:
                        continue
                    is_g = 'global' in utl
                    is_r = any(k in utl for k in ('apac', 'eu-cris', 'eu.'))
                    tgt = global_p if is_g else regional_p if is_r else direct_p
                    tgt.setdefault(name, {'input': None, 'output': None})
                    if 'inputtoken' in utl:
                        if tgt[name]['input'] is None or ppm < tgt[name]['input']: tgt[name]['input'] = ppm
                    elif 'outputtoken' in utl:
                        if tgt[name]['output'] is None or ppm < tgt[name]['output']: tgt[name]['output'] = ppm
    result = {}
    for n in set(list(global_p) + list(regional_p) + list(direct_p)):
        g, r, d = global_p.get(n, {}), regional_p.get(n, {}), direct_p.get(n, {})
        inp = (g.get('input') or r.get('input') or d.get('input'))
        out = (g.get('output') or r.get('output') or d.get('output'))
        result[n] = {'modelName': n, 'inputTokenPrice': inp / 1000 if inp else None,
                     'outputTokenPrice': out / 1000 if out else None, 'prices': raw_entries.get(n, []),
                     'source': 'AmazonBedrockFoundationModels'}
    return result


def _fetch_pricing_bedrock() -> dict:
    client = boto3.client('pricing', region_name='us-east-1')
    paginator = client.get_paginator('get_products')
    raw: dict[str, list] = {}
    for page in paginator.paginate(ServiceCode='AmazonBedrock', MaxResults=100):
        for item_json in page['PriceList']:
            item = json.loads(item_json) if isinstance(item_json, str) else item_json
            attrs = item['product']['attributes']
            mn, region, it = attrs.get('model', ''), attrs.get('regionCode', ''), attrs.get('inferenceType', '')
            if not mn: continue
            for tv in item.get('terms', {}).get('OnDemand', {}).values():
                for dv in tv.get('priceDimensions', {}).values():
                    p = float(dv.get('pricePerUnit', {}).get('USD', '0'))
                    if p > 0:
                        raw.setdefault(mn, []).append({'inferenceType': it, 'pricePerUnit': p, 'region': region})
    result = {}
    for dn, prices in raw.items():
        us = [p for p in prices if p['region'] == 'us-east-1']
        dp = us if us else prices
        g_in = g_out = r_in = r_out = s_in = s_out = f_in = f_out = None
        for p in dp:
            t = p['inferenceType'].lower()
            if 'batch' in t or 'priority' in t or 'cache' in t: continue
            gc = 'cross-region' in t and ('global' in t or not any(k in t for k in ('us', 'eu', 'apac', 'ap')))
            rc = 'cross-region' in t and any(k in t for k in ('us', 'eu', 'apac', 'ap'))
            fl = 'flex' in t
            if 'input' in t:
                if gc: g_in = min(p['pricePerUnit'], g_in) if g_in else p['pricePerUnit']
                elif rc: r_in = min(p['pricePerUnit'], r_in) if r_in else p['pricePerUnit']
                elif fl: f_in = min(p['pricePerUnit'], f_in) if f_in else p['pricePerUnit']
                else: s_in = min(p['pricePerUnit'], s_in) if s_in else p['pricePerUnit']
            if 'output' in t:
                if gc: g_out = min(p['pricePerUnit'], g_out) if g_out else p['pricePerUnit']
                elif rc: r_out = min(p['pricePerUnit'], r_out) if r_out else p['pricePerUnit']
                elif fl: f_out = min(p['pricePerUnit'], f_out) if f_out else p['pricePerUnit']
                else: s_out = min(p['pricePerUnit'], s_out) if s_out else p['pricePerUnit']
        result[dn] = {'modelName': dn, 'inputTokenPrice': g_in or r_in or s_in or f_in,
                      'outputTokenPrice': g_out or r_out or s_out or f_out,
                      'prices': us or prices, 'source': 'AmazonBedrock'}
    return result


def fetch_pricing() -> dict:
    data: dict[str, dict] = {}
    for n, fb in FALLBACK_PRICING.items():
        data[n] = {'modelName': n, 'inputTokenPrice': fb.get('inputTokenPrice'), 'outputTokenPrice': fb.get('outputTokenPrice'),
                   'prices': [], 'source': 'fallback', **{k: v for k, v in fb.items() if k not in ('inputTokenPrice', 'outputTokenPrice')}}
    with ThreadPoolExecutor(max_workers=2) as ex:
        f1, f2 = ex.submit(_fetch_pricing_foundation_models), ex.submit(_fetch_pricing_bedrock)
        try:
            fm = f1.result(timeout=60); logger.info(f"FoundationModels: {len(fm)}"); data.update(fm)
        except Exception as e: logger.warning(f"FM pricing failed: {e}")
        try:
            br = f2.result(timeout=60); logger.info(f"Bedrock: {len(br)}")
            for k, v in br.items():
                if k not in data: data[k] = v
        except Exception as e: logger.warning(f"BR pricing failed: {e}")
    logger.info(f"Total pricing: {len(data)}")
    return data


def fetch_aws_docs_regions() -> dict[str, dict]:
    try:
        resp = requests.get(AWS_DOCS_URL, timeout=30); resp.raise_for_status(); html = resp.text
    except Exception as e:
        logger.warning(f"AWS docs failed: {e}"); return {}
    tables = re.findall(r'<table[^>]*>\s*<caption>(.*?)</caption>(.*?)</table>', html, re.DOTALL)
    result = {}
    for cap, body in tables:
        m = re.search(r'>([^<]+)</a>', cap) or re.search(r'([^<]+)', cap)
        name = m.group(1).strip() if m else ""
        if not name: continue
        rows = re.findall(r'<tr>(.*?)</tr>', body, re.DOTALL)
        regions = []
        for row in rows:
            if '<th' in row: continue
            cm = re.search(r'<code[^>]*>([^<]+)</code>', row)
            if not cm: continue
            alts = re.findall(r'alt="(Yes|No)"', row)
            if any(a == 'Yes' for a in alts):
                regions.append(cm.group(1).strip())
        if regions:
            result[name] = {'all_regions': sorted(set(regions))}
    logger.info(f"AWS docs: {len(result)} models")
    return result


# ── Mantle-only model synthesis ────────────────────────────────

# Provider prefix (from the mantle model id) -> display name used across the UI
# (matches LOGO_MAP keys in the frontend). Derived from the id, not hardcoded per model.
MANTLE_PROVIDER_NAMES = {
    "anthropic": "Anthropic", "openai": "OpenAI", "google": "Google",
    "meta": "Meta", "mistral": "Mistral AI", "amazon": "Amazon",
    "cohere": "Cohere", "ai21": "AI21 Labs", "deepseek": "DeepSeek",
    "qwen": "Qwen", "minimax": "MiniMax", "moonshotai": "Moonshot AI",
    "nvidia": "NVIDIA", "writer": "Writer", "zai": "Z.AI", "xai": "xAI",
    "stabilityai": "Stability AI", "twelvelabs": "TwelveLabs", "luma": "Luma",
}


def _titleize_model_id(model_id: str) -> str:
    """Best-effort display name from a mantle model id (e.g. 'openai.gpt-5.6-luna' -> 'GPT-5.6 Luna')."""
    tail = model_id.split(".", 1)[1] if "." in model_id else model_id
    tail = re.sub(r"-instruct$", "", tail)
    acronyms = {"gpt", "glm", "vl", "oss", "it", "bf16", "a4b", "a3b",
                "a22b", "a35b", "a12b", "e2b", "moe"}
    words = []
    for w in tail.replace("_", "-").split("-"):
        if not w:
            continue
        if w in acronyms:
            words.append(w.upper())
        elif re.fullmatch(r"\d+[bBkKmM]", w):  # size suffix like 31b, 480b, 8k
            words.append(w[:-1] + w[-1].upper())
        else:
            words.append(w[0].upper() + w[1:] if w[0].isalpha() else w)
    return " ".join(words)


def synthesize_mantle_model(model_id: str, regions: list[str], mantle_price: dict | None,
                            card: dict | None = None, created: int | None = None) -> dict:
    """Build a catalog model entry for a Mantle-only model not present in the classic API.

    Metadata precedence, by field:
      - releaseDate: fallback_metadata (manually verified) > card launch date >
        mantle `created` timestamp. fallback wins first because AWS cards sometimes
        carry a wrong launch date (e.g. Gemma 4 shows Gemma 3's date).
      - context / modalities / lifecycle: card (authoritative) > fallback.
      - description: fallback.fullDescription (curated) > card description paragraph.
    Base structure mirrors parse_model()'s output shape.
    """
    provider_pfx = model_id.split(".", 1)[0]
    fb = FALLBACK_METADATA.get(model_id, {})
    if not fb and model_id.count(":") >= 2:
        fb = FALLBACK_METADATA.get(":".join(model_id.split(":")[:2]), {})
    card = card or {}
    provider = (fb.get("providerName")
                or (mantle_price or {}).get("provider")
                or MANTLE_PROVIDER_NAMES.get(provider_pfx)
                or provider_pfx.upper())
    max_out = fb.get("maxOutputTokens")
    max_out_def = fb.get("maxOutputTokensDefault")
    if max_out and max_out_def and max_out_def > max_out:
        max_out_def = max_out
    ctx_window = card.get("maxContextWindow") or fb.get("maxContextWindow")
    input_mods = card.get("inputModalities") or fb.get("inputModalities") or ["TEXT"]
    output_mods = card.get("outputModalities") or fb.get("outputModalities") or ["TEXT"]
    # fallback date wins (cards can be wrong); then card; then mantle created ts.
    release = (epoch_to_iso(fb.get("releaseDate"))
               or card.get("releaseDate")
               or epoch_to_iso(created))
    lifecycle = card.get("lifecycle") or "ACTIVE"
    # Card description is the authoritative marketing paragraph; prefer it over the
    # curated fallback text (which is a generic placeholder for cards we hadn't parsed).
    # The card has no short/long split, so when present it fills both fields.
    full_desc = card.get("description") or fb.get("fullDescription")
    short_desc = card.get("description") or fb.get("shortDescription") or full_desc
    return {
        "modelId": model_id,
        "modelName": fb.get("modelName") or _titleize_model_id(model_id),
        "providerName": provider,
        "modelFamily": fb.get("modelFamily"),
        "modalities": {"input": input_mods, "output": output_mods},
        "context": {"maxInputTokens": ctx_window,
                    "maxOutputTokens": max_out, "maxOutputTokensDefault": max_out_def},
        "capabilities": {
            "categories": fb.get("modelAttributes"), "reasoning": fb.get("reasoning"),
            "promptCaching": bool(fb.get("promptCaching", False)), "guardrails": False,
            "streaming": True, "agent": None, "knowledgeBase": None, "batchInference": None,
            "flow": False, "promptOptimization": False, "latencyOptimization": False,
            "intelligentPromptRouting": False, "systemTools": [],
        },
        "mediaSupport": {"inputImages": [], "inputDocuments": [], "inputVideos": []},
        "description": {"short": short_desc, "full": full_desc,
                        "useCases": fb.get("supportedUseCases"), "invokeExample": fb.get("invokeExample")},
        "metadata": {"releaseDate": release, "version": fb.get("version"),
                     "lifecycle": lifecycle, "supportedLanguages": fb.get("supportedLanguages"),
                     "customizations": [], "inferenceTypes": ["ON_DEMAND"]},
        "crossRegionInference": {"supported": False, "profiles": []},
        "availableRegions": sorted(regions),
        "mantle": {"supported": True, "regions": sorted(regions)},
        "pricing": None,
    }


def merge_mantle_into_models(all_models: dict[str, dict],
                             mantle_ids: dict[str, list[str]],
                             mantle_pricing: dict[str, dict]) -> set[str]:
    """Enrich overlapping classic models with the mantle flag+regions and synthesize
    entries for Mantle-only models. Mutates all_models in place.

    Mantle pricing (extracted per-tier from usagetype) is applied to every model
    that has it — both enriched and synthesized — because it is more accurate than
    the classic AmazonBedrock price match, which can leak the Flex tier into the
    headline price for these newer models. Returns the set of model ids whose
    pricing came from Mantle, so callers can skip re-matching them.
    """
    def _alnum(s: str) -> str:
        return re.sub(r"[^a-z0-9]", "", s.replace("-instruct", "").lower())

    price_by_key = {_alnum(core): pd for core, pd in mantle_pricing.items()}

    def _match_mantle_price(model_id: str) -> dict | None:
        key = _alnum(model_id.split(":")[0])
        if key in price_by_key:
            return price_by_key[key]
        for pk, pd in price_by_key.items():
            if key.startswith(pk) or pk.startswith(key):
                return pd
        return None

    def _apply_mantle_price(model: dict, mp: dict) -> None:
        model["pricing"] = {
            "modelName": model.get("modelName"),
            "inputTokenPrice": mp.get("inputTokenPrice"),
            "outputTokenPrice": mp.get("outputTokenPrice"),
            "prices": mp.get("prices", []),
        }

    # Fetch AWS model cards for every Mantle model (authoritative metadata).
    cards = fetch_model_cards(list(mantle_ids.keys()))

    def _enrich_from_card(model: dict, card: dict) -> None:
        """Fill gaps on an existing (runtime-sourced) model from its card.

        Per 'runtime wins' rule: only set fields the classic API left empty; never
        overwrite classic data. Release date is the main gap the classic API has
        for newer models — filling it fixes the newest-first sort ordering.
        """
        if not card:
            return
        md = model.setdefault("metadata", {})
        if not md.get("releaseDate") and card.get("releaseDate"):
            md["releaseDate"] = card["releaseDate"]
        ctx = model.setdefault("context", {})
        if ctx.get("maxInputTokens") in (None, "") and card.get("maxContextWindow"):
            ctx["maxInputTokens"] = card["maxContextWindow"]
        mods = model.setdefault("modalities", {})
        if not mods.get("input") and card.get("inputModalities"):
            mods["input"] = card["inputModalities"]
        if not mods.get("output") and card.get("outputModalities"):
            mods["output"] = card["outputModalities"]
        desc = model.setdefault("description", {})
        if not desc.get("full") and card.get("description"):
            desc["full"] = card["description"]
            if not desc.get("short"):
                desc["short"] = card["description"]

    norm_to_model: dict[str, dict] = {}
    for m in all_models.values():
        norm_to_model.setdefault(_mantle_norm(m["modelId"]), m)

    synth_norms: dict[str, dict] = {}
    mantle_priced: set[str] = set()
    enriched = synthesized = 0
    for mid, regs in sorted(mantle_ids.items()):
        norm = _mantle_norm(mid)
        card = cards.get(mid, {})
        existing = norm_to_model.get(norm)
        if existing is not None:
            # runtime + mantle coexist → keep classic (runtime) data, fill gaps from card
            existing["mantle"] = {"supported": True, "regions": sorted(regs)}
            existing["availableRegions"] = sorted(set(existing.get("availableRegions", [])) | set(regs))
            _enrich_from_card(existing, card)
            mp = _match_mantle_price(mid)
            if mp and (mp.get("inputTokenPrice") is not None or mp.get("outputTokenPrice") is not None):
                _apply_mantle_price(existing, mp)
                mantle_priced.add(existing["modelId"])
            enriched += 1
            continue
        # Mantle-only. Collapse dated snapshots that normalize to the same base.
        prior = synth_norms.get(norm)
        if prior is not None:
            prior["availableRegions"] = sorted(set(prior["availableRegions"]) | set(regs))
            prior["mantle"]["regions"] = sorted(set(prior["mantle"]["regions"]) | set(regs))
            if len(mid) < len(prior["modelId"]):  # prefer shorter (non-dated) id
                prior["modelId"] = mid
                prior["modelName"] = FALLBACK_METADATA.get(mid, {}).get("modelName") or _titleize_model_id(mid)
            continue
        mp = _match_mantle_price(mid)
        model = synthesize_mantle_model(mid, regs, mp, card)
        if mp:
            _apply_mantle_price(model, mp)
        else:
            # Not in the Pricing API yet — fall back to console-sourced prices
            # (fallback_pricing.json, keyed by modelName) if we have them.
            fbp = FALLBACK_PRICING.get(model.get("modelName") or "")
            if fbp and (fbp.get("inputTokenPrice") is not None or fbp.get("outputTokenPrice") is not None):
                model["pricing"] = {
                    "modelName": model.get("modelName"),
                    "inputTokenPrice": fbp.get("inputTokenPrice"),
                    "outputTokenPrice": fbp.get("outputTokenPrice"),
                    "prices": [],
                }
        synth_norms[norm] = model
        all_models[mid] = model
        norm_to_model[norm] = model
        mantle_priced.add(mid)
        synthesized += 1
    logger.info(f"Mantle merge: enriched {enriched}, synthesized {synthesized}, "
                f"mantle-priced {len(mantle_priced)}, cards {len(cards)}")
    return mantle_priced


# ── Model Parsing ──────────────────────────────────────────────

def parse_console_metadata(raw: str | None) -> dict:
    if not raw: return {}
    try: return json.loads(raw)
    except: return {}

def epoch_to_iso(epoch) -> str | None:
    if epoch is None: return None
    if isinstance(epoch, str): return epoch
    try: return datetime.fromtimestamp(float(epoch), tz=timezone.utc).isoformat()
    except: return None

def parse_model(raw_model: dict, inference_profiles: list[dict] | None = None) -> dict:
    mid = raw_model.get("modelId", "")
    cm = parse_console_metadata(raw_model.get("consoleIDEMetadata"))
    desc = cm.get("description") or {}
    td = raw_model.get("description") if isinstance(raw_model.get("description"), dict) else {}
    fb = FALLBACK_METADATA.get(mid, {})
    if not fb and mid.count(":") >= 2:
        fb = FALLBACK_METADATA.get(":".join(mid.split(":")[:2]), {})
        if not fb: fb = FALLBACK_METADATA.get(mid.split(":")[0], {})
    # Fallback has highest priority — overrides wrong consoleIDEMetadata/API data
    md = {**{k: v for k, v in td.items() if v is not None}, **{k: v for k, v in desc.items() if v is not None}, **fb}
    feat = cm.get("featureSupport", {})
    cv_m, cv_t = cm.get("converse", {}), raw_model.get("converse") or {}
    rd = epoch_to_iso(md.get("releaseDate"))
    if not rd: rd = (raw_model.get("modelLifecycle") or {}).get("startOfLifeTime")
    cr = {"supported": False, "profiles": []}
    if inference_profiles:
        for prof in inference_profiles:
            pm = prof.get("models", [])
            if not any(m.get("modelArn", "").endswith(mid) for m in pm): continue
            cr["supported"] = True
            pid = prof.get("inferenceProfileId", "")
            pfx = pid.split(".")[0] if "." in pid else ""
            pt = {"us": "US", "eu": "EU", "jp": "JP"}.get(pfx, "APAC" if pfx in ("apac", "ap") else "GLOBAL")
            regs = [m.get("modelArn", "").split(":")[3] for m in pm if ":" in m.get("modelArn", "") and m.get("modelArn", "").split(":")[3]]
            cr["profiles"].append({"profileId": pid, "name": prof.get("inferenceProfileName"), "type": pt, "regions": regs})
    ft = raw_model.get("featuresSupported") or {}
    rr = cv_t.get("reasoningSupported")
    max_out = fb.get("maxOutputTokens") or cv_t.get("maxTokensMaximum") or cv_m.get("maxTokensMaximum")
    max_out_def = fb.get("maxOutputTokensDefault") or cv_t.get("maxTokensDefault") or cv_m.get("maxTokensDefault")
    if max_out and max_out_def and max_out_def > max_out:
        max_out_def = max_out
    return {
        "modelId": mid, "modelName": raw_model.get("modelName"), "providerName": raw_model.get("providerName"),
        "modelFamily": cm.get("modelFamily") or raw_model.get("modelFamily"),
        "modalities": {"input": raw_model.get("inputModalities", []), "output": raw_model.get("outputModalities", [])},
        "context": {"maxInputTokens": md.get("maxContextWindow"), "maxOutputTokens": max_out, "maxOutputTokensDefault": max_out_def},
        "capabilities": {
            "categories": md.get("modelAttributes"), "reasoning": bool(rr) if rr is not None else None,
            "promptCaching": (raw_model.get("explicitPromptCaching") or {}).get("isSupported", False),
            "guardrails": raw_model.get("guardrailsSupported", False), "streaming": raw_model.get("responseStreamingSupported", False),
            "agent": feat.get("agent"), "knowledgeBase": feat.get("knowledgeBase"), "batchInference": feat.get("batchInference"),
            "flow": (feat.get("flow") or {}).get("isSupported", False),
            "promptOptimization": ft.get("promptOptimization") or (feat.get("prompt") or {}).get("isSupported", False),
            "latencyOptimization": raw_model.get("latencyOptimizationSupported", False),
            "intelligentPromptRouting": (raw_model.get("intelligentPromptRouting") or {}).get("isSupported", False),
            "systemTools": [t["name"] for t in (feat.get("systemTool") or {}).get("supportedSystemTools", []) if "name" in t],
        },
        "mediaSupport": {"inputImages": cv_t.get("userImageTypesSupported", []),
                         "inputDocuments": cv_t.get("userDocumentTypesSupported", []),
                         "inputVideos": cv_t.get("userVideoTypesSupported", [])},
        "description": {"short": md.get("shortDescription"), "full": md.get("fullDescription"),
                        "useCases": md.get("supportedUseCases"), "invokeExample": md.get("invokeExample")},
        "metadata": {"releaseDate": rd, "version": md.get("version"),
                     "lifecycle": (raw_model.get("modelLifecycle") or {}).get("status"),
                     "supportedLanguages": md.get("supportedLanguages"),
                     "customizations": raw_model.get("customizationsSupported", []),
                     "inferenceTypes": raw_model.get("inferenceTypesSupported", [])},
        "crossRegionInference": cr,
        "mantle": {"supported": False, "regions": []},
        "pricing": None,
    }


def upload_to_s3(key: str, data: Any) -> None:
    s3 = boto3.client("s3")
    body = json.dumps(data, ensure_ascii=False, indent=2, default=str)
    s3.put_object(Bucket=S3_BUCKET, Key=key, Body=body.encode("utf-8"),
                  ContentType="application/json", CacheControl="public, max-age=86400")
    logger.info(f"Uploaded s3://{S3_BUCKET}/{key} ({len(body)} bytes)")


# ── Handler ────────────────────────────────────────────────────

def handler(event: dict, context: Any) -> dict:
    logger.info(f"Starting: {len(REGIONS)} regions")
    now = datetime.now(timezone.utc).isoformat()

    pricing_data = {}
    try: pricing_data = fetch_pricing()
    except Exception as e: logger.warning(f"Pricing failed: {e}")

    docs_regions = {}
    try: docs_regions = fetch_aws_docs_regions()
    except Exception as e: logger.warning(f"Docs failed: {e}")

    all_models: dict[str, dict] = {}
    all_profiles: dict[str, list] = {}
    with ThreadPoolExecutor(max_workers=10) as ex:
        futs = {ex.submit(collect_region_data, r): r for r in REGIONS}
        for f in as_completed(futs):
            region, raws, profs = f.result()
            if not raws: continue
            all_profiles[region] = profs
            for raw in raws:
                mid = raw.get("modelId", "")
                if mid not in all_models:
                    all_models[mid] = parse_model(raw, profs)
                    all_models[mid]["availableRegions"] = [region]
                else:
                    if region not in all_models[mid].get("availableRegions", []):
                        all_models[mid]["availableRegions"].append(region)
                    existing_profiles = {p["profileId"]: p for p in all_models[mid]["crossRegionInference"]["profiles"]}
                    for p in parse_model(raw, profs)["crossRegionInference"]["profiles"]:
                        if p["profileId"] not in existing_profiles:
                            all_models[mid]["crossRegionInference"]["profiles"].append(p)
                            all_models[mid]["crossRegionInference"]["supported"] = True
                        else:
                            ep = existing_profiles[p["profileId"]]
                            ep["regions"] = sorted(set(ep["regions"]) | set(p["regions"]))

    models = sorted(all_models.values(), key=lambda m: m.get("modelId", ""))

    # PT inheritance
    for m in models:
        mid = m["modelId"]
        if mid.count(":") >= 2 and not m["capabilities"]["categories"]:
            base = all_models.get(":".join(mid.split(":")[:2])) or all_models.get(mid.split(":")[0])
            if base and base["capabilities"]["categories"]:
                m["capabilities"]["categories"] = base["capabilities"]["categories"]
                if not m["description"]["full"]: m["description"] = base["description"].copy()
                if not m["metadata"]["supportedLanguages"]: m["metadata"]["supportedLanguages"] = base["metadata"]["supportedLanguages"]

    # Merge docs regions
    if docs_regions:
        by_name = {}
        for m in models:
            n = m.get("modelName", "")
            if n and n not in by_name: by_name[n] = m
        merged = 0
        for dn, dd in docs_regions.items():
            api_name = DOCS_NAME_ALIASES.get(dn, dn)
            mo = by_name.get(api_name)
            if not mo: continue
            old = set(mo.get("availableRegions", []))
            mo["availableRegions"] = sorted(old | set(dd['all_regions']))
            merged += len(set(dd['all_regions']) - old)
        logger.info(f"Docs merge: +{merged} regions")

    # ── Mantle merge ────────────────────────────────────────────
    # Enrich overlapping classic models with the mantle flag + regions; synthesize
    # entries for Mantle-only models (gpt-5.x, grok, glm-4.6, gemma-4, deepseek.v3.1...).
    mantle_ids: dict[str, list[str]] = {}
    mantle_pricing: dict[str, dict] = {}
    try:
        mantle_ids = fetch_mantle_models()
    except Exception as e:
        logger.warning(f"Mantle models failed: {e}")
    try:
        mantle_pricing = fetch_mantle_pricing()
    except Exception as e:
        logger.warning(f"Mantle pricing failed: {e}")

    _synth_ids = merge_mantle_into_models(all_models, mantle_ids, mantle_pricing)

    # Rebuild sorted list to include synthesized models
    models = sorted(all_models.values(), key=lambda m: m.get("modelId", ""))

    # Pricing match
    # Build hard-coded reverse mapping: catalog name -> pricing data
    hardcoded = {}
    for pricing_name, catalog_name in PRICING_TO_CATALOG.items():
        if pricing_name in pricing_data:
            hardcoded[catalog_name] = pricing_data[pricing_name]

    def _norm(s): return s.lower().replace("-", " ").replace(".", " ").replace("_", " ").strip()
    pbn = {_norm(k): v for k, v in pricing_data.items()}
    def _match(mn):
        if not mn: return None
        # 0. Hard-coded mapping
        if mn in hardcoded: return hardcoded[mn]
        # 1. Exact match
        if mn in pricing_data: return pricing_data[mn]
        # 2. Normalized
        n = _norm(mn)
        if n in pbn: return pbn[n]
        # 3. Prefix match
        for pn, pd in pricing_data.items():
            pnr = _norm(pn)
            if n.startswith(pnr) or pnr.startswith(n): return pd
        # 4. Substring
        for pn, pd in pricing_data.items():
            pnr = _norm(pn)
            if len(pnr) >= 3 and pnr in n: return pd
        return None

    def _has_useful_price(p):
        if not p: return False
        return any(p.get(k) is not None for k in [
            'inputTokenPrice', 'outputTokenPrice', 'imagePrice',
            'videoPrice', 'videoSecPrice', 'searchUnitPrice',
        ])

    matched = 0
    for m in models:
        # Synthesized Mantle-only models already carry mantle pricing (from usagetype).
        if m["modelId"] in _synth_ids:
            if _has_useful_price(m.get("pricing")):
                matched += 1
            continue
        mn = m.get("modelName") or ""
        mp = _match(mn)
        # Fallback: use fallback_pricing.json if API match has no useful price
        if not _has_useful_price(mp) and mn in FALLBACK_PRICING:
            fb = FALLBACK_PRICING[mn]
            mp = {'modelName': mn, 'prices': [], **{k: v for k, v in fb.items()}}
        if mp:
            mp.pop('source', None)
            matched += 1
        m["pricing"] = mp
    logger.info(f"Pricing: {matched}/{len(models)}")

    # Cleanup
    for m in models:
        d = m.get("description") or {}
        for f in ("short", "full", "useCases"):
            v = d.get(f)
            if v and "\\n" in v: d[f] = v.replace("\\n", "\n")
        p = m.get("pricing")
        if p and p.get("prices"):
            p["prices"] = [e for e in p["prices"] if (e.get("inferenceType") or "").strip()]
            seen, dd = set(), []
            for e in p["prices"]:
                k = (e["inferenceType"], round(e.get("pricePerUnit", 0), 8))
                if k not in seen: seen.add(k); dd.append(e)
            p["prices"] = dd

    # Upload v2
    cat2 = {"lastUpdated": now, "regions": REGIONS, "totalRegions": len(REGIONS), "totalModels": len(models), "models": models}
    upload_to_s3("v2/models.json", cat2)
    for m in models:
        upload_to_s3(f"v2/models/{m['modelId'].replace('/', '_').replace(':', '_')}.json", m)
    pp = all_profiles.get(PRIMARY_REGION, [])
    upload_to_s3("v2/inference-profiles.json", {"lastUpdated": now, "region": PRIMARY_REGION, "totalProfiles": len(pp), "profiles": pp})
    upload_to_s3("v2/metadata.json", {"lastUpdated": now, "regions": REGIONS, "totalRegions": len(REGIONS),
                                       "totalModels": len(models), "totalInferenceProfiles": len(pp),
                                       "version": "2.0.0", "features": ["pricing", "all-regions", "cris-profiles", "aws-docs-regions"]})

    # Upload v1 (no pricing)
    v1m = []
    for m in models:
        c = m.copy(); c.pop("pricing", None); v1m.append(c)
    upload_to_s3("v1/models.json", {"lastUpdated": now, "regions": REGIONS, "totalModels": len(v1m), "models": v1m})
    for m in v1m:
        upload_to_s3(f"v1/models/{m['modelId'].replace('/', '_').replace(':', '_')}.json", m)
    upload_to_s3("v1/inference-profiles.json", {"lastUpdated": now, "region": PRIMARY_REGION, "totalProfiles": len(pp), "profiles": pp})
    upload_to_s3("v1/metadata.json", {"lastUpdated": now, "regions": REGIONS, "totalModels": len(v1m),
                                       "totalInferenceProfiles": len(pp), "version": "1.0.0"})

    result = {"statusCode": 200, "body": {"message": "Done", "totalModels": len(models), "pricingMatched": matched, "regions": len(REGIONS)}}
    logger.info(json.dumps(result))
    return result
