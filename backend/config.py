import os
from functools import lru_cache
from langchain_anthropic import ChatAnthropic
from dotenv import load_dotenv

load_dotenv()


@lru_cache(maxsize=1)
def get_llm() -> ChatAnthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set")
    return ChatAnthropic(
        model="claude-sonnet-4-6",
        api_key=api_key,
    )


def is_headless() -> bool:
    return os.environ.get("BROWSER_HEADLESS", "true").lower() == "true"
