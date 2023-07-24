import Requests, SaveFile
import json
import emoji_data_python


def GetTags():
    TagsCh = {}
    Tags = {}
    MyTags = {}
    AllTags = Requests.GetAPI("tags")
    for idx, tag in enumerate(AllTags["data"]):
        Tag = {}
        name = emoji_data_python.replace_colons(tag["name"].replace("target","dart"))
        Tag.update({"ID": tag["id"], "NAME": name})
        if "challenge" in tag:
            TagsCh.update({name: Tag})
        else:
            Tags.update({name: Tag})
        MyTags.update({"ChallengeTags": TagsCh, "PersonalTags": Tags})

    SaveFile.SaveFile(MyTags, "AllTags")
    return MyTags
