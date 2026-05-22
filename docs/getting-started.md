# Agent Skills

Teach your AI coding agent how to look up Bedrock model pricing, capabilities, and regional availability using the Bedrock Model Catalog API.

The skill follows the open [Agent Skills](https://agentskills.io) standard and works across Claude Code, GitHub Copilot, Kiro, Cursor, and more.

## Quick Install

### Using the Agent Skills CLI (recommended)

Works with any agent that supports the Agent Skills standard:

```bash
npx skills add didhd/bedrock-model-catalog-api-v2
```

The CLI guides you through selecting your agent:

```
$ npx skills add didhd/bedrock-model-catalog-api-v2

? Select an agent: (Use arrow keys)
› Claude Code
  GitHub Copilot
  Kiro CLI
  Cursor
  Windsurf
  OpenCode
  Codex

? Select a scope: (Use arrow keys)
› Project — install in current directory
  Global — install globally for all projects
```

### Download Skill

[Download bedrock-model-lookup-skill.zip](/bedrock-model-lookup-skill.zip) and extract to your agent's skill directory.

---

## Agent-Specific Setup

### Claude Code

```bash
# Option 1: Agent Skills CLI
npx skills add didhd/bedrock-model-catalog-api-v2 -a claude-code

# Option 2: Manual install
mkdir -p .claude/skills
curl -L https://bedrock.sanghwa.people.aws.dev/bedrock-model-lookup-skill.zip -o skill.zip
unzip skill.zip -d .claude/skills/ && rm skill.zip
```

After installing, just ask:

```
What's the pricing for Claude Sonnet 4 on Bedrock?
Which models are available in ap-northeast-2?
Compare pricing across all Anthropic models.
```

### GitHub Copilot

```bash
npx skills add didhd/bedrock-model-catalog-api-v2 -a github-copilot
```

Or manually:

```bash
mkdir -p .github/skills/bedrock-model-lookup
# Copy SKILL.md into the directory
```

### Kiro

**Kiro IDE**: The skill activates automatically when installed via the Skills CLI.

**Kiro CLI**:

```bash
npx skills add didhd/bedrock-model-catalog-api-v2 -a kiro-cli
```

Then add to your agent config (`.kiro/agents/<agent>.json`):

```json
{
  "resources": [
    "skill://.kiro/skills/**/SKILL.md"
  ]
}
```

### Cursor / Windsurf

```bash
# Cursor
mkdir -p .cursor/skills/bedrock-model-lookup
cp SKILL.md .cursor/skills/bedrock-model-lookup/

# Windsurf
mkdir -p .windsurf/skills/bedrock-model-lookup
cp SKILL.md .windsurf/skills/bedrock-model-lookup/
```

---

## Direct API Usage

No SDK or authentication needed — just fetch JSON:

```bash
# All models with pricing
curl -s https://bedrock.sanghwa.people.aws.dev/v2/models.json | jq '.totalModels'

# Specific model
curl -s https://bedrock.sanghwa.people.aws.dev/v2/models/anthropic.claude-sonnet-4-20250514-v1_0.json

# API metadata
curl -s https://bedrock.sanghwa.people.aws.dev/v2/metadata.json
```

### Examples with jq

```bash
BASE=https://bedrock.sanghwa.people.aws.dev/v2

# Top 5 cheapest models
curl -s $BASE/models.json | jq '
  [.models[] | select(.pricing.inputTokenPrice != null) |
   {name: .modelName, in: (.pricing.inputTokenPrice * 1000),
    out: (.pricing.outputTokenPrice * 1000)}] |
  sort_by(.in) | .[:5]'

# Models with reasoning support
curl -s $BASE/models.json | jq '
  [.models[] | select(.capabilities.reasoning == true) | .modelName]'

# All models in Seoul region
curl -s $BASE/models.json | jq '
  [.models[] | select(.availableRegions | index("ap-northeast-2")) | .modelName]'
```

---

## Supported Agents

| Agent | Install Method | Skill Directory |
|-------|---------------|-----------------|
| **Claude Code** | `npx skills add` or manual | `.claude/skills/` |
| **GitHub Copilot** | `npx skills add` | `.github/skills/` |
| **Kiro IDE** | Built-in power | Automatic |
| **Kiro CLI** | `npx skills add` | `.kiro/skills/` |
| **Cursor** | Manual copy | `.cursor/skills/` |
| **Windsurf** | Manual copy | `.windsurf/skills/` |
| **OpenCode** | `npx skills add` | `.opencode/skills/` |
| **Codex** | `npx skills add` | `.codex/skills/` |

## What the Skill Does

Once installed, the skill activates when you mention Bedrock model pricing, availability, or capabilities. It instructs the agent to:

1. Query the Bedrock Model Catalog API (`/v2/models.json`)
2. Parse pricing tiers (Standard, Flex, Priority, Batch, Cache)
3. Check regional availability across 33+ AWS regions
4. Compare CRIS profiles (US, EU, APAC, Global)
5. Present results in a clear, actionable format
