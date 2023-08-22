import json
import database

Response = object


def debug_object(obj: object) -> None:
    print(json.dumps(obj, indent=2, default=str).replace("\n", "\r"))


def handler(event, context) -> Response:
    debug_object(event)
    debug_object(context)

    user_pool_id = event["userPoolId"]
    sub = event["request"]["userAttributes"]["sub"]

    user_name = event["userName"]
    userId = "{}|{}".format(user_pool_id, sub)

    database.create_user(userId, user_name)

    # Create a user in the database and create their first list of tasks
    list_count = database.count_lists(userId)
    if list_count == 0:
        with open("resources/starter-list.json") as starter_list_file:
            starter_list = json.load(starter_list_file)

        list_id = database.create_list(userId, starter_list["name"], starter_list["description"])
        for task in starter_list["tasks"]:
            database.create_task(list_id, task["name"], task["description"])
        return event
    else:
        return event
