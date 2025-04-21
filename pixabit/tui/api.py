HABITICA_USER_ID = "DUMMY_USER_ID_CONFIG_MISSING"
HABITICA_API_TOKEN = "DUMMY_API_TOKEN_CONFIG_MISSING"
config = DummyConfig()
DEFAULT_BASE_URL: str = "https://habitica.com/api/v3"
REQUESTS_PER_MINUTE: int = 29
MIN_REQUEST_INTERVAL: float = 60.0 / REQUESTS_PER_MINUTE
HabiticaApiResponsePayload = Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]


class HabiticaAPIError(Exception):
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        error_type: Optional[str] = None,
        response_data: Optional[Any] = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.error_type = error_type
        self.response_data = response_data

    def __str__(self) -> str:
        details = []
        if self.status_code is not None:
            details.append(f"Status={self.status_code}")
        if self.error_type:
            details.append(f"Type='{self.error_type}'")
        base_msg = super().__str__()
        return f"HabiticaAPIError: {base_msg}" + (f" ({', '.join(details)})" if details else "")


class HabiticaAPI:
    BASE_URL: str = DEFAULT_BASE_URL

    def __init__(
        self,
        user_id: Optional[str] = None,
        api_token: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
    ):
        self.user_id: str = user_id or config.HABITICA_USER_ID
        self.api_token: str = api_token or config.HABITICA_API_TOKEN
        self.base_url: str = base_url
        if not self.user_id or not self.api_token or "DUMMY" in self.user_id:
            raise ValueError("Habitica User ID and API Token are required and must be valid.")
        self.headers: Dict[str, str] = {
            "x-api-user": self.user_id,
            "x-api-key": self.api_token,
            "Content-Type": "application/json",
            "x-client": "pixabit-tui-v0.1.0",
        }
        self.last_request_time: float = 0.0
        self.request_interval: float = MIN_REQUEST_INTERVAL

    async def _wait_for_rate_limit(self) -> None:
        current_time = time.monotonic()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.request_interval:
            wait_time = self.request_interval - time_since_last
            await asyncio.sleep(wait_time)
        self.last_request_time = time.monotonic()

    async def _request(
        self, method: str, endpoint: str, **kwargs: Any
    ) -> HabiticaApiResponsePayload:
        await self._wait_for_rate_limit()
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        response: Optional[httpx.Response] = None
        try:
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.request(method, url, headers=self.headers, **kwargs)
            response.raise_for_status()
            if response.status_code == 204 or not response.content:
                return None
            response_data = response.json()
            if isinstance(response_data, dict) and "success" in response_data:
                if response_data["success"]:
                    return response_data.get("data")
                else:
                    error_type = response_data.get("error", "Unknown Habitica Error")
                    message = response_data.get("message", "No message provided.")
                    raise HabiticaAPIError(
                        f"{error_type} - {message}",
                        status_code=response.status_code,
                        error_type=error_type,
                        response_data=response_data,
                    )
            elif isinstance(response_data, (dict, list)):
                return response_data
            else:
                raise ValueError(
                    f"Unexpected JSON structure received: {type(response_data).__name__}"
                )
        except httpx.TimeoutException as timeout_err:
            msg = f"Request timed out for {method} {endpoint}"
            log.error(f"[error]Timeout Error:[/error] {msg}: {timeout_err}")
            raise HabiticaAPIError(msg, status_code=408) from timeout_err
        except httpx.HTTPStatusError as http_err:
            response = http_err.response
            status_code = response.status_code
            error_details = f"HTTP Error {status_code} for {method} {url}"
            try:
                err_data = response.json()
                error_type = err_data.get("error", f"HTTP{status_code}")
                message = err_data.get(
                    "message",
                    response.reason_phrase or f"HTTP {status_code} Error",
                )
                api_err_msg = f"{error_type} - {message}"
                error_details += f" | API: '{api_err_msg}'"
                raise HabiticaAPIError(
                    api_err_msg,
                    status_code=status_code,
                    error_type=error_type,
                    response_data=err_data,
                ) from http_err
            except json.JSONDecodeError:
                body_preview = response.text[:200].replace("\n", "\\n")
                error_details += f" | Response Body (non-JSON): {body_preview}"
                log.error(f"[error]Request Failed:[/error] {error_details}")
                raise HabiticaAPIError(
                    f"HTTP Error {status_code} with non-JSON body",
                    status_code=status_code,
                ) from http_err
            except Exception as parse_err:
                log.error(
                    f"[error]Request Failed & Error Parsing Failed:[/error] {error_details} | Parse Err: {parse_err}"
                )
                raise HabiticaAPIError(
                    f"HTTP Error {status_code} (error parsing failed)",
                    status_code=status_code,
                ) from http_err
        except httpx.RequestError as req_err:
            msg = f"Network/Request Error for {method} {endpoint}"
            log.error(f"[error]Network Error:[/error] {msg}: {req_err}")
            raise HabiticaAPIError(msg) from req_err
        except json.JSONDecodeError as json_err:
            msg = f"Could not decode successful JSON response from {method} {endpoint}"
            status = response.status_code if response else "N/A"
            body = response.text[:200].replace("\n", "\\n") if response else "N/A"
            log.error(f"[error]JSON Decode Error:[/error] {msg} (Status: {status}, Body: {body})")
            raise ValueError(f"Invalid JSON received from {method} {endpoint}") from json_err
        except ValueError as val_err:
            log.error(f"[error]Data Error:[/error] For {method} {endpoint}: {val_err}")
            raise
        except Exception as e:
            log.error(
                f"[error]Unexpected Error:[/error] During API request ({method} {endpoint}): {type(e).__name__} - {e}"
            )
            raise HabiticaAPIError(f"Unexpected error: {e}") from e

    async def get(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> HabiticaApiResponsePayload:
        return await self._request("GET", endpoint, params=params)

    async def post(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> HabiticaApiResponsePayload:
        return await self._request("POST", endpoint, json=data, params=params)

    async def put(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> HabiticaApiResponsePayload:
        return await self._request("PUT", endpoint, json=data, params=params)

    async def delete(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> HabiticaApiResponsePayload:
        return await self._request("DELETE", endpoint, params=params)

    async def get_user_data(self) -> Optional[Dict[str, Any]]:
        result = await self.get("/user")
        return result if isinstance(result, dict) else None

    async def update_user(self, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        result = await self.put("/user", data=update_data)
        return result if isinstance(result, dict) else None

    async def set_custom_day_start(self, hour: int) -> Optional[Dict[str, Any]]:
        if not 0 <= hour <= 23:
            raise ValueError("Hour must be between 0 and 23")
        result = await self.post("/user/custom-day-start", data={"dayStart": hour})
        return result if isinstance(result, dict) else None

    async def toggle_user_sleep(self) -> Optional[Union[bool, Dict[str, Any]]]:
        result = await self.post("/user/sleep")
        return result

    async def run_cron(self) -> Optional[Dict[str, Any]]:
        result = await self.post("/cron")
        return result if isinstance(result, dict) else None

    async def get_tasks(self, task_type: Optional[str] = None) -> List[Dict[str, Any]]:
        params = {"type": task_type} if task_type else None
        result = await self.get("/tasks/user", params=params)
        return result if isinstance(result, list) else []

    async def create_task(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not data.get("text") or not data.get("type"):
            raise ValueError("Task data requires 'text' and 'type'.")
        result = await self.post("/tasks/user", data=data)
        return result if isinstance(result, dict) else None

    async def update_task(self, task_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        result = await self.put(f"/tasks/{task_id}", data=data)
        return result if isinstance(result, dict) else None

    async def delete_task(self, task_id: str) -> bool:
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        result = await self.delete(f"/tasks/{task_id}")
        return result is None

    async def score_task(self, task_id: str, direction: str = "up") -> Optional[Dict[str, Any]]:
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        if direction not in ["up", "down"]:
            raise ValueError("Direction must be 'up' or 'down'.")
        result = await self.post(f"/tasks/{task_id}/score/{direction}")
        return result if isinstance(result, dict) else None

    async def set_attribute(self, task_id: str, attribute: str) -> Optional[Dict[str, Any]]:
        if attribute not in ["str", "int", "con", "per"]:
            raise ValueError("Invalid attribute. Must be 'str', 'int', 'con', or 'per'.")
        return await self.update_task(task_id, {"attribute": attribute})

    async def move_task_to_position(self, task_id: str, position: int) -> Optional[List[str]]:
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        if not isinstance(position, int):
            raise ValueError("Position must be an integer.")
        result = await self.post(f"/tasks/{task_id}/move/to/{position}")
        return result if isinstance(result, list) else None

    async def clear_completed_todos(self) -> bool:
        result = await self.post("/tasks/clearCompletedTodos")
        return result is None

    async def get_tags(self) -> List[Dict[str, Any]]:
        result = await self.get("/tags")
        return result if isinstance(result, list) else []

    async def create_tag(self, name: str) -> Optional[Dict[str, Any]]:
        if not name or not name.strip():
            raise ValueError("Tag name cannot be empty.")
        result = await self.post("/tags", data={"name": name.strip()})
        return result if isinstance(result, dict) else None

    async def update_tag(self, tag_id: str, name: str) -> Optional[Dict[str, Any]]:
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

    async def add_tag_to_task(self, task_id: str, tag_id: str) -> Optional[Dict[str, Any]]:
        if not task_id or not tag_id:
            raise ValueError("task_id and tag_id cannot be empty.")
        result = await self.post(f"/tasks/{task_id}/tags/{tag_id}")
        return result if isinstance(result, dict) else None

    async def delete_tag_from_task(self, task_id: str, tag_id: str) -> Optional[Dict[str, Any]]:
        if not task_id or not tag_id:
            raise ValueError("task_id and tag_id cannot be empty.")
        result = await self.delete(f"/tasks/{task_id}/tags/{tag_id}")
        return result if isinstance(result, dict) else None

    async def add_checklist_item(self, task_id: str, text: str) -> Optional[Dict[str, Any]]:
        if not task_id or not text:
            raise ValueError("task_id and text cannot be empty.")
        result = await self.post(f"/tasks/{task_id}/checklist", data={"text": text})
        return result if isinstance(result, dict) else None

    async def update_checklist_item(
        self, task_id: str, item_id: str, text: str
    ) -> Optional[Dict[str, Any]]:
        if not task_id or not item_id or text is None:
            raise ValueError("task_id, item_id, and text required.")
        result = await self.put(f"/tasks/{task_id}/checklist/{item_id}", data={"text": text})
        return result if isinstance(result, dict) else None

    async def delete_checklist_item(self, task_id: str, item_id: str) -> Optional[Dict[str, Any]]:
        if not task_id or not item_id:
            raise ValueError("task_id and item_id required.")
        result = await self.delete(f"/tasks/{task_id}/checklist/{item_id}")
        return result if isinstance(result, dict) else None

    async def score_checklist_item(self, task_id: str, item_id: str) -> Optional[Dict[str, Any]]:
        if not task_id or not item_id:
            raise ValueError("task_id and item_id required.")
        result = await self.post(f"/tasks/{task_id}/checklist/{item_id}/score")
        return result if isinstance(result, dict) else None

    async def get_challenges(self, member_only: bool = True, page: int = 0) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"page": page}
        params["member"] = "true" if member_only else "false"
        result = await self.get("/challenges/user", params=params)
        return result if isinstance(result, list) else []

    async def get_all_challenges_paginated(self, member_only: bool = True) -> List[Dict[str, Any]]:
        all_challenges = []
        current_page = 0
        console.log(
            f"Fetching all challenges (member_only={member_only}, paginating)...",
            style="info",
        )
        while True:
            try:
                page_data = await self.get_challenges(member_only=member_only, page=current_page)
                if not page_data:
                    break
                all_challenges.extend(page_data)
                current_page += 1
                await self._wait_for_rate_limit()
            except HabiticaAPIError as e:
                log.error(
                    f"API Error fetching challenges page {current_page}: {e}. Returning partial list.",
                    style="error",
                )
                break
            except Exception as e:
                log.error(
                    f"Unexpected Error fetching challenges page {current_page}: {e}. Returning partial list.",
                    style="error",
                )
                break
        console.log(
            f"Finished fetching challenges. Total: {len(all_challenges)}",
            style="info",
        )
        return all_challenges

    async def create_challenge(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not data.get("name") or not data.get("shortName") or not data.get("group"):
            raise ValueError(
                "Challenge creation requires at least 'name', 'shortName', and 'group' ID."
            )
        result = await self.post("/challenges", data=data)
        return result if isinstance(result, dict) else None

    async def get_challenge_tasks(self, challenge_id: str) -> List[Dict[str, Any]]:
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        result = await self.get(f"/tasks/challenge/{challenge_id}")
        return result if isinstance(result, list) else []

    async def create_challenge_task(
        self, challenge_id: str, task_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        if not task_data.get("text") or not task_data.get("type"):
            raise ValueError("Task data requires 'text' and 'type'.")
        if task_data["type"] not in {"habit", "daily", "todo", "reward"}:
            raise ValueError("Invalid task type.")
        result = await self.post(f"/tasks/challenge/{challenge_id}", data=task_data)
        return result if isinstance(result, dict) else None

    async def unlink_task_from_challenge(self, task_id: str, keep: str = "keep") -> bool:
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        if keep not in ["keep", "remove"]:
            raise ValueError("keep must be 'keep' or 'remove'")
        result = await self.post(f"/tasks/{task_id}/unlink", params={"keep": keep})
        return result is None

    async def unlink_all_challenge_tasks(self, challenge_id: str, keep: str = "keep-all") -> bool:
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        if keep not in ["keep-all", "remove-all"]:
            raise ValueError("keep must be 'keep-all' or 'remove-all'")
        result = await self.post(f"/tasks/unlink-all/{challenge_id}", params={"keep": keep})
        return result is None

    async def leave_challenge(self, challenge_id: str, keep: str = "keep-all") -> bool:
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        if keep not in ["keep-all", "remove-all"]:
            raise ValueError("keep must be 'keep-all' or 'remove-all'")
        result = await self.post(f"/challenges/{challenge_id}/leave", params={"keep": keep})
        return result is None

    async def clone_challenge(self, challenge_id: str) -> Optional[Dict[str, Any]]:
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

    async def get_party_data(self) -> Optional[Dict[str, Any]]:
        result = await self.get("/groups/party")
        return result if isinstance(result, dict) else None

    async def get_quest_status(self) -> Optional[bool]:
        try:
            party_data = await self.get_party_data()
            if party_data is None:
                return None
            quest_info = party_data.get("quest", {})
            return isinstance(quest_info, dict) and quest_info.get("active", False)
        except HabiticaAPIError as e:
            log.error(f"API Error getting quest status: {e}", style="warning")
            return None
        except Exception as e:
            log.error(f"Unexpected error getting quest status: {e}", style="error")
            return None

    async def cast_skill(
        self, spell_id: str, target_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        if not spell_id:
            raise ValueError("spell_id cannot be empty.")
        params = {"targetId": target_id} if target_id else None
        result = await self.post(f"/user/class/cast/{spell_id}", params=params)
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

    async def get_inbox_messages(
        self, page: int = 0, conversation_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        params: Dict[str, Any] = {"page": page}
        if conversation_id:
            params["conversation"] = conversation_id
        result = await self.get("/inbox/messages", params=params)
        return result if isinstance(result, list) else []

    async def send_private_message(
        self, recipient_id: str, message_text: str
    ) -> Optional[Dict[str, Any]]:
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

    async def get_content(self) -> Optional[Dict[str, Any]]:
        result = await self._request("GET", "/content")
        return result if isinstance(result, dict) else None
