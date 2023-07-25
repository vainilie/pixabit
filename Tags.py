import Requests
import SaveFile
import emoji_data_python


def GetTags():
    TagsCh = []
    Tags = []
    MyTags = {}
    AllTags = Requests.GetAPI("tags")
    for idx, tag in enumerate(AllTags["data"]):
        Tag = {}
        name = emoji_data_python.replace_colons(tag["name"].replace("target", "dart"))
        Tag.update({"id": tag["id"], "name": name})
        if "challenge" in tag:
            TagsCh.append(Tag)
        else:
            Tags.append(Tag)

    MyTags.update(
        {
            "challengeTags": sorted(TagsCh, key=lambda x: x["name"].lower()),
            "personalTags": sorted(Tags, key=lambda x: x["name"].lower()),
        }
    )

    SaveFile.SaveFile(MyTags, "AllTags")
    return MyTags
