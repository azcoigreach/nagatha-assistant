import abc


class Agent(abc.ABC):
    """
    Base Agent class for Nagatha Assistant.
    """

    @abc.abstractmethod
    async def run(self, *args, **kwargs):
        """
        Run the agent's main logic.
        """
        pass