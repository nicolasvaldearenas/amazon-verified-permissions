from typing import Union

import os
import boto3

import database
from api_types import List, Share, SharedList
from util import debug_object

POLICY_STORE_ID = os.environ["POLICY_STORE_ID"]
TASK_LIST_EDITOR_TEMPLATE_ID = os.environ["TASK_LIST_EDITOR_TEMPLATE_ID"]
TASK_LIST_VIEWER_TEMPLATE_ID = os.environ["TASK_LIST_VIEWER_TEMPLATE_ID"]
avp = boto3.client("verifiedpermissions")


class ShareExists(Exception):
    pass


def entity(entity_type: str, entity_id: Union[str, int]) -> dict:
    return {"entityType": f"TinyTodo::{entity_type}", "entityId": str(entity_id)}


def attributes(**kwargs) -> dict:
    return {key: attribute_value(value) for key, value in kwargs.items()}


def attribute_value(value: any) -> dict:
    if isinstance(value, str):
        return {"string": value}
    elif isinstance(value, set) or isinstance(value, list):
        return {"set": [attribute_value(v) for v in value]}
    elif isinstance(value, dict):
        return {"entityIdentifier": value}
    else:
        raise f"Unknown attribute value type: {type(value)}"


def permissions_check(avp_principal: str, action: str, task_list: List) -> bool:
    args = {
        "policyStoreId": POLICY_STORE_ID,
        "principal": entity("User", avp_principal),
        "action": {"actionType": "TinyTodo::Action", "actionId": action},
        "resource": entity("Application", "TinyTodo"),
    }

    if task_list:
        args["resource"] = entity("List", task_list.id)
        args["entities"] = {
            "entityList": [
                {
                    "identifier": entity("List", task_list.id),
                    "attributes": attributes(
                        owner=entity("User", task_list.owner),
                    ),
                }
            ]
        }

    debug_object(args)
    resp = avp.is_authorized(**args)
    return resp["decision"]


def permissions_check_token(token: str, action: str, task_list: List) -> bool:
    args = {
        "policyStoreId": POLICY_STORE_ID,
        "identityToken": token,
        "action": {"actionType": "TinyTodo::Action", "actionId": action},
        "resource": entity("Application", "TinyTodo"),
    }

    if task_list:
        args["resource"] = entity("List", task_list.id)
        args["entities"] = {
            "entityList": [
                {
                    "identifier": entity("List", task_list.id),
                    "attributes": attributes(
                        owner=entity("User", task_list.owner),
                    ),
                }
            ]
        }

    debug_object(args)
    resp = avp.is_authorized_with_token(**args)
    return resp["decision"]


def create_share(list_id: int, user: str, role: str) -> None:
    print("Creating template-linked policy")
    principal = entity("User", user)
    resource = entity("List", str(list_id))
    template_id = TASK_LIST_EDITOR_TEMPLATE_ID if role == "editor" else TASK_LIST_VIEWER_TEMPLATE_ID
    templateLinkedDef = {
        "templateLinked": {"policyTemplateId": template_id, "principal": principal, "resource": resource}
    }
    templateLinked = avp.create_policy(policyStoreId=POLICY_STORE_ID, definition=templateLinkedDef)
    debug_object(templateLinked)


def policy_to_share(policy) -> Share:
    user = policy["principal"]["entityId"]
    role = (
        "editor"
        if policy["definition"]["templateLinked"]["policyTemplateId"] == TASK_LIST_EDITOR_TEMPLATE_ID
        else "viewer"
    )
    return Share(user, role)


def list_shares(list_id: int) -> list[Share]:
    resp = avp.list_policies(
        policyStoreId=POLICY_STORE_ID, filter={"resource": {"identifier": entity("List", list_id)}}
    )
    return [policy_to_share(policy) for policy in resp["policies"]]


def list_shared_lists(user: str) -> list[SharedList]:
    resp = avp.list_policies(
        policyStoreId=POLICY_STORE_ID,
        filter={"principal": {"identifier": entity("User", user)}},
    )
    print(f"User {user} has {len(resp['policies'])} policies")
    debug_object(resp["policies"])

    result = []
    for policy in resp["policies"]:
        list_id = int(policy["resource"]["entityId"])
        role = (
            "editor"
            if policy["definition"]["templateLinked"]["policyTemplateId"] == TASK_LIST_EDITOR_TEMPLATE_ID
            else "viewer"
        )
        try:
            list = database.get_list(list_id)
            result.append(SharedList.from_list(list, role))
        except KeyError:
            # Share references a deleted list, ignore it
            pass
    return result


def get_sharing_policy(list_id: int, user: str):
    policies = list_sharing_policies(list_id, user)
    # Based on how we create shares, there should never be more than one policy in this list
    assert len(policies) == 1
    return policies[0]


def list_sharing_policies(list_id: int, user: str):
    resp = avp.list_policies(
        policyStoreId=POLICY_STORE_ID,
        filter={
            "principal": {"identifier": entity("User", user)},
            "resource": {"identifier": entity("List", list_id)},
        },
    )
    return resp["policies"]


def update_share(list_id: int, user: str, role: str) -> None:
    # This is non-atomic, so we hope nothing goes wrong halfway through
    delete_share(list_id, user)
    create_share(list_id, user, role)


def delete_share(list_id: int, user: str) -> None:
    policy = get_sharing_policy(list_id, user)
    avp.delete_policy(policyStoreId=POLICY_STORE_ID, policyId=policy["policyId"])
