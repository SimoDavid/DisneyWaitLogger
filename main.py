import requests
import datetime
import pytz
import gspread
import json
import os
from oauth2client.service_account import ServiceAccountCredentials

def disney_wait_logger():
    TOKYO_TZ = pytz.timezone('Asia/Tokyo')
    NOW = datetime.datetime.now(TOKYO_TZ)
    YEAR_MONTH = NOW.strftime('%Y-%m')
    DAY = NOW.strftime('%Y-%m-%d')
    HOUR = NOW.hour

    # Skip updates outside of 8AM–11:45PM Tokyo time
    if HOUR < 8 or HOUR > 23:
        return '⏳ Outside Tokyo Disney hours. No update.', 200
    MINUTE = NOW.minute

    SHEET_NAME_TEMPLATE = f'TokyoDisneyWaitTimes-{YEAR_MONTH}'
    DAY_TAB_NAME = DAY

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

    creds_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON')
    if creds_json is None:
        raise Exception("Missing GOOGLE_APPLICATION_CREDENTIALS_JSON environment variable.")
    
    creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(creds_json), scope)
    client = gspread.authorize(creds)

    PARK_IDS = {
        "3cc919f1-d16d-43e0-8c3f-1dd269bd1a42": "Tokyo Disneyland",
        "67b290d5-3478-4f23-b601-2f8fb71ba803": "Tokyo DisneySea"
    }

    try:
        sheet = client.open(SHEET_NAME_TEMPLATE)
    except gspread.SpreadsheetNotFound:
        sheet = client.create(SHEET_NAME_TEMPLATE)
    sheet.share('davidsimpson716@gmail.com', perm_type='user', role='writer')

    try:
        worksheet = sheet.worksheet(DAY_TAB_NAME)
    except gspread.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=DAY_TAB_NAME, rows="500", cols="97")
        worksheet.freeze(rows=1, cols=2)  # Freeze first row and two columns
        worksheet.update([['Park', 'Attraction Name']], 'A1:B1')

        # Create 15-min interval headers from 8:00 to 0:00 (64 columns)
        headers = []
        for h in range(8, 24):
            for m in [0, 15, 30, 45]:
                label = datetime.time(h, m).strftime('%-I:%M%p').lower().replace(':00', '')
                headers.append(label)
        worksheet.update([headers], 'C1:' + chr(ord('C') + len(headers) - 1) + '1')

    LIVE_URLS = [
        'https://api.themeparks.wiki/v1/entity/faff60df-c766-4470-8adb-dee78e813f42/live',
        'https://api.themeparks.wiki/v1/entity/7340550e-c14d-4213-8c3f-5b5b987f973e/live'
    ]

    all_attractions = []

    for url in LIVE_URLS:
        response = requests.get(url)
        if response.status_code == 200:
            park_data = response.json()
            if 'liveData' in park_data:
                for ride in park_data['liveData']:
                    park_id = ride.get('parkId')
                    park_name = PARK_IDS.get(park_id, "Unknown Park")

                    wait_time = ''
                    if ride.get('queue') and ride['queue'].get('STANDBY'):
                        wait_time = ride['queue']['STANDBY'].get('waitTime')

                    all_attractions.append({
                        'park': park_name,
                        'name': ride.get('name'),
                        'waitTime': wait_time
                    })

    all_attractions_sorted = sorted(all_attractions, key=lambda x: (x['park'], x['name']))
    park_ride_rows = [[a['park'], a['name']] for a in all_attractions_sorted]

    start_row = 2
    end_row = start_row + len(park_ride_rows) - 1
    worksheet.update(park_ride_rows, f'A{start_row}:B{end_row}')

    # Calculate 15-minute slot index (0 = 8:00AM, 1 = 8:15AM, ..., 63 = 11:45PM)
    if HOUR < 8 or HOUR >= 24:
        return 'Outside of Tokyo Disney logging window.', 200

    quarter_hour_index = (HOUR - 8) * 4 + (MINUTE // 15)
    if quarter_hour_index < 0 or quarter_hour_index >= 64:
        return 'Outside of scheduled logging intervals.', 200

    column_letter = chr(ord('C') + quarter_hour_index)
    wait_times = []

    for attraction in all_attractions_sorted:
        wait_time = attraction['waitTime']
        wait_times.append(['' if wait_time in [None, 0] else wait_time])

    worksheet.update(wait_times, f'{column_letter}{start_row}:{column_letter}{end_row}')

    return f"✅ Updated {len(park_ride_rows)} rides at {NOW.strftime('%Y-%m-%d %H:%M:%S')} Tokyo time.", 200

if __name__ == "__main__":
    disney_wait_logger()
