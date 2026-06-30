# Freelance Domination Engine v5.0 — HYBRID SYSTEM

## Architecture
```
YOUR DEVICE (Local Scraper)          CLOUDFLARE (Worker)
Residential IP (not blocked)    →    D1 Database
33 job sources scanned          →    Gemini AI Proposals
Every 30 minutes                →    MailChannels Auto-Email
                                 →    Telegram Instant Alerts
```

**Why hybrid?** Cloudflare Workers run on datacenter IPs that are blocked by all job boards. Your home/mobile IP is not blocked. So your device finds the jobs, and the Worker handles AI + email + Telegram.

---

## Quick Start

```bash
# Download
git clone https://github.com/guh829510-cmd/fde-hybrid.git
cd fde-hybrid

# Install (optional but recommended)
pip install requests beautifulsoup4

# Run
python local_scraper.py --once       # single run
python local_scraper.py              # continuous mode (every 30 min)
```

## Dashboard
**https://freelance-domination-engine.fde-work.workers.dev/**

## Your Configuration (pre-filled)
- **Email:** bharath31015r@gmail.com
- **Portfolio:** https://gnpypqgq4ol4i.kimi.page
- **Domains:** FEA/Structural, Flutter/Mobile, AI/ML, General Engineering
- **Budget range:** $300 - $45K+

**Version:** 5.0.0-hybrid
