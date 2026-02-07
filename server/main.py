import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware #even though adk api-server has allow origin option we can enable it here too
from pydantic import BaseModel
import httpx

ADK_BASE_URL = "http://127.0.0.1:8000"

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # allow all origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class QueryRequest(BaseModel):
    message: str
    # send these from your frontend to truly maintain per-user/per-chat history:
    user_id: str = "web_user"
    session_id: str = "web_session"
    reset: bool = False  # optionally start a fresh conversation


async def ensure_session(client: httpx.AsyncClient, app_name: str, user_id: str, session_id: str, reset: bool):
    # Optional reset
    if reset:
        # Delete if exists; ignore 404
        del_res = await client.delete(f"{ADK_BASE_URL}/apps/{app_name}/users/{user_id}/sessions/{session_id}")
        if del_res.status_code not in (204, 404):
            raise HTTPException(status_code=500, detail=f"Failed to delete session: {del_res.text}")
    else:
        # Avoid 409 spam by checking existence first
        get_res = await client.get(f"{ADK_BASE_URL}/apps/{app_name}/users/{user_id}/sessions/{session_id}")
        if get_res.status_code == 200:
            return
        if get_res.status_code != 404:
            raise HTTPException(status_code=500, detail=f"Failed to read session: {get_res.text}")

    # Create session (409 means it already exists → OK)
    create_res = await client.post(
        f"{ADK_BASE_URL}/apps/{app_name}/users/{user_id}/sessions/{session_id}",
        json={},  # optional initial state
    )
    if create_res.status_code not in (200, 201, 409):
        raise HTTPException(status_code=500, detail=f"Failed to create session: {create_res.text}")


@app.post("/agent/query")
async def query_agent(req: QueryRequest):
    app_name = "my_agent"

    async with httpx.AsyncClient(timeout=None) as client:
        await ensure_session(client, app_name, req.user_id, req.session_id, req.reset)

        run_res = await client.post(
            f"{ADK_BASE_URL}/run",
            json={
                "app_name": app_name,
                "user_id": req.user_id,
                "session_id": req.session_id,
                "new_message": {
                    "role": "user",
                    "parts": [{"text": req.message}],
                },
                "state_delta": {
                    "ps_session_id": req.session_id,
                    "ps_user_id": req.user_id,
                },
            },
        )

        if run_res.status_code != 200:
            raise HTTPException(status_code=run_res.status_code, detail=run_res.text)

        return run_res.json()


@app.post("/agent/stream")
async def stream_agent(req: QueryRequest):
    app_name = "my_agent"

    async def sse_generator():
        async with httpx.AsyncClient(timeout=None) as client:
            await ensure_session(client, app_name, req.user_id, req.session_id, req.reset)

            async with client.stream(
                "POST",
                f"{ADK_BASE_URL}/run_sse",
                json={
                    "app_name": app_name,
                    "user_id": req.user_id,
                    "session_id": req.session_id,
                    "new_message": {
                        "role": "user",
                        "parts": [{"text": req.message}],
                    },
                    "state_delta": {
                        "ps_session_id": req.session_id,
                        "ps_user_id": req.user_id,
                    },
                    # ADK: token-level streaming when true
                    "streaming": True,
                },
            ) as res:
                if res.status_code != 200:
                    # Return a single SSE error event
                    yield f"event: error\ndata: {res.text}\n\n"
                    return

                # ADK already emits SSE lines like: data: {...}
                async for line in res.aiter_lines():
                    if not line:
                        continue
                    # forward exactly
                    yield line + "\n"

    return StreamingResponse(sse_generator(), media_type="text/event-stream")


if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8001)
