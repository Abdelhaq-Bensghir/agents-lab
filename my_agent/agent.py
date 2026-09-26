# la définition de ton agent (modèle, instructions, outils)
from google.adk.agents.llm_agent import Agent


def get_current_time(city: str) -> dict:
    """Returns the current time in a specified city."""
    return {"status": "success", "city": city, "time": "10:30 AM"}


root_agent = Agent(
    model='gemini-3.5-flash-lite',
    # identifiant de l'agent dans les logs et dans l'interface web
    name='root_agent',
    # ne sert pas à l'agent lui-même, mais aux autres agents et à Gemini Entreprise
    description="Tells the current time in a specified city.",
    # le « prompt système », les consignes que le modèle suit à chaque message.
    instruction="You are a helpful assistant that tells the current time in cities. "
                "Use the 'get_current_time' tool for this purpose.",
    # donne au modèle le droit d'appeler cette fonction
    tools=[get_current_time],
)
