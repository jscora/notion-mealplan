import os
from typing import Union, List, Sequence, Generator, Mapping, Optional
from ingredient_parser import parse_multiple_ingredients
from . import notion_filters as nf
from . import units as units

n_headings = nf.headings


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
        """Finds the ingredients block and returns a list of those ingredients.

        Returns
        -------
        Optional[List[str]]
            Returns list of rich_text items in bulleted list blocks
        """
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

    def _locate_ingredients(self, title: str) -> tuple[bool, Optional[List]]:
        """Function to check if there are ingredients on this page

        Parameters
        ----------
        title : str
            name of page

        Returns
        -------
        tuple[bool, Optional[List]]
            ing_true: True if the ingredients header exists
            ing_list: returns a list of blocks after the ingredients header if found
        """
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

    def get_prev_todo_ids(self) -> Sequence:
        """Function to get todo items after 'Grocery List' heading on Notion Mealplan page

        Returns
        -------
        Sequence
            block_ids: the ids of all the blocks after 'Grocery List'
        """
        todo_true, todo_list = self._locate_ingredients("grocery list")

        block_ids = []
        if todo_true and todo_list:
            for block in todo_list:
                block_ids.append(block["id"])

        return block_ids


def get_full_ingred_list(recipes, notion_client) -> Optional[List[str]]:
    """Function that takes planned meals and gets a list of ingredient sentences

    Parameters
    ----------
    recipes : _type_
        an instance of NotionDatabase class with the recipes for the new meal plan
    notion_client : _type_
        an instance of the NotionClient class

    Returns
    -------
    all_ingred: Optional[List[str]]
        if ingredients are found for any of the pages, returns list of all ingredients
    """

    if recipes.selected_pages:
        all_ingred = []
        for page, page_name in zip(recipes.selected_pages, recipes.selected_page_names):
            n_page = NotionPage(notion_client, page_name)
            n_page.get_content([page])
            ingred = n_page.get_ingredients()

            if ingred is not None:
                all_ingred = all_ingred + ingred
    else:
        print("no recipes found")
        all_ingred = None

    return all_ingred


def ingredients_to_list(recipes, notion_client) -> Optional[Mapping]:
    """Function that takes the planned meals, gets ingredients for each, and condenses them into a grocery list

    Parameters
    ----------
    recipes : _type_
        An instance of the NotionDatabase class with current recipes in it
    notion_client : _type_
        An instance of the NotionClient class

    Returns
    -------
    ingred_dict: Optional[Mapping]
        A dictionary with the final ingredient name, amount and units, with no duplicates
    """

    all_ingred = get_full_ingred_list(recipes, notion_client)

    if all_ingred is not None:
        parsed_ingredients = parse_multiple_ingredients(all_ingred)
        ingred_dict = {"name": [], "amount": [], "unit": []}

        for p in parsed_ingredients:
            if p.name is None:
                continue

            elif p.name.confidence < 0.9:
                # ingredient likely not parsed correctly, just add as is
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
                    # pick the amount with the highest confidence
                    prev_conf = 0
                    amount = None
                    for a in p.amount:
                        if a.confidence > prev_conf:
                            amount = a
                            prev_conf = a.confidence
                    if amount is not None:
                        ingred_dict["amount"].append(amount.quantity)
                        ingred_dict["unit"].append(amount.unit)
                    else:
                        print("amount confidence less than 0 for {0}".format(p.amount))
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
    pl = "None"
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

    # if units are convertible, continue to add them together
    if unit_a_type == "other" or unit_b_type == "other":
        # if not volume or weight, can't convert
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


def add_amounts(amount_a: str, amount_b: str) -> Union[str, float]:
    """Function that adds two amounts together

    Parameters
    ----------
    amount_a : str
        amount of a
    amount_b : str
        amount of b

    Returns
    -------
    Union[str, float]
        returns either a float of the two added together or a string if not convertible to float
    """
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


def convert_dict_to_notion_todo(ingred_dict: Mapping) -> Mapping:
    """Function that converts ingredient dictionary into notion page update format

    Parameters
    ----------
    ingred_dict : Mapping
        Dictionary of ingredient name, amount, and unit

    Returns
    -------
    Mapping
        Dictionary to be converted to json of each ingredient as a to-do block
    """
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
    """Function that removes any old grocery list and posts new grocery list to Notion

    Parameters
    ----------
    recipes :
        An instance of the NotionDatabase class
    notion_client :
        An instance of the NotionClient class
    """

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

        if ingred_dict is not None:
            # convert to appropriate json
            new_blocks = convert_dict_to_notion_todo(ingred_dict)

            try:
                notion_client.append_block_children(NOTION_MP_ID, new_blocks)

                print("Updated grocery list")
            except:
                print("error updating grocery list")
        else:
            print("No ingredients were found")

    else:
        print("There are no selected recipes")
