from collections import ChainMap
import os
import requests
import json
from urllib.parse import urljoin
from dotenv import load_dotenv
import random
from typing import Union, List, Sequence, Generator, Mapping
from . import notion_filters as nf

n_headings = nf.headings


def load_env_variables():
    # check for Notion variables
    if (not "NOTION_KEY" in os.environ) and (not "NOTION_PAGE_ID" in os.environ):
        load_dotenv()
    elif (not "NOTION_KEY" in os.environ) and ("NOTION_PAGE_ID" in os.environ):
        print("Notion key doesn't exist")
    elif ("NOTION_KEY" in os.environ) and (not "NOTION_PAGE_ID" in os.environ):
        print("Notion page id doesn't exist")


class NotionClient:
    # class to deal with Notion API
    # gets notion key and page number from environment variables
    # outputs response from notion api
    # has methods for querying database and updating properties of a page in the database

    def __init__(self, notion_key):
        self.notion_key = notion_key

        self.default_headers = {
            "Authorization": f"Bearer {self.notion_key}",
            "Content-Type": "application/json",
            "Notion-Version": "2022-06-28",
        }
        self.session = requests.Session()
        self.session.headers.update(self.default_headers)
        self.NOTION_BASE_URL = "https://api.notion.com/v1/"

    def query_database(
        self, db_id, filter_object=None, sorts=None, start_cursor=None, page_size=None
    ):
        db_url = urljoin(self.NOTION_BASE_URL, f"databases/{db_id}/query")
        params = {}
        if filter_object is not None:
            params["filter"] = filter_object
        if sorts is not None:
            params["sorts"] = sorts
        if start_cursor is not None:
            params["start_cursor"] = start_cursor
        if page_size is not None:
            params["page_size"] = page_size

        return self.session.post(db_url, json=params)

    def update_page(self, page_id, properties):
        pg_url = urljoin(self.NOTION_BASE_URL, f"pages/{page_id}")

        return self.session.patch(pg_url, json=properties)

    def get_children(self, block_id):
        b_url = urljoin(self.NOTION_BASE_URL, f"blocks/{block_id}/children")
        return self.session.get(b_url)


class NotionDatabase:
    # holds notion database
    # reads in all of the pages into one class object
    # has a method that gets the length of the final database
    # Mubdi pointed out could even have a variable that stores all the previous iterations of random select
    # that way when you call it again, it would be able to compare to prev versions, and if there's repetition
    # repeat as necessary
    selected_pages = []

    def __init__(self, notion_client):
        self.notion_client = notion_client

    def load_db(self, db_id, filter_object=None):
        page_count = 1
        print(f"Loading page {page_count}")
        db_response = self.notion_client.query_database(db_id, filter_object)
        records = {}
        if db_response.ok:
            records = db_response.json()
            db_response_obj = db_response.json()

            while db_response_obj.get("has_more"):
                page_count += 1
                print(f"Loading page {page_count}")
                start_cursor = db_response_obj.get("next_cursor")
                db_response = self.notion_client.query_database(
                    db_id, filter_object, start_cursor=start_cursor
                )

                if db_response.ok:
                    records = ChainMap(records, db_response.json())
                else:
                    db_response.raise_for_status()
        else:
            # raise an error if there's something wrong
            db_response.raise_for_status()

        self.db = records
        self.db_len = len(
            self.db["results"]
        )  # calculate length every time database is loaded in

    def get_page(self, k: int) -> str:
        # input: unique integer
        # output: page ids to update
        return self.db["results"][k]["id"]

    def random_select(self, n: int, prev_pages=None, repeat_freq: int = 0):
        # randomly select indices
        # output: list of unique integer
        rep = 0
        pages = []
        i = 0
        while i < n:
            k = random.randint(0, self.db_len - 1)
            page = self.get_page(k)
            if prev_pages is not None and page in prev_pages:
                rep += 1
                if rep > repeat_freq:
                    continue
                else:
                    i += 1
                    pages.append(page)
            elif page in pages:
                continue
            else:
                i += 1
                pages.append(page)

        self.selected_pages = pages
        # self.sample = random.sample(range(0,self.db_len),k=n)

        # pages = []
        # for s in self.sample:
        #    pages.append(self.get_page(s))

        # rep = set(prev_pages) & set(pages)
        # if len(rep) > repeat_freq:
        #    diff = len(rep) - repeat_freq

        # type(self).selected_pages = pages  #store list of pages selected (in case size of database changes between calls)

    def get_selected(self, page_ind: Union[None, Sequence] = None):
        pages = []
        if page_ind == None:
            for i in range(0, self.db_len):
                pages.append(self.get_page(i))
            self.selected_pages = pages
        else:
            for p in page_ind:
                pages.append(self.get_page(p))
            self.selected_pages = pages

    def update_planned(self, properties_to_update: Mapping):
        # update planned column for specific pages in database
        # input: pages ids to update in the database
        # output: calls the NotionClient and updates the properties of each page id in the list
        for page in self.selected_pages:
            # could add this in to the random sample code so that I don't have to do a loop twice
            # but they're short loops so I'm not too worried
            errcode = self.notion_client.update_page(page, properties_to_update)

            # check that this worked
            if errcode.ok:
                continue
            else:
                print("for page id {0}".format(page))
                print(errcode)
                errcode.raise_for_status()


def remove_prev(notion_client, notion_key, notion_page_id):
    prev_recipes = NotionDatabase(notion_client)
    prev_recipes.load_db(notion_page_id, filter_object=nf.filter_prev)
    print(prev_recipes.db_len)
    if prev_recipes.db_len > 0:
        prev_recipes.get_selected()
        prev_recipes.update_planned(nf.update_prev_planned_props)
    else:
        print("no previous meal plan")
    return prev_recipes


def get_mealplan(k: int, repeat_freq: int):
    """Function that gets the previous meal plan, removes it, and selects a new meal plan."""

    load_env_variables()

    notion_key = os.environ.get("NOTION_KEY")
    notion_page_id = os.environ.get("NOTION_PAGE_ID")

    notion_client = NotionClient(notion_key)

    # remove prev meal plan
    prev_recipes = remove_prev(notion_client, notion_key, notion_page_id)

    # get new meal plan
    recipes = NotionDatabase(notion_client)
    recipes.load_db(notion_page_id, filter_object=nf.filter_ld)
    print(recipes.db_len)
    recipes.random_select(k, prev_recipes.selected_pages, repeat_freq)
    recipes.update_planned(nf.update_planned_props)


def check_ingredients(block_object):
    for i in range(0, len(block_object["results"])):
        dtype = block_object["results"][i]["type"]

        if dtype in n_headings:
            header = block_object["results"][i][dtype]["rich_text"][0]["plain_text"]
            if header == "Ingredients":
                r_ing = block_object["results"][i + 1 :]
            else:
                r_ing = None
        else:
            r_ing = None
    return r_ing


def iterate_block(block_result, notion_client):
    block_object = block_result.json()
    for b in block_object["results"]:
        child_ind = b.get("has_children")
        if child_ind == True:
            block_id = b.get("id")
            block_response = notion_client.get_children(block_id)
            if block_response.ok:
                iterate_block(block_response, notion_client)
            else:
                block_response.raise_for_status()
                block_object = block_response.json()
                return block_object
        elif child_ind == False:
            return block_object


def get_ingredients(page_id, notion_client):
    """Functions that gets the ingredients from a selected recipe page"""

    page_response = notion_client.get_children(page_id)

    # get block children until they don't have their own children
    if page_response.ok:
        block_object = iterate_block(page_response, notion_client)
    else:
        page_response.raise_for_status()

    # check that the block has header 'Ingredients'
    r_ing = check_ingredients(block_object)

    if r_ing is None:
        print("Couldn't find ingredients block")
        ing = None
    else:
        ing = []
        # get ingredients from list
        for r in r_ing:
            if r["type"] == "bulleted_list_item":
                ing.append(r["bulleted_list_item"]["rich_text"][0]["plain_text"])
            else:
                print("ingredients may not be in bulleted list")

    return ing


def ingredients_to_list(recipes, notion_client):
    """Function that takes the planned meals, gets ingredients for each, and condenses them into a grocery list"""

    if len(recipes.selected_pages > 0):
        ingredients = []
        for page in recipes.selected_pages:
            ing = get_ingredients(page_id, notion_client)
            ingredients.append(ing)


def post_grocery_list():
    """Function that takes grocery list and posts it to the Notion Meal Plan page"""
