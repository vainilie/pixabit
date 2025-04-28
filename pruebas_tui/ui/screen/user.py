from textual.app import ComposeResult
from textual.containers import Container, Horizontal, Vertical
from textual.widget import Widget
from textual.widgets import Digits, Label, ProgressBar, Static


class UserStat(Widget):
    """Widget para mostrar una estadística de usuario con nombre y valor."""

    def __init__(self, name, value, max_value=None, id=None):
        super().__init__(id=id)
        self.name = name
        self.value = value
        self.max_value = max_value

    def compose(self) -> ComposeResult:
        with Container(classes="user-stat"):
            yield Label(self.name, classes="stat-name")
            if self.max_value:
                yield Digits(f"{self.value}/{self.max_value}", classes="stat-value")
                yield ProgressBar(value=(int(self.value) / int(self.max_value)) * 100, classes="stat-progress")
            else:
                yield Digits(str(self.value), classes="stat-value")


class UserStatsWidget(Widget):
    """Widget que muestra todas las estadísticas del usuario."""

    def __init__(self, user_data):
        super().__init__()
        self.user_data = user_data

    def compose(self) -> ComposeResult:
        with Container(id="user-stats-container"):
            yield Label(f"Usuario: {self.user_data['username']}", id="username")

            with Horizontal(id="basic-stats"):
                yield UserStat("Nivel", self.user_data["level"])
                yield UserStat("Clase", self.user_data["class"])

            with Horizontal(id="health-mana"):
                yield UserStat("Salud", self.user_data["health"], self.user_data["max_health"], id="health-stat")
                yield UserStat("Maná", self.user_data["mana"], self.user_data["max_mana"], id="mana-stat")

            with Horizontal(id="exp-gold"):
                yield UserStat("Experiencia", self.user_data["exp"], self.user_data["next_level"], id="exp-stat")
                yield UserStat("Oro", self.user_data["gold"], id="gold-stat")

            yield Label("Atributos", classes="section-title")
            with Horizontal(id="attributes"):
                yield UserStat("Fuerza", self.user_data["str"])
                yield UserStat("Inteligencia", self.user_data["int"])
                yield UserStat("Constitución", self.user_data["con"])
                yield UserStat("Percepción", self.user_data["per"])

            yield Label("Equipamiento", classes="section-title")
            with Container(id="equipment"):
                for slot, item in self.user_data["equipment"].items():
                    yield Label(f"{slot}: {item}")

            yield Label("Logros y Récords", classes="section-title")
            with Container(id="achievements"):
                for achievement in self.user_data["achievements"]:
                    yield Label(f"🏆 {achievement}")

    class Meta:
        css = """
        #user-stats-container {
            height: 100%;
            overflow: auto;
            padding: 1;
        }

        #username {
            text-style: bold;
            background: $primary;
            color: $text;
            width: 100%;
            height: 3;
            content-align: center middle;
            margin-bottom: 1;
        }

        #basic-stats, #health-mana, #exp-gold, #attributes {
            height: auto;
            margin-bottom: 1;
        }

        .user-stat {
            width: 1fr;
            border: solid $accent;
            padding: 1;
            height: auto;
        }

        .stat-name {
            text-style: bold;
        }

        .stat-value {
            content-align: center middle;
            text-style: bold;
        }

        .stat-progress {
            margin-top: 1;
        }

        #health-stat .stat-progress {
            color: red;
        }

        #mana-stat .stat-progress {
            color: blue;
        }

        #exp-stat .stat-progress {
            color: green;
        }

        .section-title {
            background: $panel-lighten-1;
            text-style: bold;
            content-align: center middle;
            margin-top: 1;
            margin-bottom: 1;
        }

        #equipment, #achievements {
            margin-bottom: 1;
        }
        """


# Ejemplo de uso
dummy_user_data = {
    "username": "AventureRPG",
    "level": 42,
    "class": "Mago",
    "health": 35,
    "max_health": 50,
    "mana": 87,
    "max_mana": 100,
    "exp": 6789,
    "next_level": 8000,
    "gold": 2534,
    "str": 15,
    "int": 30,
    "con": 18,
    "per": 22,
    "equipment": {"Cabeza": "Sombrero del Archiconocimiento", "Torso": "Túnica de Concentración", "Arma": "Báculo de Poder Místico", "Escudo": "Grimorio Antiguo"},
    "achievements": ["Completaste 100 tareas", "Mantuviste un hábito por 30 días", "Completaste 5 retos", "Alcanzaste el nivel 25", "Derrotaste a 10 jefes"],
}
