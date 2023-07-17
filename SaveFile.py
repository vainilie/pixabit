import json


def SaveFile(data, title):
    outfile = open("files/" + title + ".json", "w", encoding="utf-8")
    json.dump(
        data,
        outfile,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        indent=3,
    )
