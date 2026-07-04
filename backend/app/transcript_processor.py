from pydantic import BaseModel
from typing import Tuple, List, Literal
from pydantic_ai import Agent
from pydantic_ai.model.anthropic import AnthropicModel
from pydantic_ai.model.groq import GroqModel
from pydantic_ai.model.openai import OpenAIModel
from pydantic_ai.providers.anthropic import AnthropicProvider
from pydantic_ai.providers.groq import GroqProvider
from pydantic_ai.providers.openai import OpenAIProvider


import logging
import os
from dotenv import load_dotenv
from
