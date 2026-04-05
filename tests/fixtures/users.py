TEST_USERS = [
    {"email": "user1@example.com", "name": "User One"},
    {"email": "user2@example.com", "name": "User Two"}
]

EDGE_CASE_EMAILS = [
    "user.name+tag@example.com",
    "user-name@example.co.uk"
]

INVALID_EMAILS = [
    "user@example",
    "user",
    "user@.com",
    "@example.com"
]
