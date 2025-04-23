# --- Example Usage (Illustrative) ---
async def main():
    # Assume USER_ID and API_TOKEN are loaded securely (e.g., env vars, config file)
    try:
        import os

        user_id = os.environ.get("HABITICA_USER_ID")
        api_token = os.environ.get("HABITICA_API_TOKEN")
        if not user_id or not api_token:
            raise ValueError(
                "Set HABITICA_USER_ID and HABITICA_API_TOKEN environment variables"
            )

        # --- Initialize Client ---
        api = HabiticaAPI(user_id=user_id, api_token=api_token)

        try:
            # --- Make API Calls ---
            print("Fetching user data...")
            user_data = await api.get_user_data()
            if user_data:
                print(
                    f"  Welcome, {user_data.get('profile', {}).get('name', 'User')}!"
                )
                print(
                    f"  Level: {user_data.get('stats', {}).get('lvl', 'N/A')}"
                )
            else:
                print("  Could not fetch user data.")

            print("\nFetching tasks...")
            tasks = await api.get_tasks()
            print(f"  Fetched {len(tasks)} tasks.")
            if tasks:
                print(f"  First task text: {tasks[0].get('text', 'N/A')}")

            # Example: Score a task (replace with a real task ID)
            # try:
            #     print("\nScoring task 'dummy-task-id' up...")
            #     score_result = await api.score_task("dummy-task-id", "up")
            #     print(f"  Score result: {score_result}")
            # except HabiticaAPIError as e:
            #     print(f"  Failed to score task: {e}")

        finally:
            # --- Close Client ---
            await api.close()

    except ValueError as e:
        print(f"Configuration Error: {e}")
    except HabiticaAPIError as e:
        print(f"API Error: {e}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        logger.exception("Unexpected error in main execution", exc_info=True)


if __name__ == "__main__":
    # Basic logging setup for the example
    logging.basicConfig(
        level="INFO", format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logger.info("Starting Habitica API example...")
    asyncio.run(main())
