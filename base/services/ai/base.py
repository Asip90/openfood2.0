class AIProvider:
    """Common interface for LLM providers. complete() returns the raw text
    reply from the model (expected to be a JSON string)."""

    def __init__(self, api_key, model):
        self.api_key = api_key
        self.model = model

    def complete(self, system, messages):
        raise NotImplementedError
