import json
import os
import sys
import urllib.error
import urllib.request


GROQ_URL = "https://api.groq.com/openai/v1/chat/completions"
MODEL = "openai/gpt-oss-20b"


def classify_format(headers):
    content_type = (headers.get("Content-Type") or "").lower()

    if "application/json" in content_type:
        return "json"
    if "text/html" in content_type:
        return "html"
    if content_type.startswith("text/"):
        return "text"
    if content_type:
        return "other"
    return "absent"


def classify_origin(headers):
    server = (headers.get("Server") or "").lower()

    if "cloudflare" in server or headers.get("CF-RAY"):
        return "cloudflare"
    if "groq" in server:
        return "groq"
    if server:
        return "server_present"
    if headers.get("Via"):
        return "via_present"
    return "unclassified"


def report(status, headers, result):
    print(f"http_status={status}")
    print(f"response_format={classify_format(headers)}")
    print(f"response_origin={classify_origin(headers)}")
    print(f"connectivity_result={result}")


def main():
    api_key = (os.environ.get("GROQ_API_KEY") or "").strip()

    if not api_key:
        print("probe_error=missing_groq_api_key")
        sys.exit(2)

    payload = {
        "model": MODEL,
        "messages": [
            {
                "role": "user",
                "content": "Reply with exactly: GROQ CONNECTIVITY OK",
            }
        ],
        "temperature": 0,
        "max_tokens": 20,
    }

    request = urllib.request.Request(
        GROQ_URL,
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "User-Agent": "north-star-groq-connectivity-probe/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            report(response.status, response.headers, "PASS")
            return

    except urllib.error.HTTPError as exc:
        report(exc.code, exc.headers, "FAIL")
        return

    except Exception as exc:
        print(f"transport_error={type(exc).__name__}")
        print("connectivity_result=FAIL")


if __name__ == "__main__":
    main()
