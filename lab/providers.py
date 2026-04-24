import json
from urllib import error, parse, request


def extract_code_block(content):
    text = content.strip()
    if not text.startswith("```"):
        return text

    lines = text.splitlines()
    if lines:
        lines = lines[1:]
    while lines and lines[-1].strip().startswith("```"):
        lines.pop()
    return "\n".join(lines).strip()


def build_auth_headers(token="", api_key="", api_secret=""):
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if api_key:
        headers["x-onyx-key"] = api_key
    if api_secret:
        headers["x-onyx-secret"] = api_secret
    return headers


def post_json(endpoint, payload, headers):
    http_request = request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    try:
        with request.urlopen(http_request, timeout=120) as response:
            return json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        exc.body_text = body
        raise


def post_stream_packets(endpoint, payload, headers):
    http_request = request.Request(
        endpoint,
        data=json.dumps(payload).encode("utf-8"),
        headers=headers,
        method="POST",
    )

    packets = []
    try:
        with request.urlopen(http_request, timeout=120) as response:
            raw = response.read().decode("utf-8", errors="replace")
    except error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        exc.body_text = body
        raise

    for raw_line in raw.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith("data:"):
            line = line[5:].strip()
        if not line or line == "[DONE]":
            continue
        try:
            packets.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return packets


def call_onyx_ai_chat(prompt, base_url, model, token="", database_id="", api_key="", api_secret=""):
    if not base_url:
        raise ValueError("ONYX_BASE_URL is required when LLM_PROVIDER=onyx.")
    if not model:
        raise ValueError("ONYX_MODEL or LLM_MODEL is required when LLM_PROVIDER=onyx.")

    endpoint = base_url.rstrip("/") + "/api/chat"
    if database_id:
        endpoint = endpoint + "?" + parse.urlencode({"databaseId": database_id})

    payload = {
        "model": model,
        "stream": False,
        "messages": [
            {
                "role": "system",
                "content": (
                    prompt["contract"]
                    + "\nReturn Python code only. Do not use markdown fences."
                ),
            },
            {
                "role": "user",
                "content": json.dumps({
                    "task": prompt["task"],
                    "mistakes": prompt["mistakes"],
                    "strategy_source": prompt["strategy_source"],
                }, indent=2),
            },
        ],
    }

    body = post_json(endpoint, payload, build_auth_headers(token, api_key, api_secret))

    content = body.get("message", {}).get("content", "")
    if not content:
        raise ValueError("Onyx response did not contain assistant code content.")
    return extract_code_block(content)


def call_onyx_app_chat(prompt, base_url, model, token="", api_key="", api_secret=""):
    root = base_url.rstrip("/")
    if root.endswith("/api"):
        endpoint = root + "/chat/send-chat-message"
    else:
        endpoint = root + "/api/chat/send-chat-message"

    message = "\n\n".join([
        prompt["contract"],
        "Return Python code only. Do not use markdown fences.",
        "Task:",
        prompt["task"],
        "Mistakes:",
        json.dumps(prompt["mistakes"], indent=2),
        "Current strategy source:",
        prompt["strategy_source"],
    ])

    payload = {
        "message": message,
        "stream": True,
    }
    if model:
        payload["llm_override"] = {
            "model_version": model,
        }

    try:
        packets = post_stream_packets(endpoint, payload, build_auth_headers(token, api_key, api_secret))
    except error.HTTPError as exc:
        if exc.code in {401, 403}:
            raise ValueError(
                "Onyx rejected the request. Your self-hosted Onyx app at localhost:3000 "
                "requires an API key. Set ONYX_TOKEN or ONYX_KEY/ONYX_SECRET."
            ) from exc
        raise

    answer_parts = []
    for packet in packets:
        if packet.get("error"):
            raise ValueError(packet["error"])
        if packet.get("answer"):
            answer_parts = [packet["answer"]]
        elif packet.get("answer_piece"):
            answer_parts.append(packet["answer_piece"])
        elif packet.get("answer_delta"):
            answer_parts.append(packet["answer_delta"])
        elif packet.get("answer_citationless"):
            answer_parts = [packet["answer_citationless"]]
        elif isinstance(packet.get("obj"), dict):
            obj = packet["obj"]
            if obj.get("type") == "message_delta" and obj.get("content"):
                answer_parts.append(obj["content"])
            elif obj.get("type") in {"error", "message_error"}:
                raise ValueError(obj.get("error") or obj.get("message") or "Onyx returned an error packet.")

    content = "".join(answer_parts).strip()
    if not content:
        raise ValueError("Onyx app API response did not contain answer content.")
    return extract_code_block(content)


def call_onyx_chat(
    prompt,
    base_url,
    model,
    token="",
    database_id="",
    api_key="",
    api_secret="",
    mode="auto",
):
    if mode not in {"auto", "ai_endpoint", "app"}:
        raise ValueError("ONYX_API_MODE must be one of: auto, ai_endpoint, app.")

    if mode == "ai_endpoint":
        return call_onyx_ai_chat(prompt, base_url, model, token, database_id, api_key, api_secret)
    if mode == "app":
        return call_onyx_app_chat(prompt, base_url, model, token, api_key, api_secret)

    try:
        return call_onyx_ai_chat(prompt, base_url, model, token, database_id, api_key, api_secret)
    except error.HTTPError as exc:
        if exc.code == 404:
            return call_onyx_app_chat(prompt, base_url, model, token, api_key, api_secret)
        if exc.code in {401, 403}:
            raise ValueError(
                "Onyx rejected the request. For self-hosted Onyx at localhost:3000, "
                "create an API key and set ONYX_TOKEN or ONYX_KEY/ONYX_SECRET."
            ) from exc
        raise
