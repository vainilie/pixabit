#!/usr/bin/env python3

from utils.rich_utils import Confirm, IntPrompt, Panel, Columns, console
from core.auth_file import check_auth_file
from get import bkup_challenges, get_tags, get_tasks, get_stats, get_userdata
from interface import rich_stats, rich_tags, mainmenu
from actions import unused_tags, filter_task, sleeping, category_tags, challenges, sort

def main():
    while True:
#        sort.sort_alpha()
        selected_action = mainmenu.display_main_menu()
        mainmenu.select_option(selected_action)

if __name__ == "__main__":
    main()
