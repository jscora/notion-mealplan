from collections import ChainMap
import os
import requests
import json
from urllib.parse import urljoin
from dotenv import load_dotenv
import random
from typing import Union, List, Sequence, Generator, Mapping, Optional
from . import notion_filters as nf
from . import units as units

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

    def __init__(self, notion_key: Optional[str]):
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

    def update_page(self, page_id: str, properties: Mapping):
        pg_url = urljoin(self.NOTION_BASE_URL, f"pages/{page_id}")

        return self.session.patch(pg_url, json=properties)

    def get_children(self, block_id: str):
        b_url = urljoin(self.NOTION_BASE_URL, f"blocks/{block_id}/children")
        return self.session.get(b_url)

    def append_block_children(self, block_id: str, properties: Mapping):
        ab_url = urljoin(self.NOTION_BASE_URL, f"blocks/{block_id}/children")
        return self.session.patch(ab_url, json=properties)

    def delete_block(self, block_id: str):
        """Function that deletes blocks using Notion API

        Parameters
        ----------
        block_id : str
            id of block to be deleted

        Returns
        -------
        _type_
            _description_
        """
        d_url = urljoin(self.NOTION_BASE_URL, f"blocks/{block_id}")
        return self.session.delete(d_url)


class NotionDatabase:
    """Class that contains and performs methods on a Notion Database"""

    selected_pages = []

    def __init__(self, notion_client):
        self.notion_client = notion_client

    def load_db(self, db_id: Optional[str], filter_object=None):
        """Loads in database pages from Notion, iterating through pages if necessary

        Parameters
        ----------
        db_id : Optional[str]
            The id of the database to be read in
        filter_object : _type_, optional
            Any filter to be applied to the database, typically one of those in notion_filters, by default None
        """
        page_count = 1
        db_response = self.notion_client.query_database(db_id, filter_object)
        records = {}
        if db_response.ok:
            records = db_response.json()
            db_response_obj = db_response.json()

            while db_response_obj.get("has_more"):
                page_count += 1
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

    def get_page(self, k: int) -> tuple[str, str]:
        """Gets page name and id from the database info

        Parameters
        ----------
        k : int
            _description_

        Returns
        -------
        Tuple[str,str]
            page_id : str
                id of the page
            page_name : str
                title of the page
        """

        page_id = self.db["results"][k]["id"]
        page_name = self.db["results"][k]["properties"]["Name"]["title"][0][
            "plain_text"
        ]
        return (page_id, page_name)

    def random_select(
        self, n: int, prev_pages: Optional[Sequence] = None, repeat_freq: int = 0
    ):
        """randomly selects n unique recipes, checking against previous recipe list for repetition

        Parameters
        ----------
        n : int
            number of recipes to select
        prev_pages : Optional[Sequence], optional
            previous list of recipe ids, by default None
        repeat_freq : int, optional
            number of times that a recipe from prev_pages can appear, by default 0
        """

        rep = 0
        pages = []
        page_names = []
        i = 0
        while i < n:
            k = random.randint(0, self.db_len - 1)
            page, page_name = self.get_page(k)
            if prev_pages is not None and page in prev_pages:
                rep += 1
                if rep > repeat_freq:
                    continue
                else:
                    i += 1
                    pages.append(page)
                    page_names.append(page_name)
            elif page in pages:
                continue
            else:
                i += 1
                pages.append(page)
                page_names.append(page_name)

        self.selected_pages = pages
        self.selected_page_names = page_names

        # self.sample = random.sample(range(0,self.db_len),k=n)

        # pages = []
        # for s in self.sample:
        #    pages.append(self.get_page(s))

        # rep = set(prev_pages) & set(pages)
        # if len(rep) > repeat_freq:
        #    diff = len(rep) - repeat_freq

        # type(self).selected_pages = pages  #store list of pages selected (in case size of database changes between calls)

    def get_selected(self, page_ind: Optional[Sequence] = None):
        """Updated self.selected_pages and self.selected_page_names, either with a list of page ids or with all of the pages currently in the database results

        Parameters
        ----------
        page_ind : Optional[Sequence], optional
            list of page ids to select, by default None
        """
        pages = []
        page_names = []
        if page_ind == None:
            for i in range(0, self.db_len):
                page, page_name = self.get_page(i)
                pages.append(page)
                page_names.append(page_name)
            self.selected_pages = pages
            self.selected_page_names = page_names
        else:
            for p in page_ind:
                page, page_name = self.get_page(p)
                pages.append(page)
                page_names.append(page_name)
            self.selected_pages = pages
            self.selected_page_names = page_names

    def update_planned(self, properties_to_update: Mapping):
        """Updates pages in self.selected_pages with the parameter 'Planned this week'

        Parameters
        ----------
        properties_to_update : Mapping
            typically from the notion_filters.py
        """

        for page in self.selected_pages:
            errcode = self.notion_client.update_page(page, properties_to_update)

            # check that this worked
            if errcode.ok:
                continue
            else:
                print("for page id {0}".format(page))
                print(errcode)
                errcode.raise_for_status()


def remove_prev(
    notion_client, notion_key: Optional[str], notion_page_id: Optional[str]
):
    """_summary_

    Parameters
    ----------
    notion_client : NotionClient
        _description_
    notion_key : Optional[str]
        the personal notion key
    notion_page_id : Optional[str]
        _description_

    Returns
    -------
    NotionDatabase
        returns a database with the previously selected recipes
    """
    prev_recipes = NotionDatabase(notion_client)
    prev_recipes.load_db(notion_page_id, filter_object=nf.filter_prev)

    if prev_recipes.db_len > 0:
        prev_recipes.get_selected()
        prev_recipes.update_planned(nf.update_prev_planned_props)
    else:
        print("no previous meal plan")
    return prev_recipes


def get_mealplan(k: int, repeat_freq: int):
    """Function that gets the previous meal plan, removes it, and selects a new meal plan.

    Parameters
    ----------
    k : int
        _description_
    repeat_freq : int
        _description_
    """

    load_env_variables()

    notion_key = os.environ.get("NOTION_KEY")
    notion_page_id = os.environ.get("NOTION_PAGE_ID")
    notion_client = NotionClient(notion_key)

    # remove prev meal plan
    prev_recipes = remove_prev(notion_client, notion_key, notion_page_id)

    # get new meal plan
    recipes = NotionDatabase(notion_client)
    recipes.load_db(notion_page_id, filter_object=nf.filter_ld)
    recipes.random_select(k, prev_recipes.selected_pages, repeat_freq)
    recipes.update_planned(nf.update_planned_props)

    return recipes, notion_client
