# from rich.table import Table
# import timeago
# from rich.console import Console, ConsoleOptions, Group, RenderableType, RenderResult
# from rich.panel import Panel
# from rich.prompt import Confirm, Prompt, IntPrompt
# from art import text2art
# from datetime import datetime, timezone
# from rich.theme import Theme
# import timeago, datetime

# from rich import box

# theme = Theme.read("styles")

# console = Console(theme=theme)
# # nowUTC = datetime.now(timezone.utc)
# # nowLOC = nowUTC.astimezone()

# #
# # ─── % DISPLAY STATS ────────────────────────────────────────────────────────────
# #


# def display(Stats):
#     """display"""

#     now = datetime.datetime.now(datetime.timezone.utc)
#     LastLogin = Stats.get("time")
#     LastLogin = datetime.datetime.fromisoformat(LastLogin)

#     userStats = Table.grid(padding=(0, 2), expand=True)
#     userStats.add_column(no_wrap=True, justify="right")
#     userStats.add_column(no_wrap=True, justify="left")

#     userStats.add_row(
#         "[habitica][b]",
#         f"[habitica]Hello, [b i]{Stats.get('username')}",
#     )
#     userStats.add_row(
#         "[neo][b]󰔚",
#         f"You last logged-in [b i]{timeago.format(LastLogin, now)}",
#     )
#     userStats.add_row(
#         "[b #2995CD]start time down",
#         f"{Stats.get('start')} am",
#     )
#     if Stats.get("sleeping") is True:
#         userStats.add_row("[gold][b]󰒲", "You are [gold][i b]resting[/] in the Inn")

#     if bool(Stats.get("quest")) is True:
#         quest = Table.grid(
#             expand=False,
#         )
#         quest.add_column()
#         quest.add_column()
#         quest.add_column()
#         quest.add_row(
#             "[pink]You're [i]in a quest",
#             "",
#             f"[up][b] 󰶣 {int(Stats.get('quest').get('progress').get('up'))}",
#             f"[down][b] 󰶡 {int(Stats.get('quest').get('progress').get('down'))}",
#         )
#         userStats.add_row("[b][pink]󰞇", quest)

#     stats = Table.grid(padding=(0, 2), expand=True)

#     stats.add_row("[b #FFA624]󱉏", f"{int(Stats.get('stats').get('gp'))}")

#     stats.add_row("[b #F74E52]", f"{int(Stats.get('stats').get('hp'))}")

#     stats.add_row("[b #FFBE5D]󰫢", f"{int(Stats.get('stats').get('exp'))}")

#     stats.add_row("[b #50B5E9]", f"{int(Stats.get('stats').get('mp'))}")
#     about = Table.grid(padding=0, expand=True)
#     about.add_column(no_wrap=True)
#     about.add_row("[b #6133b4]" + text2art("HABITICA", font="eftifont"))
#     about.add_row(userStats)
#     aboute = Table.grid(padding=2, expand=True)
#     aboute.add_column(no_wrap=True)
#     aboute.add_column(no_wrap=True)
#     statss = Panel(
#         stats,
#         box=box.ROUNDED,
#         title=f"[b][i]level {Stats.get('level')}:sparkles:",
#         border_style="pink",
#         subtitle=f"{Stats.get('class')}",
#         expand=False,
#     )

#     aboute.add_row(about, statss)

#     console.print(
#         Panel(
#             aboute,
#             box=box.ROUNDED,
#             title=f":space_invader: [b]{text2art('Habitica Stats', font='fancy135')} :space_invader:",
#             border_style="#BDA8FF",
#             expand=False,
#         ),
#     )
#     return Stats

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


def display(Stats):
    """Display user stats in a rich panel."""

    now = datetime.datetime.now(datetime.timezone.utc)
    LastLogin = Stats.get("time")
    LastLogin = datetime.datetime.fromisoformat(LastLogin)

    # Create a table to show user information
    userStats = Table.grid(padding=(0, 2), expand=True)
    userStats.add_column(no_wrap=True, justify="right")
    userStats.add_column(no_wrap=True, justify="left")

    userStats.add_row(
        "[habitica][b]",
        f"[habitica]Hello, [b i]{Stats.get('username')}",
    )
    userStats.add_row(
        "[neo][b]󰔚",
        f"You last logged-in [b i]{timeago.format(LastLogin, now)}",
    )
    userStats.add_row(
        "[b #2995CD]🕧",
        f"Your day starts at {Stats.get('start')} am",
    )

    # Add the 'resting in the Inn' status if user is sleeping
    if Stats.get("sleeping") is True:
        userStats.add_row("[gold][b]󰒲", "You are [gold][i b]resting[/] in the Inn")

    # Add the 'in a quest' information if user is in a quest
    if bool(Stats.get("quest")) is True:
        quest = Table.grid(expand=False)
        quest.add_column()
        quest.add_column()
        quest.add_column()
        quest.add_row(
            "[pink]You're [i]in a quest",
            "",
            f"[up][b] 󰶣 {int(Stats.get('quest').get('progress').get('up'))}",
            f"[down][b] 󰶡 {int(Stats.get('quest').get('progress').get('down'))}",
        )
        userStats.add_row("[b][pink]󰞇", quest)

    # Create a table to show user stats
    stats = Table.grid(padding=(0, 2), expand=True)

    # Add rows for each stat
    stats.add_row("[b #FFA624]󱉏", f"{int(Stats.get('stats').get('gp'))}")
    stats.add_row("[b #F74E52]", f"{int(Stats.get('stats').get('hp'))}")
    stats.add_row("[b #FFBE5D]󰫢", f"{int(Stats.get('stats').get('exp'))}")
    stats.add_row("[b #50B5E9]", f"{int(Stats.get('stats').get('mp'))}")

    # Create a table for the "About" section
    about = Table.grid(padding=0, expand=True)
    about.add_column(no_wrap=True)
    about.add_row("[b #6133b4]" + text2art("HABITICA", font="eftifont"))
    about.add_row(userStats)

    # Create a panel to display user stats and info
    statss = Panel(
        stats,
        box=box.ROUNDED,
        title=f"[b][i]level {Stats.get('level')}:sparkles:",
        border_style="pink",
        subtitle=f"{Stats.get('class')}",
        expand=False,
    )

    # Create a table for the final display
    aboute = Table.grid(padding=2, expand=True)
    aboute.add_column(no_wrap=True)
    aboute.add_column(no_wrap=True)
    aboute.add_row(about, statss)

    # Print the final panel with the user stats
    console.print(
        Panel(
            aboute,
            box=box.ROUNDED,
            title=f":space_invader: [b]{text2art('Habitica Stats', font='fancy135')} :space_invader:",
            border_style="#BDA8FF",
            expand=False,
        ),
    )

    return Stats
