import time
from typing import Any, Optional, Union, dict, list

import requests

from pixabit import config
from pixabit.utils.display import console

DEFAULT_BASE_URL = "https://habitica.com/api/v3"
REQUESTS_PER_MINUTE = 29
MIN_REQUEST_INTERVAL = 60.0 / REQUESTS_PER_MINUTE
HabiticaApiResponse = Optional[Union[dict[str, Any], list[dict[str, Any]]]]


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
            raise ValueError(
                "Habitica User ID and API Token are required. Check .env file or provide directly."
            )
        self.headers = {
            "x-api-user": self.user_id,
            "x-api-key": self.api_token,
            "Content-Type": "application/json",
            "x-client": "pixabit-cli-your_identifier",
        }
        self.last_request_time: float = 0.0
        self.request_interval: float = MIN_REQUEST_INTERVAL

    def _wait_for_rate_limit(self) -> None:
        current_time = time.monotonic()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.request_interval:
            wait_time = self.request_interval - time_since_last
            time.sleep(wait_time)
        self.last_request_time = time.monotonic()

    def _request(self, method: str, endpoint: str, **kwargs: Any) -> HabiticaApiResponse:
        self._wait_for_rate_limit()
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        response: Optional[requests.Response] = None
        try:
            kwargs.setdefault("timeout", 120)
            response = requests.request(method, url, headers=self.headers, **kwargs)
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
                    err_msg = (
                        f"Habitica API Error ({response.status_code}): {error_type} - {message}"
                    )
                    console.print(err_msg, style="error")
                    raise requests.exceptions.RequestException(err_msg)
            else:
                if isinstance(response_data, (dict, list)):
                    return response_data
                else:
                    console.print(
                        f"Warning: Unexpected non-dict/list JSON from {method} {endpoint}: {type(response_data)}",
                        style="warning",
                    )
                    raise ValueError("Unexpected JSON structure received from API.")
        except requests.exceptions.HTTPError as http_err:
            error_details = f"HTTP Error: {http_err}"
            if http_err.response is not None:
                response = http_err.response
                error_details += f" | Status Code: {response.status_code}"
                try:
                    err_data = response.json()
                    error_type = err_data.get("error", "N/A")
                    message = err_data.get("message", "N/A")
                    error_details += f" | API Error: '{error_type}' | Message: '{message}'"
                except requests.exceptions.JSONDecodeError:
                    error_details += f" | Response Body (non-JSON): {response.text[:200]}"
            console.print(f"Request Failed: {error_details}", style="error")
            raise requests.exceptions.RequestException(error_details) from http_err
        except requests.exceptions.Timeout as timeout_err:
            msg = f"Request timed out ({kwargs.get('timeout')}s) for {method} {endpoint}"
            console.print(f"{msg}: {timeout_err}", style="error")
            raise requests.exceptions.RequestException(msg) from timeout_err
        except requests.exceptions.JSONDecodeError as json_err:
            msg = f"Could not decode JSON response from {method} {endpoint}"
            status = response.status_code if response is not None else "N/A"
            body = response.text[:200] if response is not None else "N/A"
            console.print(f"{msg}", style="error")
            console.print(f"Response Status: {status}, Body starts with: {body}", style="subtle")
            raise ValueError(f"Invalid JSON received from {method} {endpoint}") from json_err
        except requests.exceptions.RequestException as req_err:
            msg = f"Network/Request Error for {method} {endpoint}"
            console.print(f"{msg}: {req_err}", style="error")
            raise
        except Exception as e:
            console.print(
                f"Unexpected error during API request: {type(e).__name__} - {e}", style="error"
            )
            console.print_exception(show_locals=False)
            raise

    def get(self, endpoint: str, params: Optional[dict[str, Any]] = None) -> HabiticaApiResponse:
        return self._request("GET", endpoint, params=params)

    def post(self, endpoint: str, data: Optional[dict[str, Any]] = None) -> HabiticaApiResponse:
        return self._request("POST", endpoint, json=data)

    def put(self, endpoint: str, data: Optional[dict[str, Any]] = None) -> HabiticaApiResponse:
        return self._request("PUT", endpoint, json=data)

    def delete(
        self, endpoint: str, params: Optional[dict[str, Any]] = None
    ) -> HabiticaApiResponse:
        return self._request("DELETE", endpoint, params=params)

    def get_user_data(self) -> Optional[dict[str, Any]]:
        result = self.get("/user")
        return result if isinstance(result, dict) else None

    def update_user(self, update_data: dict[str, Any]) -> Optional[dict[str, Any]]:
        result = self.put("/user", data=update_data)
        return result if isinstance(result, dict) else None

    def set_custom_day_start(self, hour: int) -> Optional[dict[str, Any]]:
        if not 0 <= hour <= 23:
            raise ValueError("Hour must be between 0 and 23")
        return self.update_user({"preferences.dayStart": hour})

    def toggle_user_sleep(self) -> Optional[dict[str, Any]]:
        result = self.post("/user/sleep")
        if isinstance(result, bool):
            return {"sleep": result}
        elif isinstance(result, dict):
            return result
        return None

    def get_tasks(self, task_type: Optional[str] = None) -> list[dict[str, Any]]:
        params = {"type": task_type} if task_type else None
        result = self.get("/tasks/user", params=params)
        return result if isinstance(result, list) else []

    def create_task(self, data: dict[str, Any]) -> Optional[dict[str, Any]]:
        if "text" not in data or "type" not in data:
            raise ValueError("Task creation data must include 'text' and 'type'.")
        result = self.post("/tasks/user", data=data)
        return result if isinstance(result, dict) else None

    def update_task(self, task_id: str, data: dict[str, Any]) -> Optional[dict[str, Any]]:
        result = self.put(f"/tasks/{task_id}", data=data)
        return result if isinstance(result, dict) else None

    def delete_task(self, task_id: str) -> Optional[dict[str, Any]]:
        result = self.delete(f"/tasks/{task_id}")
        return result if isinstance(result, dict) else None

    def score_task(self, task_id: str, direction: str = "up") -> Optional[dict[str, Any]]:
        if direction not in ["up", "down"]:
            raise ValueError("Direction must be 'up' or 'down'")
        result = self.post(f"/tasks/{task_id}/score/{direction}")
        return result if isinstance(result, dict) else None

    def set_attribute(self, task_id: str, attribute: str) -> Optional[dict[str, Any]]:
        if attribute not in ["str", "int", "con", "per"]:
            raise ValueError("Attribute must be one of 'str', 'int', 'con', 'per'")
        return self.update_task(task_id, {"attribute": attribute})

    def move_task_to_position(self, task_id: str, position: int) -> Optional[list[dict[str, Any]]]:
        if position not in [0, -1]:
            raise ValueError("Position must be 0 (to move to top) or -1 (to move to bottom).")
        result = self.post(f"/tasks/{task_id}/move/to/{position}")
        return result if isinstance(result, list) else None

    def get_tags(self) -> list[dict[str, Any]]:
        result = self.get("/tags")
        return result if isinstance(result, list) else []

    def create_tag(self, name: str) -> Optional[dict[str, Any]]:
        result = self.post("/tags", data={"name": name})
        return result if isinstance(result, dict) else None

    def update_tag(self, tag_id: str, name: str) -> Optional[dict[str, Any]]:
        result = self.put(f"/tags/{tag_id}", data={"name": name})
        return result if isinstance(result, dict) else None

    def delete_tag(self, tag_id: str) -> Optional[dict[str, Any]]:
        result = self.delete(f"/tags/{tag_id}")
        return result if isinstance(result, dict) else None

    def add_tag_to_task(self, task_id: str, tag_id: str) -> Optional[dict[str, Any]]:
        result = self.post(f"/tasks/{task_id}/tags/{tag_id}")
        return result if isinstance(result, dict) else None

    def delete_tag_from_task(self, task_id: str, tag_id: str) -> Optional[dict[str, Any]]:
        result = self.delete(f"/tasks/{task_id}/tags/{tag_id}")
        return result if isinstance(result, dict) else None

    def add_checklist_item(self, task_id: str, text: str) -> Optional[dict[str, Any]]:
        result = self.post(f"/tasks/{task_id}/checklist", data={"text": text})
        return result if isinstance(result, dict) else None

    def update_checklist_item(
        self, task_id: str, item_id: str, text: str
    ) -> Optional[dict[str, Any]]:
        result = self.put(f"/tasks/{task_id}/checklist/{item_id}", data={"text": text})
        return result if isinstance(result, dict) else None

    def delete_checklist_item(self, task_id: str, item_id: str) -> Optional[dict[str, Any]]:
        result = self.delete(f"/tasks/{task_id}/checklist/{item_id}")
        return result if isinstance(result, dict) else None

    def score_checklist_item(self, task_id: str, item_id: str) -> Optional[dict[str, Any]]:
        result = self.post(f"/tasks/{task_id}/checklist/{item_id}/score")
        return result if isinstance(result, dict) else None

    def get_challenges(self, member_only: bool = True) -> list[dict[str, Any]]:
        all_challenges = []
        page = 0
        member_param = "true" if member_only else "false"
        console.log(
            f"Fetching challenges (member_only={member_only}, paginating)...", style="info"
        )
        while True:
            try:
                challenge_page_data = self.get(
                    "/challenges/user", params={"member": member_param, "page": page}
                )
                if isinstance(challenge_page_data, list):
                    if not challenge_page_data:
                        break
                    all_challenges.extend(challenge_page_data)
                    page += 1
                else:
                    console.print(
                        f"Warning: Expected list from /challenges/user page {page}, got {type(challenge_page_data)}. Stopping pagination.",
                        style="warning",
                    )
                    break
            except (requests.exceptions.RequestException, ValueError) as e:
                console.print(
                    f"Error fetching challenges page {page}: {e}. Stopping pagination.",
                    style="error",
                )
                break
        console.log(
            f"Finished fetching challenges. Total found: {len(all_challenges)}", style="info"
        )
        return all_challenges

    def create_challenge(self, data: dict[str, Any]) -> Optional[dict[str, Any]]:
        result = self.post("/challenges", data=data)
        return result if isinstance(result, dict) else None

    def get_challenge_tasks(self, challenge_id: str) -> list[dict[str, Any]]:
        result = self.get(f"/tasks/challenge/{challenge_id}")
        return result if isinstance(result, list) else []

    def unlink_task_from_challenge(
        self, task_id: str, keep: str = "keep"
    ) -> Optional[dict[str, Any]]:
        if keep not in ["keep", "remove"]:
            raise ValueError("keep must be 'keep' or 'remove'")
        result = self.post(f"/tasks/unlink-one/{task_id}?keep={keep}")
        return result if isinstance(result, dict) else None

    def unlink_all_challenge_tasks(
        self, challenge_id: str, keep: str = "keep-all"
    ) -> Optional[dict[str, Any]]:
        if keep not in ["keep-all", "remove-all"]:
            raise ValueError("keep must be 'keep-all' or 'remove-all'")
        result = self.post(f"/tasks/unlink-all/{challenge_id}?keep={keep}")
        return result if isinstance(result, dict) else None

    def leave_challenge(
        self, challenge_id: str, keep: str = "keep-all"
    ) -> Optional[dict[str, Any]]:
        if keep not in ["keep-all", "remove-all"]:
            raise ValueError("keep must be 'keep-all' or 'remove-all'")
        result = self.post(f"/challenges/{challenge_id}/leave?keep={keep}")
        return result if isinstance(result, dict) else None

    def get_party_data(self) -> Optional[dict[str, Any]]:
        result = self.get("/groups/party")
        return result if isinstance(result, dict) else None

    def get_quest_status(self) -> bool:
        try:
            party_data = self.get_party_data()
            return (
                party_data is not None and party_data.get("quest", {}).get("active", False) is True
            )
        except requests.exceptions.RequestException as e:
            console.print(f"Could not get party data for quest status: {e}", style="warning")
            return False
        except ValueError as e:
            console.print(f"Invalid data received for party data: {e}", style="warning")
            return False

    def get_inbox_messages(self, page: int = 0) -> list[dict[str, Any]]:
        result = self.get("/inbox/messages", params={"page": page})
        return result if isinstance(result, list) else []

    def get_content(self) -> Optional[dict[str, Any]]:
        result = self._request("GET", "/content")
        return result if isinstance(result, dict) else None
