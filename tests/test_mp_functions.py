from notion_mealplan import mp_functions as mp
import os
import pytest
from typing import Tuple, List
import requests

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


@pytest.fixture
def bad_keys() -> Tuple[str, str]:
    return ("123a", "543b")


@pytest.fixture(scope="session")
def notion_keys() -> Tuple[str, str]:
    mp.load_env_variables()
    notion_key = os.environ["NOTION_KEY"]
    notion_page_id = os.environ["NOTION_PAGE_ID"]

    return (notion_key, notion_page_id)


def test_make_client_class(notion_keys):
    """Class to test creation of the Notion Client"""

    n_key, n_page_id = notion_keys

    notion_client = mp.NotionClient(n_key)

    assert notion_client.notion_key == n_key
    assert isinstance(notion_client.session, requests.Session)
    assert "Authorization" in notion_client.session.headers


def test_load_env_variables():
    # it doesn't have input
    # so test that the relevant environment variables exists post-run?
    mp.load_env_variables()

    assert "NOTION_KEY" in os.environ and "NOTION_PAGE_ID" in os.environ
    # is there a way to test that these both exist and aren't empty?


def test_loaddb(loaded_database):
    """Test that database is loaded in correctly and is not empty"""
    l_db = loaded_database(None)
    assert l_db.db_len > 0
    assert "results" in l_db.db

    # check that pages in database have planned this week parameter
    assert "Planned this week" in l_db.db["results"][0]["properties"]


@pytest.mark.xfail
def test_bad_load_db(loaded_database):
    # check response when database is empty?
    # or check what happens when you try to load in with bad keys?
    # not sure what to do here
    # also should test that it fails when a bad filter is given?
    l_db = loaded_database(filter_bad)


def test_get_page(loaded_database):
    """Function to test that get_page works"""

    l_db = loaded_database(None)
    page, page_name = l_db.get_page(0)

    assert isinstance(page, str)
    assert isinstance(page_name, str)


def test_random_select(loaded_database):
    """Function to test that NotionDatabase.random_select works properly"""
    num = 5
    l_db = loaded_database(None)
    l_db.random_select(num)
    l_pages = len(l_db.selected_pages)

    assert l_pages == num
    assert len(set(l_db.selected_pages)) == l_pages

    # test repetition frequency
    prev_pages = l_db.selected_pages
    l_db.random_select(num, prev_pages, 2)

    l_pages_n = len(l_db.selected_pages)
    pages_added = prev_pages + l_db.selected_pages
    assert l_pages_n == num
    assert len(set(pages_added)) >= len(pages_added) - 2


def test_get_selected(loaded_database):
    """Function that tests that get_selected works properly"""
    l_db = loaded_database(filter_b)
    l_db.get_selected()

    assert len(l_db.selected_pages) == l_db.db_len
    assert l_db.db["results"][0]["id"] == l_db.selected_pages[0]


def test_update_planned_and_remove(loaded_database):
    """Function that checks that update_planned works, and then removes planned recipes from database"""
    # get planned meals from database and remove
    prev_db = loaded_database(filter_prev)
    if prev_db.db_len > 0:
        prev_db.get_selected()
        prev_db.update_planned(update_prev_planned_props)

    # select random meals
    l_db = loaded_database(None)
    l_db.random_select(2)
    l_db.update_planned(update_planned_props)

    # check that they exist
    prev_db2 = loaded_database(filter_prev)

    assert len(l_db.selected_pages) == prev_db2.db_len

    prev_db2.get_selected()
    prev_db2.update_planned(update_prev_planned_props)

    # re-add the meals that were planned before?


def test_remove_prev(loaded_database, client, notion_keys):
    # how do I test this? Do I have to add a planned meal and check that it's removed?
    # this would take a long time, not sure it's necessary
    # might also want a negative test for this
    db_1 = loaded_database(filter_b)
    db_1.random_select(1)
    db_1.update_planned(update_planned_props)

    n_key, n_page_id = notion_keys
    prev_db = mp.remove_prev(client, n_key, n_page_id)

    db_2 = loaded_database(filter_prev)

    assert db_2.db_len == 0


def test_get_mealplan(notion_keys, client, loaded_database):
    """Function that checks that the meal plan is added successfully"""
    mp.get_mealplan(5, 0)

    db1 = loaded_database(filter_prev)
    assert db1.db_len == 5

    # return everything to prev (nothing planned)
    db1.get_selected()
    db1.update_planned(update_prev_planned_props)
