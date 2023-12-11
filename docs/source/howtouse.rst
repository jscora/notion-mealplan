How to run the code
===================

To run the Notion Mealplan Generator, follow the steps below:

1. Install the code and Notion template and integration as described above
2. Open up terminal and enter the ``notion_mealplan`` directory
3. Run ``poetry run mealplan``
4. Respond to the code prompts

The prompts will ask you to enter the number of meals you want, and the repetition frequency to allow. 
Both should be integers. Repetition frequency refers to how many recipes from the previous week can be on your current week's meal plan (though it is not a guarantee that any will be). 
You can enter any number from 0 to the number of meals you've chosen in the first prompt. 


Notes on the grocery list
-------------------------

The code will generate a grocery list for the recipes in your meal plan that week. 
This code works best if you follow the template for recipes that is given in the Recipes database in the template mentioned above. 
However, the code will still function if it cannot find ingredients for any (or all) of your recipes. 
It will simply notify you of any recipes that it cannot find ingredients for in the terminal output, and will put all of the ingredients it did find into the Notion page under the **Grocery List** heading.

