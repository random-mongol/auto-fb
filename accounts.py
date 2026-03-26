import json
import os
from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class Account:
    id: str
    email: str
    password: str
    profile_path: str
    fb_profile_url: Optional[str] = None  # Used by fb_poster.py
    personal_profile_name: Optional[str] = None  # Used by fb_poster.py for profile switching

    @property
    def resolved_profile_path(self) -> str:
        """Returns absolute path, resolving relative paths from project root."""
        if os.path.isabs(self.profile_path):
            return self.profile_path
        base = os.path.dirname(os.path.abspath(__file__))
        return os.path.join(base, self.profile_path)


def load_accounts() -> List[Account]:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "accounts.json")
    if not os.path.exists(path):
        raise FileNotFoundError(
            "accounts.json not found. Copy accounts.example.json to accounts.json and fill in your credentials."
        )
    with open(path) as f:
        data = json.load(f)
    return [
        Account(
            id=item["id"],
            email=item["email"],
            password=item["password"],
            profile_path=item["profile_path"],
            fb_profile_url=item.get("fb_profile_url"),
            personal_profile_name=item.get("personal_profile_name"),
        )
        for item in data
    ]


def get_account(account_id: str) -> Account:
    for account in load_accounts():
        if account.id == account_id:
            return account
    raise ValueError(f"Account '{account_id}' not found in accounts.json")
