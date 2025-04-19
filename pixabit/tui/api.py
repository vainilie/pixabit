# pixabit/tui/api.py

# SECTION: MODULE DOCSTRING
"""Provides an asynchronous HabiticaAPI client for interacting with the Habitica API v3.

This module contains the `HabiticaAPI` class, which simplifies making calls
to the Habitica API (v3) using `httpx` for non-blocking network operations.
It handles authentication using User ID and API Token (read from config),
implements automatic rate limiting, and offers async wrappers for standard
HTTP methods (GET, POST, PUT, DELETE) and convenience methods for common
endpoints like user data, tasks, tags, challenges, party, inbox, and content.
"""

# SECTION: IMPORTS
import asyncio
import json
import logging
import time
from typing import (
    Any,
    Dict,
    List,
    Optional,
    Union,
)  # Keep Dict/List for clarity

import httpx
from rich.logging import RichHandler
from rich.text import Text
from rich.traceback import install
from textual import log

from pixabit.utils.display import console, print

install(show_locals=True)
FORMAT = "%(message)s"
logging.basicConfig(level="NOTSET", format=FORMAT, datefmt="[%X]", handlers=[RichHandler(rich_tracebacks=True, console=console, markup=True)])

log = logging.getLogger("rich")
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("httpcore").setLevel(logging.WARNING)


# Local Imports
try:
    # Assumes config is at the root level or PYTHONPATH is set correctly
    # Use themed console/print from utils
    from pixabit.cli import (
        config,
    )  # Import config from the cli package structure
    from pixabit.utils.display import console, print

except ImportError:
    # Fallback for standalone testing or import issues

    # Define dummy config values if needed for basic instantiation
    class DummyConfig:
        HABITICA_USER_ID = "DUMMY_USER_ID_CONFIG_MISSING"
        HABITICA_API_TOKEN = "DUMMY_API_TOKEN_CONFIG_MISSING"

    config = DummyConfig()  # type: ignore

# SECTION: CONSTANTS
DEFAULT_BASE_URL: str = "https://habitica.com/api/v3"
REQUESTS_PER_MINUTE: int = 29  # Stay under 30/min limit
MIN_REQUEST_INTERVAL: float = 60.0 / REQUESTS_PER_MINUTE  # ~2.07 seconds

# Type hint for the data payload within a successful Habitica API response
HabiticaApiResponsePayload = Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]


# KLASS: HabiticaAPIError
class HabiticaAPIError(Exception):
    """Custom exception for Habitica API specific errors or request failures.

    Attributes:
        message: The error message.
        status_code: The HTTP status code, if available.
        error_type: The error type string from the Habitica API response, if available.
        response_data: The raw response data, if available.
    """

    # FUNC: __init__
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

    # FUNC: __str__
    def __str__(self) -> str:
        """String representation of the error."""
        details = []
        if self.status_code is not None:
            details.append(f"Status={self.status_code}")  # Plain string part
        if self.error_type:
            details.append(f"Type='{self.error_type}'")  # Plain string part
        base_msg = super().__str__()
        return f"HabiticaAPIError: {base_msg}" + (f" ({', '.join(details)})" if details else "")


# KLASS: HabiticaAPI
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

    # FUNC: __init__
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

        if not self.user_id or not self.api_token or "DUMMY" in self.user_id:  # Check for dummy fallback too
            raise ValueError("Habitica User ID and API Token are required and must be valid.")

        self.headers: Dict[str, str] = {
            "x-api-user": self.user_id,
            "x-api-key": self.api_token,
            "Content-Type": "application/json",
            "x-client": "pixabit-tui-v0.1.0",  # Identify your client
        }

        # Rate limiting attributes
        self.last_request_time: float = 0.0  # Uses time.monotonic()
        self.request_interval: float = MIN_REQUEST_INTERVAL

        # httpx.AsyncClient - consider creating once for performance if app makes many calls
        # self._http_client = httpx.AsyncClient(headers=self.headers, timeout=120)
        # Remember to handle client closing: async with self._http_client as client: ...

    # SECTION: Internal Helper Methods

    # FUNC: _wait_for_rate_limit
    async def _wait_for_rate_limit(self) -> None:
        """Asynchronously waits if necessary to enforce the request rate limit."""
        current_time = time.monotonic()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.request_interval:
            wait_time = self.request_interval - time_since_last
            # console.log(f"Rate limit: waiting {wait_time:.2f}s", style="subtle") # Optional debug
            await asyncio.sleep(wait_time)
        # Record the time just before the request is actually sent
        self.last_request_time = time.monotonic()

    # FUNC: _request
    async def _request(self, method: str, endpoint: str, **kwargs: Any) -> HabiticaApiResponsePayload:
        """Internal async method for making API requests with rate limiting & error handling.

        Args:
            method: HTTP method string ('GET', 'POST', 'PUT', 'DELETE').
            endpoint: API endpoint path (e.g., '/user').
            kwargs: Additional arguments for `httpx.AsyncClient.request` (e.g., json, params).

        Returns:
            The JSON payload (dict or list) from the 'data' field on success,
            the raw JSON if no standard wrapper, or None for 204 No Content.

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
            # Create a new client per request for simplicity.
            # For better performance (connection reuse), create client once in __init__.
            async with httpx.AsyncClient(timeout=120) as client:  # Use instance client if created
                response = await client.request(method, url, headers=self.headers, **kwargs)

            response.raise_for_status()  # Raise httpx.HTTPStatusError for 4xx/5xx

            # Handle successful 204 No Content or empty body
            if response.status_code == 204 or not response.content:
                return None

            response_data = response.json()  # Parse JSON body

            # Check for Habitica's standard {success, data, ...} wrapper
            if isinstance(response_data, dict) and "success" in response_data:
                if response_data["success"]:
                    # Return the 'data' payload (can be None, dict, list, bool, etc.)
                    return response_data.get("data")
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
                # Assume it's the direct payload if no wrapper but successful status
                return response_data
            else:
                # Unexpected JSON type (e.g., string, number) for a successful response
                raise ValueError(f"Unexpected JSON structure received: {type(response_data).__name__}")

        # --- Specific Exception Handling ---
        except httpx.TimeoutException as timeout_err:
            msg = f"Request timed out for {method} {endpoint}"
            log.error(f"[error]Timeout Error:[/error] {msg}: {timeout_err}")
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
                    "message",
                    response.reason_phrase or f"HTTP {status_code} Error",
                )
                api_err_msg = f"{error_type} - {message}"
                error_details += f" | API: '{api_err_msg}'"
                # Raise our specific error class
                raise HabiticaAPIError(
                    api_err_msg,
                    status_code=status_code,
                    error_type=error_type,
                    response_data=err_data,
                ) from http_err
            except json.JSONDecodeError:  # Response wasn't JSON
                body_preview = response.text[:200].replace("\n", "\\n")
                error_details += f" | Response Body (non-JSON): {body_preview}"
                log.error(f"[error]Request Failed:[/error] {error_details}")
                raise HabiticaAPIError(
                    f"HTTP Error {status_code} with non-JSON body",
                    status_code=status_code,
                ) from http_err
            except Exception as parse_err:  # Handle error during error parsing itself
                log.error(f"[error]Request Failed & Error Parsing Failed:[/error] {error_details} | Parse Err: {parse_err}")
                raise HabiticaAPIError(
                    f"HTTP Error {status_code} (error parsing failed)",
                    status_code=status_code,
                ) from http_err

        except httpx.RequestError as req_err:  # Other network errors (connection, DNS)
            msg = f"Network/Request Error for {method} {endpoint}"
            log.error(f"[error]Network Error:[/error] {msg}: {req_err}")
            raise HabiticaAPIError(msg) from req_err

        except json.JSONDecodeError as json_err:  # Parsing failed on a 2xx response
            msg = f"Could not decode successful JSON response from {method} {endpoint}"
            status = response.status_code if response else "N/A"
            body = response.text[:200].replace("\n", "\\n") if response else "N/A"
            log.error(f"[error]JSON Decode Error:[/error] {msg} (Status: {status}, Body: {body})")
            raise ValueError(f"Invalid JSON received from {method} {endpoint}") from json_err

        except ValueError as val_err:  # Catch ValueErrors raised internally (e.g., unexpected structure)
            log.error(f"[error]Data Error:[/error] For {method} {endpoint}: {val_err}")
            raise  # Re-raise ValueError

        except Exception as e:  # Catch-all for other unexpected errors
            log.error(f"[error]Unexpected Error:[/error] During API request ({method} {endpoint}): {type(e).__name__} - {e}")
            # log.error_exception(show_locals=False) # Optional traceback
            raise HabiticaAPIError(f"Unexpected error: {e}") from e

    # SECTION: Core HTTP Request Methods

    # FUNC: get
    async def get(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> HabiticaApiResponsePayload:
        """Sends an asynchronous GET request.

        Args:
            endpoint: The API endpoint path (e.g., '/user').
            params: Optional dictionary of query parameters.

        Returns:
            The JSON response payload (dict or list) or None.
        """
        return await self._request("GET", endpoint, params=params)

    # FUNC: post
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
            The JSON response payload (dict or list) or None.
        """
        # httpx uses 'json' kwarg for body, 'params' for query string
        return await self._request("POST", endpoint, json=data, params=params)

    # FUNC: put
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
            The JSON response payload (dict or list) or None.
        """
        return await self._request("PUT", endpoint, json=data, params=params)

    # FUNC: delete
    async def delete(self, endpoint: str, params: Optional[Dict[str, Any]] = None) -> HabiticaApiResponsePayload:
        """Sends an asynchronous DELETE request with optional query params.

        Args:
            endpoint: The API endpoint path (e.g., '/tasks/{taskId}').
            params: Optional dictionary of query parameters.

        Returns:
            The JSON response payload (often None or empty dict) or None.
        """
        return await self._request("DELETE", endpoint, params=params)

    # SECTION: Convenience Methods (User)

    # FUNC: get_user_data
    async def get_user_data(self) -> Optional[Dict[str, Any]]:
        """Async GET /user - Retrieves the full user object data.

        Returns:
            The user data dictionary, or None on error.
        """
        result = await self.get("/user")
        return result if isinstance(result, dict) else None

    # FUNC: update_user
    async def update_user(self, update_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Async PUT /user - Updates general user settings.

        Args:
            update_data: Dictionary of fields to update (e.g., `{"preferences.sleep": True}`).

        Returns:
            The updated user data dictionary from the API response, or None on error.
        """
        result = await self.put("/user", data=update_data)
        return result if isinstance(result, dict) else None

    # FUNC: set_custom_day_start
    async def set_custom_day_start(self, hour: int) -> Optional[Dict[str, Any]]:
        """Async Sets user's Custom Day Start hour (0-23) via POST /user/custom-day-start (V4 API).

        Note: Original code used PUT /user which might be V3 behavior. This uses V4 endpoint.

        Args:
            hour: The hour (0-23) for the custom day start.

        Returns:
            API response dictionary (likely user deltas), or None on error.
        """
        if not 0 <= hour <= 23:
            raise ValueError("Hour must be between 0 and 23")
        result = await self.post("/user/custom-day-start", data={"dayStart": hour})
        return result if isinstance(result, dict) else None

    # FUNC: toggle_user_sleep
    async def toggle_user_sleep(self) -> Optional[Union[bool, Dict[str, Any]]]:
        """Async POST /user/sleep - Toggles user sleep status (Inn/Tavern).

        Returns:
            The new sleep state (boolean) if API returns it directly in 'data',
            or the full data dictionary if API returns more, or None on error.
            (Handles V3/V4 API differences where possible).
        """
        result = await self.post("/user/sleep")  # _request extracts 'data' payload
        # V3 returns boolean in 'data', V4 might return object? Return whatever 'data' is.
        return result

    # FUNC: run_cron
    async def run_cron(self) -> Optional[Dict[str, Any]]:
        """Async POST /cron - Manually triggers the user's cron process.

        Applies damage, resets dailies/streaks etc.

        Returns:
            API response dictionary (often contains task deltas), or None on error.
        """
        result = await self.post("/cron")
        return result if isinstance(result, dict) else None

    # SECTION: Convenience Methods (Tasks)

    # FUNC: get_tasks
    async def get_tasks(self, task_type: Optional[str] = None) -> List[Dict[str, Any]]:
        """Async GET /tasks/user - Gets user tasks, optionally filtered by type.

        Args:
            task_type: Optional task type ('habits', 'dailys', 'todos', 'rewards').

        Returns:
            A list of task dictionaries, or an empty list on error.
        """
        params = {"type": task_type} if task_type else None
        result = await self.get("/tasks/user", params=params)
        return result if isinstance(result, list) else []

    # FUNC: create_task
    async def create_task(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Async POST /tasks/user - Creates a new task.

        Args:
            data: Dictionary representing the task to create (must include 'text' and 'type').

        Returns:
            The created task object dictionary, or None on error.
        """
        if not data.get("text") or not data.get("type"):
            raise ValueError("Task data requires 'text' and 'type'.")
        result = await self.post("/tasks/user", data=data)
        return result if isinstance(result, dict) else None

    # FUNC: update_task
    async def update_task(self, task_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Async PUT /tasks/{taskId} - Updates an existing task.

        Args:
            task_id: The ID of the task to update.
            data: Dictionary of task attributes to update.

        Returns:
            The updated task object dictionary, or None on error.
        """
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        result = await self.put(f"/tasks/{task_id}", data=data)
        return result if isinstance(result, dict) else None

    # FUNC: delete_task
    async def delete_task(self, task_id: str) -> bool:
        """Async DELETE /tasks/{taskId} - Deletes a task.

        Args:
            task_id: The ID of the task to delete.

        Returns:
            True if deletion was successful (API likely returns 204 or success wrapper),
            False otherwise.
        """
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        # DELETE often returns 204 No Content, or {success: true, data: null}
        # _request returns None for 204 or the 'data' part (which is None).
        result = await self.delete(f"/tasks/{task_id}")
        # Consider success if result is None (meaning 204 or data=None)
        return result is None

    # FUNC: score_task
    async def score_task(self, task_id: str, direction: str = "up") -> Optional[Dict[str, Any]]:
        """Async POST /tasks/{taskId}/score/{direction} - Scores a task (+/-).

        Args:
            task_id: The ID of the task to score.
            direction: 'up' or 'down'.

        Returns:
            Score result object dictionary (contains deltas like hp, mp, exp, gp, drops),
            or None on error.
        """
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        if direction not in ["up", "down"]:
            raise ValueError("Direction must be 'up' or 'down'.")
        result = await self.post(f"/tasks/{task_id}/score/{direction}")
        return result if isinstance(result, dict) else None

    # FUNC: set_attribute
    async def set_attribute(self, task_id: str, attribute: str) -> Optional[Dict[str, Any]]:
        """Async Sets task attribute ('str', 'int', 'con', 'per') via update_task.

        Args:
            task_id: The ID of the task to update.
            attribute: The attribute string ('str', 'int', 'con', 'per').

        Returns:
            The updated task object dictionary, or None on error.
        """
        if attribute not in ["str", "int", "con", "per"]:
            raise ValueError("Invalid attribute. Must be 'str', 'int', 'con', or 'per'.")
        return await self.update_task(task_id, {"attribute": attribute})

    # FUNC: move_task_to_position
    async def move_task_to_position(self, task_id: str, position: int) -> Optional[List[str]]:
        """Async POST /tasks/{taskId}/move/to/{position} - Moves task (0=top, -1=bottom).

        Args:
            task_id: The ID of the task to move.
            position: The 0-based index to move the task to relative to other tasks
                      of the same type (-1 moves to bottom, 0 moves to top).

        Returns:
            List of sorted task IDs for the affected type, or None on error.
        """
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        # API V3 expects 0 for top, -1 for bottom. Other indices might work but are less documented.
        if not isinstance(position, int):
            raise ValueError("Position must be an integer.")

        result = await self.post(f"/tasks/{task_id}/move/to/{position}")
        # API v3 returns list of sorted task IDs in 'data' field
        return result if isinstance(result, list) else None

    # FUNC: clear_completed_todos
    async def clear_completed_todos(self) -> bool:
        """Async POST /tasks/clearCompletedTodos - Deletes user's completed ToDos.

        Note: Tasks in active Challenges/Group Plans are not deleted.

        Returns:
            True on success, False on error.
        """
        # API v3 returns { "data": null } on success.
        result = await self.post("/tasks/clearCompletedTodos")
        return result is None  # Success if 'data' is null

    # SECTION: Convenience Methods (Tags)

    # FUNC: get_tags
    async def get_tags(self) -> List[Dict[str, Any]]:
        """Async GET /tags - Gets all user tags.

        Returns:
            List of tag dictionaries, or empty list on error.
        """
        result = await self.get("/tags")
        return result if isinstance(result, list) else []

    # FUNC: create_tag
    async def create_tag(self, name: str) -> Optional[Dict[str, Any]]:
        """Async POST /tags - Creates a new tag.

        Args:
            name: The name for the new tag.

        Returns:
            The created tag object dictionary, or None on error.
        """
        if not name or not name.strip():
            raise ValueError("Tag name cannot be empty.")
        result = await self.post("/tags", data={"name": name.strip()})
        return result if isinstance(result, dict) else None

    # FUNC: update_tag
    async def update_tag(self, tag_id: str, name: str) -> Optional[Dict[str, Any]]:
        """Async PUT /tags/{tagId} - Updates tag name.

        Args:
            tag_id: The ID of the tag to update.
            name: The new name for the tag.

        Returns:
            The updated tag object dictionary, or None on error.
        """
        if not tag_id:
            raise ValueError("tag_id cannot be empty.")
        if not name or not name.strip():
            raise ValueError("New tag name cannot be empty.")
        result = await self.put(f"/tags/{tag_id}", data={"name": name.strip()})
        return result if isinstance(result, dict) else None

    # FUNC: delete_tag
    async def delete_tag(self, tag_id: str) -> bool:
        """Async DELETE /tags/{tagId} - Deletes tag globally.

        Args:
            tag_id: The ID of the tag to delete.

        Returns:
            True on success, False on error.
        """
        if not tag_id:
            raise ValueError("tag_id cannot be empty.")
        # API v3 returns { "data": null } on success.
        result = await self.delete(f"/tags/{tag_id}")
        return result is None

    # FUNC: reorder_tag
    async def reorder_tag(self, tag_id: str, position: int) -> bool:
        """Async POST /reorder-tags - Reorder a specific tag.

        Args:
            tag_id: The UUID of the tag to move.
            position: The 0-based index to move the tag to (-1 means not supported by API,
                      use index relative to current tag list).

        Returns:
            True on success, False on error.
        """
        if not tag_id:
            raise ValueError("tag_id cannot be empty.")
        # API expects 'to' which is the 0-based index. -1 is not valid here.
        if not isinstance(position, int) or position < 0:
            raise ValueError("position must be a non-negative integer index.")
        payload = {"tagId": tag_id, "to": position}
        result = await self.post("/reorder-tags", data=payload)
        # API v3 returns {"data": null} on success.
        return result is None

    # FUNC: add_tag_to_task
    async def add_tag_to_task(self, task_id: str, tag_id: str) -> Optional[Dict[str, Any]]:
        """Async POST /tasks/{taskId}/tags/{tagId} - Associates tag with task.

        Args:
            task_id: The ID of the task.
            tag_id: The ID of the tag to add.

        Returns:
            API response data (often updated task tags list), or None on error.
        """
        if not task_id or not tag_id:
            raise ValueError("task_id and tag_id cannot be empty.")
        result = await self.post(f"/tasks/{task_id}/tags/{tag_id}")
        # API v3 returns { "data": { "tags": [...] } } (updated task tags list)
        return result if isinstance(result, dict) else None

    # FUNC: delete_tag_from_task
    async def delete_tag_from_task(self, task_id: str, tag_id: str) -> Optional[Dict[str, Any]]:
        """Async DELETE /tasks/{taskId}/tags/{tagId} - Removes tag from task.

        Args:
            task_id: The ID of the task.
            tag_id: The ID of the tag to remove.

        Returns:
            API response data (often updated task tags list), or None on error.
        """
        if not task_id or not tag_id:
            raise ValueError("task_id and tag_id cannot be empty.")
        result = await self.delete(f"/tasks/{task_id}/tags/{tag_id}")
        # API v3 returns { "data": { "tags": [...] } } (updated task tags list)
        return result if isinstance(result, dict) else None

    # SECTION: Convenience Methods (Checklist)

    # FUNC: add_checklist_item
    async def add_checklist_item(self, task_id: str, text: str) -> Optional[Dict[str, Any]]:
        """Async POST /tasks/{taskId}/checklist - Adds checklist item to a task.

        Args:
            task_id: The ID of the task (must be Daily or ToDo).
            text: The text for the new checklist item.

        Returns:
            The updated task object dictionary, or None on error.
        """
        if not task_id or not text:
            raise ValueError("task_id and text cannot be empty.")
        result = await self.post(f"/tasks/{task_id}/checklist", data={"text": text})
        return result if isinstance(result, dict) else None

    # FUNC: update_checklist_item
    async def update_checklist_item(self, task_id: str, item_id: str, text: str) -> Optional[Dict[str, Any]]:
        """Async PUT /tasks/{taskId}/checklist/{itemId} - Updates checklist item text.

        Args:
            task_id: The ID of the parent task.
            item_id: The ID of the checklist item to update.
            text: The new text for the item.

        Returns:
            The updated task object dictionary, or None on error.
        """
        if not task_id or not item_id or text is None:
            raise ValueError("task_id, item_id, and text required.")
        result = await self.put(f"/tasks/{task_id}/checklist/{item_id}", data={"text": text})
        return result if isinstance(result, dict) else None

    # FUNC: delete_checklist_item
    async def delete_checklist_item(self, task_id: str, item_id: str) -> Optional[Dict[str, Any]]:
        """Async DELETE /tasks/{taskId}/checklist/{itemId} - Deletes checklist item.

        Args:
            task_id: The ID of the parent task.
            item_id: The ID of the checklist item to delete.

        Returns:
            The updated task object dictionary, or None on error.
        """
        if not task_id or not item_id:
            raise ValueError("task_id and item_id required.")
        result = await self.delete(f"/tasks/{task_id}/checklist/{item_id}")
        return result if isinstance(result, dict) else None

    # FUNC: score_checklist_item
    async def score_checklist_item(self, task_id: str, item_id: str) -> Optional[Dict[str, Any]]:
        """Async POST /tasks/{taskId}/checklist/{itemId}/score - Toggles checklist item completion.

        Args:
            task_id: The ID of the parent task.
            item_id: The ID of the checklist item to score.

        Returns:
            The updated task object dictionary, or None on error.
        """
        if not task_id or not item_id:
            raise ValueError("task_id and item_id required.")
        result = await self.post(f"/tasks/{task_id}/checklist/{item_id}/score")
        return result if isinstance(result, dict) else None

    # SECTION: Convenience Methods (Challenges)

    # FUNC: get_challenges
    async def get_challenges(self, member_only: bool = True, page: int = 0) -> List[Dict[str, Any]]:
        """Async GET /challenges/user - Gets challenges user is member of or owns. Handles pagination (fetches one page at a time).

        Args:
            member_only: If True, get challenges user is a member of. If False, get owned challenges? (API docs needed).
                         Habitica API v3 uses `member=true` for joined/owned, `owned=true` for only owned. Let's default to member.
            page: The page number to fetch (0-based).

        Returns:
            A list of challenge dictionaries for the requested page, or empty list on error/end.
        """
        params: Dict[str, Any] = {"page": page}
        # Adjust query param based on desired outcome - 'member=true' is common for "my challenges"
        params["member"] = "true" if member_only else "false"
        # Alternatively, for *only* owned: params["owned"] = "true"

        result = await self.get("/challenges/user", params=params)
        return result if isinstance(result, list) else []

    # FUNC: get_all_challenges_paginated (Helper for full list)
    async def get_all_challenges_paginated(self, member_only: bool = True) -> List[Dict[str, Any]]:
        """Async helper to fetch ALL challenges using pagination."""
        all_challenges = []
        current_page = 0
        console.log(
            f"Fetching all challenges (member_only={member_only}, paginating)...",
            style="info",
        )
        while True:
            try:
                page_data = await self.get_challenges(member_only=member_only, page=current_page)
                if not page_data:  # Empty list signifies the end
                    break
                all_challenges.extend(page_data)
                current_page += 1
                # Optional: Add a small sleep to avoid overwhelming API if many pages
                await self._wait_for_rate_limit()  # <--- ADD THIS

                # await asyncio.sleep(0.1)
            except HabiticaAPIError as e:
                log.error(
                    f"API Error fetching challenges page {current_page}: {e}. Returning partial list.",
                    style="error",
                )
                break  # Stop pagination on error
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

    # FUNC: create_challenge
    async def create_challenge(self, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Async POST /challenges - Creates a new challenge.

        Args:
            data: Dictionary containing challenge details (name, shortName, group, etc.).

        Returns:
            The created challenge object dictionary, or None on error.
        """
        if not data.get("name") or not data.get("shortName") or not data.get("group"):
            raise ValueError("Challenge creation requires at least 'name', 'shortName', and 'group' ID.")
        result = await self.post("/challenges", data=data)
        return result if isinstance(result, dict) else None

    # FUNC: get_challenge_tasks
    async def get_challenge_tasks(self, challenge_id: str) -> List[Dict[str, Any]]:
        """Async GET /tasks/challenge/{challengeId} - Gets tasks for a specific challenge.

        Args:
            challenge_id: The ID of the challenge.

        Returns:
            List of task dictionaries belonging to the challenge, or empty list on error.
        """
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        result = await self.get(f"/tasks/challenge/{challenge_id}")
        return result if isinstance(result, list) else []

    # FUNC: create_challenge_task
    async def create_challenge_task(self, challenge_id: str, task_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
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
        return result if isinstance(result, dict) else None

    # FUNC: unlink_task_from_challenge
    async def unlink_task_from_challenge(self, task_id: str, keep: str = "keep") -> bool:
        """Async POST /tasks/unlink-one/{taskId}?keep={keep} - Unlinks task from its challenge.

           (Note: Endpoint name might differ slightly across API docs, confirm /unlink-one or /unlink).

        Args:
            task_id: The ID of the task to unlink.
            keep: How to handle the task ('keep' or 'remove').

        Returns:
            True on success, False on error.
        """
        if not task_id:
            raise ValueError("task_id cannot be empty.")
        if keep not in ["keep", "remove"]:
            raise ValueError("keep must be 'keep' or 'remove'")
        # Confirm endpoint: /unlink or /unlink-one ? Using /unlink as per original code. Adjust if needed.
        # V4 might use POST /tasks/{taskId}/unlink
        result = await self.post(f"/tasks/{task_id}/unlink", params={"keep": keep})
        # API v3 returns {"data": null} on success.
        return result is None

    # FUNC: unlink_all_challenge_tasks
    async def unlink_all_challenge_tasks(self, challenge_id: str, keep: str = "keep-all") -> bool:
        """Async POST /tasks/unlink-all/{challengeId}?keep={keep} - Unlinks all tasks from a challenge.

        Args:
            challenge_id: The ID of the challenge.
            keep: How to handle tasks ('keep-all' or 'remove-all').

        Returns:
            True on success, False on error.
        """
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        if keep not in ["keep-all", "remove-all"]:
            raise ValueError("keep must be 'keep-all' or 'remove-all'")
        # V4 might use POST /challenges/{challengeId}/unlink-all
        result = await self.post(f"/tasks/unlink-all/{challenge_id}", params={"keep": keep})
        # API v3 returns {"data": null} on success.
        return result is None

    # FUNC: leave_challenge
    async def leave_challenge(self, challenge_id: str, keep: str = "keep-all") -> bool:
        """Async POST /challenges/{challengeId}/leave?keep={keep} - Leaves a challenge.

        Args:
            challenge_id: The ID of the challenge to leave.
            keep: How to handle challenge tasks ('keep-all' or 'remove-all').

        Returns:
            True on success, False on error.
        """
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        if keep not in ["keep-all", "remove-all"]:
            raise ValueError("keep must be 'keep-all' or 'remove-all'")
        result = await self.post(f"/challenges/{challenge_id}/leave", params={"keep": keep})
        # API v3 returns {"data": null} on success.
        return result is None

    # FUNC: clone_challenge
    async def clone_challenge(self, challenge_id: str) -> Optional[Dict[str, Any]]:
        """Async POST /challenges/{challengeId}/clone - Clones a challenge.

        Args:
            challenge_id: The ID of the challenge to clone.

        Returns:
            The newly cloned challenge object dictionary, or None on error.
        """
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        result = await self.post(f"/challenges/{challenge_id}/clone")
        return result if isinstance(result, dict) else None

    # FUNC: update_challenge
    async def update_challenge(self, challenge_id: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Async PUT /challenges/{challengeId} - Updates challenge details (leader only).

        Args:
            challenge_id: The ID of the challenge to update.
            data: Dictionary of fields to update (e.g., name, summary, description).

        Returns:
            The updated challenge object dictionary, or None on error.
        """
        if not challenge_id:
            raise ValueError("challenge_id cannot be empty.")
        if not data:
            raise ValueError("Update data cannot be empty.")
        # Basic validation - API handles permissions
        result = await self.put(f"/challenges/{challenge_id}", data=data)
        return result if isinstance(result, dict) else None

    # SECTION: Convenience Methods (Party / Groups)

    # FUNC: get_party_data
    async def get_party_data(self) -> Optional[Dict[str, Any]]:
        """Async GET /groups/party - Gets data for the user's current party.

        Returns:
            The party data dictionary, or None if not in a party or on error.
        """
        result = await self.get("/groups/party")
        # API returns 'Party not found.' error with 404 if not in party.
        # _request raises HabiticaAPIError in that case. Return None if error caught.
        return result if isinstance(result, dict) else None

    # FUNC: get_quest_status (Now relies on get_party_data error handling)
    async def get_quest_status(self) -> Optional[bool]:
        """Async Checks if user's party is on an active quest.

        Returns:
            True if on active quest, False if not on quest, None if party data unavailable.
        """
        try:
            party_data = await self.get_party_data()
            if party_data is None:  # Error fetching party or not in party
                return None
            # Safely check quest status
            quest_info = party_data.get("quest", {})
            return isinstance(quest_info, dict) and quest_info.get("active", False)
        except HabiticaAPIError as e:
            # Log specific API error but return None as status is unknown
            log.error(f"API Error getting quest status: {e}", style="warning")
            return None
        except Exception as e:
            log.error(f"Unexpected error getting quest status: {e}", style="error")
            return None

    # FUNC: cast_skill
    async def cast_skill(self, spell_id: str, target_id: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """Async POST /user/class/cast/{spellId}?targetId={targetId} - Casts a class skill.

        Args:
            spell_id: The key/ID of the skill/spell to cast (e.g., 'fireball', 'pickPocket').
            target_id: Optional target ID (e.g., user ID for beneficial spells, task ID for 'toolsOfTrade').

        Returns:
            API response dictionary (contains user/target deltas), or None on error.
        """
        if not spell_id:
            raise ValueError("spell_id cannot be empty.")
        params = {"targetId": target_id} if target_id else None
        result = await self.post(f"/user/class/cast/{spell_id}", params=params)
        return result if isinstance(result, dict) else None

    # FUNC: get_group_chat_messages
    async def get_group_chat_messages(self, group_id: str = "party", older_than: Optional[str] = None) -> List[Dict[str, Any]]:
        """Async GET /groups/{groupId}/chat - Gets chat messages for a group ('party' or guild UUID).

           Supports pagination via `older_than` message ID.

        Args:
            group_id: The ID of the group ('party', 'tavern', or guild UUID).
            older_than: Optional message ID to fetch messages older than this one.

        Returns:
            List of chat message dictionaries, or empty list on error.
        """
        if not group_id:
            raise ValueError("group_id cannot be empty.")
        params = {"previousMsg": older_than} if older_than else {}
        result = await self.get(f"/groups/{group_id}/chat", params=params)
        return result if isinstance(result, list) else []

    # FUNC: like_group_chat_message
    async def like_group_chat_message(self, group_id: str, chat_id: str) -> Optional[Dict[str, Any]]:
        """Async POST /groups/{groupId}/chat/{chatId}/like - Likes/unlikes a group chat message.

        Args:
            group_id: The ID of the group containing the message.
            chat_id: The ID of the chat message.

        Returns:
            The updated chat message object dictionary, or None on error.
        """
        if not group_id or not chat_id:
            raise ValueError("group_id and chat_id required.")
        result = await self.post(f"/groups/{group_id}/chat/{chat_id}/like")
        return result if isinstance(result, dict) else None

    # FUNC: mark_group_chat_seen
    async def mark_group_chat_seen(self, group_id: str = "party") -> bool:
        """Async POST /groups/{groupId}/chat/seen - Marks group messages as read.

        Args:
            group_id: The ID of the group to mark as seen.

        Returns:
            True on success, False on error.
        """
        if not group_id:
            raise ValueError("group_id cannot be empty.")
        # API v3 returns {"data": null} on success.
        result = await self.post(f"/groups/{group_id}/chat/seen")
        return result is None

    # FUNC: post_group_chat_message
    async def post_group_chat_message(self, group_id: str = "party", message_text: str = "") -> Optional[Dict[str, Any]]:
        """Async POST /groups/{groupId}/chat - Posts a chat message to a group.

        Args:
            group_id: The ID of the group to post to.
            message_text: The text content of the message.

        Returns:
            The posted message object dictionary, or None on error.
        """
        if not group_id:
            raise ValueError("group_id required.")
        if not message_text or not message_text.strip():
            raise ValueError("message_text cannot be empty.")
        payload = {"message": message_text.strip()}
        result = await self.post(f"/groups/{group_id}/chat", data=payload)
        return result if isinstance(result, dict) else None

    # SECTION: Convenience Methods (Inbox)

    # FUNC: get_inbox_messages
    async def get_inbox_messages(self, page: int = 0, conversation_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Async GET /inbox/messages - Gets inbox messages, optionally filtered by conversation.

        Args:
            page: The page number to fetch (0-based).
            conversation_id: Optional - Filter messages by conversation partner's User ID.

        Returns:
            List of message objects, or empty list on error.
        """
        params: Dict[str, Any] = {"page": page}
        if conversation_id:
            params["conversation"] = conversation_id  # API uses 'conversation' param
        result = await self.get("/inbox/messages", params=params)
        return result if isinstance(result, list) else []

    # FUNC: like_private_message (DEPRECATED? - Confirm if exists)
    # This endpoint seems less documented/stable than group chat likes. Use with caution.
    # async def like_private_message(self, unique_message_id: str) -> Optional[Dict[str, Any]]:
    #     """Async POST /inbox/like-private-message/{uniqueMessageId} - Likes a private message."""
    #     if not unique_message_id: raise ValueError("unique_message_id required.")
    #     result = await self.post(f"/inbox/like-private-message/{unique_message_id}")
    #     return result if isinstance(result, dict) else None

    # FUNC: send_private_message
    async def send_private_message(self, recipient_id: str, message_text: str) -> Optional[Dict[str, Any]]:
        """Async POST /members/send-private-message - Sends a private message.

        Args:
            recipient_id: The User ID of the recipient.
            message_text: The text content of the message.

        Returns:
            The sent message object dictionary, or None on error.
        """
        if not recipient_id:
            raise ValueError("recipient_id required.")
        if not message_text or not message_text.strip():
            raise ValueError("message_text required.")
        payload = {"toUserId": recipient_id, "message": message_text.strip()}
        result = await self.post("/members/send-private-message", data=payload)
        # API returns the sent message object in 'data' field
        return result if isinstance(result, dict) else None

    # FUNC: mark_pms_read
    async def mark_pms_read(self) -> bool:
        """Async POST /user/mark-pms-read - Marks all private messages as read.

        Returns:
            True on success, False on error.
        """
        # API v3 returns {"data": null} on success.
        result = await self.post("/user/mark-pms-read")
        return result is None

    # FUNC: delete_private_message
    async def delete_private_message(self, message_id: str) -> bool:
        """Async DELETE /user/messages/{id} - Deletes a specific private message from YOUR inbox.

        Args:
            message_id: The ID of the message to delete.

        Returns:
            True on success, False on error.
        """
        if not message_id:
            raise ValueError("message_id required.")
        # API v3 might return updated message list or null. Assuming null/204 is success.
        result = await self.delete(f"/user/messages/{message_id}")
        return result is None  # Success if no data/error

    # SECTION: Convenience Methods (Content)

    # FUNC: get_content
    async def get_content(self) -> Optional[Dict[str, Any]]:
        """Async GET /content - Retrieves the full game content object.

        Note: This endpoint does not use the standard {success, data} wrapper.

        Returns:
            The game content dictionary, or None on error.
        """
        # Use internal request directly as it handles non-wrapper responses
        result = await self._request("GET", "/content")
        return result if isinstance(result, dict) else None

    # FUNC: get_model_paths (Less common, maybe remove if unused)
    # async def get_model_paths(self, model_name: str) -> Optional[Dict[str, Any]]:
    #     """Async GET /models/{model}/paths - Gets field paths for a data model."""
    #     # ... (implementation if needed) ...
