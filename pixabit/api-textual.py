# pixabit/api.py

# SECTION: - MODULE DOCSTRING
"""Provides an asynchronous HabiticaAPI client for interacting with the Habitica API v3.

This module contains the `HabiticaAPI` class, which simplifies making calls
to the Habitica API (v3) using `httpx` for non-blocking network operations.
It handles authentication using User ID and API Token (read from config),
implements automatic rate limiting, and offers async wrappers for standard
HTTP methods (GET, POST, PUT, DELETE) and convenience methods for common
endpoints like user data, tasks, tags, challenges, party, inbox, and content.
"""

# SECTION: - IMPORTS
import asyncio
import json
import time
from typing import Any, Optional, Union  # Keep necessary typing imports for 3.9+

import httpx

# Local Imports
from pixabit import config  # For credentials

# Use themed console for logging/errors if available
try:
    from pixabit.utils.display import console, print
except ImportError:
    import builtins

    print = builtins.print

    class DummyConsole:  # Basic fallback
        def print(self, *args, **kwargs):
            builtins.print(*args)

        def log(self, *args, **kwargs):
            builtins.print(*args)

        def print_exception(self, *args, **kwargs):
            import traceback

            traceback.print_exc()

    console = DummyConsole()

# SECTION: - CONSTANTS
DEFAULT_BASE_URL = "https://habitica.com/api/v3"
REQUESTS_PER_MINUTE = 29  # Stay under 30/min limit
MIN_REQUEST_INTERVAL = 60.0 / REQUESTS_PER_MINUTE  # ~2.07 seconds

# Type hint for common API response data payload (content of 'data' or raw response)
HabiticaApiResponsePayload = Optional[Union[dict[str, Any], list[dict[str, Any]]]]


# KLASS: - HabiticaAPIError
class HabiticaAPIError(Exception):
    """Custom exception for Habitica API specific errors or request failures."""

    def __init__(self, message, status_code=None, error_type=None, response_data=None):
        """Initializes the HabiticaAPIError."""
        super().__init__(message)
        self.status_code = status_code
        self.error_type = error_type
        self.response_data = response_data

    def __str__(self):
        """String representation of the error."""
        details = ""
        if self.status_code is not None:
            details += f"Status={self.status_code}"
        if self.error_type is not None:
            details += f"{', ' if details else ''}Type='{self.error_type}'"
        base_msg = super().__str__()
        return f"HabiticaAPIError: {base_msg}" + (f" ({details})" if details else "")


# KLASS: - HabiticaAPI
class HabiticaAPI:
    """Asynchronous client for interacting with the Habitica API v3 using httpx.

    Handles authentication, rate limiting, standard HTTP requests (GET, POST,
    PUT, DELETE), and provides convenience methods for common Habitica operations.
    Credentials are loaded via the `config` module by default.

    Attributes:
        user_id (str): Habitica User ID.
        api_token (str): Habitica API Token.
        base_url (str): Base URL for the API (default: v3).
        headers (dict[str, str]): Standard request headers including auth & client ID.
        request_interval (float): Minimum seconds between requests for rate limiting.
        last_request_time (float): Monotonic timestamp of the last request initiation.
    """

    BASE_URL = DEFAULT_BASE_URL

    # FUNC: - __init__
    def __init__(
        self,
        user_id: Optional[str] = None,
        api_token: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
    ):
        """Initializes the asynchronous HabiticaAPI client.

        Loads credentials from config if not provided. Sets up headers and rate limiting state.

        Args:
            user_id: Habitica User ID. Defaults to value from config.
            api_token: Habitica API Token. Defaults to value from config.
            base_url: The base URL for the Habitica API.

        Raises:
            ValueError: If User ID or API Token is missing after checking args/config.
        """
        self.user_id = user_id or config.HABITICA_USER_ID
        self.api_token = api_token or config.HABITICA_API_TOKEN
        self.base_url = base_url

        if not self.user_id or not self.api_token:
            raise ValueError("Habitica User ID and API Token are required.")

        self.headers = {
            "x-api-user": self.user_id,
            "x-api-key": self.api_token,
            "Content-Type": "application/json",
            "x-client": "pixabit-tui-v0.1.0",  # Identify your client
        }

        # Rate limiting attributes
        self.last_request_time: float = 0.0  # Monotonic time
        self.request_interval: float = MIN_REQUEST_INTERVAL

        # Optional: Initialize httpx.AsyncClient here for connection pooling
        # self.http_client = httpx.AsyncClient(headers=self.headers, timeout=120)
        # If you do this, use self.http_client.request in _request instead of creating
        # a new client each time, and manage its lifecycle (e.g., close on app exit).
        # For simplicity now, we create a client per request.

    # SECTION: - Internal Helper Methods
    # FUNC: - _wait_for_rate_limit
    async def _wait_for_rate_limit(self) -> None:
        """Asynchronously waits if necessary to enforce rate limit."""
        current_time = time.monotonic()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.request_interval:
            wait_time = self.request_interval - time_since_last
            # console.log(f"Rate limit: waiting {wait_time:.2f}s", style="subtle")
            await asyncio.sleep(wait_time)
        self.last_request_time = time.monotonic()  # Record time request *starts* after wait

    # FUNC: - _request
    async def _request(
        self, method: str, endpoint: str, **kwargs: Any
    ) -> HabiticaApiResponsePayload:
        """Internal async method for making API requests with rate limiting & error handling.

        Args:
            method: HTTP method string ('GET', 'POST', 'PUT', 'DELETE').
            endpoint: API endpoint path (e.g., '/user').
            **kwargs: Additional arguments for `httpx.AsyncClient.request` (e.g., json, params).

        Returns:
            The JSON payload (dict or list) on success, or None for 204 No Content or errors.

        Raises:
            HabiticaAPIError: For API-specific errors or network/request issues.
            ValueError: For unexpected non-JSON or invalid JSON structure responses.
            Exception: For other unexpected errors during the request lifecycle.
        """
        await self._wait_for_rate_limit()
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        response: Optional[httpx.Response] = None
        # console.log(f"API Request: {method} {url}", style="subtle") # Debug log

        try:
            # Using a client per request for simplicity; consider instance client for performance
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.request(method, url, headers=self.headers, **kwargs)

            response.raise_for_status()  # Raise httpx.HTTPStatusError for 4xx/5xx

            if response.status_code == 204 or not response.content:
                return None  # Standard success with no body content

            response_data = response.json()  # Parse JSON body

            # Handle Habitica's {success, data, error, message} wrapper
            if isinstance(response_data, dict) and "success" in response_data:
                if response_data["success"]:
                    return response_data.get("data")  # Return the payload from 'data'
                else:
                    # API indicated failure
                    error_type = response_data.get("error", "Unknown Habitica Error")
                    message = response_data.get("message", "No message provided.")
                    raise HabiticaAPIError(
                        f"{error_type} - {message}",
                        status_code=response.status_code,
                        error_type=error_type,
                        response_data=response_data,
                    )
            # Handle successful responses (2xx) *without* the wrapper (e.g., /content)
            elif isinstance(response_data, (dict, list)):
                return response_data  # Return the raw JSON dict or list
            else:
                # Unexpected JSON type (e.g., just a string or number)
                raise ValueError(f"Unexpected JSON structure received: {type(response_data)}")

        # --- Specific Exception Handling ---
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
                message = err_data.get(
                    "message", response.reason_phrase
                )  # Use reason phrase as fallback
                error_details += f" | API: '{error_type}' - '{message}'"
                raise HabiticaAPIError(
                    f"{error_type} - {message}",
                    status_code=status_code,
                    error_type=error_type,
                    response_data=err_data,
                ) from http_err
            except json.JSONDecodeError:  # Changed from httpx.JSONDecodeError
                body_preview = response.text[:200].replace("\n", "\\n")
                error_details += f" | Response Body (non-JSON): {body_preview}"
                console.print(f"Request Failed: {error_details}", style="error")
                raise HabiticaAPIError(
                    f"HTTP Error {status_code} with non-JSON body", status_code=status_code
                ) from http_err

        except httpx.RequestError as req_err:  # Other connection/network errors
            msg = f"Network/Request Error for {method} {endpoint}"
            console.print(f"{msg}: {req_err}", style="error")
            raise HabiticaAPIError(msg) from req_err

        except json.JSONDecodeError as json_err:  # JSON parsing failed on a 2xx response
            msg = f"Could not decode successful JSON response from {method} {endpoint}"
            status = response.status_code if response is not None else "N/A"
            body = response.text[:200].replace("\n", "\\n") if response is not None else "N/A"
            console.print(f"{msg} (Status: {status}, Body: {body})", style="error")
            raise ValueError(f"Invalid JSON received from {method} {endpoint}") from json_err

        except Exception as e:  # Catch-all for truly unexpected errors
            console.print(
                f"Unexpected error during API request ({method} {endpoint}): {type(e).__name__} - {e}",
                style="error",
            )
            console.print_exception(show_locals=False)
            # Re-raise the original error or a generic HabiticaAPIError
            raise HabiticaAPIError(f"Unexpected error: {e}") from e

    # SECTION: - Core HTTP Request Methods
    # FUNC: - get
    async def get(
        self, endpoint: str, params: Optional[dict[str, Any]] = None
    ) -> HabiticaApiResponsePayload:
        """Sends async GET request. Returns JSON payload or None."""
        return await self._request("GET", endpoint, params=params)

    # FUNC: - post
    async def post(
        self, endpoint: str, data: Optional[dict[str, Any]] = None
    ) -> HabiticaApiResponsePayload:
        """Sends async POST request with JSON data. Returns JSON payload or None."""
        return await self._request("POST", endpoint, json=data)

    # FUNC: - put
    async def put(
        self, endpoint: str, data: Optional[dict[str, Any]] = None
    ) -> HabiticaApiResponsePayload:
        """Sends async PUT request with JSON data. Returns JSON payload or None."""
        return await self._request("PUT", endpoint, json=data)

    # FUNC: - delete
    async def delete(
        self, endpoint: str, params: Optional[dict[str, Any]] = None
    ) -> HabiticaApiResponsePayload:
        """Sends async DELETE request. Returns JSON payload (often empty dict) or None."""
        return await self._request("DELETE", endpoint, params=params)

    # SECTION: - Convenience Methods (User)
    # FUNC: - get_user_data
    async def get_user_data(self) -> Optional[dict[str, Any]]:
        """Async GET /user - Retrieves the full user object's data."""
        result = await self.get("/user")
        return result if isinstance(result, dict) else None

    # FUNC: - update_user
    async def update_user(self, update_data: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Async PUT /user - Updates general user settings."""
        result = await self.put("/user", data=update_data)
        return result if isinstance(result, dict) else None

    # FUNC: - set_custom_day_start
    async def set_custom_day_start(self, hour: int) -> Optional[dict[str, Any]]:
        """Async Sets user's custom day start hour (0-23) via PUT /user."""
        if not 0 <= hour <= 23:
            raise ValueError("Hour must be between 0 and 23")
        return await self.update_user({"preferences.dayStart": hour})

    # FUNC: - toggle_user_sleep
    async def toggle_user_sleep(self) -> Optional[dict[str, Any]]:
        """Async POST /user/sleep - Toggles user sleep status."""
        result = await self.post("/user/sleep")  # _request extracts 'data'
        if isinstance(result, bool):
            return {"sleep": result}  # Wrap boolean for consistency
        elif isinstance(result, dict):
            return result  # Return dict if API provides more
        return None  # Indicate failure or unexpected type

    # SECTION: - Convenience Methods (Tasks)
    # FUNC: - get_tasks
    async def get_tasks(self, task_type: Optional[str] = None) -> list[dict[str, Any]]:
        """Async GET /tasks/user - Gets user tasks, optionally filtered."""
        params = {"type": task_type} if task_type else None
        result = await self.get("/tasks/user", params=params)
        return result if isinstance(result, list) else []

    # FUNC: - create_task
    async def create_task(self, data: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Async POST /tasks/user - Creates a new task."""
        if "text" not in data or "type" not in data:
            raise ValueError("Task data requires 'text' and 'type'.")
        result = await self.post("/tasks/user", data=data)
        return result if isinstance(result, dict) else None

    # FUNC: - update_task
    async def update_task(self, task_id: str, data: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Async PUT /tasks/{taskId} - Updates an existing task."""
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        result = await self.put(f"/tasks/{task_id}", data=data)
        return result if isinstance(result, dict) else None

    # FUNC: - delete_task
    async def delete_task(self, task_id: str) -> Optional[dict[str, Any]]:
        """Async DELETE /tasks/{taskId} - Deletes a task."""
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        result = await self.delete(f"/tasks/{task_id}")
        return result if isinstance(result, dict) else None  # API might return {} or None

    # FUNC: - score_task
    async def score_task(self, task_id: str, direction: str = "up") -> Optional[dict[str, Any]]:
        """Async POST /tasks/{taskId}/score/{direction} - Scores a task."""
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        if direction not in ["up", "down"]:
            raise ValueError("Direction must be 'up' or 'down'")
        result = await self.post(f"/tasks/{task_id}/score/{direction}")
        return result if isinstance(result, dict) else None

    # FUNC: - set_attribute
    async def set_attribute(self, task_id: str, attribute: str) -> Optional[dict[str, Any]]:
        """Async Sets task attribute via update_task."""
        if attribute not in ["str", "int", "con", "per"]:
            raise ValueError("Invalid attribute.")
        return await self.update_task(task_id, {"attribute": attribute})

    # FUNC: - move_task_to_position
    async def move_task_to_position(self, task_id: str, position: int) -> Optional[list[str]]:
        """Async POST /tasks/{taskId}/move/to/{position} - Moves task (0=top, -1=bottom)."""
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        if position not in [0, -1]:
            raise ValueError("Position must be 0 or -1.")
        # API v3 returns a list of sorted task IDs in the response 'data' field
        result = await self.post(f"/tasks/{task_id}/move/to/{position}")
        return result if isinstance(result, list) else None  # Expecting list of IDs

    # SECTION: - Convenience Methods (Tags)
    # FUNC: - get_tags
    async def get_tags(self) -> list[dict[str, Any]]:
        """Async GET /tags - Gets all user tags."""
        result = await self.get("/tags")
        return result if isinstance(result, list) else []

    # FUNC: - create_tag
    async def create_tag(self, name: str) -> Optional[dict[str, Any]]:
        """Async POST /tags - Creates a new tag."""
        if not name:
            raise ValueError("Tag name cannot be empty.")
        result = await self.post("/tags", data={"name": name})
        return result if isinstance(result, dict) else None

    # FUNC: - update_tag
    async def update_tag(self, tag_id: str, name: str) -> Optional[dict[str, Any]]:
        """Async PUT /tags/{tagId} - Updates tag name."""
        if not tag_id:
            raise ValueError("tag_id cannot be empty.")
        if not name:
            raise ValueError("New tag name cannot be empty.")
        result = await self.put(f"/tags/{tag_id}", data={"name": name})
        return result if isinstance(result, dict) else None

    # FUNC: - delete_tag
    async def delete_tag(self, tag_id: str) -> Optional[dict[str, Any]]:
        """Async DELETE /tags/{tagId} - Deletes tag globally."""
        if not tag_id:
            raise ValueError("tag_id cannot be empty.")
        result = await self.delete(f"/tags/{tag_id}")
        return result if isinstance(result, dict) else None  # Often {} or None on success

    # FUNC: - add_tag_to_task
    async def add_tag_to_task(self, task_id: str, tag_id: str) -> Optional[dict[str, Any]]:
        """Async POST /tasks/{taskId}/tags/{tagId} - Associates tag with task."""
        if not task_id or not tag_id:
            raise ValueError("task_id and tag_id cannot be empty.")
        result = await self.post(f"/tasks/{task_id}/tags/{tag_id}")
        return result if isinstance(result, dict) else None  # API returns minimal response

    # FUNC: - delete_tag_from_task
    async def delete_tag_from_task(self, task_id: str, tag_id: str) -> Optional[dict[str, Any]]:
        """Async DELETE /tasks/{taskId}/tags/{tagId} - Removes tag from task."""
        if not task_id or not tag_id:
            raise ValueError("task_id and tag_id cannot be empty.")
        result = await self.delete(f"/tasks/{task_id}/tags/{tag_id}")
        return result if isinstance(result, dict) else None

    # SECTION: - Convenience Methods (Checklist)
    # FUNC: - add_checklist_item
    async def add_checklist_item(self, task_id: str, text: str) -> Optional[dict[str, Any]]:
        """Async POST /tasks/{taskId}/checklist - Adds checklist item."""
        if not task_id or not text:
            raise ValueError("task_id and text cannot be empty.")
        result = await self.post(f"/tasks/{task_id}/checklist", data={"text": text})
        return result if isinstance(result, dict) else None  # Returns updated task

    # FUNC: - update_checklist_item
    async def update_checklist_item(
        self, task_id: str, item_id: str, text: str
    ) -> Optional[dict[str, Any]]:
        """Async PUT /tasks/{taskId}/checklist/{itemId} - Updates checklist item."""
        if not task_id or not item_id or text is None:
            raise ValueError("task_id, item_id, and text are required.")
        result = await self.put(f"/tasks/{task_id}/checklist/{item_id}", data={"text": text})
        return result if isinstance(result, dict) else None  # Returns updated task

    # FUNC: - delete_checklist_item
    async def delete_checklist_item(self, task_id: str, item_id: str) -> Optional[dict[str, Any]]:
        """Async DELETE /tasks/{taskId}/checklist/{itemId} - Deletes checklist item."""
        if not task_id or not item_id:
            raise ValueError("task_id and item_id cannot be empty.")
        result = await self.delete(f"/tasks/{task_id}/checklist/{item_id}")
        return result if isinstance(result, dict) else None  # Returns updated task

    # FUNC: - score_checklist_item
    async def score_checklist_item(self, task_id: str, item_id: str) -> Optional[dict[str, Any]]:
        """Async POST /tasks/{taskId}/checklist/{itemId}/score - Toggles checklist item."""
        if not task_id or not item_id:
            raise ValueError("task_id and item_id cannot be empty.")
        result = await self.post(f"/tasks/{task_id}/checklist/{item_id}/score")
        return result if isinstance(result, dict) else None  # Returns updated task

    # SECTION: - Convenience Methods (Challenges)
    # FUNC: - get_challenges
    async def get_challenges(self, member_only: bool = True) -> list[dict[str, Any]]:
        """Async GET /challenges/user - Gets challenges, handles pagination."""
        # (Implementation from api_textual.txt is good, keep it)
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
            except HabiticaAPIError as e:  # Catch custom API errors
                console.print(
                    f"API Error fetching challenges page {page}: {e}. Stopping.", style="error"
                )
                break
            except Exception as e:  # Catch other errors
                console.print(
                    f"Unexpected Error fetching challenges page {page}: {e}. Stopping.",
                    style="error",
                )
                break
        console.log(f"Finished fetching challenges. Total: {len(all_challenges)}", style="info")
        return all_challenges

    # FUNC: - create_challenge
    async def create_challenge(self, data: dict[str, Any]) -> Optional[dict[str, Any]]:
        """Async POST /challenges - Creates challenge."""
        result = await self.post("/challenges", data=data)
        return result if isinstance(result, dict) else None

    # FUNC: - get_challenge_tasks
    async def get_challenge_tasks(self, challenge_id: str) -> list[dict[str, Any]]:
        """Async GET /tasks/challenge/{challengeId} - Gets challenge tasks."""
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        result = await self.get(f"/tasks/challenge/{challenge_id}")
        return result if isinstance(result, list) else []

    # FUNC: - unlink_task_from_challenge
    async def unlink_task_from_challenge(
        self, task_id: str, keep: str = "keep"
    ) -> Optional[dict[str, Any]]:
        """Async POST /tasks/{taskId}/unlink?keep={keep} - Unlinks task from challenge."""
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        if keep not in ["keep", "remove"]:
            raise ValueError("keep must be 'keep' or 'remove'")
        result = await self.post(f"/tasks/unlink-one/{task_id}?keep={keep}")
        return (
            result if isinstance(result, dict) else None
        )  # API returns task? or empty? Check docs

    # FUNC: - unlink_all_challenge_tasks
    async def unlink_all_challenge_tasks(
        self, challenge_id: str, keep: str = "keep-all"
    ) -> Optional[dict[str, Any]]:
        """Async POST /tasks/unlink-all/{challengeId}?keep={keep} - Unlinks all tasks."""
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        if keep not in ["keep-all", "remove-all"]:
            raise ValueError("keep must be 'keep-all' or 'remove-all'")
        result = await self.post(f"/tasks/unlink-all/{challenge_id}?keep={keep}")
        return (
            result if isinstance(result, dict) else None
        )  # API returns task? or empty? Check docs

    # FUNC: - leave_challenge
    async def leave_challenge(
        self, challenge_id: str, keep: str = "keep-all"
    ) -> Optional[dict[str, Any]]:
        """Async POST /challenges/{challengeId}/leave?keep={keep} - Leaves challenge."""
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        if keep not in ["keep-all", "remove-all"]:
            raise ValueError("keep must be 'keep-all' or 'remove-all'")
        result = await self.post(f"/challenges/{challenge_id}/leave?keep={keep}")
        return (
            result if isinstance(result, dict) else None
        )  # API returns task? or empty? Check docs

    # SECTION: - Convenience Methods (Party)
    # FUNC: - get_party_data
    async def get_party_data(self) -> Optional[dict[str, Any]]:
        """Async GET /groups/party - Gets party data."""
        result = await self.get("/groups/party")
        return result if isinstance(result, dict) else None

    # FUNC: - get_quest_status
    async def get_quest_status(self) -> bool:
        """Async Checks if party is on active quest."""
        try:
            party_data = await self.get_party_data()
            return (
                party_data is not None and party_data.get("quest", {}).get("active", False) is True
            )
        except Exception as e:  # Catch HabiticaAPIError or others
            console.print(f"Could not get quest status: {e}", style="warning")
            return False

    # SECTION: - Convenience Methods (Inbox)
    # FUNC: - get_inbox_messages
    async def get_inbox_messages(self, page: int = 0) -> list[dict[str, Any]]:
        """Async GET /inbox/messages - Gets inbox messages."""
        result = await self.get("/inbox/messages", params={"page": page})
        return result if isinstance(result, list) else []

    # SECTION: - Convenience Methods (Content)
    # FUNC: - get_content
    async def get_content(self) -> Optional[dict[str, Any]]:
        """Async GET /content - Retrieves the game content object."""
        result = await self._request("GET", "/content")  # Uses internal _request
        return result if isinstance(result, dict) else None


# --- End of File ---
