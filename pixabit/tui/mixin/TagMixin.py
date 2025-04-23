class TagMixin:

    async def get_tags(self) -> List[Dict[str, Any]]:
        result = await self.get("/tags")
        return result if isinstance(result, list) else []

    async def create_tag(self, name: str) -> Optional[Dict[str, Any]]:
        if not name or not name.strip():
            raise ValueError("Tag name cannot be empty.")
        result = await self.post("/tags", data={"name": name.strip()})
        return result if isinstance(result, dict) else None

    async def update_tag(
        self, tag_id: str, name: str
    ) -> Optional[Dict[str, Any]]:
        if not tag_id:
            raise ValueError("tag_id cannot be empty.")
        if not name or not name.strip():
            raise ValueError("New tag name cannot be empty.")
        result = await self.put(f"/tags/{tag_id}", data={"name": name.strip()})
        return result if isinstance(result, dict) else None

    async def delete_tag(self, tag_id: str) -> bool:
        if not tag_id:
            raise ValueError("tag_id cannot be empty.")
        result = await self.delete(f"/tags/{tag_id}")
        return result is None

    async def reorder_tag(self, tag_id: str, position: int) -> bool:
        if not tag_id:
            raise ValueError("tag_id cannot be empty.")
        if not isinstance(position, int) or position < 0:
            raise ValueError("position must be a non-negative integer index.")
        payload = {"tagId": tag_id, "to": position}
        result = await self.post("/reorder-tags", data=payload)
        return result is None
