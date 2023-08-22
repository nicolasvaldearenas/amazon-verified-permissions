import json

Response = object


def debug_object(obj: object) -> None:
    print(json.dumps(obj, indent=2, default=str).replace("\n", "\r"))


def handler(event, context) -> Response:
    debug_object(event)
    # Confirm the user
    event["response"]["autoConfirmUser"] = True

    # Return to Amazon Cognito
    return event
