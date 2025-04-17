class UserCron:
    """Representa la información relacionada con el cron de un usuario en Habitica."""

    def __init__(self, cron_data: Dict[str, Any], preferences_data: Dict[str, Any]):
        """Inicializa un objeto UserCron.

        Args:
            cron_data: El diccionario 'cron' del objeto de usuario de la API de Habitica.
            preferences_data: El diccionario 'preferences' del objeto de usuario de la API de Habitica.
        """
        self.cron_id: Optional[str] = cron_data.get("key")  # El ID del cron
        self.updated: Optional[datetime] = (
            datetime.fromisoformat(cron_data.get("updated").replace("Z", "+00:00"))
            if cron_data.get("updated")
            else None
        )
        self.logged_in: Optional[datetime] = (
            datetime.fromisoformat(cron_data.get("loggedIn").replace("Z", "+00:00"))
            if cron_data.get("loggedIn")
            else None
        )
        self.last_cron: Optional[datetime] = (
            datetime.fromisoformat(cron_data.get("lastCron").replace("Z", "+00:00"))
            if cron_data.get("lastCron")
            else None
        )
        self.day_start: Optional[int] = preferences_data.get("dayStart")
        self.sleep_time: Optional[int] = preferences_data.get("sleep")

    def __repr__(self) -> str:
        return f"UserCron(cron_id='{self.cron_id}', last_cron={self.last_cron}, day_start={self.day_start}, sleep_time={self.sleep_time})"


class User:
    """Representa un usuario de Habitica, centrado en la información necesaria para lanzar habilidades y manejar el cron."""

    def __init__(self, user_data: Dict[str, Any], all_skills: Dict[str, Skill]):
        """Inicializa un objeto User.

        Args:
            user_data: El objeto de usuario de la API de Habitica.
            all_skills: Un diccionario de habilidades, donde las claves son las claves de las habilidades.
        """
        self.user_id: Optional[str] = user_data.get("id")
        self.username: Optional[str] = user_data.get("auth", {}).get("local", {}).get("username")
        self.klass: Optional[str] = user_data.get("stats", {}).get("class")
        self.level: Optional[int] = user_data.get("stats", {}).get("lvl")
        self.party_id: Optional[str] = user_data.get("party", {}).get("id")
        self.gold: Optional[float] = user_data.get("stats", {}).get("gp")
        self.reputation: Optional[float] = user_data.get("stats", {}).get("rep")
        self.hp: Optional[float] = user_data.get("stats", {}).get("hp")
        self.max_hp: Optional[float] = user_data.get("stats", {}).get("maxHealth")
        self.mp: Optional[float] = user_data.get("stats", {}).get("mp")
        self.max_mp: Optional[float] = user_data.get("stats", {}).get("maxMP")

        self.skills: UserSkills = UserSkills(user_data.get("stats", {}))
        # Agrega las habilidades del usuario
        for skill_key, skill_obj in all_skills.items():
            self.skills.add_skill(skill_obj)
        self.cron: UserCron = UserCron(user_data.get("cron", {}), user_data.get("preferences", {}))

    def cast_skill(self, skill_key: str, target_id: Optional[str] = None) -> None:
        """Simula el lanzamiento de una habilidad.

        Args:
            skill_key: La clave de la habilidad a lanzar.
            target_id: El ID del objetivo (opcional).
        """
        skill = self.skills.get_skill(skill_key)
        if skill:
            print(f"Lanzando habilidad {skill.name} ({skill.key})")
            if target_id:
                print(f"  contra el objetivo con ID: {target_id}")
            # Aquí iría la lógica para interactuar con la API de Habitica
            # para lanzar la habilidad (usando self.api_client).
            print(f"  Mana Coste: {skill.mana}")
            if self.mp >= skill.mana:
                print("  Mana suficiente")
            else:
                print("  Mana insuficiente")

        else:
            print(f"Habilidad no encontrada: {skill_key}")

    def __repr__(self) -> str:
        return f"User(username='{self.username}', class='{self.klass}', level={self.level})"


def fetch_skills_and_users(api_client: HabiticaAPI) -> Dict[str, User]:
    """Obtiene las habilidades del juego y los datos de los usuarios de la API de Habitica.

    Args:
        api_client: Una instancia de la clase HabiticaAPI.

    Returns:
        Un diccionario donde las claves son los IDs de los usuarios y los valores son objetos User.
    """
    # 1. Obtener habilidades
    skills_data = api_client.get_skills()
    all_skills: Dict[str, Skill] = {}
    for skill_data in skills_data:
        skill = Skill(skill_data)
        all_skills[skill.key] = skill

    # 2. Obtener datos del usuario (esto es un ejemplo, podrías obtener varios usuarios)
    users_data = (
        api_client.get_user_data()
    )  # Esto debería devolver un diccionario o una lista de usuarios

    # 3. Procesar los datos del usuario y crear objetos User
    users: Dict[str, User] = {}
    if isinstance(users_data, dict):
        user_id = users_data.get("id")
        if user_id:
            users[user_id] = User(users_data, all_skills)
    elif isinstance(users_data, list):
        for user_data in users_data:
            user_id = user_data.get("id")
            if user_id:
                users[user_id] = User(user_data, all_skills)

    return users


if __name__ == "__main__":
    # Ejemplo de uso
    api_client = HabiticaAPI()  # Instancia de tu cliente de la API
    users = fetch_skills_and_users(api_client)

    # Ejemplo de uso de los datos
    for user_id, user in users.items():
        print(f"Usuario: {user}")
        print(f"  Clase: {user.klass}")
        print(f"  Nivel: {user.level}")
        print(f"  Cron: {user.cron}")

        # Ejemplo de lanzamiento de habilidad
        user.cast_skill("wizard-attack-fire", "algún_id_de_objetivo")
        user.cast_skill("habilidad_inexistente")
