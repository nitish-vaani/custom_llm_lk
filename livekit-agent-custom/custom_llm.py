import os
from dotenv import load_dotenv
from livekit.plugins import openai

load_dotenv()

class CustomLLM:
    def __init__(self, model="gpt-4o", temperature=0.7, max_tokens=1000):
        """
        Initialize OpenAI LLM with custom parameters
        
        Args:
            model (str): OpenAI model to use
            temperature (float): Sampling temperature
            max_tokens (int): Maximum tokens to generate
        """
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        
        # Verify API key is set
        if not os.getenv("OPENAI_API_KEY"):
            raise ValueError("OPENAI_API_KEY environment variable is required")
    
    def get_llm(self):
        """
        Returns configured OpenAI LLM instance
        """
        return openai.LLM(
            model=self.model,
            temperature=self.temperature,
            max_tokens=self.max_tokens
        )
    
    def update_config(self, **kwargs):
        """
        Update LLM configuration parameters
        """
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        return self.get_llm()