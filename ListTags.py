def Show(Tags):
    for Cat in Tags:
        print(Cat)
        for idx, Tag in enumerate(Tags[Cat]):
            print(idx, Tag)