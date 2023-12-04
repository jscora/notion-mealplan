from ast import Tuple
from collections import ChainMap
import os
from click import Option
import requests
import json
from urllib.parse import urljoin
from dotenv import load_dotenv
import random
from typing import Union, List, Sequence, Generator, Mapping, Optional
from ingredient_parser import parse_multiple_ingredients
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
    print(prev_recipes.db_len)
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
    print(recipes.db_len)
    recipes.random_select(k, prev_recipes.selected_pages, repeat_freq)
    recipes.update_planned(nf.update_planned_props)


def check_ingredients(block_object: Mapping):
    """Checks if block has 'Ingredients' header"""
    dtype = block_object["type"]

    ing_true: bool
    if dtype in n_headings:
        header = block_object[dtype]["rich_text"][0]["plain_text"]
        if header == "Ingredients":
            ing_true = True
        else:
            ing_true = False
    else:
        ing_true = False
    return ing_true


class NotionPage:
    """A class to get the contents of a Notion page and find the ingredients"""

    def __init__(self, notion_client, name: str):
        self.notion_client = notion_client
        self.page_contents = []
        self.recipe_name = name

    def get_content(self, block_ids):
        """Gets all the blocks on the page"""
        new_ids = []
        for b_id in block_ids:
            block_response = self.notion_client.get_children(b_id)
            block_object = block_response.json()
            self.page_contents.append(block_object["results"])

            for b in block_object["results"]:
                child_ind = b.get("has_children")
                if child_ind == True:
                    new_ids.append(b.get("id"))
        if len(new_ids) > 0:
            return self.get_content(new_ids)

    def get_ingredients(self):
        """Finds the ingredients block and returns a list of those ingredients"""

        ing_true, ing_list = self.locate_ingredients()

        if ing_true:
            # we found an ingredients list!
            ingredients = []
            k = 0
            for ing in ing_list:
                if ing["type"] == "bulleted_list_item":
                    ingredients.append(
                        ing["bulleted_list_item"]["rich_text"][0]["plain_text"]
                    )
                else:
                    if k + 1 < len(ing_list):
                        # check if next one isn't empty
                        type = ing_list[k + 1]["type"]
                        if type == "bulleted_list_item":
                            # there's just a gap in the list
                            continue
                        else:
                            print(
                                "Ingredients may be missing some items for {0}".format(
                                    self.recipe_name
                                )
                            )

                    else:
                        # we're at the end of the list anyway
                        continue
                k += 1

            return ingredients
        else:
            # there are no ingredients
            print("No ingredients list found for {0}".format(self.recipe_name))

    def locate_ingredients(self):
        i = 0
        ing_true = False

        while ing_true is False or i < len(self.page_contents):
            dtype = self.page_contents[i][0]["type"]
            if dtype in n_headings:
                header = self.page_contents[i][0][dtype]["rich_text"][0]["plain_text"]
                if header.lower() == "ingredients":
                    # then the blocks after are the list of ingredients
                    ing_list = self.page_contents[i][1:]
                    ing_true = True
            i += 1

        if ing_true == False:
            ing_list = None
        return (ing_true, ing_list)


def get_full_ingred_list(recipes, notion_client) -> Sequence:
    """Function that takes planned meals and gets a list of ingredient sentences"""
    all_ingred = []
    if len(recipes.selected_pages) > 0:
        all_ingred = []
        for page, page_name in zip(recipes.selected_pages, recipes.selected_page_names):
            n_page = NotionPage(notion_client, page_name)
            n_page.get_content([page])
            ingred = n_page.get_ingredients()
            print(ingred)
            all_ingred = all_ingred + ingred
    else:
        print("no recipes found")

    return all_ingred


def ingredients_to_list(recipes, notion_client):
    """Function that takes the planned meals, gets ingredients for each, and condenses them into a grocery list"""

    all_ingred = get_full_ingred_list(recipes, notion_client)

    parsed_ingredients = parse_multiple_ingredients(all_ingred)
    ingred_dict = dict.fromkeys(["name", "amount", "unit"], [])
    for p in parsed_ingredients:
        if p.name.text in ingred_dict["name"]:
            # add the amounts together

            # get the ingredient from the dictionary
            ind = ingred_dict["name"].index(p.name.text)
            add_amounts(p, ingred_dict, ind)

            # this should be a separate function because will have to deal with unit incompatibilities
            # probably shouldn't do it this way because will have to keep adding same ingredient?
        else:
            # add into the ingredient dictionary
            ingred_dict["name"].extend(p.name.text)
            if len(p.amount) > 0:
                ingred_dict["amount"].extend(p.amount.quantity)
                ingred_dict["unit"].extend(p.amount.unit)
            else:
                ingred_dict["amount"].extend(None)
                ingred_dict["unit"].extend(None)

    return ()


def pluralize_unit(unit_a: str) -> str:
    for plural, singular in unit.UNITS.items():
        if unit_a == singular:
            return plural
        elif unit_a == plural:
            return unit_a
        else:
            print("unit unchanged")
            return unit_a


def get_unit_type(unit_a: str) -> str:
    if unit_a in units.WEIGHT:
        return "weight"
    elif unit_a in units.VOLUME:
        return "volume"
    else:
        return "other"


def convert_and_add_ingred(
    unit_a: str, unit_b: str, ingred, ingred_dict: Mapping, i: int
) -> tuple[str, str]:
    unit_a_type = get_unit_type(unit_a)
    unit_b_type = get_unit_type(unit_b)

    if unit_a_type == "other" or unit_b_type == "other":
        new_amount = "{0} + {1}".format(
            ingred.amount.quantity, ingred_dict["amount"][i]
        )
        new_unit = "{0} + {1}".format(unit_a, unit_b)

    elif unit_a_type == "weight" and unit_b_type == "weight":
        ind_a = units.WEIGHT.index(unit_a)
        ind_b = units.WEIGHT.index(unit_b)

        conv = units.W_CONVERSION[ind_a, ind_b]

        # get new amount
        amount_a = ingred.amount.quantity * conv
        new_amount = amount_a + ingred_dict["amount"][i]
        new_unit = unit_b

    elif unit_a_type == "volume" and unit_b_type == "volume":
        ind_a = units.VOLUME.index(unit_a)
        ind_b = units.VOLUME.index(unit_b)

        conv = units.V_CONVERSION[ind_a, ind_b]

        # get new amount
        amount_a = ingred.amount.quantity * conv
        new_amount = amount_a + ingred_dict["amount"][i]
        new_unit = unit_b

    elif unit_b_type != unit_a_type:
        # convert unit a to unit b
        print("units are not convertible")
        new_amount = "{0} + {1}".format(
            ingred.amount.quantity, ingred_dict["amount"][i]
        )
        new_unit = "{0} + {1}".format(unit_a, unit_b)

    else:
        print("something wrong")
        print(unit_b_type, unit_a_type)
        new_amount = "{0} + {1}".format(
            ingred.amount.quantity, ingred_dict["amount"][i]
        )
        new_unit = "{0} + {1}".format(unit_a, unit_b)

    return (new_amount, new_unit)


def add_amounts(ingred, ingred_dict: Mapping, i: int) -> Mapping:
    # needs to check if units are the same
    unit_a = ingred.amount.unit
    unit_b = ingred_dict["unit"][i]

    # check if units are the same
    if unit_a == unit_b:
        # just add them together
        new_amount = ingred.amount.quantity + ingred_dict["amount"][i]
        ingred_dict["amount"][i] = new_amount
    else:
        if unit_a[-1] == "s":
            # check if units are plural
            if units.UNITS[unit_a] == unit_b:
                print("unit a is pluralized")
                new_amount = ingred.amount.quantity + ingred_dict["amount"][i]
                new_unit = unit_a
            else:
                # units don't match
                # pluralize units
                unit_b = pluralize_unit(unit_b)
                new_amount, new_unit = convert_and_add_ingred(
                    unit_a, unit_b, ingred, ingred_dict, i
                )

        elif unit_b[-1] == "s":
            if unit.UNITS[unit_b] == unit_a:
                print("unit b is pluralized")
                new_amount = ingred.amount.quantity + ingred_dict["amount"][i]
                new_unit = unit_b
            else:
                # units don't match
                unit_a = pluralize_unit(unit_a)
                new_amount, new_unit = convert_and_add_ingred(
                    unit_a, unit_b, ingred, ingred_dict, i
                )

        # add the new values to the dictionary
        ingred_dict["amount"][i] = new_amount
        ingred_dict["unit"][i] = new_unit

    return ingred_dict


def post_grocery_list():
    """Function that takes grocery list and posts it to the Notion Meal Plan page"""
