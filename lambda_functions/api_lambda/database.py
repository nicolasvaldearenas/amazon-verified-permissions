from decimal import Decimal
from typing import Optional

import boto3
from boto3.dynamodb.conditions import Key

from api_types import List, Task


class ShareExists(Exception):
    pass


dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("TinyTodoTable")
OWNER_LIST_ID_INDEX = "OwnerListIdIndex"


def query_user_key(user_name: str) -> str:
    items = table.query(KeyConditionExpression=Key("pk").eq(user_name))["Items"]

    if len(items) == 0:
        return ""

    return items[0]["sk"]


def list_key(list_id: int) -> str:
    return f"LIST#{list_id:06}"


def task_key(task_id: int) -> str:
    return f"TASK#{task_id:06}"


def count_lists(user: str) -> int:
    return table.query(
        IndexName=OWNER_LIST_ID_INDEX,
        KeyConditionExpression=Key("owner").eq(user),
        Select="COUNT",
    )["Count"]


def list_lists(user: str) -> list[List]:
    items = table.query(
        IndexName=OWNER_LIST_ID_INDEX,
        KeyConditionExpression=Key("owner").eq(user),
    )["Items"]

    return [List.from_item(item) for item in items]


def create_list(user: str, name: str, description: str) -> int:
    attributes = table.update_item(
        Key={"pk": "GLOBAL", "sk": "GLOBAL"},
        UpdateExpression="ADD nextListId :one",
        ExpressionAttributeValues={":one": Decimal("1")},
        ReturnValues="UPDATED_OLD",
    )["Attributes"]

    list_id = int(attributes["nextListId"])

    table.put_item(
        Item={
            "pk": list_key(list_id),
            "sk": "DETAILS",
            "name": name,
            "description": description,
            "listId": Decimal(list_id),
            "owner": user,
            "nextTaskId": Decimal(1),
        }
    )

    return list_id


def get_list(list_id: int) -> Optional[List]:
    try:
        item = table.get_item(Key={"pk": list_key(list_id), "sk": "DETAILS"})["Item"]
        return List.from_item(item)
    except KeyError:
        return None


def update_list(list_id: int, name: str, description: str) -> None:
    table.update_item(
        Key={"pk": list_key(list_id), "sk": "DETAILS"},
        UpdateExpression="SET #name = :name, #description = :description",
        ExpressionAttributeNames={"#name": "name", "#description": "description"},
        ExpressionAttributeValues={":name": name, ":description": description},
        ConditionExpression="attribute_exists(pk)",
    )


def delete_list(list_id: int) -> None:
    table.delete_item(Key={"pk": list_key(list_id), "sk": "DETAILS"})


def count_tasks(list_id: int) -> int:
    return table.query(
        KeyConditionExpression=Key("pk").eq(list_key(list_id)) & Key("sk").begins_with("TASK#"),
        Select="COUNT",
    )["Count"]


def list_tasks(list_id: int) -> list[Task]:
    items = table.query(
        KeyConditionExpression=Key("pk").eq(list_key(list_id)) & Key("sk").begins_with("TASK#"),
    )["Items"]

    return [Task.from_item(item) for item in items]


def create_task(list_id: int, name: str, description: str) -> int:
    attributes = table.update_item(
        Key={"pk": list_key(list_id), "sk": "DETAILS"},
        UpdateExpression="ADD nextTaskId :one",
        ExpressionAttributeValues={":one": Decimal("1")},
        ReturnValues="UPDATED_OLD",
    )["Attributes"]

    task_id = int(attributes["nextTaskId"])

    table.put_item(
        Item={
            "pk": list_key(list_id),
            "sk": task_key(task_id),
            "name": name,
            "description": description,
            "listId": Decimal(list_id),
            "taskId": Decimal(task_id),
        }
    )

    return task_id


def update_task(list_id: int, task_id: int, name: str, description: str) -> None:
    table.update_item(
        Key={"pk": list_key(list_id), "sk": task_key(task_id)},
        UpdateExpression="SET #name = :name, #description = :description",
        ExpressionAttributeNames={"#name": "name", "#description": "description"},
        ExpressionAttributeValues={":name": name, ":description": description},
        ConditionExpression="attribute_exists(pk)",
    )


def delete_task(list_id: int, task_id: int) -> None:
    table.delete_item(Key={"pk": list_key(list_id), "sk": task_key(task_id)})
