from flask import Flask, request, jsonify
import subprocess
import shlex
from dotenv import load_dotenv
import os

import requests

load_dotenv()
OPEN_AI_API_KEY = os.getenv('OPEN_AI_API_KEY')


app = Flask(__name__)


def format_response(result=None, error_msg=None):
    response = {}
    if error_msg:
        response['error'] = error_msg
        response['code'] = -1
    if result:
        response['stdout'] = result.stdout
        response['stderr'] = result.stderr
        response['code'] = result.returncode
    return response


def send_prompt_to_chat_gpt(prompt, model='gpt-4', max_tokens=None, n=None):
    endpoint = "https://api.openai.com/v1/chat/completions"

    headers = {
        "Authorization": f"Bearer {OPEN_AI_API_KEY}",
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
        response = requests.post(endpoint, headers=headers, json=payload, timeout=360)
        response_data = response.json()

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


@app.route('/', methods=['POST'])
def execute_command():
    data = request.get_json()
    secret = data.get('secret')
    if secret != 'StrongSecretCode':
        response = format_response(error_msg="You don't have permission to do it.")
    else:
        command = data.get('command')
        params = data.get('params')

        cmd = shlex.split(command)
        if params:
            cmd.extend(shlex.split(params))

        try:
            result = subprocess.run(cmd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            response = format_response(result=result)
        except subprocess.CalledProcessError as e:
            response = format_response(result=e, error_msg=str(e))
        except Exception as e:
            response = format_response(error_msg=str(e))
    return jsonify(response)


@app.route('/get_chat_gpt_full_response', methods=['POST'])
def execute_command_get_chat_gpt_full_response():
    data = request.get_json()
    secret = data.get('secret')
    if secret != 'StrongSecretCode':
        response = format_response(error_msg="You don't have permission to do it.")
        return jsonify(response)
    else:
        prompt = data.get('prompt')
        model = data.get('model', 'gpt-4')
        max_tokens = data.get('max_tokens', 'false')
        max_tokens = int(max_tokens) if max_tokens.isdigit() else None
        n = data.get('n', 'false')
        n = int(n) if n.isdigit() else None

        chat_gpt_response = send_prompt_to_chat_gpt(prompt, model, max_tokens, n)
        return Response(json.dumps({'chat_gpt_response': chat_gpt_response, 'request_data': data}), content_type='application/json')


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3535)

