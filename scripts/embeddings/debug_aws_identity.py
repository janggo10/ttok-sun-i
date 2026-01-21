import boto3
import os
from dotenv import load_dotenv

# Load env same as the main script
load_dotenv()

def mask(s):
    if not s: return "None"
    if len(s) < 8: return "*" * len(s)
    return s[:4] + "*" * (len(s)-8) + s[-4:]

def main():
    print("--- Environment Variables Check ---")
    print(f"AWS_ACCESS_KEY_ID: {mask(os.environ.get('AWS_ACCESS_KEY_ID'))}")
    print(f"AWS_SECRET_ACCESS_KEY: {mask(os.environ.get('AWS_SECRET_ACCESS_KEY'))}")
    print(f"AWS_SESSION_TOKEN: {mask(os.environ.get('AWS_SESSION_TOKEN'))}")
    print(f"AWS_REGION: {os.environ.get('AWS_REGION')}")
    print(f"AWS_PROFILE: {os.environ.get('AWS_PROFILE')}")
    
    print("\n--- Boto3 Identity Check ---")
    try:
        sts = boto3.client('sts')
        identity = sts.get_caller_identity()
        print(f"Successfully connected as: {identity['Arn']}")
        print(f"Account: {identity['Account']}")
    except Exception as e:
        print(f"❌ Connection Failed: {e}")

if __name__ == "__main__":
    main()
