from fastapi import FastAPI, Form, Request, status
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
from fastapi.security import HTTPBasic,HTTPBasicCredentials
from fastapi import UploadFile, File,Depends,HTTPException, Response
import asyncio
from json2html import *
from autogen_agentchat.agents import AssistantAgent
from autogen_agentchat.conditions import TextMentionTermination
from autogen_agentchat.teams import RoundRobinGroupChat
from autogen_agentchat.ui import Console
from autogen_core.tools import FunctionTool
from autogen_ext.models.openai import OpenAIChatCompletionClient
import asyncio
from bs4 import BeautifulSoup
from dotenv import load_dotenv
import os
import time
import requests
import arxiv
import json
import pymongo

load_dotenv()

COSMOS_CONNECTION_STRING = os.getenv("COSMOS_CONNECTION_STRING")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

client = pymongo.MongoClient(COSMOS_CONNECTION_STRING)
db = client["dei-inteia"]
collection_agente = db["agente"]
seguridad = HTTPBasic()


def google_search(query: str, num_results: int = 2, max_chars: int = 500) -> list:  # type: ignore[type-arg]

    

    api_key = os.getenv("GOOGLE_API_KEY")
    search_engine_id = os.getenv("GOOGLE_SEARCH_ENGINE_ID")

    if not api_key or not search_engine_id:
        raise ValueError("API key or Search Engine ID not found in environment variables")

    url = "https://www.googleapis.com/customsearch/v1"
    params = {"key": api_key, "cx": search_engine_id, "q": query, "num": num_results}

    response = requests.get(url, params=params)  # type: ignore[arg-type]

    if response.status_code != 200:
        print(response.json())
        raise Exception(f"Error in API request: {response.status_code}")

    results = response.json().get("items", [])

    def get_page_content(url: str) -> str:
        try:
            response = requests.get(url, timeout=10)
            soup = BeautifulSoup(response.content, "html.parser")
            text = soup.get_text(separator=" ", strip=True)
            words = text.split()
            content = ""
            for word in words:
                if len(content) + len(word) + 1 > max_chars:
                    break
                content += " " + word
            return content.strip()
        except Exception as e:
            print(f"Error fetching {url}: {str(e)}")
            return ""

    enriched_results = []
    for item in results:
        body = get_page_content(item["link"])
        enriched_results.append(
            {"title": item["title"], "link": item["link"], "snippet": item["snippet"], "body": body}
        )
        time.sleep(1)  # Be respectful to the servers

    return enriched_results


def arxiv_search(query: str, max_results: int = 2) -> list:  # type: ignore[type-arg]
    """
    Search Arxiv for papers and return the results including abstracts.
    """

    client = arxiv.Client()
    search = arxiv.Search(query=query, max_results=max_results, sort_by=arxiv.SortCriterion.Relevance)

    results = []
    for paper in client.results(search):
        results.append(
            {
                "title": paper.title,
                "authors": [author.name for author in paper.authors],
                "published": paper.published.strftime("%Y-%m-%d"),
                "abstract": paper.summary,
                "pdf_url": paper.pdf_url,
            }
        )

    # # Write results to a file
    # with open('arxiv_search_results.json', 'w') as f:
    #     json.dump(results, f, indent=2)

    return results


google_search_tool = FunctionTool(
    google_search, description="Search Google for information, returns results with a snippet and body content"
)
arxiv_search_tool = FunctionTool(
    arxiv_search, description="Search Arxiv for papers related to a given topic, including abstracts"
)

google_search_agent = AssistantAgent(
    name="Google_Search_Agent",
    tools=[google_search_tool],
    model_client=OpenAIChatCompletionClient(model="gpt-4o-mini",api_key=OPENAI_API_KEY),
    description="An agent that can search Google for information, returns results with a snippet and body content",
    system_message="You are a helpful AI assistant. Solve tasks using your tools.",
)

arxiv_search_agent = AssistantAgent(
    name="Arxiv_Search_Agent",
    tools=[arxiv_search_tool],
    model_client=OpenAIChatCompletionClient(model="gpt-4o-mini",api_key=OPENAI_API_KEY),
    description="An agent that can search Arxiv for papers related to a given topic, including abstracts",
    system_message="You are a helpful AI assistant. Solve tasks using your tools. Specifically, you can take into consideration the user's request and craft a search query that is most likely to return relevant academi papers.",
)


report_agent = AssistantAgent(
    name="Report_Agent",
    model_client=OpenAIChatCompletionClient(model="gpt-4o-mini",api_key=OPENAI_API_KEY),
    description="Genear un reporte basado en un tema dado",
    system_message="Eres un asistente útil. Tu tarea es sintetizar los datos extraídos en una revisión bibliográfica de alta calidad que incluya las referencias correctas. DEBES redactar un informe final con el formato de una revisión bibliográfica y las referencias correctas. Tu respuesta debe terminar con la palabra 'TERMINAR'",
)

termination = TextMentionTermination("TERMINAR")
team = RoundRobinGroupChat(
    participants=[google_search_agent, arxiv_search_agent, report_agent], termination_condition=termination
)


def verify_credentials(credentials: HTTPBasicCredentials):
    username = 'inteiatvcct'#os.getenv("user")
    password = 'in7314tvcc720*'#os.getenv("pws")
    if not (credentials.username == username and credentials.password == password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Autenticación fallida",
            headers={"WWW-Authenticate": "Basic"},
        )


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")



@app.get("/")
async def root(credentials:HTTPBasicCredentials=Depends(seguridad),response_class=HTMLResponse,prompt: str = "Escribe una revisión de literatura sobre tecnologías emergentes en energía"):

    verify_credentials(credentials)

    print("prompt",prompt)

    #result = await team.run(task="Escribe una revisión de literatura sobre tecnologías emergentes en energía")

    json_data = await team.run(task=prompt)
    print("type(json_data)",type(json_data))
    print("json_data",json_data)

    results = {
        'prompt': json_data.messages[0].content,
        'content': json_data.messages[-1].content      
            }
  
    collection_agente.insert_one(results)

    try:
        return HTMLResponse(content= str(results), status_code=200)
    except Exception as e:
        return Response(content=json.dumps({"error": str(e)}), status_code=500)

if __name__ == '__main__':
    uvicorn.run('main:app', host='0.0.0.0', port=8000)