from . import mp_functions as mp


def get_input():
    print("How many recipes do you need this week?")
    k = input()
    print("How much repetition will you allow from last week? (Recommended is 1)")
    repeat_freq = input()

    # convert to int
    try:
        k = int(k)
        repeat_freq = int(repeat_freq)
    except:
        print(
            "Number of recipes and repetition frequency must be integers, please try again"
        )
        get_input()

    return (k, repeat_freq)


def main():
    print("Welcome to the Notion Meal Planner")

    k, repeat_freq = get_input()

    recipes = mp.get_mealplan(k, repeat_freq)

    print("Meal plan updated")
