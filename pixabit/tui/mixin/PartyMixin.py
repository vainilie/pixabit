class PartyMixin:
    async def get_party_data(self) -> Optional[Dict[str, Any]]:
        result = await self.get("/groups/party")
        return result if isinstance(result, dict) else None

    async def get_group_chat_messages(
        self, group_id: str = "party", older_than: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        if not group_id:
            raise ValueError("group_id cannot be empty.")
        params = {"previousMsg": older_than} if older_than else {}
        result = await self.get(f"/groups/{group_id}/chat", params=params)
        return result if isinstance(result, list) else []

    async def like_group_chat_message(
        self, group_id: str, chat_id: str
    ) -> Optional[Dict[str, Any]]:
        if not group_id or not chat_id:
            raise ValueError("group_id and chat_id required.")
        result = await self.post(f"/groups/{group_id}/chat/{chat_id}/like")
        return result if isinstance(result, dict) else None

    async def mark_group_chat_seen(self, group_id: str = "party") -> bool:
        if not group_id:
            raise ValueError("group_id cannot be empty.")
        result = await self.post(f"/groups/{group_id}/chat/seen")
        return result is None

    async def post_group_chat_message(
        self, group_id: str = "party", message_text: str = ""
    ) -> Optional[Dict[str, Any]]:
        if not group_id:
            raise ValueError("group_id required.")
        if not message_text or not message_text.strip():
            raise ValueError("message_text cannot be empty.")
        payload = {"message": message_text.strip()}
        result = await self.post(f"/groups/{group_id}/chat", data=payload)
        return result if isinstance(result, dict) else None

    async def get_quest_status(self) -> Optional[bool]:
        try:
            party_data = await self.get_party_data()
            if party_data is None:
                return None
            quest_info = party_data.get("quest", {})
            return isinstance(quest_info, dict) and quest_info.get(
                "active", False
            )
        except HabiticaAPIError as e:
            log.error(f"API Error getting quest status: {e}", style="warning")
            return None
        except Exception as e:
            log.error(
                f"Unexpected error getting quest status: {e}", style="error"
            )
            return None

    async def cast_skill(
        self, spell_id: str, target_id: str | None = None
    ) -> dict[str, Any]:
        """Cast a skill/spell.

        Args:
            spell_id: ID of the spell to cast
            target_id: Optional user ID to target

        Returns:
            Cast response data

        Raises:
            ValueError: If spell_id is empty
        """
        if not spell_id:
            raise ValueError("spell_id cannot be empty.")

        params = {"targetId": target_id} if target_id else None
        result = await self.post(f"user/class/cast/{spell_id}", params=params)
        return self._ensure_type(result, dict) or {}
