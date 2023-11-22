from notion_mealplan import mp_functions as mp
import os

def test_load_env_variables():
    #it doesn't have input
    #so test that the relevant environment variables exists post-run?
    mp.load_env_variables()

    assert "NOTION_KEY" in os.environ and "NOTION_PAGE_ID" in os.environ

def test_make_mealplan():
    #not sure how to test this function
    #doesn't really have an output

#tests for specific class methods?