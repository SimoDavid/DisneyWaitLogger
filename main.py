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
    MINUTE = NOW.minute

    SHEET_NAME_TEMPLATE = f'TokyoDisneyWaitTimes-{YEAR_MONTH}'
    DAY_TAB_NAME = DAY

    # 15-minute column headers (8:00 to 23:45)
    headers = ['Park', 'Attraction Name']
    time_slots = [
        f"{hour}:{minute:02d}" for hour in range(8, 24)
        for minute in range(0, 60, 15)
    ]
    headers.extend(time_slots)

    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/drive"
    ]

    creds_json = os.getenv('GOOGLE_APPLICATION_CREDENTIALS_JSON')
    if creds_json is None:
        raise Exception("Missing GOOGLE_APPLICATION_CREDENTIALS_JSON environment variable.")
    
    creds = ServiceAccountCredentials.from_json_keyfile_dict(json.loads(creds_json), scope)
    client = gspread.authorize(creds)

    # Define known parks
    PARK_IDS = {
        "3cc919f1-d16d-43e0-8c3f-1dd269bd1a42": "Tokyo Disneyland",
        "67b290d5-3478-4f23-b601-2f8fb71ba803": "Tokyo DisneySea"
    }

    # Open or create the spreadsheet
    try:
        sheet = client.open(SHEET_NAME_TEMPLATE)
    except gspread.SpreadsheetNotFound:
        sheet = client.create(SHEET_NAME_TEMPLATE)
        sheet.share('davidsimpson716@gmail.com', perm_type='user', role='writer')

    # Open or create the daily worksheet tab
    try:
        worksheet = sheet.worksheet(DAY_TAB_NAME)
    except gspread.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=DAY_TAB_NAME, rows="500", cols=str(len(headers)))
        worksheet.update([headers], range_name='A1')  # Corrected syntax

        # Freeze top row and first two columns
        sheet.batch_update({
            "requests": [
                {
                    "updateSheetProperties": {
                        "properties": {
                            "sheetId": worksheet._properties['sheetId'],
                            "gridProperties": {
                                "frozenRowCount": 1,
                                "frozenColumnCount": 2
                            }
                        },
                        "fields": "gridProperties.frozenRowCount,gridProperties.frozenColumnCount"
                    }
                }
            ]
        })

        # Style first row
        worksheet.format("1:1", {
            "textFormat": {"bold": True},
            "horizontalAlignment": "CENTER",
            "backgroundColor": {"red": 1.0, "green": 0.8, "blue": 0.8}
        })

    # Fetch live data from both parks
    LIVE_URLS = [
        'https://api.themeparks.wiki/v1/entity/faff60df-c766-4470-8adb-dee78e813f42/live',
        'https://api.themeparks.wiki/v1/entity/7340550e-c14d-4213-8b8c-5b5b987f973e/live'
    ]

    all_attractions = []

    for url in LIVE_URLS:
        response = requests.get(url)
        if response.status_code == 200:
            park_data = response.json()
            for ride in park_data.get('liveData', []):
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

    worksheet.update(park_ride_rows, range_name=f'A{start_row}:B{end_row}')

    # Don't log wait times if outside operating hours
    if HOUR < 8 or HOUR >= 24:
        return 'Outside of Tokyo Disney opening hours. No update made.', 200

    # Compute column index based on 15-minute intervals from 8:00 AM
    total_minutes = (HOUR - 8) * 60 + MINUTE
    column_index = 2 + (total_minutes // 15)  # Offset for first 2 columns
    column_letter = chr(ord('A') + (column_index % 26))
    if column_index >= 26:
        prefix = chr(ord('A') + ((column_index - 26) // 26))
        column_letter = prefix + column_letter

    wait_times = []
    for attraction in all_attractions_sorted:
        wait_time = attraction['waitTime']
        wait_times.append(['' if wait_time in (0, None) else wait_time])

    worksheet.update(wait_times, range_name=f'{column_letter}{start_row}:{column_letter}{end_row}')

    return f"✅ Updated {len(park_ride_rows)} rides at {NOW.strftime('%Y-%m-%d %H:%M:%S')} Tokyo time.", 200

if __name__ == "__main__":
    disney_wait_logger()
