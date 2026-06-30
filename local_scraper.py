#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════╗
║           LOCAL JOB SCRAPER — FEEDS JOBS TO CLOUDFLARE WORKER               ║
║                                                                               ║
║  Author: Bharath R (bharath31015r@gmail.com)                                 ║
║  Portfolio: https://gnpypqgq4ol4i.kimi.page                                  ║
║  Worker API: https://freelance-domination-engine.fde-work.workers.dev       ║
║                                                                               ║
║  Usage: python local_scraper.py                                              ║
║  Requirements: Python 3.8+ (requests, beautifulsoup4 recommended)            ║
║                                                                               ║
║  Categories scanned: Freelance, Remote, Tech, Engineering, Reddit           ║
║  Domains filtered: FEA/Structural, Flutter/Mobile, AI/ML, General Eng/Tech  ║
╚══════════════════════════════════════════════════════════════════════════════╝
"""

import json
import hashlib
import logging
import os
import random
import re
import sqlite3
import time
import urllib.error
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any, Dict, List, Optional, Tuple
from xml.etree import ElementTree
from dataclasses import dataclass, asdict

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION — CUSTOMIZE THIS SECTION
# ═══════════════════════════════════════════════════════════════════════════════

CONFIG = {
    # ── API ──────────────────────────────────────────────────────────────────
    "worker_api_url": "https://freelance-domination-engine.fde-work.workers.dev/api/jobs",  # Primary
    # Fallback: https://fde-engine-v5.fde-work.workers.dev/api/jobs
    "api_key": "",  # Add API key if your worker requires authentication

    # ── Scraping Behaviour ─────────────────────────────────────────────────
    "request_delay_min": 1.0,       # Minimum seconds between requests
    "request_delay_max": 3.0,       # Maximum seconds between requests
    "max_retries": 3,               # Retry failed requests N times
    "retry_backoff_base": 2.0,      # Exponential backoff multiplier
    "request_timeout": 25,          # HTTP request timeout in seconds
    "max_jobs_per_source": 50,      # Max jobs to process per source per run
    "dedup_days": 90,               # How many days to remember seen jobs

    # ── Filtering ──────────────────────────────────────────────────────────
    "min_keyword_matches": 1,       # Minimum keyword matches to accept a job
    "match_mode": "any",            # "any" = match ANY domain, "domain" = best fit

    # ── Paths ──────────────────────────────────────────────────────────────
    "dedup_db_path": os.path.join(os.path.dirname(__file__), "job_scraper.db"),
    "log_path": os.path.join(os.path.dirname(__file__), "scraper.log"),
    "dry_run": False,               # If True, print jobs instead of sending

    # ── User Info ──────────────────────────────────────────────────────────
    "user_name": "Bharath R",
    "user_email": "bharath31015r@gmail.com",
    "user_skills": [
        "MSC Nastran (DMAP)", "MATLAB", "Abaqus", "ANSYS", "Altair HyperWorks",
        "CATIA V5", "SolidWorks", "Flutter", "React Native", "AI/ML",
        "Python", "Structural Dynamics", "Aeroelasticity", "FEA"
    ],
}

# ═══════════════════════════════════════════════════════════════════════════════
# KEYWORD DOMAINS — 4 Target Areas
# ═══════════════════════════════════════════════════════════════════════════════

KEYWORD_DOMAINS = {
    "FEA": {
        "weight": 1.5,
        "keywords": [
            "nastran", "abaqus", "ansys", "finite element", "structural analysis",
            "aeroelasticity", "flutter analysis", "modal analysis", "gvt",
            "ground vibration test", "msc software", "dmap", "hyperworks",
            "catia", "solidworks", "mechanical engineer", "aerospace",
            "cfd", "fea", "stress analysis", "vibration", "composite",
            "static analysis", "buckling", "fatigue", "fracture mechanics",
            "thermomechanical", "multibody dynamics", "landing gear",
            "wing", "fuselage", "aircraft structures", "rotorcraft",
            "wind tunnel", "aerodynamic", "flight dynamics", "loads analysis",
            "dynamic analysis", "shock", "impact", "nonlinear", "linear",
            "pyroshock", "random vibration", "harmonic analysis",
        ]
    },
    "Flutter": {
        "weight": 1.3,
        "keywords": [
            "flutter", "dart", "mobile app", "ios", "android", "react native",
            "cross-platform", "firebase", "mobile development", "app developer",
            "mobile ui", "state management", "bloc", "provider", "riverpod",
            "google maps", "push notification", "rest api mobile",
            "mobile sdk", "getx", "mvvm", "clean architecture",
        ]
    },
    "AI_Systems": {
        "weight": 1.3,
        "keywords": [
            "machine learning", "deep learning", "ai", "llm", "langchain",
            "openai", "gpt", "claude", "gemini", "neural network",
            "computer vision", "nlp", "tensorflow", "pytorch", "data science",
            "artificial intelligence", "reinforcement learning", "stable diffusion",
            "llama", "falcon", "mistral", "fine-tuning", "embedding",
            "vector database", "rag", "retrieval augmented", "agent",
            "autonomous", "multi-agent", "prompt engineering",
        ]
    },
    "General": {
        "weight": 1.0,
        "keywords": [
            "matlab", "python", "engineering", "simulation", "automation",
            "scripting", "optimization", "algorithm", "numerical",
            "control systems", "robotics", "signal processing", "image processing",
            "data analysis", "scientific computing", "c++", "fortran",
            "cuda", "parallel computing", "hpc", "cloud computing",
        ]
    },
}

# ═══════════════════════════════════════════════════════════════════════════════
# JOB SOURCES — 33 Sources Across All Categories
# ═══════════════════════════════════════════════════════════════════════════════

JOB_SOURCES = [
    # ── FREELANCE PLATFORMS ──
    {
        "id": "upwork_flutter",
        "name": "Upwork Flutter",
        "category": "freelance",
        "type": "rss",
        "url": "https://www.upwork.com/ab/feed/jobs/rss?ontology_v3_uid=1110580753313853440&sort=recency&paging=0%3B50",
    },
    {
        "id": "upwork_mobile",
        "name": "Upwork Mobile",
        "category": "freelance",
        "type": "rss",
        "url": "https://www.upwork.com/ab/feed/jobs/rss?ontology_v3_uid=1110580752330215424&sort=recency&paging=0%3B50",
    },
    {
        "id": "upwork_eng",
        "name": "Upwork Engineering",
        "category": "freelance",
        "type": "rss",
        "url": "https://www.upwork.com/ab/feed/jobs/rss?ontology_v3_uid=1110580752426696704&sort=recency&paging=0%3B50",
    },
    {
        "id": "upwork_ai",
        "name": "Upwork AI/ML",
        "category": "freelance",
        "type": "rss",
        "url": "https://www.upwork.com/ab/feed/jobs/rss?ontology_v3_uid=1110580753621856256&sort=recency&paging=0%3B50",
    },
    {
        "id": "upwork_fea",
        "name": "Upwork FEA/Simulation",
        "category": "freelance",
        "type": "rss",
        "url": "https://www.upwork.com/ab/feed/jobs/rss?q=FEA+OR+finite+element+OR+ANSYS+OR+Nastran+OR+simulation&sort=recency&paging=0%3B50",
    },
    {
        "id": "freelancer_dev",
        "name": "Freelancer.com",
        "category": "freelance",
        "type": "rss",
        "url": "https://www.freelancer.com/rss.xml",
    },
    {
        "id": "peopleperhour",
        "name": "PeoplePerHour",
        "category": "freelance",
        "type": "rss",
        "url": "https://www.peopleperhour.com/site/recent-jobs-feed?format=rss",
    },
    {
        "id": "guru_dev",
        "name": "Guru",
        "category": "freelance",
        "type": "rss",
        "url": "https://www.guru.com/d/jobs/rss/",
    },
    # ── REMOTE JOB BOARDS ──
    {
        "id": "wework_prog",
        "name": "WeWorkRemotely Programming",
        "category": "remote",
        "type": "rss",
        "url": "https://weworkremotely.com/categories/remote-programming-jobs.rss",
    },
    {
        "id": "wework_frontend",
        "name": "WeWorkRemotely Frontend",
        "category": "remote",
        "type": "rss",
        "url": "https://weworkremotely.com/categories/remote-front-end-programming-jobs.rss",
    },
    {
        "id": "remoteok_dev",
        "name": "RemoteOK Developer",
        "category": "remote",
        "type": "rss",
        "url": "https://remoteok.com/remote-developer-jobs.rss",
    },
    {
        "id": "remoteok_ai",
        "name": "RemoteOK AI/ML",
        "category": "remote",
        "type": "rss",
        "url": "https://remoteok.com/remote-machine-learning-jobs.rss",
    },
    {
        "id": "workingnomads",
        "name": "WorkingNomads",
        "category": "remote",
        "type": "rss",
        "url": "https://www.workingnomads.com/jobs?category=development,engineering,machine-learning,ai&format=rss",
    },
    {
        "id": "remotive_eng",
        "name": "Remotive Engineering",
        "category": "remote",
        "type": "rss",
        "url": "https://remotive.com/remote-jobs/software-dev/feed",
    },
    {
        "id": "jobspresso",
        "name": "Jobspresso",
        "category": "remote",
        "type": "rss",
        "url": "https://jobspresso.co/feed/?post_type=job_listing",
    },
    {
        "id": "hn_hiring",
        "name": "HackerNews WhoIsHiring",
        "category": "remote",
        "type": "api",
        "url": "https://hn.algolia.com/api/v1/search_by_date?tags=who_is_hiring&hitsPerPage=50",
    },
    # ── REDDIT COMMUNITIES ──
    {
        "id": "reddit_forhire",
        "name": "Reddit r/forhire",
        "category": "reddit",
        "type": "rss",
        "url": "https://www.reddit.com/r/forhire/search.rss?q=programming+OR+developer+OR+engineer&sort=new&restrict_sr=on&t=week",
    },
    {
        "id": "reddit_hiring",
        "name": "Reddit r/hiring",
        "category": "reddit",
        "type": "rss",
        "url": "https://www.reddit.com/r/hiring/search.rss?q=programming+OR+developer+OR+engineer&sort=new&restrict_sr=on&t=week",
    },
    {
        "id": "reddit_remotejs",
        "name": "Reddit r/RemoteJS",
        "category": "reddit",
        "type": "rss",
        "url": "https://www.reddit.com/r/RemoteJS/.rss",
    },
    {
        "id": "reddit_remotework",
        "name": "Reddit r/remotework",
        "category": "reddit",
        "type": "rss",
        "url": "https://www.reddit.com/r/remotework/search.rss?q=hiring+OR+job&sort=new&restrict_sr=on&t=week",
    },
    {
        "id": "reddit_freelance",
        "name": "Reddit r/freelance",
        "category": "reddit",
        "type": "rss",
        "url": "https://www.reddit.com/r/freelance/search.rss?q=hiring+OR+looking+OR+need&sort=new&restrict_sr=on&t=week",
    },
    {
        "id": "reddit_programming",
        "name": "Reddit r/programming jobs",
        "category": "reddit",
        "type": "rss",
        "url": "https://www.reddit.com/r/programming/search.rss?q=hiring+OR+remote+OR+job&sort=new&restrict_sr=on&t=week",
    },
    {
        "id": "reddit_ml",
        "name": "Reddit r/MachineLearning jobs",
        "category": "reddit",
        "type": "rss",
        "url": "https://www.reddit.com/r/MachineLearning/search.rss?q=hiring+OR+research+OR+position&sort=new&restrict_sr=on&t=week",
    },
    {
        "id": "reddit_engineering",
        "name": "Reddit r/engineering",
        "category": "reddit",
        "type": "rss",
        "url": "https://www.reddit.com/r/engineering/search.rss?q=hiring+OR+job+OR+position&sort=new&restrict_sr=on&t=week",
    },
    {
        "id": "reddit_aerospace",
        "name": "Reddit r/aerospace",
        "category": "reddit",
        "type": "rss",
        "url": "https://www.reddit.com/r/aerospace/search.rss?q=hiring+OR+job+OR+career&sort=new&restrict_sr=on&t=week",
    },
    # ── AGGREGATORS ──
    {
        "id": "indeed_dev",
        "name": "Indeed Developer",
        "category": "aggregator",
        "type": "rss",
        "url": "https://rss.indeed.com/rss?q=software+engineer+remote",
    },
    {
        "id": "simplyhired_dev",
        "name": "SimplyHired Developer",
        "category": "aggregator",
        "type": "rss",
        "url": "https://www.simplyhired.com/search?q=software+engineer&fdb=7&sb=dd&pp=",
    },
    {
        "id": "careerbuilder_dev",
        "name": "CareerBuilder Developer",
        "category": "aggregator",
        "type": "rss",
        "url": "https://www.careerbuilder.com/jobs-software-engineer-remote?emp=jtcr%2Cjtcc%2Cjtc2%2Cjtc3&pay=20&posted=1",
    },
    {
        "id": "authenticjobs",
        "name": "AuthenticJobs",
        "category": "aggregator",
        "type": "rss",
        "url": "https://authenticjobs.com/rss/index.php",
    },
    {
        "id": "landingjobs",
        "name": "LandingJobs",
        "category": "aggregator",
        "type": "rss",
        "url": "https://landing.jobs/jobs.rss",
    },
    # ── SPECIALIZED ──
    {
        "id": "angel_list",
        "name": "AngelList/Wellfound",
        "category": "specialized",
        "type": "rss",
        "url": "https://wellfound.com/jobs/rss",
    },
    {
        "id": "crypto_jobs",
        "name": "CryptoJobs",
        "category": "specialized",
        "type": "rss",
        "url": "https://cryptojobslist.com/engineering/rss.xml",
    },
    {
        "id": "gun_io",
        "name": "Gun.io",
        "category": "specialized",
        "type": "rss",
        "url": "https://www.gun.io/job-opportunities/feed/",
    },
]

# ═══════════════════════════════════════════════════════════════════════════════
# HTML STRIPPER — Remove tags without BeautifulSoup dependency
# ═══════════════════════════════════════════════════════════════════════════════

class HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.reset()
        self.text_parts = []

    def handle_data(self, d):
        self.text_parts.append(d)

    def get_text(self):
        return "".join(self.text_parts).strip()


def strip_html(html_text: str) -> str:
    if not html_text:
        return ""
    try:
        stripper = HTMLStripper()
        stripper.feed(html_text)
        return stripper.get_text()
    except Exception:
        return re.sub(r'<[^>]+>', '', html_text)


# ═══════════════════════════════════════════════════════════════════════════════
# DEDUPLICATION — SQLite-backed
# ═══════════════════════════════════════════════════════════════════════════════

class DedupStore:
    def __init__(self, db_path: str, ttl_days: int = 90):
        self.db_path = db_path
        self.ttl_days = ttl_days
        self._init_db()

    def _init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS seen_jobs (
                    hash TEXT PRIMARY KEY,
                    url TEXT,
                    title TEXT,
                    source TEXT,
                    first_seen TEXT,
                    last_seen TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_seen_jobs_url ON seen_jobs(url)
            """)
            conn.commit()

    def has_seen(self, url: str, title: str = "") -> bool:
        job_hash = hashlib.md5(f"{url}:{title}".encode()).hexdigest()
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.execute(
                "SELECT 1 FROM seen_jobs WHERE hash = ? OR url = ?",
                (job_hash, url)
            )
            return cursor.fetchone() is not None

    def mark_seen(self, url: str, title: str = "", source: str = ""):
        job_hash = hashlib.md5(f"{url}:{title}".encode()).hexdigest()
        now = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                """INSERT OR REPLACE INTO seen_jobs (hash, url, title, source, first_seen, last_seen)
                   VALUES (?, ?, ?, ?, COALESCE((SELECT first_seen FROM seen_jobs WHERE hash = ?), ?), ?)""",
                (job_hash, url, title, source, job_hash, now, now)
            )
            conn.commit()

    def cleanup_old(self):
        cutoff = datetime.now(timezone.utc).isoformat()
        with sqlite3.connect(self.db_path) as conn:
            conn.execute(
                "DELETE FROM seen_jobs WHERE last_seen < datetime(?, '-{} days')".format(self.ttl_days),
                (cutoff,)
            )
            conn.commit()

    def stats(self) -> Dict[str, int]:
        with sqlite3.connect(self.db_path) as conn:
            total = conn.execute("SELECT COUNT(*) FROM seen_jobs").fetchone()[0]
            today = conn.execute(
                "SELECT COUNT(*) FROM seen_jobs WHERE last_seen > datetime('now', '-1 day')"
            ).fetchone()[0]
            return {"total_seen": total, "seen_today": today}


# ═══════════════════════════════════════════════════════════════════════════════
# RSS / API FETCHERS
# ═══════════════════════════════════════════════════════════════════════════════

class JobFetcher:
    def __init__(self, config: Dict):
        self.config = config
        self.logger = logging.getLogger("fetcher")

    def _random_delay(self):
        delay = random.uniform(self.config["request_delay_min"], self.config["request_delay_max"])
        time.sleep(delay)

    def _fetch(self, url: str, headers: Optional[Dict] = None, timeout: Optional[int] = None) -> Tuple[bool, str]:
        if headers is None:
            headers = {
                "User-Agent": random.choice([
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
                ]),
                "Accept": "application/rss+xml,application/xml,text/xml,*/*",
                "Accept-Language": "en-US,en;q=0.9",
            }

        timeout = timeout or self.config["request_timeout"]

        for attempt in range(self.config["max_retries"]):
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    data = resp.read()
                    try:
                        return True, data.decode("utf-8")
                    except UnicodeDecodeError:
                        return True, data.decode("utf-8", errors="replace")
            except urllib.error.HTTPError as e:
                if e.code == 429:
                    backoff = self.config["retry_backoff_base"] ** attempt
                    self.logger.warning(f"  Rate limited ({url}), waiting {backoff}s...")
                    time.sleep(backoff)
                    continue
                self.logger.warning(f"  HTTP {e.code} for {url}")
                return False, str(e.code)
            except Exception as e:
                self.logger.warning(f"  Error fetching {url}: {e}")
                if attempt < self.config["max_retries"] - 1:
                    time.sleep(self.config["retry_backoff_base"] ** attempt)
                    continue
                return False, str(e)

        return False, "max_retries"

    def parse_rss(self, xml_content: str, source: Dict) -> List[Dict]:
        jobs = []
        try:
            root = ElementTree.fromstring(xml_content)
            # Handle RSS 2.0 and Atom
            channel = root.find("channel")
            if channel is not None:
                items = channel.findall("item")
            else:
                # Atom feed
                ns = {"atom": "http://www.w3.org/2005/Atom"}
                items = root.findall("atom:entry", ns)

            for item in items[:self.config["max_jobs_per_source"]]:
                if item.tag.endswith("entry"):
                    # Atom format
                    title = item.findtext("atom:title", "", ns)
                    link_el = item.find("atom:link", ns)
                    link = link_el.get("href", "") if link_el is not None else ""
                    desc = item.findtext("atom:summary", "", ns) or item.findtext("atom:content", "", ns)
                    pub_date = item.findtext("atom:updated", "", ns) or item.findtext("atom:published", "", ns)
                else:
                    # RSS 2.0 format
                    title = item.findtext("title", "")
                    link = item.findtext("link", "")
                    desc = item.findtext("description", "")
                    pub_date = item.findtext("pubDate", "")

                title = strip_html(title or "")
                desc = strip_html(desc or "")

                if not title or not link:
                    continue

                jobs.append({
                    "title": title,
                    "description": desc,
                    "url": link.strip(),
                    "source": source["id"],
                    "source_name": source["name"],
                    "posted_at": pub_date or datetime.now(timezone.utc).isoformat(),
                    "raw": item,
                })

        except ElementTree.ParseError as e:
            self.logger.warning(f"  XML parse error for {source['id']}: {e}")
        except Exception as e:
            self.logger.warning(f"  RSS parse error for {source['id']}: {e}")

        return jobs

    def parse_hn_api(self, json_content: str, source: Dict) -> List[Dict]:
        jobs = []
        try:
            data = json.loads(json_content)
            hits = data.get("hits", [])
            for hit in hits[:self.config["max_jobs_per_source"]]:
                title = hit.get("title", "")
                if not title:
                    continue
                # Filter hiring posts
                text = hit.get("story_text", "") or hit.get("comment_text", "") or ""
                url = hit.get("url", "") or f"https://news.ycombinator.com/item?id={hit.get('objectID', '')}"
                jobs.append({
                    "title": title,
                    "description": strip_html(text),
                    "url": url,
                    "source": source["id"],
                    "source_name": source["name"],
                    "posted_at": datetime.fromtimestamp(hit.get("created_at_i", 0), timezone.utc).isoformat() if hit.get("created_at_i") else datetime.now(timezone.utc).isoformat(),
                    "raw": hit,
                })
        except Exception as e:
            self.logger.warning(f"  HN API parse error: {e}")
        return jobs

    def fetch_source(self, source: Dict) -> List[Dict]:
        self.logger.info(f"📡 {source['name']}...")
        self._random_delay()

        success, content = self._fetch(source["url"])
        if not success:
            self.logger.warning(f"  ❌ Failed: {content}")
            return []

        if source["type"] == "rss":
            jobs = self.parse_rss(content, source)
        elif source["type"] == "api":
            jobs = self.parse_hn_api(content, source)
        else:
            jobs = []

        self.logger.info(f"  ✅ Found {len(jobs)} items")
        return jobs


# ═══════════════════════════════════════════════════════════════════════════════
# KEYWORD ANALYZER
# ═══════════════════════════════════════════════════════════════════════════════

class KeywordAnalyzer:
    def __init__(self, domains: Dict):
        self.domains = domains

    def analyze(self, title: str, description: str) -> Tuple[str, float, List[str]]:
        text = f"{title} {description}".lower()
        best_domain = "General"
        best_score = 0.0
        matched_keywords = []

        for domain_name, domain_data in self.domains.items():
            score = 0
            domain_matches = []
            for keyword in domain_data["keywords"]:
                if keyword.lower() in text:
                    score += 1
                    domain_matches.append(keyword)
            weighted_score = score * domain_data.get("weight", 1.0)
            if weighted_score > best_score:
                best_score = weighted_score
                best_domain = domain_name
                matched_keywords = domain_matches

        return best_domain, best_score, matched_keywords

    def should_include(self, title: str, description: str, min_matches: int = 1) -> bool:
        domain, score, _ = self.analyze(title, description)
        return score >= min_matches


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN SCRAPER ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

class JobScraper:
    def __init__(self, config: Dict = None):
        self.config = config or CONFIG
        self.fetcher = JobFetcher(self.config)
        self.analyzer = KeywordAnalyzer(KEYWORD_DOMAINS)
        self.dedup = DedupStore(self.config["dedup_db_path"], self.config["dedup_days"])
        self._setup_logging()
        self.logger = logging.getLogger("scraper")

    def _setup_logging(self):
        log_format = "%(asctime)s | %(name)s | %(levelname)s | %(message)s"
        handlers = [logging.StreamHandler()]
        if self.config.get("log_path"):
            handlers.append(logging.FileHandler(self.config["log_path"]))
        logging.basicConfig(
            level=logging.INFO,
            format=log_format,
            handlers=handlers,
        )

    def run(self) -> Dict[str, Any]:
        self.logger.info("=" * 60)
        self.logger.info("🚀 Job Scraper Starting — 33 sources")
        self.logger.info(f"📧 User: {self.config['user_name']} <{self.config['user_email']}>")
        self.logger.info(f"🌐 Worker API: {self.config['worker_api_url']}")
        self.logger.info(f"🧪 Dry run: {self.config['dry_run']}")
        self.logger.info("=" * 60)

        all_jobs = []
        source_stats = {}

        for source in JOB_SOURCES:
            try:
                jobs = self.fetcher.fetch_source(source)
                source_stats[source["id"]] = len(jobs)

                for job in jobs:
                    if self.dedup.has_seen(job["url"], job["title"]):
                        continue

                    domain, score, keywords = self.analyzer.analyze(
                        job["title"], job["description"]
                    )

                    if score < self.config["min_keyword_matches"]:
                        continue

                    job["domain"] = domain
                    job["match_score"] = score
                    job["matched_keywords"] = keywords
                    job["type"] = self._classify_job_type(job)

                    all_jobs.append(job)
                    self.dedup.mark_seen(job["url"], job["title"], source["id"])

            except Exception as e:
                self.logger.error(f"  💥 Error processing {source['id']}: {e}")

        self.logger.info("=" * 60)
        self.logger.info(f"📊 Scan complete: {len(all_jobs)} matching jobs from {len(JOB_SOURCES)} sources")

        for sid, count in sorted(source_stats.items(), key=lambda x: -x[1]):
            if count > 0:
                self.logger.info(f"  {sid}: {count} items")

        dedup_stats = self.dedup.stats()
        self.logger.info(f"📦 Dedup DB: {dedup_stats['total_seen']} total, {dedup_stats['seen_today']} today")

        if all_jobs:
            if self.config["dry_run"]:
                self._preview_jobs(all_jobs)
            else:
                self._send_to_worker(all_jobs)
        else:
            self.logger.info("🤷 No matching jobs found this run")

        self.dedup.cleanup_old()

        return {
            "total_scanned": sum(source_stats.values()),
            "matching_jobs": len(all_jobs),
            "source_stats": source_stats,
            "dedup_stats": dedup_stats,
        }

    def _classify_job_type(self, job: Dict) -> str:
        text = f"{job.get('title', '')} {job.get('description', '')}".lower()
        source = job.get("source", "")

        freelance_signals = ["freelance", "contract", "project", "gig", "hourly", "fixed price"]
        remote_signals = ["full-time", "full time", "part-time", "part time", "permanent"]

        freelance_score = sum(1 for s in freelance_signals if s in text)
        remote_score = sum(1 for s in remote_signals if s in text)

        if any(s in source for s in ["freelancer", "upwork", "guru", "peopleperhour"]):
            freelance_score += 3

        if freelance_score > remote_score:
            return "freelance"
        elif remote_score > freelance_score:
            return "remote"
        return "freelance"  # Default

    def _preview_jobs(self, jobs: List[Dict]):
        self.logger.info("\n🧪 DRY RUN — Jobs that would be sent:\n")
        for i, job in enumerate(jobs[:20], 1):
            self.logger.info(f"  {i}. [{job['domain']}] {job['title'][:80]}")
            self.logger.info(f"     Score: {job['match_score']:.0f} | Type: {job['type']} | Source: {job['source']}")
            self.logger.info(f"     URL: {job['url'][:100]}")
            if job.get('description'):
                desc = job['description'][:150].replace('\n', ' ')
                self.logger.info(f"     Desc: {desc}...")
            self.logger.info("")
        if len(jobs) > 20:
            self.logger.info(f"  ... and {len(jobs) - 20} more")

    def _send_to_worker(self, jobs: List[Dict]):
        self.logger.info(f"\n📤 Sending {len(jobs)} jobs to worker...")

        # Format jobs for the worker API
        payload = []
        for job in jobs:
            payload.append({
                "title": job.get("title", ""),
                "company": "",
                "description": job.get("description", ""),
                "url": job.get("url", ""),
                "source": job.get("source", "") + " (" + job.get("source_name", "") + ")",
                "domain": job.get("domain", "General"),
                "type": job.get("type", "freelance"),
                "budget": None,
                "contact": None,
                "location": "Remote",
                "posted_at": job.get("posted_at", datetime.now(timezone.utc).isoformat()),
            })

        # Send in batches of 10
        batch_size = 10
        total_sent = 0
        for i in range(0, len(payload), batch_size):
            batch = payload[i:i + batch_size]
            try:
                result = self._post_batch(batch)
                if result:
                    total_sent += result.get("stored", 0)
                    self.logger.info(f"  Batch {i//batch_size + 1}: {result.get('stored', 0)} stored, {result.get('duplicates', 0)} dupes")
                else:
                    self.logger.warning(f"  Batch {i//batch_size + 1}: Failed")
            except Exception as e:
                self.logger.error(f"  Batch {i//batch_size + 1} error: {e}")
            time.sleep(1)

        self.logger.info(f"✅ Sent {total_sent}/{len(jobs)} jobs to worker")

    def _post_batch(self, batch: List[Dict]) -> Optional[Dict]:
        url = self.config["worker_api_url"]
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.config.get("api_key"):
            headers["X-API-Key"] = self.config["api_key"]

        data = json.dumps(batch).encode("utf-8")
        req = urllib.request.Request(url, data=data, headers=headers, method="POST")

        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as e:
            error_body = e.read().decode("utf-8", errors="replace")
            self.logger.error(f"  Worker API HTTP {e.code}: {error_body[:200]}")
            return None
        except Exception as e:
            self.logger.error(f"  Worker API error: {e}")
            return None


# ═══════════════════════════════════════════════════════════════════════════════
# CLI ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    import argparse

    parser = argparse.ArgumentParser(description="FDE v5.0 Hybrid — Local Job Scraper")
    parser.add_argument("--once", action="store_true", help="Run once and exit")
    parser.add_argument("--dry-run", action="store_true", help="Preview jobs without sending")
    parser.add_argument("--delay", nargs=2, type=float, metavar=("MIN", "MAX"),
                        help="Custom request delay range (seconds)")
    parser.add_argument("--min-matches", type=int, default=1, help="Minimum keyword matches")
    parser.add_argument("--sources", nargs="+", help="Only scan specific source IDs")
    parser.add_argument("--api-key", help="API key for worker authentication")

    args = parser.parse_args()

    config = CONFIG.copy()
    if args.dry_run:
        config["dry_run"] = True
    if args.delay:
        config["request_delay_min"] = args.delay[0]
        config["request_delay_max"] = args.delay[1]
    if args.min_matches:
        config["min_keyword_matches"] = args.min_matches
    if args.api_key:
        config["api_key"] = args.api_key

    scraper = JobScraper(config)

    if args.once or args.dry_run:
        scraper.run()
    else:
        print("🔄 Continuous mode — runs every 30 minutes")
        print("Press Ctrl+C to stop\n")
        while True:
            try:
                scraper.run()
            except KeyboardInterrupt:
                print("\n👋 Stopping")
                break
            except Exception as e:
                logging.error(f"Run error: {e}")

            print(f"\n⏰ Next run in 30 minutes... ({datetime.now(timezone.utc).strftime('%H:%M:%S')})")
            time.sleep(1800)  # 30 minutes


if __name__ == "__main__":
    main()
