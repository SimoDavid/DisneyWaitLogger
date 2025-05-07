import gspread
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
import numpy as np
import requests
import io
import datetime
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
from oauth2client.service_account import ServiceAccountCredentials
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import os
import json

# Configuration
BANNER_URL = "https://raw.githubusercontent.com/SimoDavid/DisneyWaitLogger/refs/heads/main/banner.jpg"
DRIVE_FOLDER_ID = "1VS6rc5vVsi_yHY1td-1TmUBeY4gdboq8"
DAILY_SUBFOLDER_NAME = "daily"

# Use Tokyo time and get the previous day
tokyo_tz = datetime.timezone(datetime.timedelta(hours=9))
now_tokyo = datetime.datetime.now(tokyo_tz)
target_date = now_tokyo - datetime.timedelta(days=1)
date_str = target_date.strftime("%Y-%m-%d")
sheet_name = f"TokyoDisneyWaitTimes-{target_date.strftime('%Y-%m')}"
output_filename = f"{date_str} wait times.png"

# Google Sheets auth from environment variable
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
credentials_dict = json.loads(os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON"))
creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
client = gspread.authorize(creds)

# Load sheet data
spreadsheet = client.open(sheet_name)
worksheet = spreadsheet.worksheet(date_str)
data = worksheet.get_all_values()

# Parse ride data
rides = []
for row in data[1:]:
    if len(row) < 3:
        continue
    ride = row[1]
    times = [int(x) if x.strip().isdigit() else np.nan for x in row[2:]]
    if all(np.isnan(times)):
        continue
    avg_wait = np.nanmean(times)
    rides.append((ride, avg_wait, times))

# Select Top 10 Rides
top_rides = sorted(rides, key=lambda x: x[1], reverse=True)[:10]

# Prepare X-Axis (15-min intervals from 8:00 to 24:00)
time_labels = [f"{h}:{m:02}" for h in range(8, 24) for m in range(0, 60, 15)] + ["24:00"]
x = list(range(len(time_labels)))

# Plotting
plt.figure(figsize=(18, 9))
for ride, avg, times in top_rides:
    label = f"{ride} ({int(round(avg))})"
    padded_times = times[:len(x)] + [np.nan] * (len(x) - len(times))
    plt.plot(x, padded_times, label=label)

plt.title(f"Top 10 Rides by Average Wait Time for {target_date.strftime('%A %B')} {target_date.day}, {target_date.year}")
plt.xlabel("Time of Day")
plt.ylabel("Wait Time (mins)")
plt.xticks(ticks=x, labels=time_labels, rotation=45, ha='right')
plt.legend(loc='center left', bbox_to_anchor=(1.01, 0.3))

# Add banner graphic from GitHub URL
response = requests.get(BANNER_URL)
if response.status_code == 200:
    banner_img = mpimg.imread(io.BytesIO(response.content), format='JPG')
    imagebox = OffsetImage(banner_img, zoom=0.15)
    ab = AnnotationBbox(imagebox, (1.15, 1.02), xycoords='axes fraction', frameon=False)
    plt.gca().add_artist(ab)

# Save chart locally
plt.tight_layout()
plt.savefig(output_filename, bbox_inches="tight")
plt.close()

# Google Drive auth and upload
gauth = GoogleAuth()
gauth.credentials = creds
drive = GoogleDrive(gauth)

# Find 'daily' subfolder
file_list = drive.ListFile({'q': f"'{DRIVE_FOLDER_ID}' in parents and trashed=false"}).GetList()
daily_folder_id = None
for f in file_list:
    if f['title'].lower() == DAILY_SUBFOLDER_NAME and f['mimeType'] == 'application/vnd.google-apps.folder':
        daily_folder_id = f['id']
        break

if not daily_folder_id:
    raise Exception("❌ Could not find 'daily' folder in Google Drive.")

# Upload the chart
uploaded_file = drive.CreateFile({'title': output_filename, 'parents': [{'id': daily_folder_id}]})
uploaded_file.SetContentFile(output_filename)
uploaded_file.Upload()
uploaded_file.InsertPermission({'type': 'anyone', 'value': 'anyone', 'role': 'reader'})

# Output embed URL
file_id = uploaded_file['id']
embed_url = f"https://drive.google.com/uc?export=view&id={file_id}"
print(f"✅ Uploaded to Google Drive.")
print(f"🔗 Embed in HTML: {embed_url}")
