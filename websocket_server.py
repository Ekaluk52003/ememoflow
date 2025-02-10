import asyncio
import websockets
import json
import redis.asyncio as redis
from django.conf import settings

# Store active connections
connections = {}

async def register(websocket, user_id):
    """Register a WebSocket connection for a user."""
    if user_id not in connections:
        connections[user_id] = set()
    connections[user_id].add(websocket)
    try:
        await websocket.wait_closed()
    finally:
        connections[user_id].remove(websocket)
        if not connections[user_id]:
            del connections[user_id]

async def redis_listener(redis_client):
    """Listen for messages from Redis and forward them to WebSocket clients."""
    pubsub = redis_client.pubsub()
    
    # Subscribe to all user channels
    pattern = "user_*"
    await pubsub.psubscribe(pattern)
    
    try:
        async for message in pubsub.listen():
            if message["type"] == "pmessage":
                # Extract user_id from channel name (e.g., "user_123" -> "123")
                channel = message["channel"].decode('utf-8')
                user_id = channel.split('_')[1]
                
                if user_id in connections:
                    notification_data = message["data"].decode('utf-8')
                    websockets_to_remove = set()
                    
                    for websocket in connections[user_id]:
                        try:
                            await websocket.send(notification_data)
                        except websockets.exceptions.ConnectionClosed:
                            websockets_to_remove.add(websocket)
                    
                    # Clean up closed connections
                    for websocket in websockets_to_remove:
                        connections[user_id].remove(websocket)
                    if not connections[user_id]:
                        del connections[user_id]
    finally:
        await pubsub.punsubscribe(pattern)
        await pubsub.close()

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
    redis_client = redis.from_url(settings.CELERY_BROKER_URL)
    
    try:
        # Start Redis listener
        redis_task = asyncio.create_task(redis_listener(redis_client))
        
        # Start WebSocket server
        async with websockets.serve(
            handler,
            "0.0.0.0",  # Listen on all available interfaces
            8001,       # Port number
            ping_interval=30,  # Send ping every 30 seconds
            ping_timeout=10    # Wait 10 seconds for pong response
        ) as server:
            print("WebSocket server started on ws://0.0.0.0:8001")
            await asyncio.Future()  # run forever
    finally:
        await redis_client.close()

if __name__ == "__main__":
    asyncio.run(main())
