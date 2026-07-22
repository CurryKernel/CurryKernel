#!/usr/bin/env python3
"""
Generate GitHub stats SVGs for profile README.
Uses GitHub REST + GraphQL API to fetch real data, outputs self-hosted SVGs.
"""
import json, os, sys, math
from datetime import datetime, timezone, timedelta
from urllib.request import urlopen, Request

USER = os.environ.get("GITHUB_USER", "CurryKernel")
TOKEN = os.environ.get("GITHUB_TOKEN", "")

BG   = "#ffffff"
CARD_BG = "#f8fafc"
TITLE_C = "#3b82f6"
ICON_C  = "#6366f1"
TEXT_C  = "#374151"
MUTED_C = "#6b7280"
BORDER  = "#e5e7eb"
RING_C  = "#3b82f6"
LANG_COLORS = {
    "C++": "#00599C", "Java": "#ED8B00", "JavaScript": "#F7DF1E",
    "Python": "#3776AB", "Shell": "#4EAA25", "TypeScript": "#3178C6",
    "Go": "#00ADD8", "Rust": "#DEA584", "C": "#555555", "HTML": "#E34F26",
    "CSS": "#563D7C", "Vue": "#4FC08D", "Jupyter Notebook": "#DA5B0B",
    "CMake": "#064F8C", "Makefile": "#427819", "Dockerfile": "#2496ED",
}

W = 480; H = 200; RADIUS = 10  # card dimensions
LW = 320; LH = 210              # top-langs card dimensions


def gh(path, gql=False):
    url = "https://api.github.com/graphql" if gql else f"https://api.github.com{path}"
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "stats-gen"}
    if TOKEN:
        headers["Authorization"] = f"bearer {TOKEN}"
    data = json.dumps({"query": path}).encode() if gql else None
    if data:
        headers["Content-Type"] = "application/json"
    req = Request(url, data=data, headers=headers)
    with urlopen(req, timeout=30) as r:
        return json.loads(r.read())


def fetch_stats():
    """Fetch all stats from GitHub API."""
    user = gh(f"/users/{USER}")
    repos = gh(f"/users/{USER}/repos?per_page=100&type=owner")

    # Stars
    total_stars = sum(r.get("stargazers_count", 0) for r in repos)

    # Followers
    followers = user.get("followers", 0)

    # Contributions & streak from GraphQL
    today = datetime.now(timezone.utc)
    one_year_ago = today - timedelta(days=365)
    gql = """
    query {
      user(login: "%s") {
        contributionsCollection(from: "%s") {
          totalCommitContributions
          totalPullRequestContributions
          totalIssueContributions
          contributionCalendar {
            totalContributions
            weeks { contributionDays { contributionCount date } }
          }
        }
      }
    }
    """ % (USER, one_year_ago.strftime("%Y-%m-%dT%H:%M:%SZ"))
    gql_data = gh(gql, gql=True)
    contrib = gql_data["data"]["user"]["contributionsCollection"]

    commits = contrib["totalCommitContributions"]
    prs = contrib["totalPullRequestContributions"]
    issues = contrib["totalIssueContributions"]
    total_contribs = contrib["contributionCalendar"]["totalContributions"]

    # Streak calculation
    days_data = []
    for week in contrib["contributionCalendar"]["weeks"]:
        for day in week["contributionDays"]:
            days_data.append((day["date"], day["contributionCount"]))

    current_streak = 0; longest_streak = 0; streak = 0
    for date_str, count in days_data:
        if count > 0:
            streak += 1
            longest_streak = max(longest_streak, streak)
        else:
            streak = 0
    # current streak from today backwards
    current_streak = 0
    for date_str, count in reversed(days_data):
        if count > 0:
            current_streak += 1
        else:
            break

    # Top languages
    lang_bytes = {}
    for repo in repos:
        if repo.get("fork") or repo.get("language") is None:
            continue
        lang = repo["language"]
        # Get real bytes from repo languages API
        try:
            langs_data = gh(f"/repos/{USER}/{repo['name']}/languages")
            for l, b in langs_data.items():
                lang_bytes[l] = lang_bytes.get(l, 0) + b
        except Exception:
            lang_bytes[lang] = lang_bytes.get(lang, 0) + 1000

    sorted_langs = sorted(lang_bytes.items(), key=lambda x: x[1], reverse=True)[:6]
    total_bytes = sum(b for _, b in sorted_langs) or 1

    return {
        "stars": total_stars,
        "followers": followers,
        "commits": commits,
        "prs": prs,
        "issues": issues,
        "total_contribs": total_contribs,
        "current_streak": current_streak,
        "longest_streak": longest_streak,
        "langs": [(l, round(b / total_bytes * 100, 1)) for l, b in sorted_langs],
        "total_repos": user.get("public_repos", 0),
    }


def hex_to_rgb(h):
    h = h.lstrip("#")
    return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))


def svg_tag(tag, attrs=None, body="", close=True):
    attrs = attrs or {}
    attr_str = " ".join(f'{k}="{v}"' for k, v in attrs.items())
    if close:
        return f"<{tag} {attr_str}>{body}</{tag}>"
    return f"<{tag} {attr_str}/>"


def svg_text(x, y, text, size=14, color=TEXT_C, anchor="start", bold=False, font="sans-serif"):
    weight = "font-weight=\"bold\"" if bold else ""
    return f'<text x="{x}" y="{y}" font-family="{font}" font-size="{size}" fill="{color}" text-anchor="{anchor}" {weight}>{text}</text>'


def svg_rect(x, y, w, h, r=4, fill=BG, stroke=None):
    s = f' stroke="{stroke}" stroke-width="1"' if stroke else ""
    return f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{r}" fill="{fill}"{s}/>'


def build_card(title, items, w=W, h=H):
    """Build an SVG card with title + grid of stat items."""
    rows = []
    # Background
    rows.append(svg_rect(0, 0, w, h, RADIUS, CARD_BG, BORDER))
    # Title
    rows.append(svg_text(24, 38, title, 16, TITLE_C, bold=True))

    icon_map = {
        "Stars": "★", "Commits": "⬡", "PRs": "⇄", "Issues": "●",
        "Followers": "♥", "Total Contributions": "∑", "Repos": "▤",
    }

    x, y = 24, 72
    for i, (label, value) in enumerate(items):
        col = i % 2
        cx = x + col * 220
        cy = y + (i // 2) * 52

        icon = icon_map.get(label, "·")
        rows.append(svg_rect(cx, cy, 200, 40, 6, BG, BORDER))
        rows.append(svg_text(cx + 12, cy + 17, f"{icon}  {label}", 11, MUTED_C))
        val_text = str(value)
        rows.append(svg_text(cx + 188, cy + 28, val_text, 22, TITLE_C, anchor="end", bold=True))

    rows.append('</svg>')
    header = f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
    return header + "\n  " + "\n  ".join(rows)


def build_langs_card(langs, w=LW, h=LH):
    """Build a top-languages bar chart SVG card."""
    rows = []
    rows.append(svg_rect(0, 0, w, h, RADIUS, CARD_BG, BORDER))
    rows.append(svg_text(20, 34, "Most Used Languages", 16, TITLE_C, bold=True))

    bar_x = 20; bar_w = w - 60; bar_y = 52; bar_h = 18; gap = 28
    total_pct = sum(p for _, p in langs)
    for i, (lang, pct) in enumerate(langs):
        y = bar_y + i * gap
        color = LANG_COLORS.get(lang, "#9ca3af")
        # Label
        rows.append(svg_text(bar_x, y + 13, lang, 12, TEXT_C))
        # Bar background
        rows.append(svg_rect(bar_x + 100, y + 2, bar_w - 100, bar_h, 9, "#f1f5f9"))
        # Bar fill
        fill_w = max(4, int((bar_w - 100) * pct / 100))
        rows.append(svg_rect(bar_x + 100, y + 2, fill_w, bar_h, 9, color))
        # Percentage
        pct_display = round(pct * total_pct / 100 if total_pct != 100 else pct, 1)
        rows.append(svg_text(w - 20, y + 13, f"{pct_display}%", 12, MUTED_C, anchor="end"))

    rows.append('</svg>')
    header = f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
    return header + "\n  " + "\n  ".join(rows)


def build_streak_card(current, longest, total, w=W, h=130):
    """Build a streak / contributions summary card."""
    rows = []
    rows.append(svg_rect(0, 0, w, h, RADIUS, CARD_BG, BORDER))
    rows.append(svg_text(24, 38, "Contribution Activity", 16, TITLE_C, bold=True))

    items = [
        ("Current Streak", f"{current} days"),
        ("Longest Streak", f"{longest} days"),
        ("Past Year", f"{total} commits"),
    ]
    for i, (label, value) in enumerate(items):
        cx = 24 + i * 152
        rows.append(svg_rect(cx, 58, 136, 52, 6, BG, BORDER))
        rows.append(svg_text(cx + 12, 80, label, 11, MUTED_C))
        rows.append(svg_text(cx + 68, 100, value, 16, TITLE_C, anchor="middle", bold=True))

    rows.append('</svg>')
    header = f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" viewBox="0 0 {w} {h}">'
    return header + "\n  " + "\n  ".join(rows)


def main():
    print("Fetching GitHub stats...")
    try:
        stats = fetch_stats()
    except Exception as e:
        print(f"ERROR fetching stats: {e}", file=sys.stderr)
        sys.exit(1)

    out_dir = sys.argv[1] if len(sys.argv) > 1 else "dist"
    os.makedirs(out_dir, exist_ok=True)

    # Stats card
    items = [
        ("Stars", stats["stars"]),
        ("Commits", stats["commits"]),
        ("PRs", stats["prs"]),
        ("Issues", stats["issues"]),
        ("Followers", stats["followers"]),
        ("Repos", stats["total_repos"]),
    ]
    svg = build_card("GitHub Stats", items)
    path = os.path.join(out_dir, "github-stats.svg")
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"  → {path}")

    # Top langs
    svg = build_langs_card(stats["langs"])
    path = os.path.join(out_dir, "github-top-langs.svg")
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"  → {path}")

    # Streak
    svg = build_streak_card(stats["current_streak"], stats["longest_streak"], stats["commits"])
    path = os.path.join(out_dir, "github-streak.svg")
    with open(path, "w", encoding="utf-8") as f:
        f.write(svg)
    print(f"  → {path}")

    print("Done! Generated 3 SVGs.")


if __name__ == "__main__":
    main()
