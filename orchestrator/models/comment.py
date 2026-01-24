from dataclasses import dataclass


@dataclass
class Comment:
    id: str
    author: str
    message: str
    timestamp: str
    platform: str = "youtube"
    is_superchat: bool = False
    superchat_amount: float = 0.0
    is_member: bool = False
