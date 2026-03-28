import requests
import sys
import json

BASE_URL = "http://127.0.0.1:8000"

BANNER = """
╔══════════════════════════════════════════════════════╗
║         💸  Expense Logger  ·  API Client             ║
║                                                      ║
║  Connects to: http://127.0.0.1:8000                  ║
║  Log, Query, or Chat in one place!                  ║
╚══════════════════════════════════════════════════════╝
"""

def main():
    print(BANNER)
    
    # Check server health
    try:
        resp = requests.get(f"{BASE_URL}/")
        if resp.status_code != 200:
            print(f"⚠️  Server at {BASE_URL} responded with {resp.status_code}. It might not be ready.")
    except requests.exceptions.ConnectionError:
        print(f"❌  Could not connect to server at {BASE_URL}.")
        print("    Please start the server first: uvicorn app:app --reload")
        sys.exit(1)

    while True:
        try:
            user_input = input("💬 You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye!")
            break

        if not user_input:
            continue

        if user_input.lower() in {"quit", "exit", "q"}:
            print("Goodbye!")
            break

        print("  ⏳ Thinking...")
        try:
            response = requests.post(
                f"{BASE_URL}/api/chat",
                json={"message": user_input}
            )
            
            response.raise_for_status()
            data = response.json()
            
            intent = data.get("intent")
            answer = data.get("answer")
            
            if intent == "log":
                print(f"  ✅ {answer}")
                # Optionally print the full structured object if returned
                # expense = data.get("expense")
                # if expense:
                #     print(f"     Details: {json.dumps(expense, indent=2)}")
            else:
                print(f"\n  🤖 {answer}\n")
                
        except requests.exceptions.RequestException as e:
            print(f"  ❌ Error: {e}")

if __name__ == "__main__":
    main()
