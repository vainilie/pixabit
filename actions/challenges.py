from core.auth_file import get_key_from_config
from core.habitica_api import post, delete
from utils.rich_utils import Confirm, print
from get import get_challenges
from utils.rich_utils import Table, Console, Panel, box, console, Columns


### api get challenges member YES not working

def list_challenges(challengue):
    all_challenges = get_challenges.get_my_challenges()
    
    challenges_table=  Table(title="Challenges",box=box.MARKDOWN)
    challenges_table.add_column("#")   
    challenges_table.add_column("$")
    challenges_table.add_column("u")
    challenges_table.add_column("%")
    challenges_table.add_column("H")
    challenges_table.add_column("D")
    challenges_table.add_column("T")
    challenges_table.add_column("R")
    challenges_table.add_column("X")
    challenges_table.add_column("name")
    for idx, challenge in enumerate(all_challenges):
        if challenge["id"] in challengue["cats"]["challenge"]:
            challenges_table.add_row(str(idx), str(challenge['prize']), 
                                     str(challenge['memberCount']),
                                     str(round(100/challenge['memberCount'],2)),
                                     str(len(challenge['tasksOrder']['habits'])),
                                     str(len(challenge['tasksOrder']['dailys'])),
                                     str(len(challenge['tasksOrder']['todos'])),
                                     str(len(challenge['tasksOrder']['rewards'])),
str(len(challenge['tasksOrder']['habits']) +                len(challenge['tasksOrder']['dailys']) +                len(challenge['tasksOrder']['todos']) +                len(challenge['tasksOrder']['rewards'])),
challenge['name'][:25]
        )
    print(challenges_table)
