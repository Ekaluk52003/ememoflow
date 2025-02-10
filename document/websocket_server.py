# websocket_server.py
import os
import sys
import asyncio
import websockets
import json
import redis.asyncio as redis
from django.core.asgi import get_asgi_application
from django.conf import settings

# Initialize Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'django_project.settings')
get_asgi_application()  # This initializes Django

class NotificationServer:
    def __init__(self):
        self.clients = {}  # Store active connections
        self.redis = None

    async def connect_redis(self):
        if not self.redis:
            self.redis = await redis.from_url(settings.CELERY_BROKER_URL)
        return self.redis

    async def handle_client(self, websocket, path):
        try:
            # Extract user ID from path
            user_id = path.split('/')[-1]
            
            # Store the connection
            self.clients[user_id] = websocket
            
            # Connect to Redis
            redis_client = await self.connect_redis()
            pubsub = redis_client.pubsub()
            
            # Subscribe to user's channel
            await pubsub.subscribe(f'user_{user_id}')
            
            # Send connection confirmation
            await websocket.send(json.dumps({
                'type': 'connection',
                'status': 'connected'
            }))

            while True:
                try:
                    # Get message from Redis
                    message = await pubsub.get_message(ignore_subscribe_messages=True)
                    if message:
                        await websocket.send(message['data'].decode())
                    
                    # Small delay to prevent CPU hogging
                    await asyncio.sleep(0.1)
                    
                except websockets.exceptions.ConnectionClosed:
                    break
                    
        except Exception as e:
            print(f"Error in handle_client: {e}")
        finally:
            # Cleanup
            if user_id in self.clients:
                del self.clients[user_id]
            await pubsub.unsubscribe()

    async def start_server(self, host='0.0.0.0', port=8001):
        async with websockets.serve(
            self.handle_client, 
            host, 
            port,
            ping_interval=20,
            ping_timeout=30
        ):
            print(f"WebSocket server running on ws://{host}:{port}")
            await asyncio.Future()  # run forever

def main():
    server = NotificationServer()
    asyncio.run(server.start_server())

if __name__ == "__main__":
    main()