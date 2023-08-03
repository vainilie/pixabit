from rich.table import Table
from rich.console import Console
from rich.panel import Panel
from rich import box
from art import text2art
import datetime
import timeago
from rich.theme import Theme

# Read the theme from "styles" file and initialize the console with the theme
theme = Theme.read("styles")
console = Console(theme=theme)


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
        "[habitica][b]",
        f"[habitica]Hello, [b i]{input_stats.get('username')}",
    )
    user_stats.add_row(
        "[neo][b]󰔚",
        f"You last logged-in [b i]{timeago.format(LastLogin, now)}",
    )
    user_stats.add_row(
        "[b #2995CD]⧗",
        f"Your day starts at {input_stats.get('start')} am",
    )

    # Add the 'resting in the Inn' status if user is sle    eping
    if input_stats.get("sleeping") is True:
        user_stats.add_row("[gold][b]󰒲", "You are [gold][i b]resting[/] in the Inn")
    if input_stats.get("broken") > 0:
        user_stats.add_row(
            "[health][b]💔",
            f"You have {input_stats.get('broken')} broken challenge tasks",
        )

    # Add the 'in a quest' information if user is in a quest
    if bool(input_stats.get("quest")) is True:
        quest = Table.grid(expand=False)
        quest.add_column()
        quest.add_column()
        quest.add_column()
        quest.add_row(
            "[pink]You're [i]in a quest",
            "",
            f"[up][b] 󰶣 {int(input_stats.get('quest').get('progress').get('up'))}",
            f"[down][b] 󰶡 {int(input_stats.get('quest').get('progress').get('down'))}",
        )
        user_stats.add_row("[b][pink]󰞇", quest)

    # Create a table to show user stats
    stats = Table.grid(padding=(0, 2), expand=True)

    # Add rows for each stat
    stats.add_row("[b #FFA624]󱉏", f"{int(input_stats.get('stats').get('gp'))}")
    stats.add_row("[b #F74E52]", f"{int(input_stats.get('stats').get('hp'))}")
    stats.add_row("[b #FFBE5D]󰫢", f"{int(input_stats.get('stats').get('exp'))}")
    stats.add_row("[b #50B5E9]", f"{int(input_stats.get('stats').get('mp'))}")

    # Create a table to show task counts
    counts = Table.grid(padding=(0, 2), expand=True)

    # Add rows for each stat
    counts.add_row(
        "[b #FFA624]Dailys:", f"{sum(input_stats['numbers']['dailys'].values())}"
    )
    counts.add_row("[b #FFA624]Habits:", f"{input_stats['numbers']['habits']}")
    counts.add_row(
        "[b #FFA624]Todos:", f"{sum(input_stats['numbers']['todos'].values())}"
    )
    counts.add_row("[b #FFA624]Rewards:", f"{input_stats['numbers']['rewards']}")
    counts.add_row()

    counts.add_row("[b #FFA624]❑ dailys:", f"{input_stats['numbers']['dailys']['due']}")
    counts.add_row(
        "[b #FFA624]◯ dailys:", f"{input_stats['numbers']['dailys']['grey']}"
    )
    counts.add_row(
        "[b #FFA624]:heavy_check_mark: dailys:",
        f"{input_stats['numbers']['dailys']['done']}",
    )
    counts.add_row()

    counts.add_row("[b #FFA624]❑ todos:", f"{input_stats['numbers']['todos']['due']}")
    counts.add_row("[b #FFA624]☒ todos:", f"{input_stats['numbers']['todos']['red']}")
    counts.add_row("[b #FFA624]◯ todos:", f"{input_stats['numbers']['todos']['grey']}")

    # Create a table for the "About" section
    about = Table.grid(padding=0, expand=True)
    about.add_column(no_wrap=True)
    about.add_row("[b #6133b4]" + text2art("HABITICA", font="eftifont"))
    about.add_row(user_stats)

    # Create a panel to display user stats and info
    display_stats = Panel(
        stats,
        box=box.ROUNDED,
        title=f"[b][i]level {input_stats.get('level')}:sparkles:",
        border_style="pink",
        subtitle=f"{input_stats.get('class')}",
        expand=True,
    )

    # Create a panel to display user stats and info
    display_numbers = Panel(
        counts,
        box=box.ROUNDED,
        title=f"[b][i]total tasks: {input_stats['numbers']['total']} :sparkles:",
        border_style="pink",
        subtitle=f"{input_stats.get('class')}",
        expand=True,
    )
    # Create a table for the final display
    about_panel = Table.grid(padding=2, expand=False)
    about_panel.add_column(no_wrap=False)
    about_panel.add_column(no_wrap=False)
    about_panel.add_column(no_wrap=False)

    about_panel.add_row(about, display_stats, display_numbers)

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
