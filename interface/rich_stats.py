from utils.rich_utils import Table, Panel, box, console
from art import text2art
import datetime
import timeago


def get_total(numbers):
    """
    Calculate the total sum of all numbers in the nested dictionary.

    Args:
        numbers (dict): The nested dictionary containing numbers to sum.

    Returns:
        int: The total sum of all numbers.
    """
    total = 0

    for category, category_data in numbers.items():
        if isinstance(category_data, dict):
            for status, value in category_data.items():
                total += value
        else:
            total += category_data

    return total


def print_stats(input_stats):
    """Display user stats in a rich panel."""

    now = datetime.datetime.now(datetime.timezone.utc)
    LastLogin = input_stats.get("time")
    LastLogin = datetime.datetime.fromisoformat(LastLogin)

    # Create a table to show user information
    user_stats = Table.grid(padding=(0, 2), expand=True)
    user_stats.add_column(no_wrap=False, justify="right")
    user_stats.add_column(no_wrap=False, justify="left")

    user_stats.add_row(
        "[habitica][b]:mage:",
        f"[habitica]Hello, [b i]{input_stats.get('username')}",
    )
    user_stats.add_row(
        "[neo][b]:hourglass:",
        f"You last logged-in [b i]{timeago.format(LastLogin, now)}",
    )
    user_stats.add_row(
        "[b #2995CD]:alarm_clock:",
        f"Your day starts at {input_stats.get('start')} am",
    )

    # Add the 'resting in the Inn' status if user is sle    eping
    if input_stats.get("sleeping") is True:
        user_stats.add_row("[b][pink]:zzz:", "You are [gold][i b]resting[/] in the Inn")
    if input_stats.get("broken") > 0:
        user_stats.add_row(
            "[health][b]:wilted_flower:",
            f"You have {input_stats.get('broken')} broken challenge tasks",
        )

    # Add the 'in a quest' information if user is in a quest
    if bool(input_stats.get("quest")) is True:
        to_do = int(input_stats.get('quest').get('progress').get('up'))
        down = int(input_stats.get('quest').get('progress').get('down'))
        user_stats.add_row(
            "[pink][b]:dragon:",
            f"[pink]You're [i]in a quest.[/pink] Damage:[/] [up][b] 󰶣{to_do} [/][down][b] 󰶡{down}",
        )

    # Create a table to show user stats
    stats = Table.grid(padding=(0, 1), expand=True)

    # Add rows for each stat
    stats.add_row("[b #FFA624]:moneybag:", f"{int(input_stats.get('stats').get('gp'))}")
    stats.add_row(
        "[b #F74E52]:heartpulse:", f"{int(input_stats.get('stats').get('hp'))}"
    )
    stats.add_row("[b #FFBE5D]:dizzy:", f"{int(input_stats.get('stats').get('exp'))}")
    stats.add_row("[b #50B5E9]:gem:", f"{int(input_stats.get('stats').get('mp'))}")

    # Create a table to show task counts
    counts = Table.grid(padding=(0, 2), expand=True, )

    # Add rows for each stat

    counts.add_row(
        Panel(f"{input_stats['numbers']['habits']}", title="Habits"),
        Panel(f"{input_stats['numbers']['rewards']}", title="Rewards"),
    )

    todos = Table.grid(padding=(0, 1), expand=True)
    todos.add_column()
    todos.add_column(justify="right")
    todos.add_row("[b]Total", f"{sum(input_stats['numbers']['todos'].values())}")
    todos.add_row("[b]Due", f"{input_stats['numbers']['todos']['due']}")
    todos.add_row("[b]Expired", f"{input_stats['numbers']['todos']['red']}")
    todos.add_row("[b]Grey", f"{input_stats['numbers']['todos']['grey']}")

    dailys = Table.grid(padding=(0, 1), expand=True)
    dailys.add_column()
    dailys.add_column(justify="right")
    dailys.add_row("[b]Total", f"{sum(input_stats['numbers']['dailys'].values())}")
    dailys.add_row("[b]Due", f"{input_stats['numbers']['dailys']['due']}")
    dailys.add_row("[b]Done", f"{input_stats['numbers']['dailys']['done']}")
    dailys.add_row("[b]Grey", f"{input_stats['numbers']['dailys']['grey']}")

    counts.add_row(
        Panel(
            dailys,
            title="Dailies",
        ),
        Panel(
            todos,
            title="Todos",
        ),
    )


    # Create a panel to display user stats and info
    display_stats = Panel(
        stats,
        
        box=box.ROUNDED,
        title=f"[b][i]level[/i] {input_stats.get('level')}",
        border_style="pink",
        subtitle=f"[i]{input_stats.get('class')}",
        expand=True,
    )

    # Create a table for the "About" section
    about = Table.grid(padding=1, expand=True)
    about.add_column(no_wrap=True)
    about.add_column(no_wrap=True)

    about.add_row(user_stats, display_stats)
    
    # Create a panel to display user stats and info
    display_numbers = Panel(
        counts,
        box=box.ROUNDED,
        title=f"[b][i]Total tasks {get_total(input_stats['numbers'])}",
        border_style="pink",
        expand=True,
    )
    # Create a table for the final display
    about_panel = Table.grid(padding=0, expand=False)
    about_panel.add_column(no_wrap=False)

    about_panel.add_row(about)
    about_panel.add_row(display_numbers)

    # Print the final panel with the user stats
    console.print(
        Panel(
            about_panel,
            box=box.ROUNDED,
            title=":space_invader: [b i]Stats :space_invader:",
            border_style="#BDA8FF",
            expand=False,
        ),
    )

    return input_stats
