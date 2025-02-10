import asyncio
import websockets
import json
from collections import defaultdict

# Store active connections
connections = defaultdict(set)

async def register(websocket, user_id):
    """Register a WebSocket connection for a user."""
    connections[user_id].add(websocket)
    try:
        await websocket.wait_closed()
    finally:
        connections[user_id].remove(websocket)
        if not connections[user_id]:
            del connections[user_id]

async def notify_user(user_id, message):
    """Send a notification to all connections of a specific user."""
    if user_id in connections:
        websockets_to_remove = set()
        for websocket in connections[user_id]:
            try:
                await websocket.send(json.dumps(message))
            except websockets.exceptions.ConnectionClosed:
                websockets_to_remove.add(websocket)
        
        # Clean up closed connections
        for websocket in websockets_to_remove:
            connections[user_id].remove(websocket)
        if not connections[user_id]:
            del connections[user_id]

async def handler(websocket, path):
    """Handle incoming WebSocket connections."""
    try:
        # Extract user_id from path (e.g., /ws/123)
        user_id = path.split('/')[-1]
        if not user_id:
            return
        
        await register(websocket, user_id)
        
    except Exception as e:
        print(f"Error in handler: {e}")

async def main():
    """Start the WebSocket server."""
    server = await websockets.serve(
        handler,
        "0.0.0.0",  # Listen on all available interfaces
        8001,       # Port number
        ping_interval=30,  # Send ping every 30 seconds
        ping_timeout=10    # Wait 10 seconds for pong response
    )
    print("WebSocket server started on ws://0.0.0.0:8001")
    await server.wait_closed()

if __name__ == "__main__":
    asyncio.run(main())
