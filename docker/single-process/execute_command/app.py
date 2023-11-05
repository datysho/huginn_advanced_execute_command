from flask import Flask, request, jsonify
import subprocess
import shlex

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


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3535)
