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

    # FUNC: -Set custom day start
    async def set_custom_day_start_version2(self, day_start: int = 0) -> Optional[dict[str, Any]]:
        """Async POST /user/custom-day-start - Set Custom Day Start time for user.

        Args:
            day_start (int): The hour number (0-23) for the day to begin. Defaults to 0.

        Returns:
            Optional[dict[str, Any]]: A dictionary containing the success message, or None on failure.
                                      Example success: {"success": true, "data": {"message": "..."}}

        Raises:
            ValueError: If day_start is outside the range 0-23 (handled by API, but good practice).
                        API returns 400 BadRequest for invalid values.
        """
        if not 0 <= day_start <= 23:
            raise ValueError("day_start must be between 0 and 23.")
        payload = {"dayStart": day_start}
        result = await self.post("/user/custom-day-start", data=payload)
        return result if isinstance(result, dict) else None

    # FUNC: - toggle_user_sleep
    async def toggle_user_sleep(self) -> Optional[dict[str, Any]]:
        """Async POST /user/sleep - Toggles user sleep status."""
        result = await self.post("/user/sleep")  # _request extracts 'data'
        if isinstance(result, bool):
            return {"sleep": result}  # Wrap boolean for consistency
        elif isinstance(result, dict):
            return result  # Return dict if API provides more
        return None  # Indicate failure or unexpected type

    # FUNC: - Run cron
    async def run_cron(self) -> Optional[dict[str, Any]]:
        """Async POST /cron - Manually trigger the cron process.

        Assumes user has acknowledged "Record Yesterday's Activity". Immediately applies
        damage for incomplete due Dailies.
        """
        result = await self.post("/cron")
        return result if isinstance(result, dict) else None

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
        """Async PUT /tasks/{taskId} - Updates an existing task.
        data= Task attributes to update. Refer to Habitica API docs for possible fields:
                            text (str), attribute (str: 'str', 'int', 'per', 'con'),
                            collapseChecklist (bool), notes (str), date (Date string),
                            priority (Number: 0.1, 1, 1.5, 2), reminders (list[dict]),
                            frequency (str: 'daily', 'weekly', 'monthly', 'yearly'),
                            repeat (dict[str, bool]), everyX (Number), streak (Number),
                            daysOfMonth (list[int]), weeksOfMonth (list[int]),
                            startDate (Date string), up (bool), down (bool), value (Number).
        """
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

    # FUNC: - Clear completed todos
    async def clear_completed_todos(self) -> Optional[dict[str, Any]]:
        """Async POST /tasks/clearCompletedTodos - Delete user's completed To Do tasks.

        Deletes all completed To Do's except those in active Challenges/Group Plans.
        """
        result = await self.post("/tasks/clearCompletedTodos")
        return result if isinstance(result, dict) else None

    # FUNC: - Reorder tag
    async def reorder_tag(self, tag_id: str, position: int) -> Optional[dict[str, Any]]:
        """Async POST /reorder-tags - Reorder a specific tag.

        Args:
            tag_id (str): The UUID of the tag to move.
            position (int): The 0-based index to move the tag to.

        Returns:
            Optional[dict[str, Any]]: An empty data object on success, or None on failure.

        Raises:
            ValueError: If tag_id is empty.
                        API returns 404 NotFound if the tag does not exist.
        """
        if not tag_id:
            raise ValueError("tag_id cannot be empty.")
        payload = {"tagId": tag_id, "to": position}
        result = await self.post("/reorder-tags", data=payload)
        return result if isinstance(result, dict) else None

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

    # FUNC: - Create challenge task
    async def create_challenge_task(
        self, challenge_id: str, task_type: str, text: str, **kwargs: Any
    ) -> Optional[Union[dict[str, Any], list[dict[str, Any]]]]:
        """Async POST /tasks/challenge/{challengeId} - Create task(s) for a challenge.

        Note: This implementation creates a single task. The API allows sending an array
              in the body to create multiple tasks. A separate method might be needed for bulk creation.

        Args:
            challenge_id (str): The UUID of the challenge to add the task to.
            task_type (str): Type of task ('habit', 'daily', 'todo', 'reward').
            text (str): The display text for the task.
            **kwargs (Any): Additional task attributes. Refer to Habitica API docs:
                            attribute (str), collapseChecklist (bool), notes (str),
                            date (Date), priority (Number), reminders (list[dict]),
                            frequency (str), repeat (dict), everyX (Number), streak (Number),
                            daysOfMonth (list[int]), weeksOfMonth (list[int]),
                            startDate (Date), up (bool), down (bool), value (Number).

        Returns:
            Optional[Union[dict[str, Any], list[dict[str, Any]]]]:
                A dictionary representing the created task (or list if API supports/used), or None on failure.

        Raises:
            ValueError: If challenge_id, task_type, or text are empty.
                        API returns 400 BadRequest for various validation errors (type, text required, alias format, enum values).
                        API returns 401 NotAuthorized if credentials invalid.
                        API returns 404 NotFound if challenge or checklist item not found.
        """
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        if not task_type:
            raise ValueError("task_type cannot be empty.")
        if not text:
            raise ValueError("text cannot be empty.")

        # Basic check for task type
        if task_type not in {"habit", "daily", "todo", "reward"}:
            raise ValueError("task_type must be one of 'habit', 'daily', 'todo', 'reward'.")

        payload = {"type": task_type, "text": text, **kwargs}
        # To handle bulk creation, payload would need to be list[dict[str, Any]]
        # e.g., payload = [{"type": "todo", "text": "Task 1"}, {"type": "habit", "text": "Task 2"}]

        result = await self.post(f"/tasks/challenge/{challenge_id}", data=payload)
        # The API might return a single object or an array in the 'data' field.
        # The wrapper method usually returns the whole response dict.
        return result if isinstance(result, dict) else None

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

    # FUNC: - clone_challenge
    async def clone_challenge(self, challenge_id: str) -> Optional[dict[str, Any]]:
        """Async POST /challenges/{challengeId}/clone - Clone an existing challenge.

        Creates a new challenge based on the specified existing challenge. The user
        running this command becomes the leader of the new cloned challenge.

        Args:
            challenge_id (str): The UUID (_id) of the challenge to clone.

        Returns:
            Optional[dict[str, Any]]: A dictionary representing the newly cloned challenge object,
                                    or None on failure. The structure is similar to the
                                    response from updating a challenge.

        Raises:
            ValueError: If challenge_id is empty.
                        API returns 404 NotFound if the specified challenge to clone
                        could not be found.
        """
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")

        # This endpoint uses POST but typically doesn't require a request body.
        result = await self.post(f"/challenges/{challenge_id}/clone")
        return result if isinstance(result, dict) else None

    # FUNC: - Update Challenge
    async def update_challenge(self, challenge_id: str, **kwargs: Any) -> Optional[dict[str, Any]]:
        """Async PUT /challenges/{challengeId} - Update a challenge's details.

        Requires user to be the challenge leader.

        Args:
            challenge_id (str): The UUID (_id) of the challenge to update.
            **kwargs (Any): Fields to update. Allowed:
                            name (str): The new full name.
                            summary (str): The new short summary.
                            description (str): The new detailed description.

        Returns:
            Optional[dict[str, Any]]: A dictionary representing the updated challenge, or None on failure.

        Raises:
            ValueError: If challenge_id is empty or no valid update fields provided.
                        API returns 401 NotAuthorized if user is not the challenge leader.
                        API returns 404 NotFound if the challenge does not exist.
        """
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")

        allowed_fields = {"name", "summary", "description"}
        update_data = {k: v for k, v in kwargs.items() if k in allowed_fields}

        if not update_data:
            raise ValueError(
                f"No valid update fields provided. Allowed fields: {', '.join(allowed_fields)}"
            )

        result = await self.put(f"/challenges/{challenge_id}", data=update_data)
        return result if isinstance(result, dict) else None

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

    # FUNC: - Cast Skill
    async def cast_skill(
        self, spell_id: str, target_id: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        """Async POST /user/class/cast/{spellId} - Cast a skill (spell) on a target.

        Args:
            spell_id (str): The key of the skill to cast (e.g., 'fireball', 'healAll').
                            Allowed values: fireball, mpheal, earth, frost, smash,
                            defensiveStance, valorousPresence, intimidate, pickPocket,
                            backStab, toolsOfTrade, stealth, heal, protectAura,
                            brightness, healAll, snowball, spookySparkles, seafoam, shinySeed.
            target_id (Optional[str]): The UUID of the target (party member or task) if applicable.
                                       Not needed if casting on self or current party.

        Returns:
            Optional[dict[str, Any]]: A dictionary containing the modified targets (including the user), or None on failure.

        Raises:
            ValueError: If spell_id is empty.
                        API returns 400 NotAuthorized if insufficient mana.
                        API returns 404 NotFound if task, party, or user target not found.
        """
        if not spell_id:
            raise ValueError("spell_id cannot be empty.")

        # Basic check - a more robust check would use a set of allowed values
        allowed_spells = {
            "fireball",
            "mpheal",
            "earth",
            "frost",
            "smash",
            "defensiveStance",
            "valorousPresence",
            "intimidate",
            "pickPocket",
            "backStab",
            "toolsOfTrade",
            "stealth",
            "heal",
            "protectAura",
            "brightness",
            "healAll",
            "snowball",
            "spookySparkles",
            "seafoam",
            "shinySeed",
        }
        if spell_id not in allowed_spells:
            print(
                f"Warning: spell_id '{spell_id}' may not be a valid spell."
            )  # Or raise ValueError

        params = {}
        if target_id:
            params["targetId"] = target_id

        result = await self.post(f"/user/class/cast/{spell_id}", params=params)
        return result if isinstance(result, dict) else None

    # FUNC: - Get group chat messages
    async def get_group_chat_messages(self, group_id: str) -> Optional[dict[str, Any]]:
        """Async GET /groups/{groupId}/chat - Get chat messages from a group.

        Args:
            group_id (str): The group _id ('party', 'habitrpg', or a UUID).

        Returns:
            Optional[dict[str, Any]]: A dictionary containing an array of chat messages in the 'data' field,
                                      or None on failure.

        Raises:
            ValueError: If group_id is empty.
                        API returns 400 BadRequest if groupId is missing.
                        API returns 404 NotFound if the group does not exist.
        """
        if not group_id:
            raise ValueError("group_id cannot be empty.")
        result = await self.get(f"/groups/{group_id}/chat")
        return result if isinstance(result, dict) else None

    # FUNC: - Like group chat message
    async def like_group_chat_message(
        self, group_id: str, chat_id: str
    ) -> Optional[dict[str, Any]]:
        """Async POST /groups/{groupId}/chat/{chatId}/like - Like a group chat message.

        Args:
            group_id (str): The group _id ('party', 'habitrpg', or a UUID).
            chat_id (str): The _id (UUID) of the chat message to like.

        Returns:
            Optional[dict[str, Any]]: A dictionary representing the liked chat message, or None on failure.

        Raises:
            ValueError: If group_id or chat_id is empty.
                        API returns 400 BadRequest if groupId or chatId is missing.
                        API returns 404 NotFound if the group or message does not exist.
        """
        if not group_id:
            raise ValueError("group_id cannot be empty.")
        if not chat_id:
            raise ValueError("chat_id cannot be empty.")
        result = await self.post(f"/groups/{group_id}/chat/{chat_id}/like")
        return result if isinstance(result, dict) else None

    # FUNC: - Mark group chat seen
    async def mark_group_chat_seen(self, group_id: str) -> Optional[dict[str, Any]]:
        """Async POST /groups/{groupId}/chat/seen - Mark all messages as read for a group.

        Args:
            group_id (str): The group _id ('party', 'habitrpg', or a UUID).

        Returns:
            Optional[dict[str, Any]]: An empty data object on success, or None on failure.

        Raises:
            ValueError: If group_id is empty.
                        API returns 400 BadRequest if groupId is missing.
                        API returns 404 NotFound if the group does not exist.
        """
        if not group_id:
            raise ValueError("group_id cannot be empty.")
        result = await self.post(f"/groups/{group_id}/chat/seen")
        return result if isinstance(result, dict) else None

    # FUNC: - Post group chat messages
    async def post_group_chat_message(
        self, group_id: str, message_text: str, previous_message_id: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        """Async POST /groups/{groupId}/chat - Post a chat message to a group.

        Args:
            group_id (str): The group _id ('party', 'habitrpg', or a UUID).
            message_text (str): The message content to post.
            previous_message_id (Optional[str]): The UUID of the previous message. If provided,
                                                 forces a return of the full group chat.

        Returns:
            Optional[dict[str, Any]]: A dictionary containing the posted message or the full chat, or None on failure.

        Raises:
            ValueError: If group_id or message_text is empty.
                        API returns 400 BadRequest if groupId is missing.
                        API returns 400 NotAuthorized if chat privileges are revoked.
                        API returns 404 NotFound if the group does not exist.
        """
        if not group_id:
            raise ValueError("group_id cannot be empty.")
        if not message_text:
            raise ValueError("message_text cannot be empty.")

        payload = {"message": message_text}
        params = {}
        if previous_message_id:
            params["previousMsg"] = previous_message_id

        result = await self.post(f"/groups/{group_id}/chat", data=payload, params=params)
        return result if isinstance(result, dict) else None

    # SECTION: - Convenience Methods (Inbox)
    # FUNC: - get_inbox_messages
    async def get_inbox_messages(self, page: int = 0) -> list[dict[str, Any]]:
        """Async GET /inbox/messages - Gets inbox messages."""
        result = await self.get("/inbox/messages", params={"page": page})
        return result if isinstance(result, list) else []

    # FUNC: - Get inbox messages
    async def get_inbox_messages_v2(
        self, page: Optional[int] = None, conversation_id: Optional[str] = None
    ) -> Optional[dict[str, Any]]:
        """Async GET /inbox/messages - Get inbox messages for the authenticated user.

        Args:
            page (Optional[int]): The page number to retrieve (10 messages per page).
            conversation_id (Optional[str]): A GUID to filter messages for a specific conversation.

        Returns:
            Optional[dict[str, Any]]: A dictionary containing an array of inbox messages in the 'data' field,
                                      or None on failure.
        """
        params: dict[str, Any] = {}
        if page is not None:
            params["page"] = page
        if conversation_id:
            params["conversation"] = conversation_id

        result = await self.get("/inbox/messages", params=params)
        return result if isinstance(result, dict) else None

    # FUNC: - Like private message
    async def like_private_message(self, unique_message_id: str) -> Optional[dict[str, Any]]:
        """Async POST /inbox/like-private-message/{uniqueMessageId} - Like a private message.

        Uses the shared uniqueMessageId, NOT the individual message.id.
        Note: Uses API v4 path as specified.

        Args:
            unique_message_id (str): The uniqueMessageId (UUID) of the message to like.

        Returns:
            Optional[dict[str, Any]]: A dictionary representing the liked private message, or None on failure.

        Raises:
            ValueError: If unique_message_id is empty.
                        API returns 404 NotFound if the message could not be found.
        """
        if not unique_message_id:
            raise ValueError("unique_message_id cannot be empty.")
        # Path seems to have double slash in docs, assuming /v4/inbox/... is correct
        result = await self.post(f"/inbox/like-private-message/{unique_message_id}")
        return result if isinstance(result, dict) else None

    # FUNC: - Send private message
    async def send_private_message(
        self, recipient_id: str, message_text: str
    ) -> Optional[dict[str, Any]]:
        """Async POST /members/send-private-message - Send a private message to another user.

        Args:
            recipient_id (str): The UUID of the user to send the message to.
            message_text (str): The content of the message.

        Returns:
            Optional[dict[str, Any]]: A dictionary containing the message object that was just sent, or None on failure.

        Raises:
            ValueError: If recipient_id or message_text is empty.
                        API returns 404 NotFound if the recipient user does not exist.
        """
        if not recipient_id:
            raise ValueError("recipient_id cannot be empty.")
        if not message_text:
            raise ValueError("message_text cannot be empty.")

        payload = {"toUserId": recipient_id, "message": message_text}
        result = await self.post("/members/send-private-message", data=payload)
        return result if isinstance(result, dict) else None

    # FUNC: - Mark al priv read
    async def mark_pms_read(self) -> Optional[dict[str, Any]]:
        """Async POST /user/mark-pms-read - Mark all Private Messages as read."""
        result = await self.post("/user/mark-pms-read")
        return result if isinstance(result, dict) else None

    # FUNC: - Delete private message
    async def delete_private_message(self, message_id: str) -> Optional[dict[str, Any]]:
        """Async DELETE /user/messages/{id} - Delete a specific private message.

        Args:
            message_id (str): The UUID of the message to delete.

        Returns:
            Optional[dict[str, Any]]: A dictionary containing the remaining messages in the inbox, or None on failure.

        Raises:
            ValueError: If message_id is empty.
        """
        if not message_id:
            raise ValueError("message_id cannot be empty.")
        result = await self.delete(f"/user/messages/{message_id}")
        return result if isinstance(result, dict) else None

    # SECTION: - Convenience Methods (Content)
    # FUNC: - get_content
    async def get_content(self) -> Optional[dict[str, Any]]:
        """Async GET /content - Retrieves the game content object."""
        result = await self._request("GET", "/content")  # Uses internal _request
        return result if isinstance(result, dict) else None

    # FUNC: - Get model paths
    async def get_model_paths(self, model_name: str) -> Optional[dict[str, Any]]:
        """Async GET /models/{model}/paths - Get all field paths for a specified data model.

        Args:
            model_name (str): The name of the model. Allowed: 'user', 'group',
                              'challenge', 'tag', 'habit', 'daily', 'todo', 'reward'.

        Returns:
            Optional[dict[str, Any]]: A dictionary containing field paths and their types, or None on failure.
                                      Example: {'data': {'field.nested': 'Boolean', ...}}

        Raises:
            ValueError: If model_name is empty or not one of the allowed values.
                        API returns 400 BadRequest if the model name is not found.
        """
        if not model_name:
            raise ValueError("model_name cannot be empty.")
        allowed_models = {"user", "group", "challenge", "tag", "habit", "daily", "todo", "reward"}
        if model_name not in allowed_models:
            raise ValueError(
                f"Invalid model_name. Allowed values are: {', '.join(allowed_models)}"
            )

        result = await self.get(f"/models/{model_name}/paths")
        return result if isinstance(result, dict) else None


# --- End of File ---
