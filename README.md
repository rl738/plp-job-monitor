# PLP Job Monitor

Automatically checks the [Public Law Project opportunities page](https://publiclawproject.org.uk/support-us/latest-opportunities/) once a day and emails you when new jobs appear.

Runs free on GitHub Actions.

---

## Setup (takes about 10 minutes)

### 1. Create a GitHub account and a new repository

- Go to [github.com](https://github.com) and sign up / log in
- Click **New repository**, name it `plp-job-monitor`, make it **Private**, click **Create**

### 2. Upload these files

Upload all four files to the repo root, keeping the folder structure:
```
plp-job-monitor/
├── monitor.py
├── requirements.txt
├── seen_jobs.json
└── .github/
    └── workflows/
        └── monitor.yml
```

The easiest way: on the repo page, click **Add file → Upload files** and drag them all in.
For the `.github/workflows/monitor.yml` file, you need to create the folders manually using the
"Create new file" option and typing `.github/workflows/monitor.yml` as the filename.

### 3. Set up a Gmail App Password

You need a Gmail account to send the alert emails (it can be any Gmail, doesn't have to be your main one).

1. Go to your Google Account → **Security**
2. Make sure **2-Step Verification** is turned on
3. Search for **App passwords** in the security settings
4. Create a new app password — call it "PLP Monitor"
5. Copy the 16-character password Google gives you

### 4. Add secrets to GitHub

In your GitHub repo, go to **Settings → Secrets and variables → Actions → New repository secret**

Add these two secrets:

| Name | Value |
|------|-------|
| `GMAIL_ADDRESS` | Your Gmail address (e.g. `yourname@gmail.com`) |
| `GMAIL_APP_PASSWORD` | The 16-character app password from step 3 |

### 5. Test it

Go to **Actions** tab in your repo → click **PLP Job Monitor** → click **Run workflow**.

It will run immediately. If a job is already listed on the page, you'll get an email straight away
(since `seen_jobs.json` starts empty). After that, you'll only hear when something *new* appears.

---

## How it works

- Runs every day at **8am UTC** (9am UK time in winter, same in summer since UK is UTC+1)
- Scrapes the PLP opportunities page
- Compares what's there against `seen_jobs.json` (saved in the repo)
- If anything new is found, sends you an email with the title and a direct link
- Updates `seen_jobs.json` so you don't get alerted twice

## Changing the schedule

Edit the `cron` line in `.github/workflows/monitor.yml`. Use [crontab.guru](https://crontab.guru) to build a schedule. For example:
- Twice a day: `0 8,17 * * *`
- Weekdays only: `0 8 * * 1-5`
