from core import auth_file, habitica_api


def category_Tags(all_tasks):
    challenge_tag = auth_file.get_key_from_config("tags", "challenge")
    personal_tag = auth_file.get_key_from_config("tags", "owned")

    categories = {"challenge": [], "unpersonal": [], "unchallenge": [], "personal": []}
    for counter1, task in enumerate(all_tasks):
        item = all_tasks[task]
        task = {"id": item["id"], "tags": item["tag_id"]}
        if len(item["challenge"]) != 0:
            if challenge_tag not in item["tag_id"]:
                habitica_api.post("tasks/" + item["id"] + "/tags/" + challenge_tag)
            elif personal_tag in item["tag_id"]:
                habitica_api.delete("tasks/" + item["id"] + "/tags/" + personal_tag)
        else:
            if challenge_tag in item["tag_id"]:
                habitica_api.delete("tasks/" + item["id"] + "/tags/" + challenge_tag)

            elif personal_tag not in item["tag_id"]:
                habitica_api.post("tasks/" + item["id"] + "/tags/" + personal_tag)
    return categories