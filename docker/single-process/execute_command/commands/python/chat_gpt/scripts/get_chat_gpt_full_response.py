import json5 as json

import requests
import sys


def send_prompt_to_chat_gpt(prompt, model='gpt-4', max_tokens=None, n=None):
    api_key = "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"
    endpoint = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": model,
        "frequency_penalty": 0,
        "presence_penalty": 0,
        "top_p": 1,
        "temperature": 1,
        "max_tokens": max_tokens,
        "n": n,
        "messages": [
            {
                "role": "system",
                "content": "You are a helpful assistant."
            },
            {
                "role": "user",
                "content": f"{prompt}"
            }
        ]
    }

    merged_content = ""
    while True:
        # print('sending requests')
        response = requests.post(endpoint, headers=headers, json=payload)
        # print('response got')
        # print(payload["messages"])
        response_data = response.json()
        # print(response_data)

        if response.status_code == 200:
            choice = response_data["choices"][0]
            payload["messages"].append(choice["message"])
            merged_content += choice["message"]["content"]
            if choice["finish_reason"] != "stop":
                payload["messages"].append({"role": "user", "content": "continue"})
            else:
                break
        else:
            merged_content += f"|Error: {response.status_code}, Message: {response_data}|"
            break

    return merged_content


if __name__ == "__main__":
    if len(sys.argv) < 1:
        print("Usage: script <json_data>")
        sys.exit(1)

    raw_data = sys.argv[1]
    parsed_data = json.loads(raw_data)
    prompt = parsed_data.get('prompt')
    model = parsed_data.get('model', 'gpt-4')
    max_tokens = parsed_data.get('max_tokens', None)
    n = parsed_data.get('n', None)

    output_dict = send_prompt_to_chat_gpt(prompt, model, max_tokens, n)
    print(json.dumps(output_dict))
