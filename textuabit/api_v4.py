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
from typing import Any, Dict, List, Optional, Union  # Use Dict, List etc. for Python 3.9

import httpx

# Local Imports
# Assume config.py provides HABITICA_USER_ID, HABITICA_API_TOKEN
from pixabit import config

# Use themed console for logging/errors if available
try:
    from pixabit.utils.display import console, print
except ImportError:
    import builtins

    print = builtins.print

    # Define a simple fallback console if Rich isn't available during import
    class DummyConsole:
        def print(self, *args, **kwargs):
            builtins.print(*args)

        def log(self, *args, **kwargs):
            builtins.print("LOG:", *args)  # Add LOG prefix

        def print_exception(self, *args, **kwargs):
            import traceback

            traceback.print_exc()

    console = DummyConsole()
    print("Warning: pixabit.utils.display not found, using basic print/log.")


# SECTION: - CONSTANTS
DEFAULT_BASE_URL = "https://habitica.com/api/v3"
REQUESTS_PER_MINUTE = 29  # Stay under 30/min limit
MIN_REQUEST_INTERVAL = 60.0 / REQUESTS_PER_MINUTE  # ~2.07 seconds

# Type hint for the data payload within a successful Habitica API response
# Can be None (e.g., for 204 No Content or if 'data' field is missing)
HabiticaApiResponsePayload = Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]


# KLASS: - HabiticaAPIError
class HabiticaAPIError(Exception):
    """Custom exception for Habitica API specific errors or request failures.

    Attributes:
        message (str): The error message.
        status_code (Optional[int]): The HTTP status code, if available.
        error_type (Optional[str]): The error type string from the Habitica API response, if available.
        response_data (Optional[Any]): The raw response data, if available.
    """

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        error_type: Optional[str] = None,
        response_data: Optional[Any] = None,
    ):
        """Initializes the HabiticaAPIError."""
        super().__init__(message)
        self.status_code = status_code
        self.error_type = error_type
        self.response_data = response_data

    def __str__(self) -> str:
        """String representation of the error."""
        details = []
        if self.status_code is not None:
            details.append(f"Status={self.status_code}")
        if self.error_type:
            details.append(f"Type='{self.error_type}'")
        base_msg = super().__str__()
        return f"HabiticaAPIError: {base_msg}" + (f" ({', '.join(details)})" if details else "")


# KLASS: - HabiticaAPI
class HabiticaAPI:
    """Asynchronous client for interacting with the Habitica API v3 using httpx.

    Handles authentication, rate limiting, standard HTTP requests (GET, POST,
    PUT, DELETE), and provides convenience methods for common Habitica operations.
    Credentials are loaded via the `config` module by default.

    Attributes:
        user_id: Habitica User ID.
        api_token: Habitica API Token.
        base_url: Base URL for the API (default: v3).
        headers: Standard request headers including auth & client ID.
        request_interval: Min seconds between requests for rate limiting.
        last_request_time: Monotonic timestamp of the last request initiation.
    """

    BASE_URL: str = DEFAULT_BASE_URL

    # FUNC: - __init__
    def __init__(
        self,
        user_id: Optional[str] = None,
        api_token: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
    ):
        """Initializes the asynchronous HabiticaAPI client.

        Args:
            user_id: Habitica User ID. Defaults to config.HABITICA_USER_ID.
            api_token: Habitica API Token. Defaults to config.HABITICA_API_TOKEN.
            base_url: The base URL for the Habitica API.

        Raises:
            ValueError: If User ID or API Token is missing after checking args/config.
        """
        self.user_id: str = user_id or config.HABITICA_USER_ID
        self.api_token: str = api_token or config.HABITICA_API_TOKEN
        self.base_url: str = base_url

        if not self.user_id or not self.api_token:
            # This check ensures required credentials are present upon instantiation.
            raise ValueError("Habitica User ID and API Token are required.")

        self.headers: Dict[str, str] = {
            "x-api-user": self.user_id,
            "x-api-key": self.api_token,
            "Content-Type": "application/json",
            "x-client": "pixabit-tui-v0.1.0",  # Identify your client (update version as needed)
        }

        # Rate limiting attributes
        self.last_request_time: float = 0.0  # Uses time.monotonic()
        self.request_interval: float = MIN_REQUEST_INTERVAL

        # Consider creating the client once if making frequent calls
        # self._http_client = httpx.AsyncClient(headers=self.headers, timeout=120)
        # Remember to handle closing the client gracefully on app exit if you do this.

    # SECTION: - Internal Helper Methods
    # FUNC: - _wait_for_rate_limit
    async def _wait_for_rate_limit(self) -> None:
        """Asynchronously waits if necessary to enforce the request rate limit."""
        current_time = time.monotonic()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.request_interval:
            wait_time = self.request_interval - time_since_last
            await asyncio.sleep(wait_time)
        # Record the time just before the request is actually sent
        self.last_request_time = time.monotonic()

    # FUNC: - _request
    async def _request(
        self, method: str, endpoint: str, **kwargs: Any
    ) -> HabiticaApiResponsePayload:
        """Internal async method for making API requests with rate limiting & error handling.

        Args:
            method: HTTP method string ('GET', 'POST', 'PUT', 'DELETE').
            endpoint: API endpoint path (e.g., '/user').
            kwargs: Additional arguments for `httpx.AsyncClient.request` (e.g., json, params).

        Returns:
            The JSON payload (dict or list) on success, or None for 204 No Content.

        Raises:
            HabiticaAPIError: For API-specific errors or network/request issues.
            ValueError: For unexpected non-JSON or invalid JSON structure responses.
            Exception: For other unexpected errors during the request lifecycle.
        """
        await self._wait_for_rate_limit()
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        response: Optional[httpx.Response] = None
        # console.log(f"API Request: {method} {url}", style="subtle")

        try:
            # Create a new client per request for simplicity. Use instance client for performance.
            async with httpx.AsyncClient(timeout=120) as client:
                response = await client.request(method, url, headers=self.headers, **kwargs)

            response.raise_for_status()  # Raise httpx.HTTPStatusError for 4xx/5xx

            # Handle successful 204 No Content or empty body
            if response.status_code == 204 or not response.content:
                return None

            response_data = response.json()  # Parse JSON body

            # Check for Habitica's standard {success, data, ...} wrapper
            if isinstance(response_data, dict) and "success" in response_data:
                if response_data["success"]:
                    return response_data.get("data")  # Return the 'data' payload
                else:
                    # API indicated failure in the wrapper
                    error_type = response_data.get("error", "Unknown Habitica Error")
                    message = response_data.get("message", "No message provided.")
                    raise HabiticaAPIError(
                        f"{error_type} - {message}",
                        status_code=response.status_code,
                        error_type=error_type,
                        response_data=response_data,
                    )
            # Handle successful responses (2xx) *without* the standard wrapper (e.g., /content)
            elif isinstance(response_data, (dict, list)):
                return response_data  # Return the raw JSON dict or list
            else:
                # Unexpected JSON type (e.g., string, number) for a successful response
                raise ValueError(f"Unexpected JSON structure received: {type(response_data)}")

        # --- Specific Exception Handling ---
        except httpx.TimeoutException as timeout_err:
            msg = f"Request timed out for {method} {endpoint}"
            console.print(f"{msg}: {timeout_err}", style="error")
            raise HabiticaAPIError(msg, status_code=408) from timeout_err

        except httpx.HTTPStatusError as http_err:
            response = http_err.response
            status_code = response.status_code
            error_details = f"HTTP Error {status_code} for {method} {url}"
            try:
                # Attempt to parse Habitica error details from JSON body
                err_data = response.json()
                error_type = err_data.get("error", f"HTTP{status_code}")
                message = err_data.get(
                    "message", response.reason_phrase or f"HTTP {status_code} Error"
                )
                error_details += f" | API: '{error_type}' - '{message}'"
                raise HabiticaAPIError(
                    f"{error_type} - {message}",
                    status_code=status_code,
                    error_type=error_type,
                    response_data=err_data,
                ) from http_err
            except json.JSONDecodeError:  # Response wasn't JSON
                body_preview = response.text[:200].replace("\n", "\\n")
                error_details += f" | Response Body (non-JSON): {body_preview}"
                console.print(f"Request Failed: {error_details}", style="error")
                raise HabiticaAPIError(
                    f"HTTP Error {status_code} with non-JSON body", status_code=status_code
                ) from http_err

        except httpx.RequestError as req_err:  # Other network errors (connection, DNS)
            msg = f"Network/Request Error for {method} {endpoint}"
            console.print(f"{msg}: {req_err}", style="error")
            raise HabiticaAPIError(msg) from req_err

        except json.JSONDecodeError as json_err:  # Parsing failed on a 2xx response
            msg = f"Could not decode successful JSON response from {method} {endpoint}"
            status = response.status_code if response else "N/A"
            body = response.text[:200].replace("\n", "\\n") if response else "N/A"
            console.print(f"{msg} (Status: {status}, Body: {body})", style="error")
            raise ValueError(f"Invalid JSON received from {method} {endpoint}") from json_err

        except (
            ValueError
        ) as val_err:  # Catch ValueErrors raised internally (e.g., unexpected structure)
            console.print(f"Data Error for {method} {endpoint}: {val_err}", style="error")
            raise  # Re-raise ValueError

        except Exception as e:  # Catch-all for other unexpected errors
            console.print(
                f"Unexpected error during API request ({method} {endpoint}): {type(e).__name__} - {e}",
                style="error",
            )
            console.print_exception(show_locals=False)
            raise HabiticaAPIError(f"Unexpected error: {e}") from e

    # SECTION: - Core HTTP Request Methods
    # FUNC: - get
    async def get(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> HabiticaApiResponsePayload:
        """Sends an asynchronous GET request.

        Args:
            endpoint: The API endpoint path (e.g., '/user').
            params: Optional dictionary of query parameters.

        Returns:
            The JSON response payload (dict or list) or None on error/no content.
        """
        return await self._request("GET", endpoint, params=params)

    # FUNC: - post
    async def post(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> HabiticaApiResponsePayload:
        """Sends an asynchronous POST request with an optional JSON body and query params.

        Args:
            endpoint: The API endpoint path (e.g., '/tasks/user').
            data: Optional dictionary for the JSON request body.
            params: Optional dictionary of query parameters.

        Returns:
            The JSON response payload (dict or list) or None on error/no content.
        """
        return await self._request("POST", endpoint, json=data, params=params)

    # FUNC: - put
    async def put(
        self,
        endpoint: str,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
    ) -> HabiticaApiResponsePayload:
        """Sends an asynchronous PUT request with an optional JSON body and query params.

        Args:
            endpoint: The API endpoint path (e.g., '/tasks/{taskId}').
            data: Optional dictionary for the JSON request body.
            params: Optional dictionary of query parameters.

        Returns:
            The JSON response payload (dict or list) or None on error/no content.
        """
        return await self._request("PUT", endpoint, json=data, params=params)

    # FUNC: - delete
    async def delete(
        self, endpoint: str, params: Optional[Dict[str, Any]] = None
    ) -> HabiticaApiResponsePayload:
        """Sends an asynchronous DELETE request with optional query params.

        Args:
            endpoint: The API endpoint path (e.g., '/tasks/{taskId}').
            params: Optional dictionary of query parameters.

        Returns:
            The JSON response payload (often None or empty dict) or None on error.
        """
        return await self._request("DELETE", endpoint, params=params)

    # SECTION: - Convenience Methods (User)
    # FUNC: - get_user_data
    async def get_user_data(self) -> Optional[Dict[str, Any]]:
        """Async GET /user - Retrieves the full user object data."""
        result = await self.get("/user")
        return result if isinstance(result, dict) else None

    # FUNC: - update_user
    async def update_user(self, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Async PUT /user - Updates general user settings."""
        result = await self.put("/user", data=update_data)
        return result if isinstance(result, dict) else None

    # FUNC: - set_custom_day_start
    async def set_custom_day_start(self, hour: int) -> Optional[Dict[str, Any]]:
        """Async Sets user's Custom Day Start hour (0-23) via PUT /user."""
        # Note: API v3 uses PUT /user for this, v4 uses POST /user/custom-day-start
        if not 0 <= hour <= 23:
            raise ValueError("Hour must be between 0 and 23")
        # Using PUT /user based on original code structure
        # return await self.update_user({"preferences.dayStart": hour})
        # If targeting v4 specifically:
        result = await self.post("/user/custom-day-start", data={"dayStart": hour})
        return result if isinstance(result, dict) else None

    # FUNC: - toggle_user_sleep
    async def toggle_user_sleep(self) -> Optional[Dict[str, Any]]:
        """Async POST /user/sleep - Toggles user sleep status (Inn/Tavern)."""
        result = await self.post("/user/sleep")  # _request extracts 'data' payload
        if isinstance(result, bool):
            return {"sleep": result}  # Wrap boolean
        elif isinstance(result, dict):
            return result  # Return full dict if API gives more
        return None

    # FUNC: - run_cron
    async def run_cron(self) -> Optional[Dict[str, Any]]:
        """Async POST /cron - Manually triggers the user's cron process."""
        # Applies damage, resets dailies/streaks etc.
        result = await self.post("/cron")
        return result if isinstance(result, dict) else None  # API returns task deltas

    # SECTION: - Convenience Methods (Tasks)
    # FUNC: - get_tasks
    async def get_tasks(self, task_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Async GET /tasks/user - Gets user tasks, optionally filtered by type."""
        params = {"type": task_type} if task_type else None
        result = await self.get("/tasks/user", params=params)
        return result if isinstance(result, list) else []

    # FUNC: - create_task
    async def create_task(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Async POST /tasks/user - Creates a new task."""
        if not data.get("text") or not data.get("type"):
            raise ValueError("Task data requires 'text' and 'type'.")
        result = await self.post("/tasks/user", data=data)
        return result if isinstance(result, dict) else None  # Returns created task object

    # FUNC: - update_task
    async def update_task(self, task_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Async PUT /tasks/{taskId} - Updates an existing task.

        Args:
            task_id: The ID of the task to update.
            data: Dictionary of task attributes to update. See Habitica API docs.
                  Common fields: text, notes, attribute, priority, date, checklist, etc.
        """
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        result = await self.put(f"/tasks/{task_id}", data=data)
        return result if isinstance(result, dict) else None  # Returns updated task object

    # FUNC: - delete_task
    async def delete_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Async DELETE /tasks/{taskId} - Deletes a task."""
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        result = await self.delete(f"/tasks/{task_id}")
        # API v3 returns { "data": null } on success, _request returns None.
        # Return None explicitly for successful deletion or error.
        return None

    # FUNC: - score_task
    async def score_task(self, task_id: str, direction: str = "up") -> Optional[Dict[str, Any]]:
        """Async POST /tasks/{taskId}/score/{direction} - Scores a task (+/-)."""
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        if direction not in ["up", "down"]:
            raise ValueError("Direction must be 'up' or 'down'.")
        result = await self.post(f"/tasks/{task_id}/score/{direction}")
        return result if isinstance(result, dict) else None  # Returns score result object

    # FUNC: - set_attribute
    async def set_attribute(self, task_id: str, attribute: str) -> Optional[Dict[str, Any]]:
        """Async Sets task attribute ('str', 'int', 'con', 'per') via update_task."""
        if attribute not in ["str", "int", "con", "per"]:
            raise ValueError("Invalid attribute.")
        return await self.update_task(task_id, {"attribute": attribute})

    # FUNC: - move_task_to_position
    async def move_task_to_position(self, task_id: str, position: int) -> Optional[List[str]]:
        """Async POST /tasks/{taskId}/move/to/{position} - Moves task (0=top, -1=bottom)."""
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        if position not in [0, -1]:
            raise ValueError("Position must be 0 (top) or -1 (bottom).")
        result = await self.post(f"/tasks/{task_id}/move/to/{position}")
        # API v3 returns list of sorted task IDs in 'data' field
        return result if isinstance(result, list) else None

    # FUNC: - clear_completed_todos
    async def clear_completed_todos(self) -> Optional[Dict[str, Any]]:
        """Async POST /tasks/clearCompletedTodos - Deletes user's completed ToDos."""
        # Note: Tasks in active Challenges/Group Plans are not deleted.
        result = await self.post("/tasks/clearCompletedTodos")
        # API v3 returns { "data": null } on success, _request returns None.
        return None

    # SECTION: - Convenience Methods (Tags)
    # FUNC: - get_tags
    async def get_tags(self) -> List[Dict[str, Any]]:
        """Async GET /tags - Gets all user tags."""
        result = await self.get("/tags")
        return result if isinstance(result, list) else []

    # FUNC: - create_tag
    async def create_tag(self, name: str) -> Optional[Dict[str, Any]]:
        """Async POST /tags - Creates a new tag."""
        if not name or not name.strip():
            raise ValueError("Tag name cannot be empty.")
        result = await self.post("/tags", data={"name": name.strip()})
        return result if isinstance(result, dict) else None  # Returns the created tag object

    # FUNC: - update_tag
    async def update_tag(self, tag_id: str, name: str) -> Optional[Dict[str, Any]]:
        """Async PUT /tags/{tagId} - Updates tag name."""
        if not tag_id:
            raise ValueError("tag_id cannot be empty.")
        if not name or not name.strip():
            raise ValueError("New tag name cannot be empty.")
        result = await self.put(f"/tags/{tag_id}", data={"name": name.strip()})
        return result if isinstance(result, dict) else None  # Returns updated tag object

    # FUNC: - delete_tag
    async def delete_tag(self, tag_id: str) -> Optional[Dict[str, Any]]:
        """Async DELETE /tags/{tagId} - Deletes tag globally."""
        if not tag_id:
            raise ValueError("tag_id cannot be empty.")
        result = await self.delete(f"/tags/{tag_id}")
        # API v3 returns { "data": null } on success, _request returns None.
        return None

    # FUNC: - reorder_tag
    async def reorder_tag(self, tag_id: str, position: int) -> Optional[Dict[str, Any]]:
        """Async POST /reorder-tags - Reorder a specific tag.

        Args:
            tag_id: The UUID of the tag to move.
            position: The 0-based index to move the tag to (-1 for bottom).

        Returns:
            None on success (API returns {"data": null}). Raises error on failure.
        """
        if not tag_id:
            raise ValueError("tag_id cannot be empty.")
        if not isinstance(position, int) or position < -1:
            raise ValueError("position must be >= -1.")
        payload = {"tagId": tag_id, "to": position}
        result = await self.post("/reorder-tags", data=payload)
        # API v3 returns { "data": null } on success, _request returns None.
        return None

    # FUNC: - add_tag_to_task
    async def add_tag_to_task(self, task_id: str, tag_id: str) -> Optional[Dict[str, Any]]:
        """Async POST /tasks/{taskId}/tags/{tagId} - Associates tag with task."""
        if not task_id or not tag_id:
            raise ValueError("task_id and tag_id cannot be empty.")
        result = await self.post(f"/tasks/{task_id}/tags/{tag_id}")
        # API v3 returns { "data": { "tags": [...] } } (updated task tags list)
        return result if isinstance(result, dict) else None

    # FUNC: - delete_tag_from_task
    async def delete_tag_from_task(self, task_id: str, tag_id: str) -> Optional[Dict[str, Any]]:
        """Async DELETE /tasks/{taskId}/tags/{tagId} - Removes tag from task."""
        if not task_id or not tag_id:
            raise ValueError("task_id and tag_id cannot be empty.")
        result = await self.delete(f"/tasks/{task_id}/tags/{tag_id}")
        # API v3 returns { "data": { "tags": [...] } } (updated task tags list)
        return result if isinstance(result, dict) else None

    # SECTION: - Convenience Methods (Checklist)
    # FUNC: - add_checklist_item
    async def add_checklist_item(self, task_id: str, text: str) -> Optional[Dict[str, Any]]:
        """Async POST /tasks/{taskId}/checklist - Adds checklist item."""
        if not task_id or not text:
            raise ValueError("task_id and text cannot be empty.")
        result = await self.post(f"/tasks/{task_id}/checklist", data={"text": text})
        return result if isinstance(result, dict) else None  # Returns updated task object

    # FUNC: - update_checklist_item
    async def update_checklist_item(
        self, task_id: str, item_id: str, text: str
    ) -> Optional[Dict[str, Any]]:
        """Async PUT /tasks/{taskId}/checklist/{itemId} - Updates checklist item text."""
        if not task_id or not item_id or text is None:
            raise ValueError("task_id, item_id, and text required.")
        result = await self.put(f"/tasks/{task_id}/checklist/{item_id}", data={"text": text})
        return result if isinstance(result, dict) else None  # Returns updated task object

    # FUNC: - delete_checklist_item
    async def delete_checklist_item(self, task_id: str, item_id: str) -> Optional[Dict[str, Any]]:
        """Async DELETE /tasks/{taskId}/checklist/{itemId} - Deletes checklist item."""
        if not task_id or not item_id:
            raise ValueError("task_id and item_id required.")
        result = await self.delete(f"/tasks/{task_id}/checklist/{item_id}")
        return result if isinstance(result, dict) else None  # Returns updated task object

    # FUNC: - score_checklist_item
    async def score_checklist_item(self, task_id: str, item_id: str) -> Optional[Dict[str, Any]]:
        """Async POST /tasks/{taskId}/checklist/{itemId}/score - Toggles checklist item."""
        if not task_id or not item_id:
            raise ValueError("task_id and item_id required.")
        result = await self.post(f"/tasks/{task_id}/checklist/{item_id}/score")
        return result if isinstance(result, dict) else None  # Returns updated task object

    # SECTION: - Convenience Methods (Challenges)
    # FUNC: - get_challenges
    async def get_challenges(self, member_only: bool = True) -> List[Dict[str, Any]]:
        """Async GET /challenges/user - Gets challenges, handles pagination."""
        all_challenges = []
        page = 0
        member_param = "true" if member_only else "false"
        # console.log(f"Fetching challenges (member_only={member_only}, paginating)...", style="info")
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
                        f"Warning: Expected list from /challenges/user page {page}, got {type(page_data)}. Stop.",
                        style="warning",
                    )
                    break
            except HabiticaAPIError as e:
                console.print(
                    f"API Error fetching challenges page {page}: {e}. Stop.", style="error"
                )
                break
            except Exception as e:
                console.print(
                    f"Unexpected Error fetching challenges page {page}: {e}. Stop.", style="error"
                )
                break
        # console.log(f"Finished fetching challenges. Total: {len(all_challenges)}", style="info")
        return all_challenges

    # FUNC: - create_challenge
    async def create_challenge(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Async POST /challenges - Creates challenge."""
        # Basic validation (consult API docs for required fields like name, shortName, group)
        if not data.get("name") or not data.get("shortName") or not data.get("group"):
            raise ValueError(
                "Challenge creation requires at least 'name', 'shortName', and 'group' ID."
            )
        result = await self.post("/challenges", data=data)
        return result if isinstance(result, dict) else None  # Returns created challenge object

    # FUNC: - get_challenge_tasks
    async def get_challenge_tasks(self, challenge_id: str) -> List[Dict[str, Any]]:
        """Async GET /tasks/challenge/{challengeId} - Gets tasks for a challenge."""
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        result = await self.get(f"/tasks/challenge/{challenge_id}")
        # API returns list of task objects in 'data' field
        return result if isinstance(result, list) else []

    # FUNC: - create_challenge_task
    async def create_challenge_task(
        self, challenge_id: str, task_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """Async POST /tasks/challenge/{challengeId} - Creates a single task for a challenge.

        Args:
            challenge_id: The ID of the challenge.
            task_data: Dictionary representing the task to create (must include 'text', 'type').

        Returns:
            The created task object dictionary, or None on failure.
        """
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        if not task_data.get("text") or not task_data.get("type"):
            raise ValueError("Task data requires 'text' and 'type'.")
        if task_data["type"] not in {"habit", "daily", "todo", "reward"}:
            raise ValueError("Invalid task type.")

        result = await self.post(f"/tasks/challenge/{challenge_id}", data=task_data)
        # API returns the created task object in 'data' field
        return result if isinstance(result, dict) else None

    # FUNC: - unlink_task_from_challenge
    async def unlink_task_from_challenge(
        self, task_id: str, keep: str = "keep"
    ) -> Optional[Dict[str, Any]]:
        """Async POST /tasks/{taskId}/unlink?keep={keep} - Unlinks task from challenge."""
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        if keep not in ["keep", "remove"]:
            raise ValueError("keep must be 'keep' or 'remove'")
        result = await self.post(f"/tasks/{task_id}/unlink", params={"keep": keep})
        # API v3 returns {"data": null}, _request returns None
        return None

    # FUNC: - unlink_all_challenge_tasks
    async def unlink_all_challenge_tasks(
        self, challenge_id: str, keep: str = "keep-all"
    ) -> Optional[Dict[str, Any]]:
        """Async POST /tasks/unlink-all/{challengeId}?keep={keep} - Unlinks all tasks."""
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        if keep not in ["keep-all", "remove-all"]:
            raise ValueError("keep must be 'keep-all' or 'remove-all'")
        result = await self.post(f"/tasks/unlink-all/{challenge_id}?keep={keep}")
        # API v3 returns {"data": null}, _request returns None
        return None

    # FUNC: - leave_challenge
    async def leave_challenge(
        self, challenge_id: str, keep: str = "keep-all"
    ) -> Optional[Dict[str, Any]]:
        """Async POST /challenges/{challengeId}/leave?keep={keep} - Leaves challenge."""
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        if keep not in ["keep-all", "remove-all"]:
            raise ValueError("keep must be 'keep-all' or 'remove-all'")
        result = await self.post(f"/challenges/{challenge_id}/leave?keep={keep}")
        # API v3 returns {"data": null}, _request returns None
        return None

    # FUNC: - clone_challenge
    async def clone_challenge(self, challenge_id: str) -> Optional[Dict[str, Any]]:
        """Async POST /challenges/{challengeId}/clone - Clones a challenge."""
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        result = await self.post(f"/challenges/{challenge_id}/clone")
        # API returns the newly cloned challenge object in 'data' field
        return result if isinstance(result, dict) else None

    # FUNC: - update_challenge
    async def update_challenge(self, challenge_id: str, **kwargs: Any) -> Optional[Dict[str, Any]]:
        """Async PUT /challenges/{challengeId} - Updates challenge details (leader only)."""
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        allowed_fields = {"name", "summary", "description"}
        update_data = {
            k: v for k, v in kwargs.items() if k in allowed_fields and v is not None
        }  # Filter nulls
        if not update_data:
            raise ValueError("No valid update fields provided.")
        result = await self.put(f"/challenges/{challenge_id}", data=update_data)
        # API returns the updated challenge object in 'data' field
        return result if isinstance(result, dict) else None

    # SECTION: - Convenience Methods (Party / Groups)
    # FUNC: - get_party_data
    async def get_party_data(self) -> Optional[Dict[str, Any]]:
        """Async GET /groups/party - Gets data for the user's current party."""
        result = await self.get("/groups/party")
        return result if isinstance(result, dict) else None

    # FUNC: - get_quest_status
    async def get_quest_status(self) -> bool:
        """Async Checks if user's party is on an active quest."""
        try:
            party_data = await self.get_party_data()
            return (
                party_data is not None and party_data.get("quest", {}).get("active", False) is True
            )
        except Exception as e:
            console.print(f"Could not get quest status: {e}", style="warning")
            return False

    # FUNC: - cast_skill
    async def cast_skill(
        self, spell_id: str, target_id: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """Async POST /user/class/cast/{spellId}?targetId={targetId} - Casts a skill."""
        if not spell_id:
            raise ValueError("spell_id cannot be empty.")
        # Basic validation - consider using an Enum or Set for allowed_spells
        params = {"targetId": target_id} if target_id else None
        result = await self.post(f"/user/class/cast/{spell_id}", params=params)
        # API returns user delta and potentially target deltas in 'data' field
        return result if isinstance(result, dict) else None

    # FUNC: - get_group_chat_messages
    async def get_group_chat_messages(self, group_id: str = "party") -> List[Dict[str, Any]]:
        """Async GET /groups/{groupId}/chat - Gets chat messages for a group ('party' or UUID)."""
        if not group_id:
            raise ValueError("group_id cannot be empty ('party', guild ID, etc.).")
        result = await self.get(f"/groups/{group_id}/chat")
        # API returns list of chat message objects in 'data' field
        return result if isinstance(result, list) else []

    # FUNC: - like_group_chat_message
    async def like_group_chat_message(
        self, group_id: str, chat_id: str
    ) -> Optional[Dict[str, Any]]:
        """Async POST /groups/{groupId}/chat/{chatId}/like - Likes a group chat message."""
        if not group_id or not chat_id:
            raise ValueError("group_id and chat_id required.")
        result = await self.post(f"/groups/{group_id}/chat/{chat_id}/like")
        # API returns the updated chat message object in 'data' field
        return result if isinstance(result, dict) else None

    # FUNC: - mark_group_chat_seen
    async def mark_group_chat_seen(self, group_id: str = "party") -> Optional[Dict[str, Any]]:
        """Async POST /groups/{groupId}/chat/seen - Marks group messages as read."""
        if not group_id:
            raise ValueError("group_id cannot be empty.")
        result = await self.post(f"/groups/{group_id}/chat/seen")
        # API v3 returns {"data": null}, _request returns None
        return None

    # FUNC: - post_group_chat_message
    async def post_group_chat_message(
        self, group_id: str = "party", message_text: str = ""
    ) -> Optional[Dict[str, Any]]:
        """Async POST /groups/{groupId}/chat - Posts a chat message to a group."""
        if not group_id:
            raise ValueError("group_id required.")
        if not message_text or not message_text.strip():
            raise ValueError("message_text cannot be empty.")
        payload = {"message": message_text.strip()}
        result = await self.post(f"/groups/{group_id}/chat", data=payload)
        # API returns the posted message object in 'data' field
        return result if isinstance(result, dict) else None

    # SECTION: - Convenience Methods (Inbox)
    # FUNC: - get_inbox_messages
    async def get_inbox_messages(
        self, page: int = 0, conversation_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Async GET /inbox/messages - Gets inbox messages, optionally filtered."""
        params: Dict[str, Any] = {"page": page}
        if conversation_id:
            params["conversation"] = conversation_id
        result = await self.get("/inbox/messages", params=params)
        # API returns list of message objects in 'data' field
        return result if isinstance(result, list) else []

    # FUNC: - like_private_message
    async def like_private_message(self, unique_message_id: str) -> Optional[Dict[str, Any]]:
        """Async POST /inbox/like-private-message/{uniqueMessageId} - Likes a private message."""
        # Note: Uses V4 path as specified in original file. Confirmed in some docs.
        if not unique_message_id:
            raise ValueError("unique_message_id required.")
        result = await self.post(f"/inbox/like-private-message/{unique_message_id}")
        # API returns the liked message object in 'data' field
        return result if isinstance(result, dict) else None

    # FUNC: - send_private_message
    async def send_private_message(
        self, recipient_id: str, message_text: str
    ) -> Optional[Dict[str, Any]]:
        """Async POST /members/send-private-message - Sends a private message."""
        if not recipient_id:
            raise ValueError("recipient_id required.")
        if not message_text or not message_text.strip():
            raise ValueError("message_text required.")
        payload = {"toUserId": recipient_id, "message": message_text.strip()}
        result = await self.post("/members/send-private-message", data=payload)
        # API returns the sent message object in 'data' field
        return result if isinstance(result, dict) else None

    # FUNC: - mark_pms_read
    async def mark_pms_read(self) -> Optional[Dict[str, Any]]:
        """Async POST /user/mark-pms-read - Marks all private messages as read."""
        result = await self.post("/user/mark-pms-read")
        # API v3 returns {"data": null}, _request returns None
        return None

    # FUNC: - delete_private_message
    async def delete_private_message(self, message_id: str) -> Optional[Dict[str, Any]]:
        """Async DELETE /user/messages/{id} - Deletes a specific private message."""
        if not message_id:
            raise ValueError("message_id required.")
        result = await self.delete(f"/user/messages/{message_id}")
        # API v3 returns list of remaining messages in 'data' field? Or null? Check docs.
        # Assuming it returns null based on other delete actions.
        return None

    # SECTION: - Convenience Methods (Content)
    # FUNC: - get_content
    async def get_content(self) -> Optional[Dict[str, Any]]:
        """Async GET /content - Retrieves the game content object."""
        result = await self._request("GET", "/content")  # Uses internal request (no wrapper)
        return result if isinstance(result, dict) else None

    # FUNC: - get_model_paths
    async def get_model_paths(self, model_name: str) -> Optional[Dict[str, Any]]:
        """Async GET /models/{model}/paths - Gets field paths for a data model."""
        if not model_name:
            raise ValueError("model_name cannot be empty.")
        allowed = {"user", "group", "challenge", "tag", "habit", "daily", "todo", "reward"}
        if model_name not in allowed:
            raise ValueError(f"Invalid model_name. Allowed: {allowed}")
        result = await self.get(f"/models/{model_name}/paths")
        # API returns {"data": {"path": "type", ...}}
        return result if isinstance(result, dict) else None


# --- End of File ---
