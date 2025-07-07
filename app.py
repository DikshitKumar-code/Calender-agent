from fastapi import FastAPI
from pydantic import BaseModel
from typing import List,TypedDict,Annotated

# Import your graph and related components
from src.graph import graph  # Adjust import path as needed

app = FastAPI()



class UserInput(BaseModel):
    user_input: str

@app.post("/invoke")
async def invoke_graph(data: UserInput):
    try:
        # Wrap the user input as a single "user" message
        messages = [{"role": "user", "content": data.user_input}]
        result = graph.invoke({"messages": messages})
        return {"status": "success", "result": result}
    except Exception as e:
        return {"status": "error", "message": str(e)}

@app.get("/health")
async def health_check():
    return {"status": "API is running"}
