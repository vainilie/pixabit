import asyncio
import json
import time
from typing import Any, Optional, Union

import httpx
from pixabit import config

try:
    from pixabit.utils.display import console, print
except ImportError:
    import builtins

    print = builtins.print

    class DummyConsole:
        def print(self, *args, **kwargs):
            builtins.print(*args)

        def log(self, *args, **kwargs):
            builtins.print(*args)

        def print_exception(self, *args, **kwargs):
            import traceback

            traceback.print_exc()

    console = DummyConsole()
DEFAULT_BASE_URL = "https://habitica.com/api/v3"
REQUESTS_PER_MINUTE = 29
MIN_REQUEST_INTERVAL = 60.0 / REQUESTS_PER_MINUTE
HabiticaApiResponsePayload = Optional[Union[dict[str, Any], list[dict[str, Any]]]]


class HabiticaAPIError(Exception):
    def __init__(self, message, status_code=None, error_type=None, response_data=None):
        super().__init__(message)
        self.status_code = status_code
        self.error_type = error_type
        self.response_data = response_data

    def __str__(self):
        details = ""
        if self.status_code is not None:
            details += f"Status={self.status_code}"
        if self.error_type is not None:
            details += f"{', ' if details else ''}Type='{self.error_type}'"
        base_msg = super().__str__()
        return f"HabiticaAPIError: {base_msg}" + (f" ({details})" if details else "")


class HabiticaAPI:
    BASE_URL = DEFAULT_BASE_URL

    def __init__(
        self,
        user_id: Optional[str] = None,
        api_token: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
    ):
        self.user_id = user_id or config.HABITICA_USER_ID
        self.api_token = api_token or config.HABITICA_API_TOKEN
        self.base_url = base_url
        if not self.user_id or not self.api_token:
            raise ValueError("Habitica User ID and API Token are required.")
        self.headers = {
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
                raise ValueError(f"Unexpected JSON structure received: {type(response_data)}")
        except httpx.TimeoutException as timeout_err:
            msg = f"Request timed out ({kwargs.get('timeout', 120)}s) for {method} {endpoint}"
            console.print(f"{msg}: {timeout_err}", style="error")
            raise HabiticaAPIError(msg, status_code=408) from timeout_err
        except httpx.HTTPStatusError as http_err:
            response = http_err.response
            status_code = response.status_code
            error_details = f"HTTP Error {status_code} for {method} {url}"
            try:
                err_data = response.json()
                error_type = err_data.get("error", f"HTTP{status_code}")
                message = err_data.get("message", response.reason_phrase)
                error_details += f" | API: '{error_type}' - '{message}'"
                raise HabiticaAPIError(
                    f"{error_type} - {message}",
                    status_code=status_code,
                    error_type=error_type,
                    response_data=err_data,
                ) from http_err
            except json.JSONDecodeError:
                body_preview = response.text[:200].replace("\n", "\\n")
                error_details += f" | Response Body (non-JSON): {body_preview}"
                console.print(f"Request Failed: {error_details}", style="error")
                raise HabiticaAPIError(
                    f"HTTP Error {status_code} with non-JSON body", status_code=status_code
                ) from http_err
        except httpx.RequestError as req_err:
            msg = f"Network/Request Error for {method} {endpoint}"
            console.print(f"{msg}: {req_err}", style="error")
            raise HabiticaAPIError(msg) from req_err
        except json.JSONDecodeError as json_err:
            msg = f"Could not decode successful JSON response from {method} {endpoint}"
            status = response.status_code if response is not None else "N/A"
            body = response.text[:200].replace("\n", "\\n") if response is not None else "N/A"
            console.print(f"{msg} (Status: {status}, Body: {body})", style="error")
            raise ValueError(f"Invalid JSON received from {method} {endpoint}") from json_err
        except Exception as e:
            console.print(
                f"Unexpected error during API request ({method} {endpoint}): {type(e).__name__} - {e}",
                style="error",
            )
            console.print_exception(show_locals=False)
            raise HabiticaAPIError(f"Unexpected error: {e}") from e

    async def get(
        self, endpoint: str, params: Optional[dict[str, Any]] = None
    ) -> HabiticaApiResponsePayload:
        return await self._request("GET", endpoint, params=params)

    async def post(
        self, endpoint: str, data: Optional[dict[str, Any]] = None
    ) -> HabiticaApiResponsePayload:
        return await self._request("POST", endpoint, json=data)

    async def put(
        self, endpoint: str, data: Optional[dict[str, Any]] = None
    ) -> HabiticaApiResponsePayload:
        return await self._request("PUT", endpoint, json=data)

    async def delete(
        self, endpoint: str, params: Optional[dict[str, Any]] = None
    ) -> HabiticaApiResponsePayload:
        return await self._request("DELETE", endpoint, params=params)

    async def get_user_data(self) -> Optional[dict[str, Any]]:
        result = await self.get("/user")
        return result if isinstance(result, dict) else None

    async def update_user(self, update_data: dict[str, Any]) -> Optional[dict[str, Any]]:
        result = await self.put("/user", data=update_data)
        return result if isinstance(result, dict) else None

    async def set_custom_day_start(self, hour: int) -> Optional[dict[str, Any]]:
        if not 0 <= hour <= 23:
            raise ValueError("Hour must be between 0 and 23")
        return await self.update_user({"preferences.dayStart": hour})

    async def toggle_user_sleep(self) -> Optional[dict[str, Any]]:
        result = await self.post("/user/sleep")
        if isinstance(result, bool):
            return {"sleep": result}
        elif isinstance(result, dict):
            return result
        return None

    async def get_tasks(self, task_type: Optional[str] = None) -> list[dict[str, Any]]:
        params = {"type": task_type} if task_type else None
        result = await self.get("/tasks/user", params=params)
        return result if isinstance(result, list) else []

    async def create_task(self, data: dict[str, Any]) -> Optional[dict[str, Any]]:
        if "text" not in data or "type" not in data:
            raise ValueError("Task data requires 'text' and 'type'.")
        result = await self.post("/tasks/user", data=data)
        return result if isinstance(result, dict) else None

    async def update_task(self, task_id: str, data: dict[str, Any]) -> Optional[dict[str, Any]]:
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        result = await self.put(f"/tasks/{task_id}", data=data)
        return result if isinstance(result, dict) else None

    async def delete_task(self, task_id: str) -> Optional[dict[str, Any]]:
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        result = await self.delete(f"/tasks/{task_id}")
        return result if isinstance(result, dict) else None

    async def score_task(self, task_id: str, direction: str = "up") -> Optional[dict[str, Any]]:
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        if direction not in ["up", "down"]:
            raise ValueError("Direction must be 'up' or 'down'")
        result = await self.post(f"/tasks/{task_id}/score/{direction}")
        return result if isinstance(result, dict) else None

    async def set_attribute(self, task_id: str, attribute: str) -> Optional[dict[str, Any]]:
        if attribute not in ["str", "int", "con", "per"]:
            raise ValueError("Invalid attribute.")
        return await self.update_task(task_id, {"attribute": attribute})

    async def move_task_to_position(self, task_id: str, position: int) -> Optional[list[str]]:
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        if position not in [0, -1]:
            raise ValueError("Position must be 0 or -1.")
        result = await self.post(f"/tasks/{task_id}/move/to/{position}")
        return result if isinstance(result, list) else None

    async def get_tags(self) -> list[dict[str, Any]]:
        result = await self.get("/tags")
        return result if isinstance(result, list) else []

    async def create_tag(self, name: str) -> Optional[dict[str, Any]]:
        if not name:
            raise ValueError("Tag name cannot be empty.")
        result = await self.post("/tags", data={"name": name})
        return result if isinstance(result, dict) else None

    async def update_tag(self, tag_id: str, name: str) -> Optional[dict[str, Any]]:
        if not tag_id:
            raise ValueError("tag_id cannot be empty.")
        if not name:
            raise ValueError("New tag name cannot be empty.")
        result = await self.put(f"/tags/{tag_id}", data={"name": name})
        return result if isinstance(result, dict) else None

    async def delete_tag(self, tag_id: str) -> Optional[dict[str, Any]]:
        if not tag_id:
            raise ValueError("tag_id cannot be empty.")
        result = await self.delete(f"/tags/{tag_id}")
        return result if isinstance(result, dict) else None

    async def add_tag_to_task(self, task_id: str, tag_id: str) -> Optional[dict[str, Any]]:
        if not task_id or not tag_id:
            raise ValueError("task_id and tag_id cannot be empty.")
        result = await self.post(f"/tasks/{task_id}/tags/{tag_id}")
        return result if isinstance(result, dict) else None

    async def delete_tag_from_task(self, task_id: str, tag_id: str) -> Optional[dict[str, Any]]:
        if not task_id or not tag_id:
            raise ValueError("task_id and tag_id cannot be empty.")
        result = await self.delete(f"/tasks/{task_id}/tags/{tag_id}")
        return result if isinstance(result, dict) else None

    async def add_checklist_item(self, task_id: str, text: str) -> Optional[dict[str, Any]]:
        if not task_id or not text:
            raise ValueError("task_id and text cannot be empty.")
        result = await self.post(f"/tasks/{task_id}/checklist", data={"text": text})
        return result if isinstance(result, dict) else None

    async def update_checklist_item(
        self, task_id: str, item_id: str, text: str
    ) -> Optional[dict[str, Any]]:
        if not task_id or not item_id or text is None:
            raise ValueError("task_id, item_id, and text are required.")
        result = await self.put(f"/tasks/{task_id}/checklist/{item_id}", data={"text": text})
        return result if isinstance(result, dict) else None

    async def delete_checklist_item(self, task_id: str, item_id: str) -> Optional[dict[str, Any]]:
        if not task_id or not item_id:
            raise ValueError("task_id and item_id cannot be empty.")
        result = await self.delete(f"/tasks/{task_id}/checklist/{item_id}")
        return result if isinstance(result, dict) else None

    async def score_checklist_item(self, task_id: str, item_id: str) -> Optional[dict[str, Any]]:
        if not task_id or not item_id:
            raise ValueError("task_id and item_id cannot be empty.")
        result = await self.post(f"/tasks/{task_id}/checklist/{item_id}/score")
        return result if isinstance(result, dict) else None

    async def get_challenges(self, member_only: bool = True) -> list[dict[str, Any]]:
        all_challenges = []
        page = 0
        member_param = "true" if member_only else "false"
        console.log(
            f"Fetching challenges (member_only={member_only}, paginating)...", style="info"
        )
        while True:
            try:
                page_data = await self.get(
                    "/challenges/user", params={"member": member_param, "page": page}
                )
                if isinstance(page_data, list):
                    if not page_data:
                        break
                    all_challenges.extend(page_data)
                    page += 1
                else:
                    console.print(
                        f"Warning: Expected list from /challenges/user page {page}, got {type(page_data)}. Stopping.",
                        style="warning",
                    )
                    break
            except HabiticaAPIError as e:
                console.print(
                    f"API Error fetching challenges page {page}: {e}. Stopping.", style="error"
                )
                break
            except Exception as e:
                console.print(
                    f"Unexpected Error fetching challenges page {page}: {e}. Stopping.",
                    style="error",
                )
                break
        console.log(f"Finished fetching challenges. Total: {len(all_challenges)}", style="info")
        return all_challenges

    async def create_challenge(self, data: dict[str, Any]) -> Optional[dict[str, Any]]:
        result = await self.post("/challenges", data=data)
        return result if isinstance(result, dict) else None

    async def get_challenge_tasks(self, challenge_id: str) -> list[dict[str, Any]]:
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        result = await self.get(f"/tasks/challenge/{challenge_id}")
        return result if isinstance(result, list) else []

    async def unlink_task_from_challenge(
        self, task_id: str, keep: str = "keep"
    ) -> Optional[dict[str, Any]]:
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        if keep not in ["keep", "remove"]:
            raise ValueError("keep must be 'keep' or 'remove'")
        result = await self.post(f"/tasks/unlink-one/{task_id}?keep={keep}")
        return result if isinstance(result, dict) else None

    async def unlink_all_challenge_tasks(
        self, challenge_id: str, keep: str = "keep-all"
    ) -> Optional[dict[str, Any]]:
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        if keep not in ["keep-all", "remove-all"]:
            raise ValueError("keep must be 'keep-all' or 'remove-all'")
        result = await self.post(f"/tasks/unlink-all/{challenge_id}?keep={keep}")
        return result if isinstance(result, dict) else None

    async def leave_challenge(
        self, challenge_id: str, keep: str = "keep-all"
    ) -> Optional[dict[str, Any]]:
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        if keep not in ["keep-all", "remove-all"]:
            raise ValueError("keep must be 'keep-all' or 'remove-all'")
        result = await self.post(f"/challenges/{challenge_id}/leave?keep={keep}")
        return result if isinstance(result, dict) else None

    async def get_party_data(self) -> Optional[dict[str, Any]]:
        result = await self.get("/groups/party")
        return result if isinstance(result, dict) else None

    async def get_quest_status(self) -> bool:
        try:
            party_data = await self.get_party_data()
            return (
                party_data is not None and party_data.get("quest", {}).get("active", False) is True
            )
        except Exception as e:
            console.print(f"Could not get quest status: {e}", style="warning")
            return False

    async def get_inbox_messages(self, page: int = 0) -> list[dict[str, Any]]:
        result = await self.get("/inbox/messages", params={"page": page})
        return result if isinstance(result, list) else []

    async def get_content(self) -> Optional[dict[str, Any]]:
        result = await self._request("GET", "/content")
        return result if isinstance(result, dict) else None
