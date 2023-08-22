from decimal import Decimal

import boto3
from boto3.dynamodb.conditions import Key
from botocore.exceptions import ClientError

dynamodb = boto3.resource("dynamodb")
table = dynamodb.Table("TinyTodoTable")
OWNER_LIST_ID_INDEX = "OwnerListIdIndex"


def list_key(list_id: int) -> str:
    return f"LIST#{list_id:06}"


def task_key(task_id: int) -> str:
    return f"TASK#{task_id:06}"


def create_user(userId: str, userName: str):
    table.put_item(
        Item={
            "pk": userId,
            "sk": userName,
        }
    )

    table.put_item(
        Item={
            "pk": userName,
            "sk": userId,
        }
    )


def create_list(userId: str, name: str, description: str) -> int:
    try:
        response = table.get_item(Key={"pk": "GLOBAL", "sk": "GLOBAL"})
        if "Item" not in response:
            # item does not exist, create it
            table.put_item(Item={"pk": "GLOBAL", "sk": "GLOBAL", "nextListId": Decimal("1")})
            attributes = {"nextListId": Decimal("1")}
        else:
            attributes = response["Item"]
    except ClientError as e:
        # unexpected error, re-raise exception
        raise e

    list_id = int(attributes["nextListId"])

    table.put_item(
        Item={
            "pk": list_key(list_id),
            "sk": "DETAILS",
            "name": name,
            "description": description,
            "listId": Decimal(list_id),
            "owner": userId,
            "nextTaskId": Decimal(1),
        }
    )

    # increment nextListId for the next list
    table.update_item(
        Key={"pk": "GLOBAL", "sk": "GLOBAL"},
        UpdateExpression="SET nextListId = nextListId + :one",
        ExpressionAttributeValues={":one": Decimal("1")},
    )

    return list_id


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


def count_lists(userId: str) -> int:
    return table.query(
        IndexName=OWNER_LIST_ID_INDEX,
        KeyConditionExpression=Key("owner").eq(userId),
        Select="COUNT",
    )["Count"]
