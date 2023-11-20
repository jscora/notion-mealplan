import os
import requests
import json
from urllib.parse import urljoin
from dotenv import load_dotenv

load_dotenv()
properties_to_update = {
    "properties": {
            "Planned this week": { "checkbox": True }
    }
        }


NOTION_KEY = os.environ.get("NOTION_KEY")
NOTION_PAGE_ID = os.environ.get("NOTION_PAGE_ID")
headers = {'Authorization': f"Bearer {NOTION_KEY}", 
           'Content-Type': 'application/json', 
           'Notion-Version': '2022-06-28'}
search_params = {"filter": {"value": "page", "property": "object"}}
search_response = requests.post(
    f'https://api.notion.com/v1/search', 
     headers=headers)

query_response = requests.post(
    f'https://api.notion.com/v1/databases/{NOTION_PAGE_ID}/query',
    headers=headers
)

print(len(query_response.json()['results']))
x = query_response.json()['results'][0]['properties']['Planned this week']
print(x)


#page_id = query_response.json()['results'][8]['id']
#response = requests.patch(f'https://api.notion.com/v1/pages/{page_id}',
#    headers=headers,json=properties_to_update)
#print(response.json())
#print(search_response.json())