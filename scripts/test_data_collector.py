import json
import os
import sys
from dotenv import load_dotenv

# Load env variables (API Keys)
load_dotenv()

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '../'))

from backend.functions.data_collector.app import lambda_handler

def test_collector():
    print("--- Starting Data Collector Test ---")
    
    # Check API Key
    api_key = os.environ.get('PUBLIC_DATA_PORTAL_API_KEY')
    print(f"API Key present: {'Yes' if api_key else 'No'}")
    
    # Mock Event
    event = {}
    context = {}
    
    response = lambda_handler(event, context)
    
    print("\n--- Test Result ---")
    print(json.dumps(response, indent=2, ensure_ascii=False))

if __name__ == "__main__":
    test_collector()
