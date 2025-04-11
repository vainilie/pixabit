# pixabit/processing.py

# Add math import for pow()
import math
from typing import Dict, Any, List, Optional, Set # Ensure needed types are imported

# Ensure Console is imported if used within TaskProcessor for logging/warnings
from rich.console import Console

# Import API class and other utils
from .api import HabiticaAPI
from .utils.dates import is_date_passed # Keep necessary utils
# from .utils.save_file import save_file # Not needed in processor itself
import emoji_data_python # Keep for processing text/notes

# Keep get_user_stats function separate for now, but we'll modify it later
# def get_user_stats(...)


class TaskProcessor:
    """
    Processes raw task data fetched from the Habitica API into a structured
    format, including calculated potential damage for dailies.
    """

    # --- MODIFIED __init__ ---
    def __init__(self, api_client: HabiticaAPI):
        """
        Initializes the TaskProcessor, fetching necessary context like
        tags, user stats, and party info needed for processing.
        """
        self.api_client = api_client
        # Get console from API client, or create a default one
        self.console = getattr(api_client, 'console', Console())
        self.console.log("Initializing TaskProcessor...")

        # Fetch tags
        self.console.log("  - Fetching tags for lookup...")
        self.tags_lookup = self._fetch_and_prepare_tags()
        self.console.log(f"  - Fetched {len(self.tags_lookup)} tags.")

        # --- Fetch and store user context needed for damage calc ---
        self.user_data: Dict[str, Any] = {}
        self.party_data: Dict[str, Any] = {}
        self.user_con: int = 0
        self.user_stealth: int = 0 # Current stealth points
        self.is_sleeping: bool = False
        self.is_on_boss_quest: bool = False
        self.boss_str: float = 0.0

        try:
            self.console.log("  - Fetching user data for context...")
            self.user_data = self.api_client.get_user_data() # Use API client method
            # Use .get with defaults for safe access
            self.user_con = self.user_data.get("stats", {}).get("con", 0)
            self.user_stealth = self.user_data.get("stats", {}).get("buffs", {}).get("stealth", 0)
            self.is_sleeping = self.user_data.get("preferences", {}).get("sleep", False)
            self.console.log(f"  - User Context: CON={self.user_con}, Stealth={self.user_stealth}, Sleeping={self.is_sleeping}")

            self.console.log("  - Fetching party data for context...")
            self.party_data = self.api_client.get_party_data() # Use API client method
            quest_info = self.party_data.get("quest", {})

            if quest_info and quest_info.get("active"):
                 boss_info = quest_info.get("content", {}).get("boss")
                 if isinstance(boss_info, dict) and boss_info.get("str") is not None:
                      self.is_on_boss_quest = True
                      try: self.boss_str = float(boss_info.get("str", 0.0))
                      except (ValueError, TypeError): self.boss_str = 0.0
                      self.console.log(f"  - Party Context: On active boss quest (Str={self.boss_str}).")
                 else:
                      self.console.log("  - Party Context: On active quest (not boss or no str).")
            else:
                 self.console.log("  - Party Context: Not on active quest.")

        except Exception as e:
            self.console.print(f"  - [Warning] Couldn't fetch all context for TaskProcessor: {e}")
            # Ensure defaults if fetches failed
            self.user_data = self.user_data or {}; self.party_data = self.party_data or {}
            self.user_con = self.user_con or 0; self.user_stealth = self.user_stealth or 0
            self.is_sleeping = self.is_sleeping or False; self.is_on_boss_quest = self.is_on_boss_quest or False
            self.boss_str = self.boss_str or 0.0
        # ------------------------------------------------------------
        self.console.log("TaskProcessor Initialized.")

    # --- Keep _fetch_and_prepare_tags, _value_color, _process_task_tags ---
    def _fetch_and_prepare_tags(self) -> Dict[str, str]:
        # ... (Implementation as before) ...
        pass

    def _value_color(self, value: Optional[float]) -> str:
        # ... (Implementation as before) ...
        pass

    def _process_task_tags(self, task_data: Dict) -> List[str]:
        # ... (Implementation as before) ...
        pass

    # --- Keep _process_habit, _process_todo, _process_reward ---
    # (Make sure they use task_data.get(...) correctly)
    def _process_habit(self, task_data: Dict) -> Dict[str, Any]:
         # ... (Implementation as before) ...
         pass

    def _process_todo(self, task_data: Dict) -> Dict[str, Any]:
         # ... (Implementation as before, using imported date utils) ...
         pass

    def _process_reward(self, task_data: Dict) -> Dict[str, Any]:
         # ... (Implementation as before) ...
         pass

    # --- NEW HELPER METHOD ---
    def _calculate_checklist_done(self, checklist: Optional[List[Dict]]) -> float:
        """Calculates the proportion (0.0 to 1.0) of checklist items done."""
        if not checklist or not isinstance(checklist, list) or len(checklist) == 0:
            # No checklist or empty = 100% "done" for damage reduction
            return 1.0
        completed_count = sum(1 for item in checklist if item.get("completed", False))
        total_count = len(checklist)
        return completed_count / total_count if total_count > 0 else 1.0

    # --- MODIFIED _process_daily ---
    def _process_daily(self, task_data: Dict) -> Dict[str, Any]:
        """Processes Daily specific fields, including per-task damage calculation."""
        processed = {}
        # Status calculation
        is_due = task_data.get("isDue", False)
        completed = task_data.get("completed", False)
        status = "grey" if not is_due else ("done" if completed else "due")
        processed["_status"] = status

        # Other daily fields
        checklist_items = task_data.get("checklist", [])
        processed["checklist"] = checklist_items # Keep raw items
        next_due_list = task_data.get("nextDue", [])
        processed["date"] = next_due_list[0] if isinstance(next_due_list, list) and len(next_due_list) > 0 else ""
        processed["is_due"] = is_due
        processed["streak"] = task_data.get("streak", 0)
        task_value = task_data.get("value", 0.0)
        processed["value"] = task_value
        processed["value_color"] = self._value_color(task_value)

        # --- Damage Calculation Logic ---
        damage_to_user = 0.0
        damage_to_party = 0.0
        # Note: We check current stealth but don't modify it here.
        # If multiple tasks would be stealthed, this calculates damage as 0 for all,
        # which might slightly underestimate total damage if stealth runs out.
        # Accurate stealth accounting would require processing dailies in order.
        if is_due and not completed and not self.is_sleeping and self.user_stealth <= 0:
            # Value capping
            value_min = -47.27; value_max = 21.27
            curr_val = max(value_min, min(task_value, value_max))

            # Base delta (~0-1, higher for more negative value)
            delta = abs(math.pow(0.9747, curr_val))

            # Checklist reduction (Full completion = 0 damage)
            checklist_done_ratio = self._calculate_checklist_done(checklist_items)
            delta *= (1.0 - checklist_done_ratio)

            # User Damage
            con_bonus = max(0.1, 1.0 - (float(self.user_con) / 250.0))
            priority = task_data.get("priority", 1.0)
            try: # Handle priority being string or number
                prio_float = float(priority)
                prio_map = {0.1: 0.1, 1.0: 1.0, 1.5: 1.5, 2.0: 2.0}
                priority_multiplier = prio_map.get(prio_float, 1.0) # Default to 1 if invalid
            except (ValueError, TypeError):
                priority_multiplier = 1.0

            hp_mod = delta * con_bonus * priority_multiplier * 2.0
            damage_to_user = round(hp_mod, 2) # Round

            # Party Damage (Boss Quests)
            if self.is_on_boss_quest and self.boss_str > 0:
                boss_delta = delta
                if priority_multiplier < 1.0: boss_delta *= priority_multiplier # Trivial adj
                damage_to_party_unrounded = boss_delta * self.boss_str
                damage_to_party = round(damage_to_party_unrounded, 1) # Round to 1 decimal
            else:
                damage_to_party = 0.0
        # else: damage remains 0 (sleeping, completed, not due, or stealthed)

        processed["damage_to_user"] = damage_to_user
        processed["damage_to_party"] = damage_to_party
        # -----------------------------

        return processed

    # --- process_single_task and process_and_categorize_all remain mostly the same ---
    # Ensure process_single_task calls the updated _process_daily
    def process_single_task(self, task_data: Dict) -> Optional[Dict[str, Any]]:
        # ... (process common fields) ...
        processed = { ... }
        task_type = task_data.get("type")
        type_specific_data = {}
        if task_type == "habit": type_specific_data = self._process_habit(task_data)
        elif task_type == "todo": type_specific_data = self._process_todo(task_data)
        elif task_type == "daily": type_specific_data = self._process_daily(task_data) # Calls updated method
        elif task_type == "reward": type_specific_data = self._process_reward(task_data)
        # ...
        processed.update(type_specific_data)
        return processed

    def process_and_categorize_all(self) -> Dict[str, Dict]:
        # ... (fetches tasks using self.api_client.get_tasks()) ...
        # ... (loops through raw tasks, calls self.process_single_task) ...
        # ... (builds tasks_dict and cats_dict) ...
        # This now uses the updated process_single_task -> _process_daily
        # The resulting 'tasks_dict' will have damage info included for dailies
        pass # Keep your existing implementation here

# --- End of TaskProcessor modifications ---

# --- Modify get_user_stats function ---
# (Remove damage calculation from here, sum it from processed_tasks instead)
def get_user_stats(api_client: HabiticaAPI, cats_dict: Dict, processed_tasks_dict: Dict) -> Dict[str, Any]:
     # ... (fetch user_data as before) ...
     # ... (calculate task_numbers from cats_dict) ...
     # ... (convert login time) ...

     # --- NEW: Sum damage from processed dailies ---
     total_potential_user_damage = 0.0
     total_potential_party_damage = 0.0
     try:
          # Get IDs of dailies marked 'due' by TaskProcessor
          # (Status reflects non-completion if task is due)
          due_daily_ids = cats_dict.get("tasks", {}).get("dailys", {}).get("due", [])

          for task_id in due_daily_ids:
               processed_task = processed_tasks_dict.get(task_id)
               if processed_task:
                    total_potential_user_damage += processed_task.get("damage_to_user", 0.0)
                    total_potential_party_damage += processed_task.get("damage_to_party", 0.0)
     except Exception as sum_e:
          print(f"Warning: Error summing damage from processed tasks: {sum_e}")
     # ------------------------------------------

     output_stats = {
          # ... (other stats as before) ...
          "potential_daily_damage_user": round(total_potential_user_damage, 2),
          "potential_daily_damage_party": round(total_potential_party_damage, 2),
          # Remove the old "potential_daily_damage_score" if it existed
     }
     return output_stats

# --- Modify CliApp._display_stats ---
# (Update to show the new *_user / *_party damage fields)
# Inside class CliApp:
    def _display_stats(self):
         # ... get stats_data = self.user_stats ...
         user_dmg = stats_data.get("potential_daily_damage_user", 0.0)
         party_dmg = stats_data.get("potential_daily_damage_party", 0.0)
         # ... build user_info_table ...
         dmg_color = "red" if user_dmg >= 10 else "yellow" if user_dmg > 0 else "dim"
         party_dmg_str = f", Party: {party_dmg:.1f}" if party_dmg > 0 else ""
         # Update the display row:
         user_info_table.add_row(":biohazard:", f"Potential Daily Damage: [{dmg_color}]User: {user_dmg:.1f}{party_dmg_str}[/]")
         # ... rest of display ...