from dataclasses import dataclass


@dataclass
class List:
    id: int
    owner: str
    name: str
    description: str

    @classmethod
    def from_item(cls, item):
        return List(
            id=int(item["listId"]),
            owner=item["owner"],
            name=item["name"],
            description=item["description"],
        )


@dataclass
class Task:
    id: int
    name: str
    description: str

    @classmethod
    def from_item(cls, item):
        return Task(
            id=int(item["taskId"]),
            name=item["name"],
            description=item["description"],
        )


@dataclass
class Share:
    user: str
    role: str

    @classmethod
    def from_item(cls, item):
        return Share(
            user=item["user"],
            role=item["role"],
        )


@dataclass
class SharedList(List):
    role: str

    @classmethod
    def from_list(cls, list: List, role: str):
        return SharedList(**list.__dict__, role=role)
