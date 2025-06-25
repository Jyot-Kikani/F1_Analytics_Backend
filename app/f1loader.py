import fastf1

def load_session(year: int, gp: str, session_name: str):
    """
    Load a FastF1 session object with lap data.
    """
    session = fastf1.get_session(year, gp, session_name)
    session.load()  # Loads laps, telemetry, weather, etc.
    return session