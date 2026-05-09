import requests
from bs4 import BeautifulSoup
import json
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

RECIPIENT_EMAIL = "rowanlightfoot2005@gmail.com"
SEEN_JOBS_FILE = "seen_jobs.json"


# ─────────────────────────────────────────────
# Site-specific scrapers
# ─────────────────────────────────────────────

def fetch_plp_jobs():
    """Public Law Project – jobs are linked list items."""
    url = "https://publiclawproject.org.uk/support-us/latest-opportunities/"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; job-monitor-bot/1.0)"}
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    content = soup.find("div", class_="entry-content") or soup.find("article") or soup.body
    jobs = {}
    for li in content.find_all("li"):
        link = li.find("a", href=True)
        if link and "publiclawproject.org.uk/latest/job" in link["href"]:
            title = link.get_text(strip=True)
            if title:
                jobs[title] = link["href"]
    return url, jobs


def fetch_pilc_jobs():
    """Public Interest Law Centre – jobs are bold headings in prose."""
    url = "https://www.pilc.org.uk/about/jobs/"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; job-monitor-bot/1.0)"}
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    jobs = {}
    content = soup.find("div", class_="entry-content") or soup.find("article") or soup.body
    skip_prefixes = (
        "Purpose", "Salary", "Hours", "Contract", "Location",
        "Start", "Closing", "How", "Accountable", "Direct", "Please"
    )
    for strong in content.find_all(["strong", "b"]):
        text = strong.get_text(strip=True)
        if len(text) > 15 and not any(text.startswith(p) for p in skip_prefixes):
            jobs[text] = url
    return url, jobs


def fetch_leighday_jobs():
    """Leigh Day – jobs are JavaScript-rendered, requires headless browser."""
    from playwright.sync_api import sync_playwright

    url = "https://careers.leighday.co.uk/jobs/vacancy/find/results/"
    jobs = {}

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        page.goto(url, wait_until="networkidle", timeout=30000)

        try:
            page.wait_for_selector(
                "a.vacancy-title, .vacancy-list a, h3.job-title a, "
                ".job-listing a, li.vacancy a, a[href*='/vacancy/']",
                timeout=10000
            )
        except Exception:
            pass  # No jobs currently listed is fine

        soup = BeautifulSoup(page.content(), "html.parser")
        browser.close()

    # eArcu ATS typically links to individual vacancy pages
    for el in soup.find_all("a", href=True):
        title = el.get_text(strip=True)
        href = el["href"]
        if "/vacancy/" in href and len(title) > 5:
            full_url = href if href.startswith("http") else f"https://careers.leighday.co.uk{href}"
            jobs[title] = full_url

    return url, jobs


# ─────────────────────────────────────────────
# All sites to monitor — add more here
# ─────────────────────────────────────────────

SITES = {
    "Public Law Project": fetch_plp_jobs,
    "Public Interest Law Centre": fetch_pilc_jobs,
    "Leigh Day": fetch_leighday_jobs,
}


# ─────────────────────────────────────────────
# State management
# ─────────────────────────────────────────────

def load_seen_jobs():
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_seen_jobs(jobs):
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(jobs, f, indent=2)


# ─────────────────────────────────────────────
# Email
# ─────────────────────────────────────────────

def send_email(new_jobs_by_site):
    sender_email = os.environ["GMAIL_ADDRESS"]
    app_password = os.environ["GMAIL_APP_PASSWORD"]

    total = sum(len(jobs) for jobs in new_jobs_by_site.values())
    subject = f"🔔 {total} new job(s) found across monitored sites"

    text_lines = ["New job posting(s) found:\n"]
    html_lines = ["<h2>New job posting(s) found</h2>"]

    for site_name, jobs in new_jobs_by_site.items():
        if not jobs:
            continue
        text_lines.append(f"\n{site_name}:")
        html_lines.append(f"<h3>{site_name}</h3><ul>")
        for title, url in jobs.items():
            text_lines.append(f"  • {title}\n    {url}")
            html_lines.append(f'  <li><a href="{url}">{title}</a></li>')
        html_lines.append("</ul>")

    html_lines.append(
        f"<p><small>Alert sent {datetime.now().strftime('%d %b %Y at %H:%M')} UTC</small></p>"
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = RECIPIENT_EMAIL
    msg.attach(MIMEText("\n".join(text_lines), "plain"))
    msg.attach(MIMEText("\n".join(html_lines), "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, app_password)
        server.sendmail(sender_email, RECIPIENT_EMAIL, msg.as_string())

    print(f"Email sent with {total} new job(s).")


# ─────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────

def main():
    seen_jobs = load_seen_jobs()
    all_current_jobs = {}
    new_jobs_by_site = {}

    for site_name, fetch_fn in SITES.items():
        print(f"Checking {site_name}...")
        try:
            url, current_jobs = fetch_fn()
            print(f"  Found {len(current_jobs)} job(s): {list(current_jobs.keys())}")

            site_seen = seen_jobs.get(site_name, {})
            new_jobs = {t: u for t, u in current_jobs.items() if t not in site_seen}

            if new_jobs:
                print(f"  🆕 {len(new_jobs)} new: {list(new_jobs.keys())}")
                new_jobs_by_site[site_name] = new_jobs
            else:
                print(f"  No new jobs.")

            all_current_jobs[site_name] = current_jobs

        except Exception as e:
            print(f"  ⚠️ Error fetching {site_name}: {e}")

    if new_jobs_by_site:
        send_email(new_jobs_by_site)

    save_seen_jobs(all_current_jobs)
    print("Done.")


if __name__ == "__main__":
    main()
