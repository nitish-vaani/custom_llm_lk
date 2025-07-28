import asyncio
import websockets
import json

async def test_ws():
    # call_id = "test-call-123"
    call_id = "abcd1234xyz"
    ws_url = f"wss://5120afcf490b.ngrok-free.app/llm-websocket/{call_id}"

    async with websockets.connect(ws_url) as ws:
        print("Connected.")

        await ws.send(json.dumps({
            "interaction_type": "response_required",
            "response_id": 1,
            "transcript": [
                {"role": "user", "content": "Hello, what can you do?"}
            ]
        }))

        while True:
            msg = await ws.recv()
            print("Received:", msg)

asyncio.run(test_ws())
