from typing import Type, Optional
from pydantic import BaseModel, Field
from langchain_core.tools import BaseTool

import requests
from bs4 import BeautifulSoup
import urllib.parse


class DuckDuckGoSearchInput(BaseModel):
    """Input schema for the DuckDuckGoSearchTool."""
    query: str = Field(description="The search query to look up on the web.")
    max_results: int = Field(default=5, description="Maximum number of search results to return.")


class DuckDuckGoSearchTool(BaseTool):
    """
    DuckDuckGo Search Tool.
    
    A completely free web search tool that uses DuckDuckGo\'s search (no API key required).
    """
    name: str = "duckduckgo_search"
    description: str = "Search the web for current information using DuckDuckGo. Free, no API key needed."
    args_schema: Type[BaseModel] = DuckDuckGoSearchInput

    model_config = {"extra": "ignore"}

    def _run(self, query: str, max_results: int = 5) -> str:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            encoded_query = urllib.parse.quote(query)
            url = f"https://html.duckduckgo.com/html/?q={encoded_query}"
            
            response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, "html.parser")
            results = []
            
            for result in soup.select(".result")[:max_results]:
                title_elem = result.select_one(".result__title a")
                snippet_elem = result.select_one(".result__snippet")
                
                if title_elem:
                    title = title_elem.get_text(strip=True)
                    link = title_elem.get("href", "")
                    if "uddg=" in link:
                        parsed = urllib.parse.urlparse(link)
                        qs = urllib.parse.parse_qs(parsed.query)
                        link = qs.get("uddg", [link])[0]
                    
                    snippet = snippet_elem.get_text(strip=True) if snippet_elem else "No description."
                    results.append(
                        f"Title: {title}\nURL: {link}\nSnippet: {snippet}"
                    )
            
            if not results:
                return f"No results found for query: \'{query}\'."
            return "\n\n".join(results)
            
        except Exception as e:
            return f"DuckDuckGo search failed: {str(e)}"
