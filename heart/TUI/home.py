# ─── Homescreen ───────────────────────────────────────────────────────────────
"""Home screen for the Textual demo app."""
# ──────────────────────────────────────────────────────────────────────────────

from __future__ import annotations

import asyncio
from importlib.metadata import version

from heart.TUI.__stats_widget import StatsCount

try:
    import httpx

    HTTPX_AVAILABLE = True
except ImportError:
    HTTPX_AVAILABLE = False

from heart.basis.auth_keys import get_api_token, get_user_id
from heart.TUI.__backup import ButtonsApp
from heart.TUI.__sleep import SwitchApp
from heart.TUI.__tags import (SelectApp, TagManagerWidget, TagsSection,
                              TagsWidget)
from textual import work
from textual.app import ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.demo.page import PageScreen
from textual.reactive import reactive
from textual.widgets import (Collapsible, Digits, Footer, Label, Markdown,
                             TabbedContent, TabPane)

WHAT_IS_TEXTUAL_MD = """\
# Welcome to **Pixabit** !

Snappy, keyboard-centric, applications that run in the terminal and [the web](https://github.com/Textualize/textual-web).

🐍 All you need is Python!

"""


WELCOME_MD = """\
## Welcome keyboard warriors!

This is a Textual app. Here's what you need to know:

* **enter** `toggle this collapsible widget`
* **tab** `focus the next widget`
* **shift+tab** `focus the previous widget`
* **ctrl+p** `summon the command palette`


👇 Also see the footer below.

`Or… click away with the mouse (no judgement).`

"""

ABOUT_MD = """\
## Textual Interfaces
* **Challenges**: 
    - Backup Challenges
    - List Challenges
    - Broken Challenges

* **Tags**:
    - List Tags
    - Fix Tags
    - Unused Tags
    - Duplicate Tags
    - Replace
    - Add second tag
    - Challenge/Mine Tags

* **Misc**:
    - Print Stats
    - Backup Stats
    - Toggle Sleeping
    - Am I on a quest
    - Tags --> Attributes
    
* **Tasks**:
    - List Tasks
    - Sort Tasks alpha / due
    - Broken Tasks
    
* **Ideas**: 
    - Damage only me.
    - Sort by tag.
    - Autoacept quest
    - Damage.
    - Clone challenges.
    - Edit tasks. 
    - Check tasks
"""

API_MD = """\


"""

DEPLOY_MD = """\
Textual apps have extremely low system requirements, and will run on virtually any OS and hardware; locally or remotely via SSH.

There are a number of ways to deploy and share Textual apps.

## As a Python library

Textual apps may be pip installed, via tools such as `pipx` or `uvx`, and other package managers.

## As a web application

It takes two lines of code to [serve your Textual app](https://github.com/Textualize/textual-serve) as a web application.

## Managed web application

With [Textual web](https://github.com/Textualize/textual-web) you can serve multiple Textual apps on the web,
with zero configuration. Even behind a firewall.
"""


class Content(VerticalScroll, can_focus=False):
    """Non focusable vertical scroll."""


class HomeScreen(PageScreen):
    DEFAULT_CSS = """
    HomeScreen {
        
        Content {
            align-horizontal: center;
            & > * {
                max-width: 100;
            }      
            margin: 0 1;          
            overflow-y: auto;
            height: 1fr;
            scrollbar-gutter: stable;
            MarkdownFence {
                height: auto;
                max-height: initial;
            }
            Collapsible {
                padding-right: 0;               
                &.-collapsed { padding-bottom: 1; }
            }
            Markdown {
                margin-right: 1;
                padding-right: 1;
                background: transparent;
            }
        }
    }
    """

    def compose(self) -> ComposeResult:
        with TabbedContent():

            with TabPane(title="Welcome"):
                yield ButtonsApp()
                yield SwitchApp()
            with TabPane(title="Textual Interfaces"):
                yield Markdown(ABOUT_MD)
            with TabPane(title="Textual API"):
                yield Markdown(API_MD)
            with TabPane(title="Deploying Textual apps"):
                yield TagsSection()
                yield SelectApp()
                yield TagManagerWidget()
            with TabPane(title="Stats ☆"):
                yield StatsCount()
        yield Footer()
