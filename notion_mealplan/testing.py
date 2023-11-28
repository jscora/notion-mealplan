import os
import requests
import json
from urllib.parse import urljoin
from dotenv import load_dotenv
import mp_functions as mp

load_dotenv()
properties_to_update = {"properties": {"Planned this week": {"checkbox": True}}}

filter_prev = {"property": "Planned this week", "checkbox": {"equals": True}}

NOTION_KEY = os.environ.get("NOTION_KEY")
NOTION_DB_ID = os.environ.get("NOTION_PAGE_ID")
headers = {
    "Authorization": f"Bearer {NOTION_KEY}",
    "Content-Type": "application/json",
    "Notion-Version": "2022-06-28",
}
# search_params = {"filter": {"value": "page", "property": "object"}}
# search_response = requests.post(
#    f'https://api.notion.com/v1/search',
#     headers=headers)

# query_response = requests.post(
#    f'https://api.notion.com/v1/databases/{NOTION_PAGE_ID}/query',
#    headers=headers
# )

# print(len(query_response.json()['results']))
# x = query_response.json()['results'][0]['properties']['Planned this week']
# print(x)


# page_id = query_response.json()['results'][8]['id']
# response = requests.patch(f'https://api.notion.com/v1/pages/{page_id}',
#    headers=headers,json=properties_to_update)
# print(response.json())
# print(search_response.json())

# get page from notion

notion_client = mp.NotionClient(NOTION_KEY)
notion_db = mp.NotionDatabase(notion_client)
notion_db.load_db(NOTION_DB_ID, filter_prev)
notion_db.get_selected()


# get ingredients from rollup
def get_ingredients(notion_db):
    ingredients = []
    for k in notion_db.db["results"]:
        ingred_array = k["properties"]["Ingredient names"]["rollup"]["array"]
        for p in ingred_array:
            ingredients.append(p["title"][0]["plain_text"])

    return ingredients


ingredients = get_ingredients(notion_db)
print(ingredients)


page_id = notion_db.selected_pages[0]
page_response = requests.get(
    f"https://api.notion.com/v1/blocks/{page_id}/children", headers=headers
)


page_object = page_response.json()

if page_response.ok:
    for r in page_object["results"]:
        children_ind = r.get("has_children")
        if children_ind == True:
            block_id = r.get("id")
            print(block_id)
            block_response = requests.get(
                f"https://api.notion.com/v1/blocks/{block_id}/children", headers=headers
            )
            block_object = block_response.json()
            for k in block_object["results"]:
                children_ind = k.get("has_children")
                if children_ind == True:
                    child_id = k.get("id")
                    print(child_id)
                    child_response = requests.get(
                        f"https://api.notion.com/v1/blocks/{child_id}/children",
                        headers=headers,
                    )
                    # print(child_response.json())
                    results = child_response.json()["results"]
                    for i in range(0, len(results)):
                        dtype = results[i]["type"]
                        if dtype == "heading_3":
                            header = results[i]["heading_3"]["rich_text"][0][
                                "plain_text"
                            ]
                            if header == "Ingredients":
                                results_ing = results[i + 1 :]

print(results_ing)
ing = []
# get ingredients from list
for n in results_ing:
    if n["type"] == "bulleted_list_item":
        ing.append(n["bulleted_list_item"]["rich_text"][0]["plain_text"])

print(ing)
