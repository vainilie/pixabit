"""Habitica data manager for efficiently handling game content."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional, Set, Union

from pydantic import BaseModel, Field

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Define base models for each content type
class Spell(BaseModel):
    """Habitica spell model."""

    key: str
    text: str
    description: str = Field(alias="notes")
    mana_cost: float = Field(alias="mana")
    target: str
    klass: Literal["healer", "warrior", "wizard", "rogue"]

    bulk: bool | None = False
    immediateUse: bool | None = False
    limited: bool | None = False
    level_required: int | None = Field(alias="lvl", default=1)
    previousPurchase: bool | None = False
    purchaseType: str | None = None
    silent: bool | None = False
    value: int | None = 0

    model_config = {
        "extra": "ignore",
        "populate_by_name": True,
    }


class BossModel(BaseModel):
    """Model for boss properties."""

    defense: int = Field(alias="def")
    hp: int
    name: str
    strength: float = Field(alias="str")


class DropModel(BaseModel):
    """Model for drop properties."""

    exp: int
    gp: int


class UnlockConditionModel(BaseModel):
    """Model for unlock condition properties."""

    condition: str
    text: str


class Quest(BaseModel):
    """Habitica quest model."""

    # Required fields
    category: str
    completion: str
    key: str
    notes: str
    text: str
    drop: DropModel

    # Optional fields
    boss: BossModel | None = None
    goldValue: int | None = None
    group: str | None = None
    unlockCondition: UnlockConditionModel | None = None

    # Additional fields from first schema that weren't in the detailed analysis
    addlNotes: str | None = None
    completionChat: str | None = None
    collect: dict[str | Any] | None = None
    colors: dict[str | Any] | None = None
    prereqQuests: dict[str | Any] | None = None
    prerequisite: dict[str | Any] | None = None
    previous: str | None = None
    previous1: str | None = None
    lvl: int | None = None
    value: int | None = None

    model_config = {
        "extra": "ignore",
        "populate_by_name": True,
    }


class Gear(BaseModel):
    """Habitica gear model."""

    constitution: int = Field(alias="con")
    index: str
    intelligence: int = Field(alias="int")
    key: str
    klass: str
    notes: str
    perception: int = Field(alias="per")
    sett: str = Field(alias="set")
    strength: int = Field(alias="str")
    text: str
    gear_type: str = Field(alias="type")
    value: int

    # optional
    event: dict | None = None
    gearSet: str | None = None
    last: bool | None = False
    mistery: str | None = None
    season: str | None = None
    specialClass: str | None = None
    twoHanded: bool | None = False

    model_config = {
        "extra": "ignore",
        "populate_by_name": True,
    }


class GameContent(BaseModel):
    """Container for all game content we're interested in."""

    spells: Dict[str, Dict[str, Spell]]
    quests: Dict[str, Quest]
    gear: Dict[str, Gear]
    last_updated: datetime

    model_config = {
        "arbitrary_types_allowed": True,
    }

    @classmethod
    def from_full_content(cls, content_data: Dict[str, Any]) -> GameContent:
        """Create GameContent from the full Habitica content JSON."""
        # Process spells (grouped by class)
        processed_spells: Dict[str, Dict[str, Spell]] = {}
        for klass, spells_dict in content_data.get("spells", {}).items():
            if klass == "special":  # Optionally skip special spells
                continue

            processed_spells[klass] = {}
            for spell_key, spell_data in spells_dict.items():
                try:
                    processed_spells[klass][spell_key] = Spell(
                        key=spell_key, klass=klass, **spell_data
                    )
                except Exception as e:
                    logger.warning(f"Error processing spell {spell_key}: {e}")

        # Process quests (flat structure)
        processed_quests: Dict[str, Quest] = {}
        for quest_key, quest_data in content_data.get("quests", {}).items():
            try:
                processed_quests[quest_key] = Quest(key=quest_key, **quest_data)
            except Exception as e:
                logger.warning(f"Error processing quest {quest_key}: {e}")

        # Process gear (flat structure)
        processed_gear: Dict[str, Gear] = {}
        for gear_key, gear_data in (
            content_data.get("gear", {}).get("flat", {}).items()
        ):
            try:
                processed_gear[gear_key] = Gear(key=gear_key, **gear_data)
            except Exception as e:
                logger.warning(f"Error processing gear {gear_key}: {e}")

        # Create the container with current timestamp
        return cls(
            spells=processed_spells,
            quests=processed_quests,
            gear=processed_gear,
            last_updated=datetime.now(),
        )


class HabiticaDataManager:
    """Manages Habitica game content data with efficient caching."""

    def __init__(
        self,
        data_dir: str | Path,
        full_content_filename: str = "content.json",
        processed_content_filename: str = "processed_content.json",
        cache_duration_days: int = 30,
    ):
        """Initialize the data manager.

        Args:
            data_dir: Directory for storing data files
            full_content_filename: Filename for full content JSON
            processed_content_filename: Filename for processed content JSON
            cache_duration_days: How often to refresh the content cache
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True, parents=True)

        self.full_content_path = self.data_dir / full_content_filename
        self.processed_content_path = self.data_dir / processed_content_filename
        self.cache_duration = timedelta(days=cache_duration_days)

        self._content: GameContent | None = None

    def load_content(self, force_refresh: bool = False) -> GameContent:
        """Load game content, using cached data if available and fresh."""
        # Check if we already have content loaded in memory
        if self._content and not force_refresh:
            return self._content

        # Check if we have processed content file and it's not expired
        if not force_refresh and self.processed_content_path.exists():
            try:
                # Load the processed content
                content_dict = json.loads(
                    self.processed_content_path.read_text(encoding="utf-8")
                )

                # Check if last_updated is present and not expired
                last_updated_str = content_dict.get("last_updated")
                if last_updated_str:
                    last_updated = datetime.fromisoformat(last_updated_str)
                    if datetime.now() - last_updated < self.cache_duration:
                        logger.info("Using cached processed content")

                        # Convert date strings back to datetime
                        content_dict["last_updated"] = last_updated

                        # Parse the content using pydantic
                        self._content = GameContent.model_validate(content_dict)
                        return self._content
            except Exception as e:
                logger.warning(
                    f"Error loading processed content: {e}. Will refresh from full content."
                )

        # If we get here, we need to process the full content
        logger.info("Processing full content file")

        # Make sure we have the full content file
        if not self.full_content_path.exists():
            raise FileNotFoundError(
                f"Full content file not found at {self.full_content_path}"
            )
            # Then load from api
            habiticaAPI.get_content()
            return self._content

        # Load and process the full content
        full_content = json.loads(
            self.full_content_path.read_text(encoding="utf-8")
        )

        # Create our GameContent object
        self._content = GameContent.from_full_content(full_content)

        # Save the processed content for future use
        self.save_processed_content()

        return self._content

    def save_processed_content(self) -> None:
        """Save the processed content to a JSON file."""
        if not self._content:
            logger.warning("No content to save")
            return

        # Convert to dict and ensure datetime is serializable
        content_dict = self._content.model_dump()
        content_dict["last_updated"] = content_dict["last_updated"].isoformat()

        # Save to file
        self.processed_content_path.write_text(
            json.dumps(content_dict, indent=2), encoding="utf-8"
        )

        logger.info(f"Saved processed content to {self.processed_content_path}")

    def get_spells(
        self, klass: str | None = None
    ) -> dict[str | dict[str | Spell]] | dict[str | Spell]:
        """Get all spells or spells for a specific class."""
        content = self.load_content()

        if klass:
            return content.spells.get(klass, {})
        return content.spells

    def get_quests(
        self, key: str | None = None, category: str | None = None
    ) -> Dict[str, Quest]:
        """Get all quests or filter by category."""
        content = self.load_content()
        result = content.quests

        if key:
            result = {k: q for k, q in result.items() if q.key == key}
        if category:
            result = {k: q for k, q in result.items() if q.category == category}
        return result

    def get_gear(
        self,
        gear_type: str | None = None,
        klass: str | None = None,
        key: str | None = None,
    ) -> Dict[str, Gear]:
        """Get gear items filtered by type and/or class."""
        content = self.load_content()

        filtered_gear = content.gear

        if gear_type:
            filtered_gear = {
                k: g for k, g in filtered_gear.items() if g.type == gear_type
            }

        if klass:
            filtered_gear = {
                k: g
                for k, g in filtered_gear.items()
                if g.klass == klass or g.klass is None
            }  # Include classless gear

        if key:
            filtered_gear = {
                k: g for k, g in filtered_gear.items() if g.key == key
            }  # Include classless gear

        return filtered_gear


# Example usage
def main():
    # Initialize the data manager with a directory path
    data_manager = HabiticaDataManager("./habitica_data")

    try:
        # Force fetch/refresh if you need to update from Habitica API
        # (This would be done separately, not shown here)

        # Load the content
        content = data_manager.load_content()

        # Example: Get all warrior spells
        warrior_spells = data_manager.get_spells("warrior")
        print(f"Found {len(warrior_spells)} warrior spells")

        # Example: Get pet quests
        pet_quests = data_manager.get_quests(category="pet")
        print(f"Found {len(pet_quests)} pet quests")

        # Example: Get wizard armor
        wizard_armor = data_manager.get_gear(gear_type="armor", klass="wizard")
        print(f"Found {len(wizard_armor)} wizard armor items")

    except Exception as e:
        logger.error(f"Error in main: {e}")


if __name__ == "__main__":
    main()
