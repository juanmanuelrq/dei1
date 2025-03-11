from fastapi import FastAPI, Form, Request, status
from fastapi.responses import HTMLResponse, FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
from fastapi.security import HTTPBasic,HTTPBasicCredentials
from fastapi import UploadFile, File,Depends,HTTPException, Response

seguridad = HTTPBasic()
#https://sisifo-email-tv.azurewebsites.net/CalcularTv
#https://sisifo-email-tv.scm.azurewebsites.net/api/logstream
 

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
async def root():
    return {"message": "Hello World"}


if __name__ == '__main__':
    uvicorn.run('main:app', host='0.0.0.0', port=8000)

