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

    def append_block_children(self, block_id: str, properties: Mapping):
        ab_url = urljoin(self.NOTION_BASE_URL, f"blocks/{block_id}/children")
        return self.session.patch(ab_url, json=properties)

    def delete_block(self, block_id: str):
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

    return recipes


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
            if block_response.ok:
                block_object = block_response.json()
                if block_object["results"]:
                    self.page_contents.extend(block_object["results"])

                for b in block_object["results"]:
                    child_ind = b.get("has_children")
                    if child_ind == True:
                        new_ids.append(b.get("id"))
            else:
                block_response.raise_for_status()

        if len(new_ids) > 0:
            return self.get_content(new_ids)

    def get_ingredients(self) -> Optional[List[str]]:
        """Finds the ingredients block and returns a list of those ingredients"""
        inst = ["instructions", "directions"]
        ing_true, ing_list = self._locate_ingredients("ingredients")

        if ing_true and ing_list is not None:
            # we found an ingredients list!
            ingredients = []
            k = 0
            for ing in ing_list:
                if ing["type"] == "bulleted_list_item":
                    if len(ing["bulleted_list_item"]["rich_text"]) == 1:
                        ingredients.append(
                            ing["bulleted_list_item"]["rich_text"][0]["plain_text"]
                        )
                    elif len(ing["bulleted_list_item"]["rich_text"]) > 1:
                        # if there are multiple items in the rich text list need to iterate over them
                        words = ""
                        for rt in ing["bulleted_list_item"]["rich_text"]:
                            words += rt["plain_text"]
                        ingredients.append(words)
                elif ing["type"] in n_headings:
                    dtype = ing["type"]
                    header = ing[dtype]["rich_text"][0]["plain_text"]
                    if inst[0] in header.lower() or inst[1] in header.lower():
                        # ingredients have ended and instructions are starting
                        break
                    elif k + 1 < len(ing_list):
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
                            break
                    else:
                        # we're at the end of the list anyway
                        continue
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
                            break

                    else:
                        # we're at the end of the list anyway
                        continue
                k += 1

            return ingredients
        else:
            # there are no ingredients
            print("No ingredients list found for {0}".format(self.recipe_name))
            return None

    def _locate_ingredients(self, title: str) -> tuple[bool, Optional[Mapping]]:
        i = 0
        ing_true = False
        ing_list = None

        if len(self.page_contents) >= 1:
            while ing_true is False and i < len(self.page_contents):
                dtype = self.page_contents[i]["type"]
                if dtype in n_headings:
                    header = self.page_contents[i][dtype]["rich_text"][0]["plain_text"]
                    if header.lower() == title:
                        # then the ingredients are in the blocks after this
                        ing_list = self.page_contents[i + 1 :]
                        ing_true = True
                i += 1

        return (ing_true, ing_list)

    def get_prev_todo_ids(self):
        todo_true, todo_list = self._locate_ingredients("grocery list")

        block_ids = []
        if todo_true:
            for block in todo_list:
                block_ids.append(block["id"])

        return block_ids


def get_full_ingred_list(recipes, notion_client) -> Optional[List[str]]:
    """Function that takes planned meals and gets a list of ingredient sentences"""
    all_ingred = []
    if len(recipes.selected_pages) > 0:
        all_ingred = []
        for page, page_name in zip(recipes.selected_pages, recipes.selected_page_names):
            n_page = NotionPage(notion_client, page_name)
            n_page.get_content([page])
            ingred = n_page.get_ingredients()
            print(ingred)
            if ingred is not None:
                all_ingred = all_ingred + ingred
    else:
        print("no recipes found")
        all_ingred = None

    return all_ingred


def ingredients_to_list(recipes, notion_client):
    """Function that takes the planned meals, gets ingredients for each, and condenses them into a grocery list"""

    all_ingred = get_full_ingred_list(recipes, notion_client)

    if all_ingred is not None:
        parsed_ingredients = parse_multiple_ingredients(all_ingred)
        ingred_dict = {"name": [], "amount": [], "unit": []}

        for p in parsed_ingredients:
            if p.name is None:
                continue

            elif p.name.confidence < 0.9:
                print(
                    "Could not parse {0} effectively, will just add as name".format(
                        p.sentence
                    )
                )
                ingred_dict["name"].append(p.sentence)
                ingred_dict["amount"].append("")
                ingred_dict["unit"].append("")

            elif p.name.text in ingred_dict["name"]:
                # add the amounts together

                # get the ingredient from the dictionary
                ind = ingred_dict["name"].index(p.name.text)

                if p.amount and ingred_dict["amount"][ind]:
                    add_ingred_together(p, ingred_dict, ind)

                else:
                    ingred_dict["amount"][ind] = "2x"

                # this should be a separate function because will have to deal with unit incompatibilities
                # probably shouldn't do it this way because will have to keep adding same ingredient?
            else:
                # add into the ingredient dictionary
                ingred_dict["name"].append(p.name.text)
                if len(p.amount) == 1:
                    ingred_dict["amount"].append(p.amount[0].quantity)
                    ingred_dict["unit"].append(p.amount[0].unit)
                elif len(p.amount) > 1:
                    print("ingredient has multiple amounts")
                    print(p.name.text)
                    print(p.amount)
                    ingred_dict["amount"].append(p.amount[0].quantity)
                    ingred_dict["unit"].append(p.amount[0].unit)
                else:
                    ingred_dict["amount"].append("")
                    ingred_dict["unit"].append("")

    else:
        ingred_dict = None

    return ingred_dict


def pluralize_unit(unit_a: str) -> str:
    """pluralizes unit to match with units.UNITS dictionary

    Parameters
    ----------
    unit_a : str
        unit

    Returns
    -------
    str
        plural
    """

    for plural, singular in units.UNITS.items():
        if unit_a == singular:
            pl = plural
            break
        elif unit_a == plural:
            pl = unit_a
            break
        else:
            pl = unit_a
            break

    return pl


def get_unit_type(unit_a: str) -> str:
    """Gets unit type (currently weight, volume, or other)

    Parameters
    ----------
    unit_a : str
        unit

    Returns
    -------
    str
        unit type
    """
    if unit_a in units.WEIGHT:
        return "weight"
    elif unit_a in units.VOLUME:
        return "volume"
    else:
        return "other"


def convert_and_add_ingred(
    unit_a: str, unit_b: str, ingred, ingred_dict: Mapping, i: int
) -> tuple[str, str]:
    """Function that converts one unit to another if they are of compatible types

    Parameters
    ----------
    unit_a : str
        unit to be converted
    unit_b : str
        unit to match
    ingred : _type_
        ingredient to be converted
    ingred_dict : Mapping
        ingredient dictionary to be modified
    i : int
        index of ingredient to be added to

    Returns
    -------
    tuple[str, str]
        new_amount: quantity of ingredient
        new_unit: unit (or units) of that quantity
    """

    unit_a_type = get_unit_type(unit_a)
    unit_b_type = get_unit_type(unit_b)

    try:
        amount_a = float(ingred.amount[0].quantity)
        amount_b = float(ingred_dict["amount"][i])
    except:
        # amounts not convertible
        new_amount = "{0} + {1}".format(
            ingred.amount[0].quantity, ingred_dict["amount"][i]
        )
        new_unit = "{0} + {1}".format(unit_a, unit_b)
        return (new_amount, new_unit)

    if unit_a_type == "other" or unit_b_type == "other":
        new_amount = "{0} + {1}".format(amount_a, amount_b)
        new_unit = "{0} + {1}".format(unit_a, unit_b)

    elif unit_a_type == "weight" and unit_b_type == "weight":
        ind_a = units.WEIGHT.index(unit_a)
        ind_b = units.WEIGHT.index(unit_b)

        conv = units.W_CONVERSIONS[ind_a, ind_b]

        # get new amount
        amount_a = amount_a * conv
        new_amount = amount_a + amount_b
        new_unit = unit_b

    elif unit_a_type == "volume" and unit_b_type == "volume":
        ind_a = units.VOLUME.index(unit_a)
        ind_b = units.VOLUME.index(unit_b)

        conv = units.V_CONVERSIONS[ind_a, ind_b]

        # get new amount
        amount_a = amount_a * conv
        new_amount = amount_a + amount_b
        new_unit = unit_b

    elif unit_b_type != unit_a_type:
        # convert unit a to unit b
        print("units are not convertible")
        new_amount = "{0} + {1}".format(amount_a, amount_b)
        new_unit = "{0} + {1}".format(unit_a, unit_b)

    else:
        print("something wrong")
        print(unit_b_type, unit_a_type)
        new_amount = "{0} + {1}".format(amount_a, amount_b)
        new_unit = "{0} + {1}".format(unit_a, unit_b)

    return (new_amount, new_unit)


def add_amounts(amount_a, amount_b):
    try:
        new_amount = float(amount_a) + float(amount_b)
    except:
        # if one of the amounts can't be converted, can't add together
        new_amount = "{0} and {1}".format(amount_a, amount_b)

    return new_amount


def add_ingred_together(ingred, ingred_dict: Mapping, i: int) -> Mapping:
    """function that takes two instances of the same ingredient and adds them together if their units are compatible

    Parameters
    ----------
    ingred : _type_
        ingredient to add
    ingred_dict : Mapping
        dictionary of previously added ingredients
    i : int
        index of the current ingredient

    Returns
    -------
    Mapping
        Dictionary of ingredient name, amount and unit
    """
    unit_a = ingred.amount[0].unit
    unit_b = ingred_dict["unit"][i]

    # check if units are the same
    if not unit_a:
        if not ingred.amount[0].quantity:
            new_amount = "{0} and 1x".format(ingred_dict["amount"][i])
        else:
            new_amount = "{0} and {1}".format(
                ingred.amount[0].quantity, ingred_dict["amount"][i]
            )
        new_unit = unit_b
    elif not unit_b:
        if not ingred_dict["amount"][i]:
            new_amount = "{0} and 1x".format(ingred.amount[0].quantity)
        else:
            new_amount = "{0} and {1}".format(
                ingred.amount[0].quantity, ingred_dict["amount"][i]
            )
        new_unit = unit_a
    elif unit_b == unit_a:
        # just add them together
        new_amount = add_amounts(ingred.amount[0].quantity, ingred_dict["amount"][i])
        new_unit = unit_b
    else:
        if unit_a[-1] == "s":
            # check if units are plural
            if units.UNITS[unit_a] == unit_b:
                print("unit a is pluralized")
                new_amount = add_amounts(
                    ingred.amount[0].quantity, ingred_dict["amount"][i]
                )
                new_unit = unit_a
            else:
                # units don't match
                # pluralize units
                unit_b = pluralize_unit(unit_b)
                # check amounts can be converted

                new_amount, new_unit = convert_and_add_ingred(
                    unit_a, unit_b, ingred, ingred_dict, i
                )

        elif unit_b[-1] == "s":
            if units.UNITS[unit_b] == unit_a:
                print("unit b is pluralized")
                new_amount = add_amounts(
                    ingred.amount[0].quantity, ingred_dict["amount"][i]
                )
                new_unit = unit_b
            else:
                # units don't match
                unit_a = pluralize_unit(unit_a)
                new_amount, new_unit = convert_and_add_ingred(
                    unit_a, unit_b, ingred, ingred_dict, i
                )
        else:
            # units don't match
            new_amount, new_unit = convert_and_add_ingred(
                unit_a, unit_b, ingred, ingred_dict, i
            )

    # add the new values to the dictionary
    ingred_dict["amount"][i] = new_amount
    ingred_dict["unit"][i] = new_unit

    return ingred_dict


def convert_dict_to_notion_todo(ingred_dict):
    new_blocks = {"children": []}

    for i in range(len(ingred_dict["name"])):
        f_ing = "{0} {1} {2}".format(
            ingred_dict["amount"][i], ingred_dict["unit"][i], ingred_dict["name"][i]
        )

        null = None
        format_block = {
            "object": "block",
            "type": "to_do",
            "to_do": {
                "rich_text": [
                    {"type": "text", "text": {"content": f_ing, "link": null}}
                ],
                "checked": False,
                "color": "default",
            },
        }

        new_blocks["children"].append(format_block)

    return new_blocks


def post_grocery_list(recipes, notion_client):
    """Function that takes grocery list and posts it to the Notion Meal Plan page"""

    if len(recipes.selected_pages) > 0:
        NOTION_MP_ID = os.environ.get("NOTION_MP_ID")

        # remove old list first
        grocery_page = NotionPage(notion_client, "Meal Plan and Grocery List")
        grocery_page.get_content([NOTION_MP_ID])
        block_ids = grocery_page.get_prev_todo_ids()

        if block_ids:
            for b in block_ids:
                notion_client.delete_block(b)

        ingred_dict = ingredients_to_list(recipes, notion_client)

        # convert to appropriate json
        new_blocks = convert_dict_to_notion_todo(ingred_dict)

        try:
            notion_client.append_block_children(NOTION_MP_ID, new_blocks)
        except:
            print("error updating grocery list")

    else:
        print("There are no selected recipes")
