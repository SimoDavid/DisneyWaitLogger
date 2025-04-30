import requests
import datetime
import pytz
import gspread
import json
import os
from oauth2client.service_account import ServiceAccountCredentials

def get_column_letter(n):
    result = ''
    while n > 0:
        n, remainder = divmod(n - 1, 26)
        result = chr(65 + remainder) + result
    return result

def disney_wait_logger():
    TOKYO_TZ = pytz.timezone('Asia/Tokyo')
    now = datetime.datetime.now(TOKYO_TZ)
    year_month = now.strftime('%Y-%m')
    day = now.strftime('%Y-%m-%d')

    sheet_name = f'TokyoDisneyWaitTimes-{year_month}'
    tab_name = day

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
        sheet = client.open(sheet_name)
    except gspread.SpreadsheetNotFound:
        sheet = client.create(sheet_name)
    sheet.share('davidsimpson716@gmail.com', perm_type='user', role='writer')

    try:
        worksheet = sheet.worksheet(tab_name)
    except gspread.WorksheetNotFound:
        worksheet = sheet.add_worksheet(title=tab_name, rows="500", cols="100")
        worksheet.update('A1:B1', [['Park', 'Attraction Name']])
        
        # 64 time slots from 8:00 AM to midnight in 15-minute increments
        time_headers = [(datetime.datetime(2000, 1, 1, 8) + datetime.timedelta(minutes=15*i)).strftime('%-I:%M %p') for i in range(64)]
        worksheet.update(f'C1:{get_column_letter(2 + len(time_headers))}1', [time_headers])

        # Freeze headers
        sheet.batch_update({
            "requests": [{
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
            }]
        })

        # Style header row: red, bold, centered
        worksheet.format("1:1", {
            "textFormat": {
                "bold": True,
                "foregroundColor": {"red": 1.0, "green": 0.0, "blue": 0.0}
            },
            "horizontalAlignment": "CENTER"
        })

    LIVE_URLS = [
        'https://api.themeparks.wiki/v1/entity/faff60df-c766-4470-8adb-dee78e813f42/live',
        'https://api.themeparks.wiki/v1/entity/7340550e-c14d-4213-8b8c-5b5b987f973e/live'
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
                    wait_time = ride.get('queue', {}).get('STANDBY', {}).get('waitTime', '')
                    all_attractions.append({
                        'park': park_name,
                        'name': ride.get('name'),
                        'waitTime': wait_time
                    })

    all_attractions_sorted = sorted(all_attractions, key=lambda x: (x['park'], x['name']))
    ride_rows = [[a['park'], a['name']] for a in all_attractions_sorted]

    start_row = 2
    end_row = start_row + len(ride_rows) - 1
    worksheet.update(f'A{start_row}:B{end_row}', ride_rows)

    # Calculate current column (15-minute blocks starting from 8:00 AM JST)
    minutes_since_open = (now.hour * 60 + now.minute) - (8 * 60)
    if minutes_since_open < 0 or minutes_since_open >= 960:
        return '⏱️ Outside Tokyo Disney hours. No update.', 200

    column_index = 3 + minutes_since_open // 15  # column C is index 3
    column_letter = get_column_letter(column_index)

    wait_times = [[a['waitTime'] if a['waitTime'] else ''] for a in all_attractions_sorted]
    worksheet.update(f'{column_letter}{start_row}:{column_letter}{end_row}', wait_times)

    return f"✅ Updated {len(ride_rows)} rides at {now.strftime('%Y-%m-%d %H:%M:%S')} JST.", 200

if __name__ == "__main__":
    disney_wait_logger()
