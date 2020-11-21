from dataclasses import dataclass, fields


@dataclass
class User:
    id: int
    username: str
    first_name: str
    last_name: str


@dataclass
class Chat:
    id: int
    username: str


@dataclass
class Message:
    message_id: int
    user: User
    chat: Chat
    text: str
    date: int


@dataclass
class Update:
    update_id: int
    message: Message


def parse_update_message(data):
    """Parses update message from tg."""
    message = None
    user = None
    chat = None

    if 'message' in data:
        message_ = data['message']

        if 'from' in message_:
            user = User(**{
                field.name: message_['from'][field.name]
                for field in fields(User)
            })
            chat = Chat(**{
                field.name: message_['chat'][field.name]
                for field in fields(Chat)
            })

        message = Message(
            message_id=message_.get('message_id'),
            user=user,
            chat=chat,
            text=message_.get('text'),
            date=message_.get('date')
        )

    update = Update(
        update_id=data.get('update_id'),
        message=message
    )

    return update

