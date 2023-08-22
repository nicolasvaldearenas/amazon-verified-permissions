from jose import JWTError
import json
import jwt

import database
import permissions
from util import debug_object

Response = object

ACTIONS = {
    # Task-list CRUD
    ("/task-list/create", "POST"): "CreateList",
    ("/task-list/read", "GET"): "ReadList",
    ("/task-list/update", "PUT"): "UpdateList",
    ("/task-list/delete", "DELETE"): "DeleteList",
    # Task CRUD
    ("/task/create", "POST"): "CreateTask",
    ("/task/read", "GET"): "ReadTask",
    ("/task/update", "PUT"): "UpdateTask",
    ("/task/delete", "DELETE"): "DeleteTask",
    # Share CRUD
    ("/share/create", "POST"): "CreateShare",
    ("/share/read", "GET"): "ReadShare",
    ("/share/update", "PUT"): "UpdateShare",
    ("/share/delete", "DELETE"): "DeleteShare",
    # List Operations
    ("/list/task-lists", "GET"): "ListLists",
    ("/list/tasks", "GET"): "ListTasks",
    ("/list/shares", "GET"): "ListShares",
    ("/list/shared-lists", "GET"): "ListSharedLists",
}


def handler(event, context) -> Response:
    debug_object(event)
    debug_object(context)

    # Get the information about the requested action
    resource = event["resource"]
    method = event["httpMethod"]
    action = ACTIONS.get((resource, method), "Unknown")
    if action == "Unknown":
        return format_response({"message": "Unknown API call"}, 404)

    # Get the information about the principal from the JWT token
    access_token = event["headers"]["Authorization"].split(" ")[1]
    try:
        jwt_claims = jwt.decode(access_token, options={"verify_signature": False})
        debug_object(jwt_claims)
        user_pool_id = jwt_claims["iss"].split("/")[-1]
        principal = "{}|{}".format(user_pool_id, jwt_claims["sub"])
    except JWTError as e:
        debug_object(e)
        return format_response({"message": "Access denied -- token broken"}, 401)

    # Variables that exist only on some requests
    list_id = None
    task_id = None
    user = None
    name = None
    description = None
    role = None
    if event["body"]:
        body = json.loads(event["body"])
        name = body["name"] if "name" in body else None
        description = body["description"] if "description" in body else None
        role = body["role"] if "role" in body else None
        list_id = int(body["listId"]) if "listId" in body else None
        task_id = int(body["taskId"]) if "taskId" in body else None
        if "user" in body:
            user = body["user"]
            if user != principal:
                user = database.query_user_key(user)
                print("Using: {} to use as share key".format(user))
            if user == "":
                return format_response({"message": "Invalid input -- user doesn't exist."}, 401)
    elif event["queryStringParameters"]:
        list_id = int(event["queryStringParameters"]["listId"]) if "listId" in event["queryStringParameters"] else None
        task_id = int(event["queryStringParameters"]["taskId"]) if "taskId" in event["queryStringParameters"] else None

    # Check if the list exists
    if list_id and database.get_list(list_id) is None:
        return format_response({"message": "Invalid input -- list doesn't exist"}, 400)
    task_list = list_id and database.get_list(list_id)

    debug_object(principal)
    debug_object(action)
    debug_object(task_list)

    # Basic permissions check
    if permissions.permissions_check(principal, action, task_list) == "DENY":
        return format_response({"message": "Access denied -- permissions check failed"}, 401)
    # id_token = event.get("headers", {}).get("id-token")
    # if not id_token:
    #     return format_response({"message": "Access denied -- no identity token provided"}, 401)
    # try:
    #     if permissions.permissions_check_token(id_token, action, task_list) == "DENY":
    #         return format_response({"message": "Access denied -- permissions check failed"}, 401)
    # except Exception as e:
    #     return format_response({"message": f"Access denied -- permissions check failed - {str(e)}"}, 401)

    if action == "ListLists":
        return list_lists(principal)
    elif action == "CreateList":
        return create_list(principal, name, description)
    elif action == "ReadList":
        return get_list(list_id)
    elif action == "UpdateList":
        return update_list(list_id, name, description)
    elif action == "DeleteList":
        return delete_list(list_id)
    elif action == "ListTasks":
        return list_tasks(list_id)
    elif action == "CreateTask":
        return create_task(list_id, name, description)
    elif action == "UpdateTask":
        return update_task(list_id, task_id, name, description)
    elif action == "DeleteTask":
        return delete_task(list_id, task_id)
    elif action == "ListShares":
        return list_shares(list_id)
    elif action == "CreateShare":
        return create_share(list_id, user, role)
    elif action == "UpdateShare":
        return update_share(list_id, user, role)
    elif action == "DeleteShare":
        return delete_share(list_id, user)
    elif action == "ListSharedLists":
        return list_shared_lists(principal)


def list_lists(user: str) -> Response:
    return format_response({"lists": database.list_lists(user)})


def create_list(user: str, name: str, description: str) -> Response:
    return format_response({"listId": database.create_list(user, name, description)})


def get_list(list_id: int) -> Response:
    return format_response({"list": database.get_list(list_id)})


def update_list(list_id: int, name: str, description: str) -> Response:
    database.update_list(list_id, name, description)
    return format_response({})


def delete_list(list_id: int) -> Response:
    task_count = database.count_tasks(list_id)

    # Note: Race condition allows us to delete lists that have tasks added at the last moment. Oh, well.
    if task_count > 0:
        return format_response({"message": "List not empty"}, 400)
    else:
        database.delete_list(list_id)
        return format_response({})


def list_tasks(list_id: int) -> Response:
    return format_response({"tasks": database.list_tasks(list_id)})


def create_task(list_id: int, name: str, description: str) -> Response:
    return format_response({"taskId": database.create_task(list_id, name, description)})


def update_task(list_id: int, task_id: int, name: str, description: str) -> Response:
    database.update_task(list_id, task_id, name, description)
    return format_response({})


def delete_task(list_id, task_id) -> Response:
    database.delete_task(list_id, task_id)
    return format_response({})


def list_shares(list_id: int) -> Response:
    return format_response({"shares": permissions.list_shares(list_id)})


def create_share(list_id: int, user: str, role: str) -> Response:
    try:
        permissions.create_share(list_id, user, role)
        return format_response({})
    except permissions.ShareExists:
        return format_response({"message": "Share already exists"}, 400)


def update_share(list_id: int, user: str, role: str) -> Response:
    permissions.update_share(list_id, user, role)
    return format_response({})


def delete_share(list_id: int, user: str) -> Response:
    permissions.delete_share(list_id, user)
    return format_response({})


def list_shared_lists(user: str) -> Response:
    return format_response({"sharedLists": permissions.list_shared_lists(user)})


def format_response(body: object, status_code=200) -> object:
    result = {
        "statusCode": status_code,
        "headers": {
            "Content-Type": "application/json",
            "Access-Control-Allow-Origin": "*",
        },
        "body": json.dumps(body, default=lambda o: o.__dict__),
    }
    debug_object(result)
    return result
