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
    """Public Interest Law Centre – job title is in an h2 or h3, or linked."""
    url = "https://www.pilc.org.uk/about/jobs/"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; job-monitor-bot/1.0)"}
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    jobs = {}
    content = soup.find("div", class_="entry-content") or soup.find("article") or soup.body

    # Try headings with links first
    for tag in content.find_all(["h2", "h3"]):
        link = tag.find("a", href=True)
        title = tag.get_text(strip=True)
        skip_phrases = ["current vacanc", "about us", "contact", "pilc", "equal opportunit"]
        if any(p in title.lower() for p in skip_phrases):
            continue
        if len(title) > 5:
            job_url = link["href"] if link else url
            if job_url and not job_url.startswith("http"):
                job_url = "https://www.pilc.org.uk" + job_url
            jobs[title] = job_url

    # Fallback: look for links to job pages
    if not jobs:
        for a in content.find_all("a", href=True):
            if "job" in a["href"].lower() or "vacanc" in a["href"].lower():
                title = a.get_text(strip=True)
                if len(title) > 5:
                    job_url = a["href"]
                    if not job_url.startswith("http"):
                        job_url = "https://www.pilc.org.uk" + job_url
                    jobs[title] = job_url

    return url, jobs


def fetch_advocate_jobs():
    """Advocate – jobs are linked from /work-for-us/ paths on the careers page."""
    url = "https://weareadvocate.org.uk/about-us/work-for-us.html"
    headers = {"User-Agent": "Mozilla/5.0 (compatible; job-monitor-bot/1.0)"}
    response = requests.get(url, headers=headers, timeout=15)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    jobs = {}
    for a in soup.find_all("a", href=True):
        href = a["href"]
        title = a.get_text(strip=True)
        # Job links follow the pattern /work-for-us/<job-slug>.html
        if "/work-for-us/" in href and href.endswith(".html") and len(title) > 5:
            if not href.startswith("http"):
                href = "https://weareadvocate.org.uk" + href
            jobs[title] = href
    return url, jobs


# ─────────────────────────────────────────────
# All sites to monitor — add more here
# ─────────────────────────────────────────────

SITES = {
    "Public Law Project": fetch_plp_jobs,
    "Public Interest Law Centre": fetch_pilc_jobs,
    "Advocate": fetch_advocate_jobs,
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

    html_lines.append(f"<p><small>Alert sent {datetime.now().strftime('%d %b %Y at %H:%M')} UTC</small></p>")

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
