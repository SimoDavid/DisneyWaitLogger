import os
import json
import datetime
import pytz
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

# Constants
SPREADSHEET_NAME = 'TokyoDisneyWaitTimes-2025-05'
BANNER_URL = 'https://raw.githubusercontent.com/SimoDavid/DisneyWaitLogger/refs/heads/main/banner.jpg'
GOOGLE_DAILY_FOLDER_ID = '1eDNTznhWvhPWmYtWsfZ2T2T12kEYb_tB'  # /disneywaittimes/daily
GITHUB_REPO_NAME = 'SimoDavid/DisneyWaitLogger'
GITHUB_CHARTS_PATH = 'charts/daily'

# Date Setup (yesterday, Tokyo time)
tokyo_tz = pytz.timezone('Asia/Tokyo')
today_tokyo = datetime.datetime.now(tokyo_tz).date()
target_date = today_tokyo - datetime.timedelta(days=1)
tab_name = target_date.strftime('%Y-%m-%d')
chart_title_date = target_date.strftime('%A %d %B %Y')
filename = f"{tab_name} wait times.png"

# Authorize Google Sheets
if os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON"):
    credentials_dict = json.loads(os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON"))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(
        credentials_dict, ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    )
else:
    creds = ServiceAccountCredentials.from_json_keyfile_name(
        'disneywaitlogger-dac8ce422390.json',
        ['https://spreadsheets.google.com/feeds', 'https://www.googleapis.com/auth/drive']
    )

client = gspread.authorize(creds)

# Load worksheet
worksheet = client.open(SPREADSHEET_NAME).worksheet(tab_name)
data = worksheet.get_all_values()
headers = data[0][2:]
ride_rows = data[1:]

ride_averages = []
ride_waits = {}

for row in ride_rows:
    name = row[1]
    times = row[2:]
    wait_times = [int(t) if t.isdigit() else np.nan for t in times]
    ride_waits[name] = wait_times
    avg = np.nanmean(wait_times)
    ride_averages.append((name, avg))

# Select top 10
top10 = sorted(ride_averages, key=lambda x: x[1], reverse=True)[:10]

# Graph
plt.figure(figsize=(18, 10))
x_ticks = headers
x_indices = np.arange(len(x_ticks))

for name, _ in top10:
    y = ride_waits[name][:len(x_indices)]
    plt.plot(x_indices, y, label=f"{name} ({int(np.nanmean(y))})")

plt.xticks(x_indices, x_ticks, rotation=45)
plt.xlabel("Time of Day")
plt.ylabel("Wait Time (minutes)")
plt.title(f"Top 10 Rides by Average Wait Time for {chart_title_date}")
plt.legend(loc='lower right')

# Banner
response = requests.get(BANNER_URL)
img = mpimg.imread(requests.get(BANNER_URL, stream=True).raw, format='jpg')
imagebox = OffsetImage(img, zoom=0.15)
ab = AnnotationBbox(imagebox, (0.95, 0.95), frameon=False, xycoords='axes fraction')
plt.gca().add_artist(ab)

# Save chart
plt.tight_layout()
plt.savefig(filename)
plt.close()
print(f"✅ Chart saved as {filename}")

# Upload to Google Drive
gauth = GoogleAuth()
gauth.LocalWebserverAuth()
drive = GoogleDrive(gauth)

# Remove existing file (if any)
existing_files = drive.ListFile({
    'q': f"'{GOOGLE_DAILY_FOLDER_ID}' in parents and title='{filename}' and trashed=false"
}).GetList()
for f in existing_files:
    f.Delete()

upload_file = drive.CreateFile({'title': filename, 'parents': [{'id': GOOGLE_DAILY_FOLDER_ID}]})
upload_file.SetContentFile(filename)
upload_file.Upload()
print("📤 Uploaded to Google Drive.")

# Upload to GitHub
github_token = os.getenv("GITHUB_TOKEN")
if github_token:
    gh = Github(github_token)
    repo = gh.get_repo(GITHUB_REPO_NAME)

    with open(filename, "rb") as f:
        content = f.read()

    path = f"{GITHUB_CHARTS_PATH}/{filename}"
    try:
        existing_file = repo.get_contents(path)
        repo.update_file(existing_file.path, f"Update {filename}", content, existing_file.sha, branch="main")
        print("✅ GitHub file updated.")
    except:
        repo.create_file(path, f"Add {filename}", content, branch="main")
        print("✅ GitHub file created.")
else:
    print("⚠️ GITHUB_TOKEN not found. Skipping GitHub upload.")
