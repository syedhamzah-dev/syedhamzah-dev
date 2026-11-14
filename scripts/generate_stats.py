#!/usr/bin/env python3
"""Generate self-hosted GitHub profile SVGs."""
import json
import os
import urllib.request
import html
from datetime import date, timedelta
from pathlib import Path

USER = "syedhamzah-dev"
TOKEN = os.environ["GITHUB_TOKEN"]
OUT = Path("assets")
OUT.mkdir(exist_ok=True)
BG, PANEL, BORDER = "#0d1117", "#161b22", "#30363d"
TEXT, MUTED, BLUE = "#e6edf3", "#8b949e", "#58a6ff"
LEVELS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]

def get_json(url, payload=None):
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": "Bearer " + TOKEN,
        "User-Agent": "profile-readme-analytics"
    }
    if payload is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=payload, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as response:
        return json.load(response)

def graphql(query):
    payload = json.dumps({"query": query, "variables": {"login": USER}}).encode()
    result = get_json("https://api.github.com/graphql", payload)
    if result.get("errors"):
        raise RuntimeError(str(result["errors"]))
    return result["data"]["user"]["contributionsCollection"]

def all_repositories():
    found = []
    page = 1
    while True:
        batch = get_json(
            f"https://api.github.com/users/{USER}/repos?per_page=100&page={page}&type=owner"
        )
        found.extend(batch)
        if len(batch) < 100:
            return found
        page += 1

def label(x, y, value, size=15, color=TEXT, weight=400, anchor="start"):
    return (
        f'<text x="{x}" y="{y}" fill="{color}" font-size="{size}" '
        f'font-weight="{weight}" text-anchor="{anchor}">'
        f'{html.escape(str(value))}</text>'
    )

def save(name, body, width, height):
    svg = (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}">'
        f'<rect width="100%" height="100%" rx="14" fill="{BG}"/>'
        f'<rect x="1" y="1" width="{width-2}" height="{height-2}" rx="13" '
        f'fill="none" stroke="{BORDER}"/>'
        f'<style>text{{font-family:Inter,-apple-system,BlinkMacSystemFont,Segoe UI,sans-serif}}</style>'
        f'{body}</svg>'
    )
    (OUT / name).write_text(svg, encoding="utf-8")

def build_stats(repos, contribution):
    calendar = contribution["contributionCalendar"]
    values = [
        ("PUBLIC REPOSITORIES", sum(not r.get("private") for r in repos)),
        ("STARS", sum(r.get("stargazers_count", 0) for r in repos)),
        ("COMMITS · LAST YEAR", contribution["totalCommitContributions"]),
        ("CONTRIBUTIONS · LAST YEAR", calendar["totalContributions"]),
        ("PULL REQUESTS · LAST YEAR", contribution["totalPullRequestContributions"]),
        ("ISSUES · LAST YEAR", contribution["totalIssueContributions"]),
        ("FORKS", sum(r.get("forks_count", 0) for r in repos)),
        ("REPOSITORIES CONTRIBUTED TO", contribution["totalRepositoryContributions"])
    ]
    positions = [(30, 91), (275, 91), (520, 91), (765, 91),
                 (30, 177), (275, 177), (520, 177), (765, 177)]
    body = label(30, 35, "GITHUB OVERVIEW", 13, MUTED, 700)
    for (name, value), (x, y) in zip(values, positions):
        body += label(x, y, f"{value:,}", 27, TEXT, 700)
        body += label(x, y + 23, name, 10, MUTED, 600)
    save("github-stats.svg", body, 1000, 220)

def build_languages(repos):
    totals = {}
    for repo in repos:
        if repo.get("fork") or repo["name"] == USER:
            continue
        data = get_json(f"https://api.github.com/repos/{USER}/{repo['name']}/languages")
        for language, count in data.items():
            totals[language] = totals.get(language, 0) + count
    ranked = sorted(totals.items(), key=lambda item: item[1], reverse=True)[:8]
    colors = ["#3572A5", "#f1e05a", "#e34c26", "#563d7c",
              "#2b7489", "#4F5D95", "#89e051", "#c6538c"]
    total = sum(value for _, value in ranked)
    body = label(30, 35, "LANGUAGE DISTRIBUTION · PUBLIC NON-FORK REPOSITORIES", 13, MUTED, 700)
    max_value = max((value for _, value in ranked), default=1)
    y = 78
    for index, (language, value) in enumerate(ranked):
        color = colors[index % len(colors)]
        pct = value / total * 100 if total else 0
        body += f'<rect x="30" y="{y-12}" width="11" height="11" rx="3" fill="{color}"/>'
        body += label(52, y-2, language, 14, TEXT, 600)
        body += f'<rect x="235" y="{y-14}" width="600" height="12" rx="6" fill="{PANEL}"/>'
        body += f'<rect x="235" y="{y-14}" width="{600*value/max_value:.1f}" height="12" rx="6" fill="{color}"/>'
        body += label(900, y-2, f"{pct:.1f}%", 13, MUTED, 600, "end")
        y += 26
    body += label(30, 290, "GitHub language byte counts · Repository composition, not skill level", 11, MUTED)
    save("languages.svg", body, 1000, 315)
    return totals

def build_contributions(contribution):
    calendar = contribution["contributionCalendar"]
    days = [day for week in calendar["weeks"] for day in week["contributionDays"]][-371:]
    body = label(30, 34, "CONTRIBUTION ACTIVITY · LAST YEAR", 13, MUTED, 700)
    for index, day in enumerate(days):
        count = day["contributionCount"]
        level = 0 if count == 0 else 1 if count < 3 else 2 if count < 6 else 3 if count < 10 else 4
        x = 30 + (index // 7) * 15
        y = 65 + (index % 7) * 15
        body += (
            f'<rect x="{x}" y="{y}" width="11" height="11" rx="2" fill="{LEVELS[level]}">'
            f'<title>{html.escape(day["date"])}: {count} contributions</title></rect>'
        )
    counts = {date.fromisoformat(day["date"]): day["contributionCount"] for day in days}
    cursor = date.today()
    if counts.get(cursor, 0) == 0:
        cursor -= timedelta(days=1)
    current = 0
    while counts.get(cursor, 0) > 0:
        current += 1
        cursor -= timedelta(days=1)
    longest = run = 0
    for day in days:
        run = run + 1 if day["contributionCount"] > 0 else 0
        longest = max(longest, run)
    body += label(30, 190, f'{calendar["totalContributions"]:,} contributions', 16, TEXT, 700)
    body += label(300, 190, f"Current streak: {current} days", 14, BLUE, 600)
    body += label(570, 190, f"Longest streak in displayed year: {longest} days", 14, BLUE, 600)
    body += label(30, 218, "Contribution counts supplied by GitHub.", 11, MUTED)
    save("contributions.svg", body, 1000, 240)


def build_stack(language_totals):
    # Programming languages come from GitHub's repository language API.
    languages = [name for name, _ in sorted(
        language_totals.items(), key=lambda item: item[1], reverse=True
    )[:8]]

    # Frameworks and tools remain curated: repository language statistics
    # cannot reliably identify dependencies or distinguish use from learning.
    groups = [
        ("LANGUAGES · FROM REPOSITORIES", languages or ["No language data"]),
        ("DATA & ANALYTICS", ["Pandas", "NumPy", "Matplotlib", "Seaborn", "Power BI"]),
        ("WEB & BACKEND", ["HTML", "CSS", "React", "Next.js", "Flask", "FastAPI"]),
        ("TOOLS", ["Git", "GitHub", "Jupyter Notebook", "Docker"])
    ]
    body, y = "", 36
    for heading, items in groups:
        body += label(30, y, heading, 11, MUTED, 700)
        y += 15
        x = 30
        for item in items:
            width = max(76, len(item) * 8 + 22)
            if x + width > 970:
                x, y = 30, y + 34
            body += f'<rect x="{x}" y="{y}" width="{width}" height="27" rx="6" fill="{PANEL}" stroke="{BORDER}"/>'
            body += label(x + width / 2, y + 18, item, 11, TEXT, 600, "middle")
            x += width + 8
        y += 42
    save("tech-stack.svg", body, 1000, y + 8)


FEATURED_PROJECTS = [
    ("election-campaign-analysis", "Election Campaign Analyzer (2004–2024)", "https://election-analyzer.streamlit.app/"),
    ("Claude-AI-Challenge", "Healthcare Efficiency Explorer", "https://healthcare-efficiency-explorer.streamlit.app/"),
    ("resourcebridge", "ResourceBridge", None),
    ("autonomous-ai-creator", "Autonomous AI Creator", None),
    ("customer_behaviour_analysis", "Customer Behaviour Analysis", None),
    ("gurgaon-real-estate-analysis", "Gurgaon Real Estate Analysis", None),
    ("engineering-journal", "Beyond the Algorithm", "https://beyond-the-algorithm-sable.vercel.app/"),
    ("portfolio", "Personal Portfolio", None),
]

FEATURED_FALLBACKS = {
    "election-campaign-analysis": "Data science pipeline and Streamlit dashboard exploring five Indian Lok Sabha election cycles, with electoral metrics and visual analysis.",
    "Claude-AI-Challenge": "Interactive analysis of healthcare expenditure and life expectancy across approximately 193 countries using World Bank data.",
    "resourcebridge": "Campus resource-sharing application built around resource discovery, booking, manager approvals, check-in, returns, and incident tracking.",
    "autonomous-ai-creator": "AI workflow for discovering technology topics, checking relevance, reducing repetition, and generating source-grounded content.",
    "customer_behaviour_analysis": "Retail analysis combining Python preprocessing, MySQL aggregation, and an interactive Power BI dashboard.",
    "gurgaon-real-estate-analysis": "Exploratory analysis of property listings, locality patterns, pricing drivers, and property valuation.",
    "engineering-journal": "Independent technology publication documenting concepts, projects, experiments, and learning in Data Science, AI, ML, and software engineering.",
    "portfolio": "Personal website presenting projects, certifications, and professional background.",
}

def replace_auto_section(readme, start_marker, end_marker, generated):
    start = readme.find(start_marker)
    end = readme.find(end_marker)
    if start == -1 or end == -1 or end < start:
        raise RuntimeError(f"README markers missing or out of order: {start_marker}")
    return readme[:start] + start_marker + "\n" + generated.rstrip() + "\n" + readme[end:]


def build_readme_projects(repos):
    public = {r["name"]: r for r in repos if not r.get("private") and not r.get("fork")}
    featured_rows = []
    for name, title, live_url in FEATURED_PROJECTS:
        repo = public.get(name)
        if not repo:
            continue
        description = (repo.get("description") or FEATURED_FALLBACKS.get(name) or "Project repository.").strip()
        language = repo.get("language") or "Multiple technologies"
        stars = repo.get("stargazers_count", 0)
        details = f"<p>{html.escape(description)}</p><p><sub>{html.escape(language)} · ⭐ {stars}</sub></p>"
        if live_url:
            details += f'<p><a href="{html.escape(live_url, quote=True)}">Live project / publication</a></p>'
        featured_rows.append(
            f'<td width="50%" valign="top"><h3><a href="{html.escape(repo["html_url"], quote=True)}">{html.escape(title)}</a></h3>{details}</td>'
        )

    table_rows = []
    for index in range(0, len(featured_rows), 2):
        cells = "".join(featured_rows[index:index + 2])
        if index + 1 == len(featured_rows):
            cells += '<td width="50%" valign="top"></td>'
        table_rows.append(f"<tr>{cells}</tr>")
    featured_markdown = "<table>\n" + "\n".join(table_rows) + "\n</table>"

    excluded = {name for name, _, _ in FEATURED_PROJECTS}
    others = [
        r for r in public.values()
        if r["name"] not in excluded and r["name"] != USER
    ]
    others.sort(key=lambda r: (r.get("stargazers_count", 0), r.get("updated_at", "")), reverse=True)
    lines = []
    for repo in others[:12]:
        description = (repo.get("description") or "").strip()
        suffix = f" — {description}" if description else ""
        language = repo.get("language")
        metadata = f" · {language}" if language else ""
        stars = repo.get("stargazers_count", 0)
        lines.append(
            f'- [{repo["name"]}]({repo["html_url"]}){html.escape(suffix)}'
            f'{html.escape(metadata)} · ⭐ {stars}'
        )
    if not lines:
        lines = ["_No additional public repositories to display yet._"]
    more_markdown = "\n".join(lines)

    path = Path("README.md")
    readme = path.read_text(encoding="utf-8")
    readme = replace_auto_section(
        readme, "<!-- AUTO-FEATURED-PROJECTS-START -->",
        "<!-- AUTO-FEATURED-PROJECTS-END -->", featured_markdown
    )
    readme = replace_auto_section(
        readme, "<!-- AUTO-MORE-PROJECTS-START -->",
        "<!-- AUTO-MORE-PROJECTS-END -->", more_markdown
    )
    path.write_text(readme, encoding="utf-8")



def build():
    repositories = all_repositories()
    contribution = graphql("""
      query($login: String!) {
        user(login: $login) {
          contributionsCollection {
            totalCommitContributions
            totalPullRequestContributions
            totalIssueContributions
            totalRepositoryContributions
            contributionCalendar {
              totalContributions
              weeks { contributionDays { date contributionCount } }
            }
          }
        }
      }
    """)
    build_stats(repositories, contribution)
    language_totals = build_languages(repositories)
    build_contributions(contribution)
    build_stack(language_totals)
    build_readme_projects(repositories)
    print(f"Updated profile analytics and README project sections from {len(repositories)} accessible repositories.")

if __name__ == "__main__":
    build()
