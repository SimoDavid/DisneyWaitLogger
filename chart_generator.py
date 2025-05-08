import os
import json
import datetime
import calendar
import gspread
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import numpy as np
import requests
from oauth2client.service_account import ServiceAccountCredentials
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
from github import Github
import io

# Constants
BANNER_URL = 'https://raw.githubusercontent.com/SimoDavid/DisneyWaitLogger/refs/heads/main/banner.jpg'
GITHUB_REPO_NAME = 'SimoDavid/DisneyWaitLogger'
GITHUB_CHARTS_PATH = 'charts/monthly'

# Date info
today = datetime.date.today()
year = today.year
month = today.month
spreadsheet_name = f"TokyoDisneyWaitTimes-{year}-{str(month).zfill(2)}"
days_in_month = calendar.monthrange(year, month)[1]
output_filename = f"{year}_{str(month).zfill(2)} monthly_wait_chart.png"

# Authorize Google Sheets
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
if os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON"):
    creds_json = json.loads(os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON"))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
else:
    creds = ServiceAccountCredentials.from_json_keyfile_name("disneywaitlogger-dac8ce422390.json", scope)

client = gspread.authorize(creds)
sheet = client.open(spreadsheet_name)

# Accumulate wait times per ride
ride_waits = {}
for day in range(1, today.day):
    tab_name = f"{year}-{str(month).zfill(2)}-{str(day).zfill(2)}"
    try:
        worksheet = sheet.worksheet(tab_name)
        data = worksheet.get_all_values()
        for row in data[1:]:
            ride_name = row[1]
            wait_times = [int(t) if t.isdigit() else np.nan for t in row[2:]]
            if ride_name not in ride_waits:
                ride_waits[ride_name] = [np.nan] * days_in_month
            ride_waits[ride_name][day - 1] = np.nanmean(wait_times)
    except:
        continue

# Calculate average wait times
averages = {
    name: np.nanmean(waits)
    for name, waits in ride_waits.items()
    if any(not np.isnan(w) for w in waits)
}

top10 = sorted(averages.items(), key=lambda x: x[1], reverse=True)[:10]

# Plotting
fig, ax = plt.subplots(figsize=(18, 10))
x = list(range(1, days_in_month + 1))
for ride_name, _ in top10:
    y = ride_waits.get(ride_name, [np.nan] * days_in_month)
    if np.all(np.isnan(y)):
        continue
    avg = np.nanmean(y)
    label = f"{ride_name} ({int(round(avg))})" if not np.isnan(avg) else ride_name
    ax.plot(x, y, label=label)

# X-axis formatting
x_labels = [
    datetime.date(year, month, day).strftime('%A %-d')
    for day in x
]
ax.set_xticks(x)
ax.set_xticklabels(x_labels, rotation=45)
ax.set_xlabel("Day of Month")
ax.set_ylabel("Wait Time (minutes)")
ax.set_title(f"Top 10 Rides by Average Wait Time for the Month of {today.strftime('%B %Y')}")

# Banner graphic
response = requests.get(BANNER_URL)
if response.status_code == 200:
    banner_img = mpimg.imread(io.BytesIO(response.content), format='jpg')
    imagebox = OffsetImage(banner_img, zoom=0.15)
    ab = AnnotationBbox(imagebox, (0.95, 0.95), frameon=False, xycoords='axes fraction')
    ax.add_artist(ab)

# Legend and save
plt.legend(loc='lower right', bbox_to_anchor=(1.25, 0))
plt.tight_layout()
plt.savefig(output_filename)
plt.close()
print(f"✅ Chart saved as {output_filename}")

# Upload to Google Drive
gauth = GoogleAuth()
gauth.credentials = creds
drive = GoogleDrive(gauth)

folder_list = drive.ListFile({'q': "'root' in parents and trashed=false"}).GetList()
disney_folder = next((f for f in folder_list if f['title'] == 'disneywaittimes'), None)

if disney_folder:
    subfolders = drive.ListFile({'q': f"'{disney_folder['id']}' in parents and trashed=false"}).GetList()
    monthly_folder = next((f for f in subfolders if f['title'] == 'monthly'), None)

    if monthly_folder:
        existing_files = drive.ListFile({'q': f"'{monthly_folder['id']}' in parents and trashed=false"}).GetList()
        for f in existing_files:
            if f['title'] == output_filename:
                f.Delete()

        upload_file = drive.CreateFile({'title': output_filename, 'parents': [{'id': monthly_folder['id']}]})
        upload_file.SetContentFile(output_filename)
        upload_file.Upload()
        print("📤 Uploaded to Google Drive.")

# Upload to GitHub
github_token = os.getenv("GITHUB_TOKEN")
if github_token:
    gh = Github(github_token)
    repo = gh.get_repo(GITHUB_REPO_NAME)

    with open(output_filename, "rb") as f:
        content = f.read()

    path = f"{GITHUB_CHARTS_PATH}/{output_filename}"
    try:
        existing_file = repo.get_contents(path)
        repo.update_file(existing_file.path, f"Update {output_filename}", content, existing_file.sha, branch="main")
        print("✅ GitHub file updated.")
    except:
        repo.create_file(path, f"Add {output_filename}", content, branch="main")
        print("✅ GitHub file created.")
else:
    print("⚠️ GITHUB_TOKEN not found. Skipping GitHub upload.")
