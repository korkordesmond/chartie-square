from fastapi import FastAPI
from decouple import config
from openai import OpenAI
from pydantic import BaseModel

class ChatRequest(BaseModel):
    message: str


app = FastAPI()
API_KEY = config('OPENAI_API_KEY')

client = OpenAI(api_key = API_KEY)

class ChatRequest(BaseModel):
    message: str


@app.get("/")
def read_root():
    return {"Hello": "World"}



@app.post("/api/v1/chat/")
async def chat_api(request: ChatRequest):
    try:
        message = request.message
        
        response = client.chat.completions.create(
            model='gpt-4o',
            messages=[
                {"role": "system", "content": "You are a helpful assistant that provides accurate answers based on the given context."},
                {"role": "user", "content": message}
            ]
        )
        
        text_response = response.choices[0].message.content
        return {"response": text_response}
        
    except Exception as e:
        return {"error": str(e)}

