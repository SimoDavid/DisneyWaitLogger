import requests
import datetime
import pytz
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import os

def disney_wait_logger(request):
    TOKYO_TZ = pytz.timezone('Asia/Tokyo')
    NOW = datetime.datetime.now(TOKYO_TZ)
    YEAR_MONTH = NOW.strftime('%Y-%m')
    DAY = NOW.strftime('%Y-%m-%d')
    HOUR = NOW.hour

    SHEET_NAME_TEMPLATE = f'TokyoDisneyWaitTimes-{YEAR_MONTH}'
    DAY_TAB_NAME = DAY

    scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]

    creds = ServiceAccountCredentials.from_json_keyfile_name('disneywaitlogger-dac8ce422390.json', scope)
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
        worksheet = sheet.add_worksheet(title=DAY_TAB_NAME, rows="500", cols="21")
        worksheet.update([['Park', 'Attraction Name']], 'A1:B1')

    worksheet.update([[
        '8AM', '9AM', '10AM', '11AM', '12PM', '1PM', '2PM', '3PM', '4PM', '5PM', '6PM', '7PM', '8PM', '9PM', '10PM', '11PM', '12AM'
    ]], 'C1:S1')

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

    column_offset = HOUR - 8
    if column_offset < 0 or column_offset > 16:
        return 'Outside of Tokyo Disney opening hours. No update made.', 200

    column_letter = chr(ord('C') + column_offset)

    wait_times = []

    for attraction in all_attractions_sorted:
        wait_time = attraction['waitTime']
        if wait_time == 0 or wait_time is None:
            wait_times.append([''])
        else:
            wait_times.append([wait_time])

    worksheet.update(wait_times, f'{column_letter}{start_row}:{column_letter}{end_row}')

    return f"✅ Updated {len(park_ride_rows)} rides at {NOW.strftime('%Y-%m-%d %H:%M:%S')} Tokyo time.", 200
