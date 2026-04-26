# Side-Project Kickoff Trigger

> UC4 (lite): start a CONTRASTING side-project after Phase 1B closes to demonstrate range to recruiters. Runs in parallel with Phase 1C (eval + public repo + README polish).

## Trigger condition (Phase 1B closed)

Run before kicking off:
```bash
cd "$REPO"
gh run list --workflow=ci.yml --limit 1 --json conclusion --jq '.[0].conclusion'   # expects: success
test -f docs/observability.png  # dashboard screenshot committed
test -f docs/slo.md             # SLO doc committed
git log --oneline | grep "feat(obs)"  # observability module landed
```

If all 4 pass, Phase 1B is closed. Proceed.

## Picking the archetype

Side-project should CONTRAST PropDeal to demonstrate range. Three options:

### Option A: Agentic LLM workflow (most relevant to 2026 hiring)
- 1-page React app calling Claude with tool use
- Example: "AI lease analyzer" — paste lease PDF, AI flags risky clauses
- Demonstrates: agentic patterns, RAG, tool use, frontend
- Stack: Next.js + Claude Sonnet 4.6 + Vercel
- Effort: 2 weeks

### Option B: Realtime data system
- WebSocket-driven price tracker (crypto / stock / sports betting odds)
- Demonstrates: stateful systems, websockets, frontend, latency-sensitive code
- Stack: Node.js + Redis + websockets + lightweight frontend
- Effort: 2 weeks

### Option C: Devtools / Claude Code skill
- Small CLI or Claude Code skill solving a niche dev workflow
- Examples: "PR description generator from diff", "AWS cost regression detector"
- Demonstrates: DX, packaging, distribution, agentic system design
- Stack: Python or TypeScript CLI + npm/pypi
- Effort: 1 week

## Decision rubric

Pick based on what your TARGET 2026 JDs emphasize:
- "Agentic AI" / "tool use" / "LLM applications" → Option A
- "Realtime systems" / "low-latency" / "data pipelines" → Option B
- "DX" / "Developer Tools" / "Open source" → Option C

Pull 5 representative JDs. Count keyword frequency. Pick the highest match.

## Kickoff checklist

```bash
# 1. Create new repo
gh repo create USER/[side-project-name] --public

# 2. Bootstrap
mkdir ~/[side-project-name] && cd ~/[side-project-name]
git init
gh repo edit --description "[1-line pitch]"

# 3. Spec via brainstorm skill
# Run: /superpowers:brainstorming "[idea]"

# 4. Allocate time
# 30% of weekly capacity until Phase 1C closes
# 100% after Phase 1C closes (or split based on Phase 1C remaining work)
```

## Anti-goals (what NOT to build as side-project)

- Another data pipeline (same archetype as PropDeal)
- Another AWS Lambda app (same stack)
- Anything taking > 4 weeks (delays job applications)
- A "platform" or marketplace (too ambitious for 2-week scope)

## Success criteria

By the time Phase 1C closes, side-project should have:
- [ ] Public GitHub repo with README + 1 screenshot/GIF
- [ ] Live demo URL (Vercel/Render/Fly.io free tier)
- [ ] One distinct keyword for resume that PropDeal doesn't cover (e.g. "agentic", "websocket", "CLI", "RAG")
- [ ] LinkedIn post linking both projects together as a portfolio narrative

## Resume integration

After both projects ship:
> "Two contrasting production projects: PropDeal (serverless AWS data pipeline + LLM eval) and [Side-Project] (agentic LLM / realtime / devtools). Demonstrates range across [stack/domain]."

This narrative beats one polished project for junior portfolios.
