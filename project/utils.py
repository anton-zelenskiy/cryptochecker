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


# data = {
#         "update_id":773970080,
#         "message":{
#             "message_id":9,
#             "from":{
#                 "id":110454962,
#                 "is_bot": False,
#                 "first_name":"\u0410\u043d\u0442\u043e\u043d",
#                 "last_name":"\u0417\u0435\u043b\u0435\u043d\u0441\u043a\u0438\u0439",
#                 "username":"antonfewwt",
#                 "language_code":"en"
#             },
#             "chat":{
#                 "id":110454962,
#                 "first_name":"\u0410\u043d\u0442\u043e\u043d",
#                 "last_name":"\u0417\u0435\u043b\u0435\u043d\u0441\u043a\u0438\u0439",
#                 "username":"antonfewwt",
#                 "type":"private"
#             },
#             "date":1560589346,
#             "text":"/start",
#             "entities":[{"offset":0,"length":6,"type":"bot_command"}]
#         }
#     }


def parse_update(data):
    """"""
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

