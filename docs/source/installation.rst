Installation and Setup
======================

Installing the Notion Mealplan Generator
----------------------------------------

1. Go to the `github page <https://github.com/jscora/notion-mealplan>`
2. On the right hand panel, under ``Releases``, download the latest version.
3. Extract the tar file in the directory where you want to run the code
4. Enter the ``notion-mealplan`` directory and run ``poetry install``. (If you don't have ``poetry``, first install it by running ``pip install poetry``).


Setting up the Mealplan Integration
-----------------------------------

To use this code, you have to set up a Notion integration using the `Notion Meal Plan Template <https://www.notion.so/Notion-Meal-Plan-Template-7a32297464554b5eb62da44732336c9c?pvs=4>`. 
First, go to this link and copy the page to your own Notion space, and change the title as desired. Then you create a new integration, with whatever title you would like. 
You then must navigate back to the page you copied, and click on the three dots on the top right, and scroll down to the ``add connections`` button. 
From there, you will be able to select your integration from the list of available ones, or search for it if it is not shown. You have to do this for both the database page, and the main page of the template.


Once this is complete, you need to populate your ``.env`` file with the integration token and the id of the two pages you have granted your integration access to. The ``.env`` file should look like this::
    NOTION_KEY = 'somevalue'
    NOTION_PAGE_ID = 'somevalue'
    NOTION_MP_ID = 'somevalue'
Where ``NOTION_KEY`` is the secret integration token, ``NOTION_PAGE_ID`` is the id of the recipe database, and ``NOTION_MP_ID`` is the id of the main page of the template, where the grocery list resides.
See the Environment variables section of `Build a notion integration <https://developers.notion.com/docs/create-a-notion-integration>` for more information on how this works, including how to find the page ids. 
