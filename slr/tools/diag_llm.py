import os, sys, json, traceback, requests

BASE = os.getenv("OPENAI_BASE_URL", "https://kiste.informatik.tu-chemnitz.de/v1")
KEY  = os.getenv("KISTE_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
MODEL= os.getenv("LLM_MODEL", "gpt-oss-120b")

print("=== ENV CHECK ===")
print("Base URL        :", BASE)
print("API key present :", "yes" if KEY else "no")
print("API key tail    :", (KEY[-6:] if KEY else "<missing>"))
print("Model           :", MODEL)
print("Proxies         :", {k:v for k,v in os.environ.items() if k.lower() in ["http_proxy","https_proxy","all_proxy"]})
print("Certs           :", {k:v for k,v in os.environ.items() if k in ["SSL_CERT_FILE","REQUESTS_CA_BUNDLE"]})
print()

print("=== /models PROBE ===")
try:
    r = requests.get(
        f"{BASE.rstrip('/')}/models",
        headers={"Authorization": f"Bearer {KEY}"} if KEY else {},
        timeout=15,
    )
    print("HTTP status     :", r.status_code)
    print("Body (head)     :", (r.text or "").replace("\n"," ")[:500])
except Exception as e:
    print("EXC (requests)  :", repr(e))
    traceback.print_exc()
    sys.exit(2)

print("\n=== CHAT PROBE (LLMClient) ===")
try:
    sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
    from slr.llm.client import LLMClient
    cli = LLMClient(model=MODEL, api_key=KEY, base_url=BASE)
    text = cli.chat(
        system="You are a minimal tester.",
        user="Reply with the single word: OK.",
        max_retries=1,
        request_timeout=20.0,
        temperature=0,
        max_tokens=8,
    )
    print("Chat response   :", (text or "")[:120])
except Exception as e:
    print("EXC (LLMClient) :", repr(e))
    traceback.print_exc()
    sys.exit(3)

print("\nAll good ✅")
