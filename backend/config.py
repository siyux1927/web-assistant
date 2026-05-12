import os
from functools import lru_cache
from browser_use.llm.anthropic.chat import ChatAnthropic as BrowserUseAnthropic
from dotenv import load_dotenv

load_dotenv()


@lru_cache(maxsize=1)
def get_llm() -> BrowserUseAnthropic:
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        raise RuntimeError("ANTHROPIC_API_KEY environment variable is not set")
    return BrowserUseAnthropic(
        model="claude-sonnet-4-5-20250929",
        api_key=api_key,
    )


def is_headless() -> bool:
    return os.environ.get("BROWSER_HEADLESS", "true").lower() == "true"
