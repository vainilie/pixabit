"""Challenge widgets for the Habitica client UI."""

from typing import Any, Callable, Dict, List, Optional, Union

from pixabit.helpers._logger import log
from pixabit.helpers._textual import (
    Button,
    ComposeResult,
    Container,
    DataTable,
    Horizontal,
    Input,
    Label,
    Message,
    OptionList,
    ScrollableContainer,
    Select,
    Static,
    Vertical,
    on,
    reactive,
)
from pixabit.models.challenge import Challenge
from pixabit.ui.widgets.challenge_detail_panel import ChallengeDetailPanel
from pixabit.ui.widgets.challenge_list_widget import ChallengeListWidget


class ChallengeContainer(Container):
    """Container widget that holds both challenge list and detail panel."""

    class ChallengeInteraction(Message):
        """Message for challenge interactions."""

        def __init__(self, challenge_id: str, action: str, data: Optional[Dict[str, Any]] = None) -> None:
            self.challenge_id = challenge_id
            self.action = action
            self.data = data or {}
            super().__init__()

    def __init__(self, id: str = None, challenge_service=None, on_data_changed: Optional[Callable] = None) -> None:
        """Initialize the challenge tab container.

        Args:
            id: Widget ID.
            challenge_service: The challenge service for API interactions.
            on_data_changed: Callback when challenge data changes.
        """
        super().__init__(id=id)
        self.challenge_service = challenge_service
        self.on_data_changed = on_data_changed
        self._challenge_list = None
        self._challenge_detail = None

    def compose(self) -> ComposeResult:
        """Compose the layout with challenge list and detail panel."""
        yield Static("Challenges", classes="tab-header")

        with Horizontal(id="challenges-content-container"):
            yield ChallengeListWidget(id="challenge-list-widget", challenge_service=self.challenge_service)
            yield ChallengeDetailPanel(id="challenge-detail-panel", challenge_service=self.challenge_service)

    async def on_mount(self) -> None:
        """Configure the widget when it's mounted."""
        # Get references to child widgets
        self._challenge_list = self.query_one(ChallengeListWidget)
        self._challenge_detail = self.query_one(ChallengeDetailPanel)

        # Initial data load
        await self._challenge_list.load_or_refresh_data()

    async def refresh_data(self) -> None:
        """Refresh the challenge data."""
        await self._challenge_list.load_or_refresh_data()

        # If there's a challenge selected in the detail panel, refresh it too
        if self._challenge_detail.current_challenge:
            challenge_id = self._challenge_detail.current_challenge.id
            if challenge_id and self.challenge_service:
                updated_challenge = await self.challenge_service.fetch_challenge_details(challenge_id)
                self._challenge_detail.current_challenge = updated_challenge

    # Message handlers

    @on(ChallengeListWidget.ViewChallengeDetailsRequest)
    async def handle_view_challenge_details(self, message: ChallengeListWidget.ViewChallengeDetailsRequest) -> None:
        # In ChallengeContainer.handle_view_challenge_details
        log.debug(f"Received ViewChallengeDetailsRequest for ID: {message.challenge_id}")

        # ... rest of the fallback logic
        """Handle request to view challenge details."""
        if not self.challenge_service:
            log.warning("No challenge service available to fetch challenge details")
            # Fallback to searching in list data
            for challenge in self._challenge_list.challenges_data:
                if challenge.id == message.challenge_id:
                    self._challenge_detail.current_challenge = challenge
                    return
            return

        try:
            # First, check if we have it in the cached list
            challenge = None
            for c in self._challenge_list.challenges_data:
                if c.id == message.challenge_id:
                    challenge = c
                    break

            # If not found or we want full details, fetch from API
            if not challenge or not hasattr(challenge, "description"):
                challenge = await self.challenge_service.fetch_challenge_details(message.challenge_id)

            self._challenge_detail.current_challenge = challenge
        except Exception as e:
            log.error(f"Error fetching challenge details: {e}")
            # Try to get from challenge list if API call fails
            for challenge in self._challenge_list.challenges_data:
                if challenge.id == message.challenge_id:
                    self._challenge_detail.current_challenge = challenge
                    return
            self._challenge_detail.current_challenge = None

    @on(ChallengeDetailPanel.ViewChallengeTasks)
    async def handle_view_challenge_tasks(self, message: ChallengeDetailPanel.ViewChallengeTasks) -> None:
        """Handle viewing challenge tasks."""
        # No need to do anything here - the detail panel handles loading tasks itself
        self.post_message(self.ChallengeInteraction(message.challenge_id, "view_tasks"))

    @on(ChallengeDetailPanel.JoinChallenge)
    async def handle_join_challenge(self, message: ChallengeDetailPanel.JoinChallenge) -> None:
        """Handle joining a challenge."""
        if not self.challenge_service:
            log.warning("No challenge service available to join challenge")
            return

        try:
            # Join the challenge via the service
            success = await self.challenge_service.join_challenge(message.challenge_id)

            if success:
                # Notify that data has changed
                if self.on_data_changed:
                    await self.on_data_changed({"action": "join", "challenge_id": message.challenge_id})

                # Fetch updated challenge details
                updated_challenge = await self.challenge_service.fetch_challenge_details(message.challenge_id)
                self._challenge_detail.current_challenge = updated_challenge

                # Refresh challenge list
                await self.refresh_data()
        except Exception as e:
            log.error(f"Error joining challenge: {e}")

    @on(ChallengeDetailPanel.LeaveChallenge)
    async def handle_leave_challenge(self, message: ChallengeDetailPanel.LeaveChallenge) -> None:
        """Handle leaving a challenge."""
        if not self.challenge_service:
            log.warning("No challenge service available to leave challenge")
            return

        try:
            # Leave the challenge via the service
            success = await self.challenge_service.leave_challenge(message.challenge_id, message.keep)

            if success:
                # Notify that data has changed
                if self.on_data_changed:
                    await self.on_data_changed({"action": "leave", "challenge_id": message.challenge_id, "keep": message.keep})

                # Fetch updated challenge details
                updated_challenge = await self.challenge_service.fetch_challenge_details(message.challenge_id)
                self._challenge_detail.current_challenge = updated_challenge

                # Refresh challenge list
                await self.refresh_data()
        except Exception as e:
            log.error(f"Error leaving challenge: {e}")

    @on(ChallengeDetailPanel.CompleteChallenge)
    async def handle_complete_challenge(self, message: ChallengeDetailPanel.CompleteChallenge) -> None:
        """Handle completing a challenge."""
        # This appears to be a placeholder in your original code
        # We'll keep it as such, but with better error handling
        if not self.challenge_service:
            log.warning("No challenge service available to complete challenge")
            return

        try:
            # This method doesn't exist in our service yet, so we'll log a warning
            log.warning(f"Complete challenge functionality not implemented for challenge {message.challenge_id}")

            # Notify that data has changed (if you implement this later)
            if self.on_data_changed:
                await self.on_data_changed({"action": "complete", "challenge_id": message.challenge_id})
        except Exception as e:
            log.error(f"Error completing challenge: {e}")

    @on(ChallengeDetailPanel.EditChallenge)
    async def handle_edit_challenge(self, message: ChallengeDetailPanel.EditChallenge) -> None:
        """Handle editing a challenge."""
        if not self.challenge_service:
            log.warning("No challenge service available to edit challenge")
            return

        # In a real implementation, you would show a form/modal to edit the challenge
        log.info(f"Edit challenge request for challenge {message.challenge_id} - not implemented yet")

        # For now, just notify that we would edit the challenge
        if self.on_data_changed:
            await self.on_data_changed({"action": "edit", "challenge_id": message.challenge_id})
