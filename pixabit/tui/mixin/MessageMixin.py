import asyncio
from typing import Any


class MessagesMixin:
    async def get_inbox_messages(
        self, page: int = 0, conversation_id: str | None = None
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {"page": page}
        if conversation_id:
            params["conversation"] = conversation_id
        result = await self.get("/inbox/messages", params=params)
        return result if isinstance(result, list) else []

    async def send_private_message(
        self, recipient_id: str, message_text: str
    ) -> dict[str, Any] | None:
        if not recipient_id:
            raise ValueError("recipient_id required.")
        if not message_text or not message_text.strip():
            raise ValueError("message_text required.")
        payload = {"toUserId": recipient_id, "message": message_text.strip()}
        result = await self.post("/members/send-private-message", data=payload)
        return result if isinstance(result, dict) else None

    async def mark_pms_read(self) -> bool:
        result = await self.post("/user/mark-pms-read")
        return result is None

    async def delete_private_message(self, message_id: str) -> bool:
        if not message_id:
            raise ValueError("message_id required.")
        result = await self.delete(f"/user/messages/{message_id}")
        return result is None
