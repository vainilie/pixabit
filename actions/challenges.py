from core.auth_file import get_key_from_config
from core.habitica_api import post, delete
from utils.rich_utils import Confirm, print
from get import get_challenges
from utils.rich_utils import Table, Console, Panel, box, console, Columns


### api get challenges member YES not working

def list_challenges(challengue):
    all_challenges = get_challenges.get_my_challenges()
    
    challenges_table=  Table.grid()
    challenges_table.add_column()
    for idx, challenge in enumerate(all_challenges):
        if challenge["id"] in challengue["cats"]["challenge"]:
            challenges_table.add_row(
            str(idx),
            f"| {challenge['prize']} | {challenge['memberCount']} | {challenge['name']}| "
        )
    print(challenges_table)
