import gspread
from oauth2client.service_account import ServiceAccountCredentials
from pydrive.auth import GoogleAuth
from pydrive.drive import GoogleDrive
import matplotlib.pyplot as plt
import matplotlib.image as mpimg
from matplotlib.offsetbox import OffsetImage, AnnotationBbox
import datetime
import calendar
import numpy as np
import os
import json
import io
import requests

# Configuration
BANNER_URL = "https://raw.githubusercontent.com/SimoDavid/DisneyWaitLogger/refs/heads/main/banner.jpg"
DRIVE_FOLDER_ID = "1VS6rc5vVsi_yHY1td-1TmUBeY4gdboq8"
MONTHLY_SUBFOLDER_NAME = "monthly"
CREDENTIALS_FILE = "disneywaitlogger-dac8ce422390.json"

# Date info
now = datetime.datetime.now()
year = now.year
month = now.month
today = now.day
last_day = calendar.monthrange(year, month)[1]
SPREADSHEET_NAME = f"TokyoDisneyWaitTimes-{year}-{month:02d}"
output_filename = f"{year}_{month:02d} monthly_wait_chart.png"
title_str = f"Top 10 Rides by Average Wait Time for the Month of {now.strftime('%B')} {year}"

# Auth credentials
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
env_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON")
if env_json:
    credentials_dict = json.loads(env_json)
    creds = ServiceAccountCredentials.from_json_keyfile_dict(credentials_dict, scope)
else:
    creds = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
client = gspread.authorize(creds)

# Load spreadsheet
spreadsheet = client.open(SPREADSHEET_NAME)

# Collect ride data
ride_data = {}
all_days = list(range(1, last_day + 1))

for day in range(1, today):
    tab_name = f"{year}-{month:02d}-{day:02d}"
    try:
        worksheet = spreadsheet.worksheet(tab_name)
        data = worksheet.get_all_values()
    except gspread.exceptions.WorksheetNotFound:
        continue

    for row in data[1:]:
        if len(row) < 3:
            continue
        ride_name = row[1]
        wait_times = [int(x) if x.strip().isdigit() else np.nan for x in row[2:]]
        if ride_name not in ride_data:
            ride_data[ride_name] = [[] for _ in all_days]
        ride_data[ride_name][day - 1] = wait_times

# Compute averages
ride_averages = {}
for ride, waits_per_day in ride_data.items():
    daily_averages = []
    for waits in waits_per_day:
        avg = np.nanmean(waits) if waits else np.nan
        daily_averages.append(avg)
    overall_avg = np.nanmean([val for val in daily_averages if not np.isnan(val)])
    ride_averages[ride] = (overall_avg, daily_averages)

# Top 10 rides
top_rides = sorted(ride_averages.items(), key=lambda x: (np.nan_to_num(x[1][0], nan=0)), reverse=True)[:10]

# Plot
x = list(range(1, last_day + 1))
x_labels = [f"{calendar.day_name[datetime.date(year, month, d).weekday()]} {d}" for d in x]
plt.figure(figsize=(18, 9))

for ride, (avg, daily_avgs) in top_rides:
    if all(np.isnan(val) for val in daily_avgs):
        continue  # Skip rides with no data at all
    safe_avg = int(round(avg)) if not np.isnan(avg) else 0
    label = f"{ride} ({safe_avg})"
    padded = daily_avgs[:last_day] + [np.nan] * (last_day - len(daily_avgs))
    plt.plot(x, padded, label=label)

plt.title(title_str)
plt.xlabel("Day of Month")
plt.ylabel("Wait Time (mins)")
plt.xticks(ticks=x, labels=x_labels, rotation=45, ha='right')
plt.legend(loc='center left', bbox_to_anchor=(1.01, 0.3))

# Add banner
response = requests.get(BANNER_URL)
if response.status_code == 200:
    banner_img = mpimg.imread(io.BytesIO(response.content), format='JPG')
    imagebox = OffsetImage(banner_img, zoom=0.15)
    ab = AnnotationBbox(imagebox, (1.15, 1.02), xycoords='axes fraction', frameon=False)
    plt.gca().add_artist(ab)

plt.tight_layout()
plt.savefig(output_filename, bbox_inches="tight")
plt.close()

# Upload to Drive
gauth = GoogleAuth()
gauth.credentials = creds
drive = GoogleDrive(gauth)

file_list = drive.ListFile({'q': f"'{DRIVE_FOLDER_ID}' in parents and trashed=false"}).GetList()
monthly_folder_id = None
for f in file_list:
    if f['title'].lower() == MONTHLY_SUBFOLDER_NAME and f['mimeType'] == 'application/vnd.google-apps.folder':
        monthly_folder_id = f['id']
        break

if not monthly_folder_id:
    raise Exception("❌ Could not find 'monthly' folder in Google Drive.")

existing_files = drive.ListFile({
    'q': f"'{monthly_folder_id}' in parents and trashed=false"
}).GetList()

for f in existing_files:
    if f['title'] == output_filename:
        f.Delete()
        break

uploaded_file = drive.CreateFile({'title': output_filename, 'parents': [{'id': monthly_folder_id}]})
uploaded_file.SetContentFile(output_filename)
uploaded_file.Upload()
uploaded_file.InsertPermission({'type': 'anyone', 'value': 'anyone', 'role': 'reader'})

embed_url = f"https://drive.google.com/uc?export=view&id={uploaded_file['id']}"
print(f"✅ Monthly chart uploaded: {output_filename}")
print(f"🔗 Embed URL: {embed_url}")
