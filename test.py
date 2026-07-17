import sqlite3

import requests

from config import ACCESS_TOKEN, BASE_URL, MEDIA_ID

# conn = sqlite3.connect("processed.db")
# cursor = conn.cursor()

# cursor.execute("""
# SELECT name
# FROM sqlite_master
# WHERE type='table';
# """)

def get_comments():
    url = f"{BASE_URL}/{MEDIA_ID}/comments"

    params = {
        "summary": 1,
        "filter": "toplevel",
        # "fields": "id,text,username",
        "access_token": ACCESS_TOKEN,
        "limit": 10
    }

    
    response = requests.get(url, params=params, timeout=30)
    response.raise_for_status()

    data = response.json()

    for comment in data.get("data", []):
        yield comment

# print(cursor.fetchall())

if __name__ == "__main__":
    for comment in get_comments():
        print(comment)