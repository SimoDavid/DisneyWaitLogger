import os
import json
import datetime
from github import Github

# Constants
GITHUB_REPO_NAME = "SimoDavid/DisneyWaitLogger"
GITHUB_TOKEN = os.getenv("GITHUB_TOKEN")
BANNER_URL = "https://raw.githubusercontent.com/SimoDavid/DisneyWaitLogger/main/banner.jpg"
CHARTS_BASE_URL = "https://raw.githubusercontent.com/SimoDavid/DisneyWaitLogger/main/charts"
OUTPUT_HTML = "index.html"

# Authenticate GitHub
gh = Github(GITHUB_TOKEN)
repo = gh.get_repo(GITHUB_REPO_NAME)

# Helper: fetch file list from GitHub path
def list_github_files(path):
    try:
        contents = repo.get_contents(path)
        return [c.name for c in contents if c.name.endswith(".png")]
    except Exception as e:
        print(f"Error accessing {path}: {e}")
        return []

# Fetch files
monthly_files = list_github_files("charts/monthly")
daily_files = list_github_files("charts/daily")

# Filter and organize daily files
daily_by_month = {}
for file in daily_files:
    if file.endswith("wait times.png"):
        try:
            date_part = file.split(" ")[0]
            date_obj = datetime.datetime.strptime(date_part, "%Y-%m-%d").date()
            key = date_obj.strftime("%Y-%m")
            daily_by_month.setdefault(key, []).append((date_obj, file))
        except Exception as e:
            print(f"⚠️ Skipping daily file {file}: {e}")

# Filter and format monthly file keys
monthly_keys = set()
for f in monthly_files:
    if f.endswith("monthly_wait_chart.png"):
        try:
            ym = f.replace("_", "-").split(" ")[0]
            datetime.datetime.strptime(ym, "%Y-%m")  # validate format
            monthly_keys.add(ym)
        except Exception as e:
            print(f"⚠️ Skipping monthly file {f}: {e}")

# Combine and sort unique months
all_months = sorted(set(daily_by_month.keys()) | monthly_keys, reverse=True)

# Generate HTML
html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <title>Disney Tokyo Wait Times Project</title>
    <style>
        body {{ font-family: Arial, sans-serif; margin: 40px; }}
        summary {{ font-weight: bold; font-size: 1.2em; margin-top: 20px; }}
        img {{ max-width: 100%; height: auto; margin: 10px 0; }}
        .banner {{ width: 300px; float: left; margin-right: 20px; }}
        .title-header {{ overflow: hidden; padding-top: 20px; }}
    </style>
</head>
<body>
    <div class="title-header">
        <img src="{BANNER_URL}" alt="Banner" class="banner">
        <h1>Disney Tokyo Wait Times Project<br>
        <small>Current at {datetime.date.today().strftime('%A %-d %B %Y')}</small></h1>
    </div>
"""

# Add charts by month
for ym in all_months:
    year, month = ym.split("-")
    month_name = datetime.date(int(year), int(month), 1).strftime('%B %Y')
    html += f"<details open><summary>{month_name}</summary>\n"

    # Monthly chart
    monthly_name = f"{ym.replace('-', '_')} monthly_wait_chart.png"
    if monthly_name in monthly_files:
        html += f'<img src="{CHARTS_BASE_URL}/monthly/{monthly_name}" alt="Monthly Chart">\n'

    # Daily charts
    for date_obj, fname in sorted(daily_by_month.get(ym, []), reverse=True):
        pretty_date = date_obj.strftime('%A %-d %B %Y')
        html += f"<details><summary>{pretty_date}</summary>\n"
        html += f'<img src="{CHARTS_BASE_URL}/daily/{fname}" alt="{fname}">\n</details>\n'

    html += "</details>\n"

html += "</body>\n</html>"

# Save locally
with open(OUTPUT_HTML, "w") as f:
    f.write(html)

print(f"✅ Static HTML page generated and saved to {OUTPUT_HTML}")

# Upload to GitHub
try:
    with open(OUTPUT_HTML, "rb") as f:
        content = f.read()
    path = OUTPUT_HTML
    try:
        existing_file = repo.get_contents(path)
        repo.update_file(existing_file.path, "Update static site", content, existing_file.sha, branch="main")
        print("✅ GitHub file updated.")
    except:
        repo.create_file(path, "Add static site", content, branch="main")
        print("✅ GitHub file created.")
except Exception as e:
    print(f"❌ Failed to upload HTML to GitHub: {e}")
