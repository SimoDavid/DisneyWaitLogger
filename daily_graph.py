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
import io

# Constants
BANNER_URL = 'https://raw.githubusercontent.com/SimoDavid/DisneyWaitLogger/refs/heads/main/banner.jpg'
GITHUB_REPO_NAME = 'SimoDavid/DisneyWaitLogger'
GITHUB_CHARTS_PATH = 'charts/daily'

# Date Setup
tokyo_tz = pytz.timezone('Asia/Tokyo')
today_tokyo = datetime.datetime.now(tokyo_tz).date()
target_date = today_tokyo - datetime.timedelta(days=1)
tab_name = target_date.strftime('%Y-%m-%d')
chart_title_date = target_date.strftime('%A %-d %B %Y')
filename = f"{tab_name} wait times.png"
spreadsheet_name = f"TokyoDisneyWaitTimes-{target_date.strftime('%Y-%m')}"

# Google Sheets Credentials
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
if os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON"):
    creds_json = json.loads(os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON"))
    creds = ServiceAccountCredentials.from_json_keyfile_dict(creds_json, scope)
else:
    creds = ServiceAccountCredentials.from_json_keyfile_name("disneywaitlogger-dac8ce422390.json", scope)

client = gspread.authorize(creds)
worksheet = client.open(spreadsheet_name).worksheet(tab_name)
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

top10 = sorted(ride_averages, key=lambda x: x[1], reverse=True)[:10]

# Graph
plt.figure(figsize=(18, 10))
x_ticks = headers
x_indices = np.arange(len(x_ticks))

for name, _ in top10:
    y = ride_waits[name][:len(x_indices)]
    if np.all(np.isnan(y)):
        continue
    avg_wait = np.nanmean(y)
    avg_label = "?" if np.isnan(avg_wait) else int(round(avg_wait))
    plt.plot(x_indices, y, label=f"{name} ({avg_label})")

plt.xticks(x_indices, x_ticks, rotation=45)
plt.xlabel("Time of Day")
plt.ylabel("Wait Time (minutes)")
plt.title(f"Top 10 Rides by Average Wait Time for {chart_title_date}")
plt.legend(loc='lower right', bbox_to_anchor=(1.25, 0))

# Banner
response = requests.get(BANNER_URL)
img = mpimg.imread(io.BytesIO(response.content), format='jpg')
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
gauth.credentials = creds
drive = GoogleDrive(gauth)

folder_list = drive.ListFile({'q': "'root' in parents and trashed=false"}).GetList()
disney_folder = next((f for f in folder_list if f['title'] == 'disneywaittimes'), None)

if disney_folder:
    subfolders = drive.ListFile({'q': f"'{disney_folder['id']}' in parents and trashed=false"}).GetList()
    daily_folder = next((f for f in subfolders if f['title'] == 'daily'), None)

    if daily_folder:
        existing_files = drive.ListFile({'q': f"'{daily_folder['id']}' in parents and trashed=false"}).GetList()
        for f in existing_files:
            if f['title'] == filename:
                f.Delete()

        upload_file = drive.CreateFile({'title': filename, 'parents': [{'id': daily_folder['id']}]})
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
