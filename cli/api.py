# pixabit/cli/api.py (LEGACY - Sync Version)

# SECTION: MODULE DOCSTRING
"""Provides HabiticaAPI client for interacting with the Habitica API v3 (Synchronous Version).

Handles authentication, rate limiting, standard HTTP methods, and provides
convenience methods for common API endpoints. This is the synchronous version
used by the original Rich-based CLI. Kept for reference.
"""

# SECTION: IMPORTS
import time
from typing import Any, Dict, List, Optional, Union  # Keep Dict/List

import requests

# Local Imports (Adjust path based on execution context)
try:
    from pixabit.cli import config  # Import config from within cli package
    from pixabit.helpers._rich import (  # Use themed console/print
        console,
        print,
    )
except ImportError:
    # Fallback imports
    import builtins

    print = builtins.print

    class DummyConsole:
        def print(self, *args: Any, **kwargs: Any) -> None:
            builtins.print(*args)

        def log(self, *args: Any, **kwargs: Any) -> None:
            builtins.print("LOG:", *args)

        def print_exception(self, *args: Any, **kwargs: Any) -> None:
            import traceback

            traceback.print_exc()

    console = DummyConsole()

    class DummyConfig:  # Dummy config
        HABITICA_USER_ID = "DUMMY_USER_ID"
        HABITICA_API_TOKEN = "DUMMY_API_TOKEN"

    config = DummyConfig()  # type: ignore
    print("Warning: Using fallback imports/config in cli/api.py")


# SECTION: CONSTANTS
DEFAULT_BASE_URL: str = "https://habitica.com/api/v3"
REQUESTS_PER_MINUTE: int = 29
MIN_REQUEST_INTERVAL: float = 60.0 / REQUESTS_PER_MINUTE  # ~2.07 seconds

# Type hint for common API response data payload
HabiticaApiResponsePayload = Optional[
    Union[dict[str, Any], list[dict[str, Any]]]
]


# KLASS: HabiticaAPI (Legacy Sync Version)
class HabiticaAPI:
    """Synchronous client class for Habitica API v3 interactions.

    Handles auth, rate limits, requests. Used by the original CLI app.

    Attributes:
        user_id: Habitica User ID.
        api_token: Habitica API Token.
        base_url: Base URL for the API.
        headers: Standard request headers including auth.
        request_interval: Min seconds between requests for rate limiting.
        last_request_time: Timestamp of the last request (monotonic).
    """

    BASE_URL: str = DEFAULT_BASE_URL

    # FUNC: __init__
    def __init__(
        self,
        user_id: str | None = None,
        api_token: str | None = None,
        base_url: str = DEFAULT_BASE_URL,
    ):
        """Initializes the synchronous HabiticaAPI client.

        Args:
            user_id: Habitica User ID. Defaults to config.HABITICA_USER_ID.
            api_token: Habitica API Token. Defaults to config.HABITICA_API_TOKEN.
            base_url: API base URL.

        Raises:
            ValueError: If User ID or API Token is missing after checking args/config.
        """
        self.user_id: str = user_id or config.HABITICA_USER_ID
        self.api_token: str = api_token or config.HABITICA_API_TOKEN
        self.base_url: str = base_url

        if not self.user_id or not self.api_token or "DUMMY" in self.user_id:
            raise ValueError(
                "Habitica User ID and API Token are required and must be valid."
            )

        self.headers: dict[str, str] = {
            "x-api-user": self.user_id,
            "x-api-key": self.api_token,
            "Content-Type": "application/json",
            "x-client": "pixabit-cli-legacy",  # Identify client
        }

        # Rate limiting attributes
        self.last_request_time: float = 0.0
        self.request_interval: float = MIN_REQUEST_INTERVAL

    # SECTION: Internal Methods

    # FUNC: _wait_for_rate_limit
    def _wait_for_rate_limit(self) -> None:
        """Sleeps if necessary to comply with the rate limit (synchronous)."""
        current_time = time.monotonic()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.request_interval:
            wait_time = self.request_interval - time_since_last
            # console.log(f"Rate limit: waiting {wait_time:.2f}s", style="subtle") # Optional debug
            time.sleep(wait_time)
        self.last_request_time = (
            time.monotonic()
        )  # Update time *after* potential sleep

    # FUNC: _request
    def _request(
        self, method: str, endpoint: str, **kwargs: Any
    ) -> HabiticaApiResponsePayload:
        """Internal sync method for making API requests with rate limiting & error handling.

        Args:
            method: HTTP method ('GET', 'POST', 'PUT', 'DELETE').
            endpoint: API endpoint path (e.g., '/user').
            kwargs: Additional arguments for `requests.request` (e.g., json, params).

        Returns:
            The JSON response payload from 'data' field or raw JSON, or None.

        Raises:
            requests.exceptions.RequestException: For network or API errors after logging.
            ValueError: For unexpected JSON structure on success.
        """
        self._wait_for_rate_limit()
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        response: Optional[requests.Response] = None
        # console.log(f"Sync Request: {method} {url}", style="subtle") # Debug

        try:
            kwargs.setdefault("timeout", 120)  # Generous timeout
            response = requests.request(
                method, url, headers=self.headers, **kwargs
            )
            response.raise_for_status()  # Raise HTTPError for 4xx/5xx

            if response.status_code == 204 or not response.content:
                return None  # Handle No Content

            response_data = response.json()

            # Handle Habitica's standard wrapper
            if isinstance(response_data, dict) and "success" in response_data:
                if response_data["success"]:
                    return response_data.get("data")  # Return 'data' payload
                else:
                    # API reported failure
                    error_type = response_data.get(
                        "error", "Unknown Habitica Error"
                    )
                    message = response_data.get(
                        "message", "No message provided."
                    )
                    err_msg = f"Habitica API Error ({response.status_code}): {error_type} - {message}"
                    console.print(f"[error]{err_msg}[/error]")
                    # Raise a general RequestException after logging
                    raise requests.exceptions.RequestException(
                        err_msg, response=response
                    )
            # Handle successful responses WITHOUT the standard wrapper
            elif isinstance(response_data, (dict, list)):
                # console.log(f"Response for {method} {endpoint} OK (no wrapper). Returning raw JSON.", style="info")
                return response_data
            else:
                # Unexpected JSON type for success
                console.print(
                    f"[warning]Warning:[/warning] Unexpected non-dict/list JSON from {method} {endpoint}: {type(response_data).__name__}"
                )
                raise ValueError("Unexpected JSON structure received from API.")

        # --- Exception Handling ---
        except requests.exceptions.HTTPError as http_err:
            error_details = f"HTTP Error: {http_err}"
            if http_err.response is not None:
                response = http_err.response
                error_details += f" | Status Code: {response.status_code}"
                try:
                    err_data = response.json()
                    error_type = err_data.get("error", "N/A")
                    message = err_data.get("message", "N/A")
                    error_details += (
                        f" | API Error: '{error_type}' | Message: '{message}'"
                    )
                except requests.exceptions.JSONDecodeError:
                    error_details += (
                        f" | Response Body (non-JSON): {response.text[:200]}"
                    )
            console.print(f"[error]Request Failed:[/error] {error_details}")
            raise requests.exceptions.RequestException(
                error_details, response=response
            ) from http_err

        except requests.exceptions.Timeout as timeout_err:
            msg = f"Request timed out ({kwargs.get('timeout')}s) for {method} {endpoint}"
            console.print(f"[error]Timeout Error:[/error] {msg}: {timeout_err}")
            raise requests.exceptions.RequestException(msg) from timeout_err

        except requests.exceptions.JSONDecodeError as json_err:
            msg = f"Could not decode JSON response from {method} {endpoint}"
            status = response.status_code if response is not None else "N/A"
            body = response.text[:200] if response is not None else "N/A"
            console.print(
                f"[error]JSON Decode Error:[/error] {msg} (Status: {status}, Body: {body})"
            )
            raise ValueError(
                f"Invalid JSON received from {method} {endpoint}"
            ) from json_err

        except requests.exceptions.RequestException as req_err:
            msg = f"Network/Request Error for {method} {endpoint}"
            console.print(f"[error]Network Error:[/error] {msg}: {req_err}")
            raise  # Re-raise the original exception

        except Exception as e:
            console.print(
                f"[error]Unexpected error during API request:[/error] {type(e).__name__} - {e}"
            )
            # console.print_exception(show_locals=False) # Optional traceback
            raise  # Re-raise

    # SECTION: Core HTTP Request Methods (Sync)

    # FUNC: get
    def get(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> HabiticaApiResponsePayload:
        """Sends sync GET request. Returns JSON data or None."""
        return self._request("GET", endpoint, params=params)

    # FUNC: post
    def post(
        self, endpoint: str, data: dict[str, Any] | None = None
    ) -> HabiticaApiResponsePayload:
        """Sends sync POST request with JSON data. Returns JSON data or None."""
        return self._request("POST", endpoint, json=data)

    # FUNC: put
    def put(
        self, endpoint: str, data: dict[str, Any] | None = None
    ) -> HabiticaApiResponsePayload:
        """Sends sync PUT request with JSON data. Returns JSON data or None."""
        return self._request("PUT", endpoint, json=data)

    # FUNC: delete
    def delete(
        self, endpoint: str, params: dict[str, Any] | None = None
    ) -> HabiticaApiResponsePayload:
        """Sends sync DELETE request. Returns JSON data or None."""
        return self._request("DELETE", endpoint, params=params)

    # --- Convenience Methods (Keep existing signatures, add return types) ---
    # (These mirror the async versions but call the sync _request)

    # FUNC: get_user_data
    def get_user_data(self) -> dict[str, Any] | None:
        result = self.get("/user")
        return result if isinstance(result, dict) else None

    # FUNC: update_user
    def update_user(self, update_data: dict[str, Any]) -> dict[str, Any] | None:
        result = self.put("/user", data=update_data)
        return result if isinstance(result, dict) else None

    # FUNC: set_custom_day_start
    def set_custom_day_start(self, hour: int) -> dict[str, Any] | None:
        if not 0 <= hour <= 23:
            raise ValueError("Hour must be between 0 and 23")
        # V3 used PUT /user
        return self.update_user({"preferences.dayStart": hour})

    # FUNC: toggle_user_sleep
    def toggle_user_sleep(self) -> Union[bool, dict[str, Any]] | None:
        result = self.post("/user/sleep")
        return result  # V3 'data' is boolean

    # FUNC: get_tasks
    def get_tasks(self, task_type: str | None = None) -> list[dict[str, Any]]:
        params = {"type": task_type} if task_type else None
        result = self.get("/tasks/user", params=params)
        return result if isinstance(result, list) else []

    # FUNC: create_task
    def create_task(self, data: dict[str, Any]) -> dict[str, Any] | None:
        if "text" not in data or "type" not in data:
            raise ValueError("Task creation requires 'text' and 'type'.")
        result = self.post("/tasks/user", data=data)
        return result if isinstance(result, dict) else None

    # FUNC: update_task
    def update_task(
        self, task_id: str, data: dict[str, Any]
    ) -> dict[str, Any] | None:
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        result = self.put(f"/tasks/{task_id}", data=data)
        return result if isinstance(result, dict) else None

    # FUNC: delete_task
    def delete_task(self, task_id: str) -> bool:
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        result = self.delete(f"/tasks/{task_id}")
        return result is None  # Success if 204 or data=None

    # FUNC: score_task
    def score_task(
        self, task_id: str, direction: str = "up"
    ) -> dict[str, Any] | None:
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        if direction not in ["up", "down"]:
            raise ValueError("Direction must be 'up' or 'down'.")
        result = self.post(f"/tasks/{task_id}/score/{direction}")
        return result if isinstance(result, dict) else None

    # FUNC: set_attribute
    def set_attribute(
        self, task_id: str, attribute: str
    ) -> dict[str, Any] | None:
        if attribute not in ["str", "int", "con", "per"]:
            raise ValueError("Invalid attribute.")
        return self.update_task(task_id, {"attribute": attribute})

    # FUNC: move_task_to_position
    def move_task_to_position(
        self, task_id: str, position: int
    ) -> list[str] | None:
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        if not isinstance(position, int):
            raise ValueError("Position must be an integer.")
        result = self.post(f"/tasks/{task_id}/move/to/{position}")
        return result if isinstance(result, list) else None

    # FUNC: get_tags
    def get_tags(self) -> list[dict[str, Any]]:
        result = self.get("/tags")
        return result if isinstance(result, list) else []

    # FUNC: create_tag
    def create_tag(self, name: str) -> dict[str, Any] | None:
        if not name or not name.strip():
            raise ValueError("Tag name cannot be empty.")
        result = self.post("/tags", data={"name": name.strip()})
        return result if isinstance(result, dict) else None

    # FUNC: update_tag
    def update_tag(self, tag_id: str, name: str) -> dict[str, Any] | None:
        if not tag_id:
            raise ValueError("tag_id cannot be empty.")
        if not name or not name.strip():
            raise ValueError("New tag name cannot be empty.")
        result = self.put(f"/tags/{tag_id}", data={"name": name.strip()})
        return result if isinstance(result, dict) else None

    # FUNC: delete_tag
    def delete_tag(self, tag_id: str) -> bool:
        if not tag_id:
            raise ValueError("tag_id cannot be empty.")
        result = self.delete(f"/tags/{tag_id}")
        return result is None

    # FUNC: add_tag_to_task
    def add_tag_to_task(
        self, task_id: str, tag_id: str
    ) -> dict[str, Any] | None:
        if not task_id or not tag_id:
            raise ValueError("task_id and tag_id cannot be empty.")
        result = self.post(f"/tasks/{task_id}/tags/{tag_id}")
        return result if isinstance(result, dict) else None

    # FUNC: delete_tag_from_task
    def delete_tag_from_task(
        self, task_id: str, tag_id: str
    ) -> dict[str, Any] | None:
        if not task_id or not tag_id:
            raise ValueError("task_id and tag_id cannot be empty.")
        result = self.delete(f"/tasks/{task_id}/tags/{tag_id}")
        return result if isinstance(result, dict) else None

    # ... Add other sync convenience methods (checklist, challenges, etc.) similarly ...
    # ... mirroring the async versions but using sync self._request ...

    # FUNC: get_challenges
    def get_challenges(
        self, member_only: bool = True, page: int = 0
    ) -> list[dict[str, Any]]:
        params: dict[str, Any] = {
            "page": page,
            "member": "true" if member_only else "false",
        }
        result = self.get("/challenges/user", params=params)
        return result if isinstance(result, list) else []

    # FUNC: get_all_challenges_paginated
    def get_all_challenges_paginated(
        self, member_only: bool = True
    ) -> list[dict[str, Any]]:
        """Sync helper to fetch ALL challenges using pagination."""
        all_challenges = []
        current_page = 0
        console.log(
            f"Sync: Fetching all challenges (member_only={member_only}, paginating)...",
            style="info",
        )
        while True:
            try:
                page_data = self.get_challenges(
                    member_only=member_only, page=current_page
                )
                if not page_data:
                    break
                all_challenges.extend(page_data)
                current_page += 1
            except requests.exceptions.RequestException as e:
                console.print(
                    f"API Error fetching challenges page {current_page}: {e}. Returning partial list.",
                    style="error",
                )
                break
            except Exception as e:
                console.print(
                    f"Unexpected Error fetching challenges page {current_page}: {e}. Returning partial list.",
                    style="error",
                )
                break
        console.log(
            f"Sync: Finished fetching challenges. Total: {len(all_challenges)}",
            style="info",
        )
        return all_challenges

    # FUNC: leave_challenge
    def leave_challenge(
        self, challenge_id: str, keep: str = "keep-all"
    ) -> bool:
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        if keep not in ["keep-all", "remove-all"]:
            raise ValueError("keep must be 'keep-all' or 'remove-all'")
        result = self.post(
            f"/challenges/{challenge_id}/leave", params={"keep": keep}
        )
        return result is None

    # FUNC: unlink_task_from_challenge
    def unlink_task_from_challenge(
        self, task_id: str, keep: str = "keep"
    ) -> bool:
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        if keep not in ["keep", "remove"]:
            raise ValueError("keep must be 'keep' or 'remove'")
        result = self.post(f"/tasks/{task_id}/unlink", params={"keep": keep})
        return result is None

    # FUNC: unlink_all_challenge_tasks
    def unlink_all_challenge_tasks(
        self, challenge_id: str, keep: str = "keep-all"
    ) -> bool:
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        if keep not in ["keep-all", "remove-all"]:
            raise ValueError("keep must be 'keep-all' or 'remove-all'")
        result = self.post(
            f"/tasks/unlink-all/{challenge_id}", params={"keep": keep}
        )
        return result is None

    # FUNC: get_party_data
    def get_party_data(self) -> dict[str, Any] | None:
        result = self.get("/groups/party")
        return result if isinstance(result, dict) else None

    # FUNC: get_quest_status
    def get_quest_status(self) -> bool | None:
        try:
            party_data = self.get_party_data()
            if party_data is None:
                return None
            quest_info = party_data.get("quest", {})
            return isinstance(quest_info, dict) and quest_info.get(
                "active", False
            )
        except requests.exceptions.RequestException as e:
            console.print(
                f"API Error getting quest status: {e}", style="warning"
            )
            return None
        except Exception as e:
            console.print(
                f"Unexpected error getting quest status: {e}", style="error"
            )
            return None

    # FUNC: get_content
    def get_content(self) -> dict[str, Any] | None:
        result = self._request("GET", "/content")  # Use internal request
        return result if isinstance(result, dict) else None
