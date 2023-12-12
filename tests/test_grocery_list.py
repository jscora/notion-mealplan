from notion_mealplan import grocery_list as groc
from notion_mealplan import mp_functions as mp
import os
import pytest
from typing import Tuple, List
import requests
from ingredient_parser import parse_ingredient

filter_prev = {"property": "Planned this week", "checkbox": {"equals": True}}
filter_b = {"property": "Dish", "multi_select": {"contains": "Breakfast"}}
filter_bad = {"property": "Fish", "multi_select": {"contains": "Elevensies"}}

update_planned_props = {"properties": {"Planned this week": {"checkbox": True}}}
update_prev_planned_props = {"properties": {"Planned this week": {"checkbox": False}}}


@pytest.fixture
def client(notion_keys):
    return mp.NotionClient(notion_keys[0])


@pytest.fixture
def loaded_database(client, notion_keys):
    db = mp.NotionDatabase(client)

    def _loaded_database(filter):
        db.load_db(notion_keys[1], filter)
        return db

    return _loaded_database


@pytest.fixture(scope="session")
def notion_keys() -> Tuple[str, str]:
    mp.load_env_variables()
    notion_key = os.environ["NOTION_KEY"]
    notion_page_id = os.environ["NOTION_PAGE_ID"]

    return (notion_key, notion_page_id)


def test_get_ingredients(client):
    """Function that tests the get_ingredients function"""
    page_id = "52003476-fc7c-470b-9b22-886246f0c14e"

    n_page = groc.NotionPage(client, "zoodles")
    n_page.get_content([page_id])

    assert len(n_page.page_contents) > 0

    ingredients = n_page.get_ingredients()

    assert ingredients is not None
    assert len(ingredients) > 0


def test_ingredients_to_list(client, loaded_database):
    """Function to test the ingredients_to_list_function"""
    prev_db = loaded_database(filter_b)
    prev_db.get_selected()

    parsed_ingredients = groc.ingredients_to_list(prev_db, client)

    assert parsed_ingredients is not None
    assert len(parsed_ingredients) > 0


def test_convert_and_add_ingred():
    """Function that tests unit conversion and addition"""

    test_ingred = "4 tablespoons of sugar"
    p_ingred = parse_ingredient(test_ingred)
    ingred_dict = {
        "name": ["flour", "sugar"],
        "amount": ["2", "1/4"],
        "unit": ["cups", "cups"],
    }

    unit_a = p_ingred.amount[0].unit
    unit_b = ingred_dict["unit"][1]

    new_amount, new_unit = groc.convert_and_add_ingred(
        unit_a, unit_b, p_ingred, ingred_dict, 1
    )

    assert new_amount == 0.5
    assert new_unit == "cups"


@pytest.mark.skip
def test_post_grocery_list(client, loaded_database):
    """Function to test that grocery list is posted"""

    prev_db = loaded_database(filter_b)
    prev_db.get_selected()
    groc.post_grocery_list(prev_db, client)

    # one way to turn into proper test is to then call function to remove blocks
    # test that the number of blocks to remove is more than 0
