# pixabit/models/test.py

# ─── Title ────────────────────────────────────────────────────────────────────
#          DataManager Test/Example Script
# ──────────────────────────────────────────────────────────────────────────────

# SECTION: IMPORTS
import asyncio
import logging  # Configure logging for the test
from pathlib import Path

# Project Imports (adjust paths if needed)
try:
    from pixabit.api.client import HabiticaClient
    from pixabit.config import HABITICA_DATA_PATH
    from pixabit.helpers._logger import log

    # Models needed for type checks if accessing data directly
    from pixabit.models.challenge import Challenge, ChallengeList
    from pixabit.models.game_content import StaticContentManager
    from pixabit.models.task import Daily, Task, TaskList

    # Data Manager and Dependencies
    from pixabit.services.data_manager import DataManager

except ImportError as e:
    print(f"Error importing modules for test script: {e}")
    print("Ensure pixabit is installed correctly or PYTHONPATH is set.")
    exit(1)


# SECTION: MAIN TEST FUNCTION
async def main():
    """Main test function for DataManager."""
    log.info("--- Starting DataManager Test Script ---")

    try:
        # 1. Setup Dependencies
        # --- API Client ---
        # Assumes HabiticaClient can be instantiated and picks up credentials
        api_client = HabiticaClient()
        static_cache_dir = HABITICA_DATA_PATH / "static_content"
        content_manager = StaticContentManager(cache_dir=static_cache_dir)
        test_cache_dir = HABITICA_DATA_PATH  # Use main cache for testing interaction
        data_manager = DataManager(api_client=api_client, static_content_manager=content_manager, cache_dir=test_cache_dir)
        log.info(f"DataManager instantiated (Cache: {test_cache_dir}).")

        # 2. Load All Data
        log.info("Loading all data using DataManager...")
        await data_manager.load_all_data(force_refresh=False)  # Set force_refresh=True to bypass caches
        log.success("Data loading phase complete.")

        # 3. Process Loaded Data
        log.info("Processing loaded data...")
        processing_successful = await data_manager.process_loaded_data()
        if not processing_successful:
            log.error("Data processing phase failed. Results may be incomplete.")
            # Decide if script should exit or continue with potentially unprocessed data
            # exit(1)

        # 4. Access Data via Properties
        log.info("Accessing data through DataManager properties...")

        user = data_manager.user
        tasks = data_manager.tasks
        tags = data_manager.tags
        party = data_manager.party
        static_gear = data_manager.static_gear_data  # Access loaded static data

        if user:
            print("\n--- User Info ---")
            print(f"Username: {user.username}")
            print(f"Display Name: {user.display_name}")
            print(f"Level: {user.level}")
            # Access calculated stats
            print(f"Effective STR: {user.effective_stats.get('str', 'N/A'):.1f}")
            print(f"Effective CON: {user.effective_stats.get('con', 'N/A'):.1f}")
            print(f"Max HP: {user.max_hp:.1f}")
            print(f"Gems: {user.gems}")
        else:
            print("\nUser data failed to load.")

        if tasks:
            print("\n--- Tasks Info ---")
            print(f"Total Tasks: {len(tasks)}")
            dailies = tasks.get_dailies()
            print(f"Dailies Count: {len(dailies)}")
            if dailies:
                first_daily = dailies[0]
                print(f"First Daily Text: {first_daily.text}")
                # Access processed info (tag names, status, damage)
                print(f"  -> Tags: {first_daily.tag_names}")
                print(f"  -> Status: {first_daily.calculated_status}")
                print(f"  -> User Damage: {first_daily.user_damage}")  # Uses computed_field
        else:
            print("\nTasks data failed to load.")

        # --- Access Tags ---
        tags = data_manager.tags
        if tags:
            print("\n--- Tags Info ---")
            print(f"Total Tags: {len(tags.tags)}")
        else:
            print("\nTags data unavailable.")

        # --- Access Party ---
        party = data_manager.party
        if party:
            print("\n--- Party Info ---")
            print(f"Party Name: {party.name}")  # ... (other party details)
        else:
            print("\nParty data unavailable or not in party.")

        # --- >>> NEW: Access and Display Challenges <<< ---
        challenges = data_manager.challenges  # Access the ChallengeList property
        if challenges:
            print("\n--- Challenges Info (Joined Sample) ---")
            print(f"Total challenges loaded: {len(challenges)}")
            joined_challenges = challenges.filter_joined(True)  # Filter example
            print(f"Joined challenges found: {len(joined_challenges)}")

            # Display first few joined challenges and their linked tasks
            for i, chal in enumerate(joined_challenges.challenges[:5]):  # Show first 5 joined
                print(f"\n[{i+1}] {repr(chal)}")  # Uses Challenge repr
                # --- Check the linked tasks ---
                if chal.tasks:
                    print(f"    Tasks Linked ({len(chal.tasks)}):")
                    for t_idx, task in enumerate(chal.tasks[:3]):  # Show first 3 linked tasks
                        print(f"      - Task {t_idx+1}: '{task.text[:40]}...' (ID: {task.id[:8]})")
                    if len(chal.tasks) > 3:
                        print("      ...")
                else:
                    print("    (No tasks linked from user's task list)")
        else:
            print("\nChallenges data unavailable.")
        # --- >>> END Challenge Display <<< ---

        log.info("\nData access demonstration complete.")
        log.info(f"Check cache folders '{test_cache_dir}/raw' and '{test_cache_dir}/processed' for saved files.")

    except Exception as e:
        log.exception("An unexpected error occurred in the test script.")


# --- Script Execution ---
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)-8s] %(message)s", datefmt="%H:%M:%S")
    logging.getLogger("Pixabit").setLevel(logging.DEBUG)  # Set level for your app's logger
    asyncio.run(main())
    log.info("--- DataManager Test Script Finished ---")


# ──────────────────────────────────────────────────────────────────────────────
