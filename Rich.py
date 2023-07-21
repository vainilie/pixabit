from rich.table import Table
import timeago
from rich.console import Console, ConsoleOptions, Group, RenderableType, RenderResult
from rich.panel import Panel
from rich.prompt import Confirm, Prompt, IntPrompt
from art import text2art
from datetime import datetime, timezone
from rich.theme import Theme

from rich import box
theme = Theme.read("styles")

console = Console(theme=theme)
nowUTC = datetime.now(timezone.utc)
nowLOC = nowUTC.astimezone()


#
# ─── % DISPLAY STATS ────────────────────────────────────────────────────────────
#


def display(Stats):
    """display"""
    print(nowUTC)
    print(nowLOC    )
    userStats = Table.grid(padding=(0,1), expand=True)
    userStats.add_column(no_wrap=True, justify="right")
    userStats.add_column(no_wrap=True, justify="left")

    userStats.add_row(
        "[i #BDA8FF i]Username",
        f"{Stats.get('username')}",
    )
    userStats.add_row(
        "[i #BDA8FF i]Level",
        f"{Stats.get('level')}",
    )
    userStats.add_row("[i #2995CD i]Class", f"{Stats.get('class')}")
    userStats.add_row("[i #BDA8FF i]Are you sleeping?", f"{Stats.get('sleeping')}")

    userStats.add_row(
        "[i #BDA8FF i]Last time logged in",
        f"{Stats.get('time')}",
    )

    userStats.add_row(
        "[i #BDA8FF i]Am I in a quest?", 
        f"{bool(Stats.get('quest'))}",
    )

    userStats.add_row(
        "[i #BDA8FF i]Damage :up:",
        f"{int(Stats.get('quest').get('progress').get('up'))}",
    )
    userStats.add_row(
        "[i #BDA8FF i]Damage :down:",
        f"{Stats.get('quest').get('progress').get('down')}",
    )
    # userStats.add_row(
    #     "[i #2995CD i]start time down",
    #     f"{Stats.get('start')} am",
    # )
    # for x in all_["rewards"]:
    #     userStats.add_row(
    #         "[i #2995CD i]start time down",
    #         f"{x.get('value')} am",
    #     )

    stats = Table.grid(padding=(0,2), expand=True)

    stats.add_row("[i #FFA624 i]gold", f"{int(Stats.get('stats').get('gp'))}")

    stats.add_row("[i #F74E52 i]health", f"{int(Stats.get('stats').get('hp'))}")

    stats.add_row("[i #FFBE5D i]experience", f"{int(Stats.get('stats').get('exp'))}")

    stats.add_row("[i #50B5E9 i]mana", f"{int(Stats.get('stats').get('mp'))}")
    about = Table.grid(padding=0, expand=True)
    about.add_column(no_wrap=True)
    about.add_row(text2art("eelianen", font="ghoulish"))
    about.add_row(userStats)
    aboute = Table.grid(padding=0, expand=True)
    aboute.add_column(no_wrap=True)
    aboute.add_column(no_wrap=True)
    aboute.add_row(about, stats)

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

