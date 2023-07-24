
def clean_tags(Tags):
    usedtag = all_["tags"]
    alltag = []

    for tag in myTags:
        alltag.append(tag)
    used = l2s(usedtag)
    alls = l2s(alltag)
    m = alls.difference(used)
    print(f"used: {len(used)} all:{len(alls)}, inter:{len(m)}")
    for x in m:
        print(x)
        print(myTags[x]["name"])
        if Confirm.ask("Delete unused tag?"):
            deletetag = requests.delete(BASEURL + "tags/" + x, headers=HEADERS)

            print(deletetag)


clean_tags()
