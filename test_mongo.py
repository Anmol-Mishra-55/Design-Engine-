from pymongo import MongoClient
from dotenv import load_dotenv
import os

load_dotenv('backend/.env')

url = os.getenv('MONGODB_URL')
client = MongoClient(url)
try:
    client.admin.command('ping')
    print('✅ MongoDB connected!')
except Exception as e:
    print(f'❌ Connection failed: {e}')
finally:
    client.close()
