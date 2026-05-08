import requests
from bs4 import BeautifulSoup
import json
import smtplib
import os
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

URL = "https://publiclawproject.org.uk/support-us/latest-opportunities/"
SEEN_JOBS_FILE = "seen_jobs.json"
RECIPIENT_EMAIL = "rowanlightfoot2005@gmail.com"


def fetch_jobs():
    """Scrape the PLP opportunities page and return a dict of {title: url}."""
    headers = {"User-Agent": "Mozilla/5.0 (compatible; job-monitor-bot/1.0)"}
    response = requests.get(URL, headers=headers, timeout=15)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    # Find the main content area and grab all links inside list items
    # The jobs appear as <li><a href="...">Job Title</a></li>
    content = soup.find("div", class_="entry-content") or soup.find("article") or soup.body
    jobs = {}
    for li in content.find_all("li"):
        link = li.find("a", href=True)
        if link and "publiclawproject.org.uk/latest/job" in link["href"]:
            title = link.get_text(strip=True)
            url = link["href"]
            if title:
                jobs[title] = url

    return jobs


def load_seen_jobs():
    """Load previously seen jobs from the JSON file."""
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE, "r") as f:
            return json.load(f)
    return {}


def save_seen_jobs(jobs):
    """Save current jobs to the JSON file."""
    with open(SEEN_JOBS_FILE, "w") as f:
        json.dump(jobs, f, indent=2)


def send_email(new_jobs):
    """Send an email alert listing the new job postings."""
    sender_email = os.environ["GMAIL_ADDRESS"]
    app_password = os.environ["GMAIL_APP_PASSWORD"]

    subject = f"🔔 New job(s) at Public Law Project ({len(new_jobs)} new)"

    # Build plain-text and HTML versions
    text_lines = [
        f"New job posting(s) have appeared on the Public Law Project opportunities page:\n",
    ]
    html_lines = [
        "<h2>New job posting(s) at Public Law Project</h2>",
        "<ul>",
    ]

    for title, url in new_jobs.items():
        text_lines.append(f"  • {title}\n    {url}\n")
        html_lines.append(f'  <li><a href="{url}">{title}</a></li>')

    html_lines.append("</ul>")
    html_lines.append(f'<p><a href="{URL}">View all opportunities →</a></p>')
    html_lines.append(f"<p><small>Alert sent {datetime.now().strftime('%d %b %Y at %H:%M')} UTC</small></p>")

    text_lines.append(f"\nView all opportunities: {URL}")

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = sender_email
    msg["To"] = RECIPIENT_EMAIL

    msg.attach(MIMEText("\n".join(text_lines), "plain"))
    msg.attach(MIMEText("\n".join(html_lines), "html"))

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(sender_email, app_password)
        server.sendmail(sender_email, RECIPIENT_EMAIL, msg.as_string())

    print(f"Email sent to {RECIPIENT_EMAIL} with {len(new_jobs)} new job(s).")


def main():
    print(f"Checking {URL} ...")
    current_jobs = fetch_jobs()
    print(f"Found {len(current_jobs)} job(s) currently listed: {list(current_jobs.keys())}")

    seen_jobs = load_seen_jobs()
    new_jobs = {title: url for title, url in current_jobs.items() if title not in seen_jobs}

    if new_jobs:
        print(f"🆕 {len(new_jobs)} new job(s) found: {list(new_jobs.keys())}")
        send_email(new_jobs)
    else:
        print("No new jobs since last check.")

    # Update the saved list to include everything currently on the page
    save_seen_jobs(current_jobs)
    print("Done.")


if __name__ == "__main__":
    main()
