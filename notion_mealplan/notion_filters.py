"""Contains all the filters and other Notion-specific headers"""

update_planned_props = {"properties": {"Planned this week": {"checkbox": True}}}

update_prev_planned_props = {"properties": {"Planned this week": {"checkbox": False}}}

filter_prev = {"property": "Planned this week", "checkbox": {"equals": True}}

filter_ld = {"property": "Dish", "multi_select": {"contains": "Lunch/Dinner"}}

headings = ["heading_1", "heading_2", "heading_3"]
