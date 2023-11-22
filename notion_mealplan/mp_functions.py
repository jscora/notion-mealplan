from collections import ChainMap
import os
import requests
import json
from urllib.parse import urljoin
from dotenv import load_dotenv
import random 
from typing import Union, List, Sequence, Generator, Mapping


#preformatted calls for the API
planned_properties = {
    "properties": {
            "Planned this week": { "checkbox": True }
    }
        }

unplanned_properties = {
    "properties": {
            "Planned this week": { "checkbox": False }
    }
}

filter_prev = {
    "property": "Planned this week",
    "checkbox": {
        "equals": True
    }
}

filter_ld = {
    "property": "Dish",
    "multi_select": {
        "contains": "Lunch/Dinner"
    }
}

def load_env_variables():
    #check for Notion variables
    if (not "NOTION_KEY" in os.environ) and (not "NOTION_PAGE_ID" in os.environ):
        load_dotenv()
    elif (not "NOTION_KEY" in os.environ) and ("NOTION_PAGE_ID" in os.environ):
        print("Notion key doesn't exist")
    elif ("NOTION_KEY" in os.environ) and (not "NOTION_PAGE_ID" in os.environ):
        print("Notion page id doesn't exist")
    

class NotionClient():
    #class to deal with Notion API
    #gets notion key and page number from environment variables
    #outputs response from notion api
    #has methods for querying database and updating properties of a page in the database

    def __init__(self,notion_key):
        self.notion_key = notion_key
        self.default_headers = {'Authorization': f"Bearer {self.notion_key}",
                                'Content-Type': 'application/json', 'Notion-Version': '2022-06-28'}
        self.session = requests.Session()
        self.session.headers.update(self.default_headers)
        self.NOTION_BASE_URL = "https://api.notion.com/v1/"


    def query_database(self, db_id, filter_object=None, sorts=None, start_cursor=None, page_size=None):
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
    
    def update_page(self,page_id,properties):
        pg_url = urljoin(self.NOTION_BASE_URL,f"pages/{page_id}")
        
        return self.session.patch(pg_url, json=properties)
        #method to update a page in Notion
        #properties would have to be a dict of property names and values



class NotionDatabase():
    
    #holds notion database
    #reads in all of the pages into one class object
    #has a method that gets the length of the final database
    #Mubdi pointed out could even have a variable that stores all the previous iterations of random select
    #that way when you call it again, it would be able to compare to prev versions, and if there's repetition 
    #repeat as necessary 
    selected_pages = []
    def __init__(self,notion_client):
        self.notion_client = notion_client

    def load_db(self,db_id,filter_object=None):
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
                db_response = self.notion_client.query_database(db_id, filter_object, start_cursor=start_cursor)
                
                if db_response.ok:
                    records = ChainMap(records,db_response.json())
        
        self.db = records
        self.db_len = len(self.db['results']) #calculate length every time database is loaded in 
        


    def get_page(self,k:int) -> str:
        #input: list of unique integers
        #output: page ids to update (again, could be done in NotionDatabase as a method?)
        return(self.db['results'][k]['id'])

    def random_select(self,n:int,prev_pages=None,repeat_freq: int=0):
        #randomly select indices
        #input: length of database
        #output: list of unique integer
        
        self.sample = random.sample(range(0,self.db_len),k=n)
        pages = []
        for s in self.sample:
            pages.append(self.get_page(s))

        type(self).selected_pages = pages  #store list of pages selected (in case size of database changes between calls)

    def get_selected(self):
        pages = []
        for i in range(0,self.db_len):
            pages.append(self.get_page(i))
        type(self).selected_pages = pages

    def update_planned(self,properties_to_update: Mapping):

        #update planned column for specific pages in database 
        #input: pages ids to update in the database
        #output: calls the NotionClient and updates the properties of each page id in the list
        for page in self.selected_pages:
            #could add this in to the random sample code so that I don't have to do a loop twice
            #but they're short loops so I'm not too worried
            errcode = self.notion_client.update_page(page,properties_to_update)

            #check that this worked
            if errcode.ok:
                continue
            else:
                print('for page id {0}'.format(page))
                print(errcode)

def get_mealplan(k:int,repeat_freq:int):

    load_env_variables()

    notion_key = os.environ.get("NOTION_KEY")
    notion_page_id = os.environ.get("NOTION_PAGE_ID")

    notion_client = NotionClient(notion_key)

    #remove prev meal plan -- should this be its own function?
    prev_recipes = NotionDatabase(notion_client)
    prev_recipes.load_db(notion_page_id,filter_object = filter_prev)
    print(prev_recipes.db_len)
    if prev_recipes.db_len > 0:
        prev_recipes.get_selected()
        prev_recipes.update_planned(unplanned_properties)
    else:
        print("no previous meal plan")
    
    #get new meal plan
    recipes = NotionDatabase(notion_client)
    recipes.load_db(notion_page_id)
    print(recipes.db_len)
    recipes.random_select(k,prev_recipes.selected_pages,repeat_freq)
    recipes.update_planned(planned_properties)