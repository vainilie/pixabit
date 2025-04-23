class TaskKeepOption(str, Enum):
    KEEP = "keep"
    REMOVE = "remove"


class ChallengeKeepOption(str, Enum):
    KEEP_ALL = "keep-all"
    REMOVE_ALL = "remove-all"


class ChallengeMixin:

    async def get_challenges(
        self, member_only: bool = True, page: int = 0
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"page": page}
        params["member"] = "true" if member_only else "false"
        result = await self.get("/challenges/user", params=params)
        return result if isinstance(result, list) else []

    async def get_all_challenges(
        self, member_only: bool = True
    ) -> List[dict[str, Any]]:
        """Get all challenges, handling pagination automatically.

        Args:
            member_only: If True, only return challenges user is a member of

        Returns:
            List of all challenges across all pages
        """
        all_challenges = []
        current_page = 0

        while True:
            page_data = await self.get_challenges(
                member_only=member_only, page=current_page
            )

            if not page_data:
                break

            all_challenges.extend(page_data)
            current_page += 1
            await asyncio.sleep(0.5)  # Pequeña pausa para no saturar la API

        return all_challenges

    async def get_challenge_tasks(
        self, challenge_id: str
    ) -> List[Dict[str, Any]]:
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        result = await self.get(f"/tasks/challenge/{challenge_id}")
        return result if isinstance(result, list) else []

    async def leave_challenge(
        self, challenge_id: str, keep: str = "keep-all"
    ) -> bool:
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        if keep not in ["keep-all", "remove-all"]:
            raise ValueError("keep must be 'keep-all' or 'remove-all'")
        result = await self.post(
            f"/challenges/{challenge_id}/leave", params={"keep": keep}
        )
        return result is None

    async def unlink_task_from_challenge(
        self, task_id: str, keep: str = "keep"
    ) -> bool:
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        if keep not in ["keep", "remove"]:
            raise ValueError("keep must be 'keep' or 'remove'")
        result = await self.post(
            f"/tasks/{task_id}/unlink", params={"keep": keep}
        )
        return result is None

    async def unlink_all_challenge_tasks(
        self, challenge_id: str, keep: str = "keep-all"
    ) -> bool:
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        if keep not in ["keep-all", "remove-all"]:
            raise ValueError("keep must be 'keep-all' or 'remove-all'")
        result = await self.post(
            f"/tasks/unlink-all/{challenge_id}", params={"keep": keep}
        )
        return result is None

    async def create_challenge(
        self, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        if (
            not data.get("name")
            or not data.get("shortName")
            or not data.get("group")
        ):
            raise ValueError(
                "Challenge creation requires at least 'name', 'shortName', and 'group' ID."
            )
        result = await self.post("/challenges", data=data)
        return result if isinstance(result, dict) else None

    async def clone_challenge(
        self, challenge_id: str
    ) -> Optional[Dict[str, Any]]:
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        result = await self.post(f"/challenges/{challenge_id}/clone")
        return result if isinstance(result, dict) else None

    async def update_challenge(
        self, challenge_id: str, data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        if not data:
            raise ValueError("Update data cannot be empty.")
        result = await self.put(f"/challenges/{challenge_id}", data=data)
        return result if isinstance(result, dict) else None

    async def create_challenge_task(
        self, challenge_id: str, task_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        if not task_data.get("text") or not task_data.get("type"):
            raise ValueError("Task data requires 'text' and 'type'.")
        if task_data["type"] not in {"habit", "daily", "todo", "reward"}:
            raise ValueError("Invalid task type.")
        result = await self.post(
            f"/tasks/challenge/{challenge_id}", data=task_data
        )
        return result if isinstance(result, dict) else None
