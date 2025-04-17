# pixabit/api.py


# SECTION: - MODULE DOCSTRING
"""Provides async HabiticaAPI client for interacting with the Habitica API v3. Uses httpx
for asynchronous requests. Handles authentication, rate limiting, async HTTP methods, and
convenience methods for common API endpoints (user, tasks, tags, challenges, etc.).
"""

# SECTION: - IMPORTS
import asyncio
import json
import time
from typing import Any, Optional, Union

import httpx
from pixabit import config
from pixabit.utils.display import console

# SECTION: - CONSTANTS
DEFAULT_BASE_URL = "https://habitica.com/api/v3"
REQUESTS_PER_MINUTE = 29
MIN_REQUEST_INTERVAL = 60.0 / REQUESTS_PER_MINUTE
HabiticaApiResponse = Optional[Union[dict[str, Any], list[dict[str, Any]]]]


# KLASS: - Custom Exception (Optional but Recommended)
class HabiticaAPIError(Exception):
    """Custom exception for Habitica API specific errors."""

    def __init__(self, message, status_code=None, error_type=None, response_data=None):
        super().__init__(message)
        self.status_code = status_code
        self.error_type = error_type
        self.response_data = response_data

    def __str__(self):
        details = f"Status={self.status_code}, Type={self.error_type}" if self.status_code else ""
        return f"HabiticaAPIError: {super().__str__()} ({details})"


# KLASS: - HabiticaAPI Class (Async)
class HabiticaAPI:
    """Asynchronous Habitica API client using httpx. Handles auth, rate  limits,
    requests.

    Attributes:
        user_id (str): Habitica User ID.
        api_token (str): Habitica API Token.
        base_url (str): Base URL for the API.
        headers (Dict[str, str]): Standard request headers including auth.
        request_interval (float): Min seconds between requests for rate limiting.
        last_request_time (float): Timestamp of the last request (monotonic).
    """

    BASE_URL = DEFAULT_BASE_URL

    # --- __init__ (Keep as before) ---
    def __init__(
        self,
        user_id: Optional[str] = None,
        api_token: Optional[str] = None,
        base_url: str = DEFAULT_BASE_URL,
    ):
        """Initializes the HabiticaAPI client.

        Loads credentials from config if not provided. Sets up headers and rate limiting.

        Args:
            user_id: Habitica User ID. Defaults to config.HABITICA_USER_ID.
            api_token: Habitica API Token. Defaults to config.HABITICA_API_TOKEN.
            base_url: API base URL.

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
            "x-client": "pixabit-tui",
        }
        self.last_request_time: float = 0.0
        self.request_interval: float = MIN_REQUEST_INTERVAL

    # --- _wait_for_rate_limit (Keep async version) ---
    async def _wait_for_rate_limit(self) -> None:
        """Sleeps if necessary to comply with the rate limit based on monotonic time."""
        current_time = time.monotonic()
        time_since_last = current_time - self.last_request_time
        if time_since_last < self.request_interval:
            wait_time = self.request_interval - time_since_last
            await asyncio.sleep(wait_time)
        self.last_request_time = time.monotonic()

    # --- _request (Refined Exception Handling) ---
    async def _request(self, method: str, endpoint: str, **kwargs: Any) -> HabiticaApiResponse:
        """Internal method for making API requests with rate limiting and error handling.

        Args:
            method: HTTP method ('GET', 'POST', 'PUT', 'DELETE').
            endpoint: API endpoint path (e.g., '/user').
            **kwargs: Additional arguments for `requests.request` (e.g., json, params).

        Returns:
            The JSON response data (dict or list) from the API's 'data' field if present
            and successful, the raw JSON if no standard wrapper is used but successful,
            or None for 204 No Content or errors.

        Raises:
            requests.exceptions.RequestException: For network or API errors after logging.
        """
        await self._wait_for_rate_limit()
        url = f"{self.base_url.rstrip('/')}/{endpoint.lstrip('/')}"
        response: Optional[httpx.Response] = None
        # console.log(f"Request: {method} {url} | Kwargs: {kwargs}", style="subtle")

        try:
            kwargs.setdefault("timeout", 120)

            # Recommended: Create one client per instance if making many calls,

            # or one per request if calls are infrequent. One per request is simpler here.
            async with httpx.AsyncClient() as client:
                response = await client.request(method, url, headers=self.headers, **kwargs)

            response.raise_for_status()

            # Raises httpx.HTTPStatusError for 4xx/5xx

            if response.status_code == 204 or not response.content:
                return None

            response_data = response.json()

            if isinstance(response_data, dict) and "success" in response_data:
                if response_data["success"]:
                    return response_data.get("data")
                else:
                    # Raise custom API error for Habitica specific failures
                    error_type = response_data.get("error", "Unknown Habitica Error")
                    message = response_data.get("message", "No message provided.")
                    raise HabiticaAPIError(
                        f"{error_type} - {message}",
                        status_code=response.status_code,
                        error_type=error_type,
                        response_data=response_data,
                    )

            # Handle successful non-wrapped JSON
            if isinstance(response_data, (dict, list)):
                return response_data
            else:
                raise ValueError(f"Unexpected JSON structure: {type(response_data)}")

        except httpx.TimeoutException as timeout_err:
            msg = f"Request timed out ({kwargs.get('timeout')}s) for {method} {endpoint}"
            console.print(f"{msg}: {timeout_err}", style="error")

            # Optionally re-raise as custom error or let httpx exception propagate
            raise HabiticaAPIError(msg, status_code=408) from timeout_err

        except httpx.HTTPStatusError as http_err:
            # Handle 4xx/5xx errors specifically
            response = http_err.response
            error_details = f"HTTP Error: {http_err.request.method} {http_err.request.url} - Status {response.status_code}"
            try:
                err_data = response.json()
                error_type = err_data.get("error", "N/A")
                message = err_data.get("message", "N/A")
                error_details += f" | API: '{error_type}' - '{message}'"

                # Raise custom error with details
                raise HabiticaAPIError(
                    f"{error_type} - {message}",
                    status_code=response.status_code,
                    error_type=error_type,
                    response_data=err_data,
                ) from http_err
            except httpx.JSONDecodeError:
                error_details += f" | Response Body (non-JSON): {response.text[:200]}"
                console.print(f"Request Failed: {error_details}", style="error")

                # Raise custom error even without API specifics
                raise HabiticaAPIError(
                    f"HTTP Error {response.status_code} with non-JSON body",
                    status_code=response.status_code,
                ) from http_err

        except httpx.RequestError as req_err:
            # Catch other httpx request errors (connection, DNS, etc.)
            msg = f"Network/Request Error for {method} {endpoint}"
            console.print(f"{msg}: {req_err}", style="error")
            raise HabiticaAPIError(msg) from req_err

        # Raise custom error

        except json.JSONDecodeError as json_err:
            # Changed from httpx.JSONDecodeError to standard json

            # Successful status code but invalid JSON body (should be rare with check above)
            msg = f"Could not decode JSON response from {method} {endpoint}"
            status = response.status_code if response else "N/A"
            body = response.text[:200] if response else "N/A"
            console.print(f"{msg} (Status: {status}, Body: {body})", style="error")
            raise ValueError(f"Invalid JSON received from {method} {endpoint}") from json_err

        except Exception as e:
            # Catch any other unexpected errors
            console.print(
                f"Unexpected error during API request: {type(e).__name__} - {e}", style="error"
            )
            console.print_exception(show_locals=False)
            raise

    # Re-raise unknown exceptions

    # --- Async Core HTTP Methods (Keep as before, using await self._request) ---
    # FUNC: - get
    async def get(
        self, endpoint: str, params: Optional[dict[str, Any]] = None
    ) -> HabiticaApiResponse:
        """Sends GET request. Returns JSON data or None."""
        return await self._request("GET", endpoint, params=params)

    # FUNC: - post
    async def post(
        self, endpoint: str, data: Optional[dict[str, Any]] = None
    ) -> HabiticaApiResponse:
        """Sends POST request with JSON data. Returns JSON data or None."""
        return await self._request("POST", endpoint, json=data)

    # FUNC: - put
    async def put(
        self, endpoint: str, data: Optional[dict[str, Any]] = None
    ) -> HabiticaApiResponse:
        """Sends PUT request with JSON data. Returns JSON data or None."""
        return await self._request("PUT", endpoint, json=data)

    # FUNC: - delete
    async def delete(
        self, endpoint: str, params: Optional[dict[str, Any]] = None
    ) -> HabiticaApiResponse:
        """Sends DELETE request. Returns JSON data (often empty dict) or None."""
        # DELETE requests might have query params sometimes (though less common)
        return await self._request("DELETE", endpoint, params=params)

    # ... (get_user_data, update_user, get_tasks, create_task, etc. - all use await) ...

    # SECTION: - Convenience Methods (User)

    # FUNC: - get_user_data
    async def get_user_data(self) -> Optional[dict[str, Any]]:
        """GET /user - Retrieves the full user object."""
        result = await self.get("/user")

        # Ensure the returned data (from 'data' field) is actually a dict
        return result if isinstance(result, dict) else None

    # FUNC: - update_user
    async def update_user(self, update_data: dict[str, Any]) -> Optional[dict[str, Any]]:
        """PUT /user - Updates general user settings."""
        result = await self.put("/user", data=update_data)
        return result if isinstance(result, dict) else None

    # FUNC: - set_custom_day_start
    async def set_custom_day_start(self, hour: int) -> Optional[dict[str, Any]]:
        """Sets user's custom day start hour (0-23). Uses PUT /user."""
        if not 0 <= hour <= 23:
            raise ValueError("Hour must be between 0 and 23")
        return await self.update_user({"preferences.dayStart": hour})

    # FUNC: - toggle_user_sleep
    async def toggle_user_sleep(self) -> Optional[dict[str, Any]]:
        """POST /user/sleep - Toggles user's sleep status."""
        # API returns { "data": <boolean> } on V3, but let's handle dict return just in case
        result = await self.post("/user/sleep")

        # The _request method extracts the 'data' field.

        # If 'data' is a boolean, wrap it for consistency, otherwise return dict if present.
        if isinstance(result, bool):
            return {"sleep": result}
        elif isinstance(result, dict):
            return result

        # Return dict if API returns more info
        return None

    # Return None on error or unexpected type

    # SECTION: - Convenience Methods (Tasks)

    # FUNC: - get_tasks
    async def get_tasks(self, task_type: Optional[str] = None) -> list[dict[str, Any]]:
        """GET /tasks/user - Gets user tasks, optionally filtered by type."""
        params = {"type": task_type} if task_type else None
        result = await self.get("/tasks/user", params=params)

        # Ensure the result is a list, return empty list otherwise
        return result if isinstance(result, list) else []

    # FUNC: - create_task
    async def create_task(self, data: dict[str, Any]) -> Optional[dict[str, Any]]:
        """POST /tasks/user - Creates a new task."""
        if "text" not in data or "type" not in data:
            raise ValueError("Task creation data must include 'text' and 'type'.")
        result = await self.post("/tasks/user", data=data)
        return result if isinstance(result, dict) else None

    # FUNC: - update_task
    async def update_task(self, task_id: str, data: dict[str, Any]) -> Optional[dict[str, Any]]:
        """PUT /tasks/{taskId} - Updates an existing task."""
        result = await self.put(f"/tasks/{task_id}", data=data)
        return result if isinstance(result, dict) else None

    # FUNC: - delete_task
    async def delete_task(self, task_id: str) -> Optional[dict[str, Any]]:
        """DELETE /tasks/{taskId} - Deletes a specific task."""
        result = await self.delete(f"/tasks/{task_id}")

        # API might return empty dict or None on success
        return result if isinstance(result, dict) else None

    # FUNC: - score_task
    async def score_task(self, task_id: str, direction: str = "up") -> Optional[dict[str, Any]]:
        """POST /tasks/{taskId}/score/{direction} - Scores a task ('clicks' it)."""
        if direction not in ["up", "down"]:
            raise ValueError("Direction must be 'up' or 'down'")
        result = await self.post(f"/tasks/{task_id}/score/{direction}")
        return result if isinstance(result, dict) else None

    # FUNC: - set_attribute
    async def set_attribute(self, task_id: str, attribute: str) -> Optional[dict[str, Any]]:
        """Sets the primary attribute for a task. Uses `update_task`."""
        if attribute not in ["str", "int", "con", "per"]:
            raise ValueError("Attribute must be one of 'str', 'int', 'con', 'per'")
        return await self.update_task(task_id, {"attribute": attribute})

    # FUNC: - move_task_to_position
    async def move_task_to_position(
        self, task_id: str, position: int
    ) -> Optional[list[dict[str, Any]]]:
        """Moves a task to a specific position (0=top, -1=bottom).

        POST /tasks/{taskId}/move/to/{position}
        """
        if position not in [0, -1]:
            # Corrected validation based on V3 API docs
            raise ValueError("Position must be 0 (to move to top) or -1 (to move to bottom).")

        # API returns the new sorted list of task IDs (not full task objects)
        result = await self.post(f"/tasks/{task_id}/move/to/{position}")

        # The API response structure for move/to is often just the sorted list of IDs, not wrapped.
        return result if isinstance(result, list) else None

    # SECTION: - Convenience Methods (Tags)

    # FUNC: - get_tags
    async def get_tags(self) -> list[dict[str, Any]]:
        """GET /tags - Gets all user tags."""
        result = await self.get("/tags")
        return result if isinstance(result, list) else []

    # FUNC: - create_tag
    async def create_tag(self, name: str) -> Optional[dict[str, Any]]:
        """POST /tags - Creates a new tag."""
        result = await self.post("/tags", data={"name": name})
        return result if isinstance(result, dict) else None

    # FUNC: - update_tag
    async def update_tag(self, tag_id: str, name: str) -> Optional[dict[str, Any]]:
        """PUT /tags/{tagId} - Updates an existing tag's name."""
        result = await self.put(f"/tags/{tag_id}", data={"name": name})
        return result if isinstance(result, dict) else None

    # FUNC: - delete_tag
    async def delete_tag(self, tag_id: str) -> Optional[dict[str, Any]]:
        """DELETE /tags/{tagId} - Deletes an existing tag globally."""
        result = await self.delete(f"/tags/{tag_id}")

        # Often returns None or empty dict on success
        return result if isinstance(result, dict) else None

    # FUNC: - add_tag_to_task
    async def add_tag_to_task(self, task_id: str, tag_id: str) -> Optional[dict[str, Any]]:
        """POST /tasks/{taskId}/tags/{tagId} - Associates a tag with a task."""
        # This endpoint might return the updated task or just success status
        result = await self.post(f"/tasks/{task_id}/tags/{tag_id}")

        # V3 API likely just returns {success: true} without data, _request handles this.

        # If it returns the task, it would be a dict.
        return result if isinstance(result, dict) else None

    # Return dict if present, else None

    # FUNC: - delete_tag_from_task
    async def delete_tag_from_task(self, task_id: str, tag_id: str) -> Optional[dict[str, Any]]:
        """DELETE /tasks/{taskId}/tags/{tagId} - Removes tag association from task."""
        result = await self.delete(f"/tasks/{task_id}/tags/{tag_id}")
        return result if isinstance(result, dict) else None

    # SECTION: - Convenience Methods (Checklist)

    # FUNC: - add_checklist_item
    async def add_checklist_item(self, task_id: str, text: str) -> Optional[dict[str, Any]]:
        """POST /tasks/{taskId}/checklist - Adds checklist item."""
        result = await self.post(f"/tasks/{task_id}/checklist", data={"text": text})
        return result if isinstance(result, dict) else None

    # Returns updated task

    # FUNC: - update_checklist_item
    async def update_checklist_item(
        self, task_id: str, item_id: str, text: str
    ) -> Optional[dict[str, Any]]:
        """PUT /tasks/{taskId}/checklist/{itemId} - Updates checklist item text."""
        result = await self.put(f"/tasks/{task_id}/checklist/{item_id}", data={"text": text})
        return result if isinstance(result, dict) else None

    # Returns updated task

    # FUNC: - delete_checklist_item
    async def delete_checklist_item(self, task_id: str, item_id: str) -> Optional[dict[str, Any]]:
        """DELETE /tasks/{taskId}/checklist/{itemId} - Deletes checklist item."""
        result = await self.delete(f"/tasks/{task_id}/checklist/{item_id}")
        return result if isinstance(result, dict) else None

    # Returns updated task

    # FUNC: - score_checklist_item
    async def score_checklist_item(self, task_id: str, item_id: str) -> Optional[dict[str, Any]]:
        """POST /tasks/{taskId}/checklist/{itemId}/score - Toggles checklist item completion."""
        result = await self.post(f"/tasks/{task_id}/checklist/{item_id}/score")
        return result if isinstance(result, dict) else None

    # Returns updated task

    # SECTION: - Convenience Methods (Challenges)

    # FUNC: - get_challenges
    async def get_challenges(self, member_only: bool = True) -> list[dict[str, Any]]:
        """GET /challenges/user - Retrieves challenges (owned or joined), handles pagination."""
        all_challenges = []
        page = 0
        member_param = "true" if member_only else "false"
        console.log(
            f"Fetching challenges (member_only={member_only}, paginating)...", style="info"
        )
        while True:
            try:
                # Use params argument for GET request
                challenge_page_data = await self.get(
                    "/challenges/user", params={"member": member_param, "page": page}
                )
                if isinstance(challenge_page_data, list):
                    if not challenge_page_data:
                        # Empty list means no more pages
                        break
                    all_challenges.extend(challenge_page_data)

                    # console.log(f"  Fetched page {page} ({len(challenge_page_data)} challenges)", style="subtle")
                    page += 1
                else:
                    # Should not happen with this endpoint if API is consistent
                    console.print(
                        f"Warning: Expected list from /challenges/user page {page}, got {type(challenge_page_data)}. Stopping pagination.",
                        style="warning",
                    )
                    break
            except (httpx.exceptions.RequestException, ValueError) as e:
                console.print(
                    f"Error fetching challenges page {page}: {e}. Stopping pagination.",
                    style="error",
                )
                break

        # Stop pagination on error
        console.log(
            f"Finished fetching challenges. Total found: {len(all_challenges)}", style="info"
        )
        return all_challenges

    # FUNC: - create_challenge
    async def create_challenge(self, data: dict[str, Any]) -> Optional[dict[str, Any]]:
        """POST /challenges - Creates a new challenge."""
        result = await self.post("/challenges", data=data)
        return result if isinstance(result, dict) else None

    # FUNC: - get_challenge_tasks
    async def get_challenge_tasks(self, challenge_id: str) -> list[dict[str, Any]]:
        """GET /tasks/challenge/{challengeId} - Retrieves tasks for a challenge."""
        result = await self.get(f"/tasks/challenge/{challenge_id}")
        return result if isinstance(result, list) else []

    # FUNC: - unlink_task_from_challenge
    async def unlink_task_from_challenge(
        self, task_id: str, keep: str = "keep"
    ) -> Optional[dict[str, Any]]:
        """POST /tasks/{taskId}/unlink - Unlinks a single task from its challenge.
        Note: V3 API uses /tasks/{taskId}/unlink?keep={keep_option}.
        """
        if keep not in ["keep", "remove"]:
            raise ValueError("keep must be 'keep' or 'remove'")

        # Endpoint path is just /unlink, keep option is a query parameter
        result = await self.post(f"/tasks/unlink-one/{task_id}?keep={keep}")

        # API often returns None or {} on success for unlink actions
        return result if isinstance(result, dict) else None

    # FUNC: - unlink_all_challenge_tasks
    async def unlink_all_challenge_tasks(
        self, challenge_id: str, keep: str = "keep-all"
    ) -> Optional[dict[str, Any]]:
        """POST /tasks/unlink-all/{challengeId} - Unlinks ALL tasks from a challenge.
        Note: V3 API uses /tasks/unlink-all/{challengeId}?keep={keep_option}.
        """
        if keep not in ["keep-all", "remove-all"]:
            raise ValueError("keep must be 'keep-all' or 'remove-all'")

        # Pass 'keep' as a query parameter
        result = await self.post(f"/tasks/unlink-all/{challenge_id}?keep={keep}")
        return result if isinstance(result, dict) else None

    # FUNC: - leave_challenge
    async def leave_challenge(
        self, challenge_id: str, keep: str = "keep-all"
    ) -> Optional[dict[str, Any]]:
        """POST /challenges/{challengeId}/leave - Leaves a challenge, handling tasks.
        Note: V3 API uses /challenges/{challengeId}/leave?keep={keep_option}.
        """
        if keep not in ["keep-all", "remove-all"]:
            raise ValueError("keep must be 'keep-all' or 'remove-all'")

        # Pass 'keep' as a query parameter
        result = await self.post(f"/challenges/{challenge_id}/leave?keep={keep}")
        return result if isinstance(result, dict) else None

    # SECTION: - Convenience Methods (Group & Party)

    # FUNC: - get_party_data
    async def get_party_data(self) -> Optional[dict[str, Any]]:
        """GET /groups/party - Gets data about the user's current party."""
        result = await self.get("/groups/party")

        # API returns null or error if not in party, _request handles errors,

        # so None means not in party or actual error occurred.
        return result if isinstance(result, dict) else None

    # FUNC: - get_quest_status
    async def get_quest_status(self) -> bool:
        """Checks if the user's party is currently on an active quest."""
        try:
            party_data = await self.get_party_data()

            # Safely access nested keys
            return (
                party_data is not None and party_data.get("quest", {}).get("active", False) is True
            )
        except httpx.exceptions.RequestException as e:
            # Log error but return False, as quest status is unknown/unavailable
            console.print(f"Could not get party data for quest status: {e}", style="warning")
            return False
        except ValueError as e:
            # Catch potential errors from API response format
            console.print(f"Invalid data received for party data: {e}", style="warning")
            return False

    # SECTION: - Convenience Methods (Inbox)

    # FUNC: - get_inbox_messages
    async def get_inbox_messages(self, page: int = 0) -> list[dict[str, Any]]:
        """GET /inbox/messages - Gets inbox messages (paginated)."""
        result = await self.get("/inbox/messages", params={"page": page})

        # API returns list directly in 'data' field
        return result if isinstance(result, list) else []

    # SECTION : - Convenience Methods (Content)

    # FUNC: - get_content
    async def get_content(self) -> Optional[dict[str, Any]]:
        """GET /content - Retrieves the game content object."""
        # This endpoint does NOT use the standard {success, data} wrapper
        result = await self._request("GET", "/content")

        return result if isinstance(result, dict) else None
