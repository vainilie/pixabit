# Architecture Overview

## Core Structure

Use a modular MVC or MVU approach:

- Model: Task, Challenge, Message, Party, UserConfig
- Views (Widgets): TaskList, TaskDetail, ChallengePanel, PartyPanel, MessagePanel
- Controller (Messages): Handle interactions, update state reactively

# UI Design (Concept)

## Main Layout (Textual Grid)

```
╔════════════════════════════════════════════════╗
║  Header (User Info, Stats, Time, Cron Status) ║
╠════════════╦══════════════════════════════════╣
║ Sidebar    ║  Main Tab Panel                  ║
║ (Menu:     ║  - Tasks                         ║
║  Tasks     ║  - Challenges                    ║
║  Party     ║  - Messages                      ║
║  Settings) ║  - Party                         ║
╠════════════╩══════════════════════════════════╣
║ Footer (Hints, Keybindings, Cron Time Left)   ║
╚════════════════════════════════════════════════╝
```

## Tabs within Panels

Tasks: Habits / Dailies / Todos / Rewards (filters)

Challenges: Joined / Created / Clone / New

Messages: Inbox / Compose

Party: Chat / Members / Cast Spells

Settings: Start custom day / Cron / Tokens / ENV
