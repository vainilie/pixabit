from core import habitica_api, save_file
import time


def get_challenges():
    counter = 0
    challenges = []
    while counter >= 0:
        challenge_data = habitica_api.get(f"challenges/user?page={counter}")["data"]
        if len(challenge_data) == 0:
            break
        else:
            challenges.append(challenge_data)
            counter += 1
            print(counter)
            time.sleep(60 / 30)
    save_file.save_file(challenges, "my_challenges", "_json")
    return challenges
