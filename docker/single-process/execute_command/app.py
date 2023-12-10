import io
import os
import shlex
import subprocess

import docx2txt
import pdfplumber
import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify

from concurrent.futures import ThreadPoolExecutor, wait

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


def send_prompt_to_chat_gpt(prompt, model='gpt-4', max_tokens=None, n=None, response_type='plain'):
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

    if response_type == 'json':
        payload["response_format"] = {"type": "json_object"}

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
        return jsonify({'chat_gpt_response': chat_gpt_response, 'request_data': data})


@app.route('/cv_rewriter', methods=['POST'])
def execute_command_cv_rewriter():
    data = request.get_json()
    secret = data.get('secret')
    if secret != 'StrongSecretCode':
        response = format_response(error_msg="You don't have permission to do it.")
        return jsonify(response)
    else:

        CV_TEMPLATE_HEAD = '''
            """TEMPLATE CV_TEMPLATE_HEAD START"""
                # John S. | Frontend Dev., 5yrs exp. | English B1
                
                ## Candidates summary
                
                ## Skills
                - Skills category 1
                    - skill name 1.1, skill name 1.2, skill name 1.3, skill name 1.N
                - Skills category 2
                    - skill name 2.1, skill name 2.2, skill name 2.3, skill name 2.N
                - Skills category M
                    - skill name M.1, skill name M.2, skill name M.3, skill name M.N
            """TEMPLATE CV_TEMPLATE_HEAD END"""
        '''

        CV_TEMPLATE_PROJECTS = '''
            """TEMPLATE CV_TEMPLATE_PROJECTS START"""
                ## Projects
                ### Project name from 1 to N [NDA Project]
                Paragraph of project description.
            """TEMPLATE CV_TEMPLATE_PROJECTS END"""
        '''

        CV_TEMPLATE_JOBS = '''
            """TEMPLATE CV_TEMPLATE_JOBS START"""
                ## Jobs if provided, return empty string if no data provided.
                ### Position name from 1 to N, 2 years, do not include companies names.
                Paragraphs of job description, responsibilities, tools and other details.
            """TEMPLATE CV_TEMPLATE_JOBS END"""
        '''

        CV_TEMPLATE_CERTIFICATIONS_EDUCATIONS_LANGUAGES = '''
            """TEMPLATE CV_TEMPLATE_CERTIFICATIONS_EDUCATIONS_LANGUAGES START"""
                ## Certifications if provided, skip it if empty
                
                ## Education if provided, skip it if empty
                
                ## Language Skills in B1/B2/C1/C2 format
            """TEMPLATE CV_TEMPLATE_CERTIFICATIONS_EDUCATIONS_LANGUAGES END"""
        '''

        CV_TEMPLATE_ADDITIONAL_AND_FOOTER = '''
            """TEMPLATE CV_TEMPLATE_ADDITIONAL_AND_FOOTER START"""
                ## Additional information if provided, skip it if empty
                ### Additional information category name from 1 to N
                Paragraph of additional information description.
                
                ## DTEAM Contacts
                * email: talk@dteam.dev
                * website: dteam.dev
                * telegram: @DTEAM_outsource_outstaff
                
                ### Thank you for reading this far. 🙂
            """TEMPLATE CV_TEMPLATE_ADDITIONAL_AND_FOOTER END"""
        '''

        def extract_text_from_file(url):
            cv_file = requests.get(url, stream=True)
            cv_content_type = cv_file.headers.get('Content-Type')
            cv_content_disposition = cv_file.headers.get('Content-Disposition', '')

            if 'pdf' in cv_content_type or '.pdf' in cv_content_disposition:
                return extract_text_from_pdf(cv_file)
            elif 'msword' in cv_content_type or '.docx' in cv_content_disposition:
                return extract_text_from_docx(cv_file)
            elif 'msword' in cv_content_type or '.doc' in cv_content_disposition:
                return extract_text_from_doc(cv_file)
            else:
                return "Unsupported file type or unable to determine file type"

        def extract_text_from_pdf(response):
            with io.BytesIO(response.content) as f:
                with pdfplumber.open(f) as pdf:
                    text = ''
                    for page in pdf.pages:
                        text += page.extract_text()
                    return text

        def extract_text_from_docx(response):
            with io.BytesIO(response.content) as f:
                return docx2txt.process(f)

        def extract_text_from_doc(response):
            with io.BytesIO(response.content) as f:
                return docx2txt.process(f)

        cv_url = data.get('cv_url')
        additional_prompt = data.get('additional_prompt', '')

        cv_raw_text = extract_text_from_file(cv_url)

        model = data.get('model', 'gpt-4')
        max_tokens = data.get('max_tokens', 'false')
        max_tokens = int(max_tokens) if max_tokens.isdigit() else None
        n = data.get('n', 'false')
        n = int(n) if n.isdigit() else None

        def get_cv_section(section_prompt, model=model, max_tokens=max_tokens, n=n):
            full_prompt = f"""
            Rules:
                GPT, you're an Expert recruiter, with 10 years of experience in this field. 
                Generate an excellent CV for this employee, based on provided information. Do not include your own comments to the result. Do not include any employee’s personal information to the result. The result need to be in Markdown format, do not use tables.
                If you see that the initial CV has any necessary project details like Responsibilities, Tools, Technologies, Role, Country, or any other necessary details like this, expand the project description with those details.
                If you don’t have enough information to fill any of those sections or some part of it, just leave it empty.
                The result resume structure must follow the template.
                Please do not miss any skill, job, project, certification or any other provided details from initial CV. It's very necessary for us to get as much relevant CV as possible. You can extend the template, if initial CV has not mentioned details.

                {CV_TEMPLATE_HEAD}

                {CV_TEMPLATE_PROJECTS}

                {CV_TEMPLATE_JOBS}

                {CV_TEMPLATE_CERTIFICATIONS_EDUCATIONS_LANGUAGES}

                {CV_TEMPLATE_ADDITIONAL_AND_FOOTER}

                The result resume must be written as from candidate in a friendly manner, very summarized and clear.
                {additional_prompt}
                Here is extracted text from the employee's CV, which was in PDF format. So, some data can be missed, or looks broken.
                
            What's to do:
                {section_prompt}
            
            Candidate's CV:
                {cv_raw_text}
            """
            return send_prompt_to_chat_gpt(full_prompt, model, max_tokens, n)

        section_prompts = [
            'Write and return only CV_TEMPLATE_HEAD section.',
            'Write and return only CV_TEMPLATE_PROJECTS section.',
            'Write and return only CV_TEMPLATE_JOBS section.',
            'Write and return only CV_TEMPLATE_CERTIFICATIONS_EDUCATIONS_LANGUAGES section.',
            'Write and return only CV_TEMPLATE_ADDITIONAL_AND_FOOTER section.',
        ]

        # Process sections in parallel using ThreadPoolExecutor
        futures = []
        with ThreadPoolExecutor() as executor:
            for prompt in section_prompts:
                future = executor.submit(get_cv_section, prompt)
                futures.append(future)
            done, _ = wait(futures)

        # Ensuring results are in the order of submission
        ordered_results = [future.result() for future in futures]
        result_text = '\n'.join(ordered_results)

        return jsonify({'chat_gpt_response': result_text, 'request_data': data})


@app.route('/analyze-email', methods=['POST'])
def execute_command_analyze_email():
    data = request.get_json()
    secret = data.get('secret')
    if secret != 'StrongSecretCode':
        response = format_response(error_msg="You don't have permission to do it.")
        return jsonify(response)
    else:
        email_content = data.get('email_content', '')
        prompt = f'''
            I will define the rules you must follow in.
    
            Basic rules:
            – Everything here in plain text format;
            – TEXT is a whole text which I provided you;
            – CONVERSATION is a part of the text, defined at the end of the TEXT;
            – You always must follow all the provided rules; 
            – Your answer must follow ANSWER_TEMPLATE;
            – If you don't see a possible ToDo (based on text, don't try to guess), make it empty;
            – Your answers always must be in JSON format, fully based on ecma-404 standard. Before you write the answer, make sure that everything in your answer match ecma-404 standard. Provide the response in pure JSON format with no additional text. Only code;
            – Your answer must follow the form of the template provided, no other information should be in your answer;
            
            Variables rules:
            – I can define any number of variables in the text;
            – A variable can contain a value or list of values;
            – If a variable or a list item starts from [smart] then consider extending it based on prompt inside;
            – Variable name must contain variable word;
            – We can define and reuse variables in any place;
            
            AUTO_REPLY_LIST_VARIABLE:
            – auto-reply;
            – automatic reply;
            – out of office;
            – in vocation;
            – not available;
            – respond to your email as soon as possible;
            – response time may be slower;
            – travelling;
            – [smart] any message that shows that the message is sent automatically;
            – [smart] any similar to cases from AUTO_REPLY_LIST_VARIABLE;
            
            STOP_MESSAGING_LIST_VARIABLE:
            – stop message;
            – stop mailing;
            – stop spam;
            – unsubscribe;
            – remove;
            – [smart] any message that shows that we're annoying him;
            – [smart] any similar to cases from STOP_MESSAGING_LIST_VARIABLE;
            
            Templates rules:
            – Template name must contain template word;
            
            ANSWER_TEMPLATE:
            """
            {{
              "Score": "Neutral",
              "ToDo": [
                "ToDo 1",
                "ToDo 2",
                "ToDo 3"
              ],
              "Explanation": "Explanation of provided Score and ToDo."
            }}
            """
            
            Conversation analyse rules:
            – This conversation can include from 1 to many messages between 1 or more people;
            – We need to analyse only the latest message;
            – The latest message always the first one in this conversation, because the order of messages always reversed, from bottom to top;
            – The person whose message we work with is lead;
            – If lead's message is always email latter, so in some cases it can contain signature, please don't use it to analyse;
            
            Score rules:
            – Conflict use it when you see two or more possible rules, like Positive and Negative;
            – Positive is any answer of lead which means that he interested or ask us to message him in later, or asked for our pricing, expertise, and technologies that we work with;
            – Negative is lead asked as for something from STOP_MESSAGING_LIST_VARIABLE;
            – Auto-reply is lead which answered something from AUTO_REPLY_LIST_VARIABLE;
            – Neutral is everything that can’t mark as auto-reply, negative, positive, conflict. Lead asked as to send message to another person, or he is not work any more on this position or in this company, or they all set, don't need any other help right now without any negative.;
            
            ToDo list rules:
            – Must include only possible items from the message, sign or send the NDA, provide a presentation, send the company's website, answer a lead's question, contact to another person, contact him later, send him our pricing / rates, send him more information about expertise and technologies that we work with, schedule a meet, etc;
            – If it's auto-reply, or he isn't available now by vocation, emergency or any other reason, then add ToDo to write to him when he will be available plus couple of days but not in weekends or holidays;
            – If lead said that they all set, don't need any other help right now, don’t have any needs at this moment, without any negative, than add ToDo to message him in 4 months, not related to auto-reply messages;
            – If lead suggest calling or message someone, then mention name and contact data (if available) in ToDo item;
            – If a reply indicating that the recipient will not be available until a specific date, or he recommends us to try at a specific date, please add the ToDo and mention the specific date inside;
            – If the lead's response doesn't explicitly state their disinterest in our services and also doesn't provide any negative feedback, then we should add a ToDo item to write to them in 6 months;
            – If lead ask exact to remove from email list, stop email campaign, remove him from your crm, take him off, etc. Not related to cases when he said not interested or so in neutral way. Then, add the ToDo to remove him from email list (you must mention name and email of this lead in this ToDo);
            
            Your task: 
            Analysed given conversation, as Senior Sales Manager working for a DTEAM company that does outsource and outstaff development, with more than 10 years of b2b sales experience.
            """
            {email_content}
            """
        '''
        model = data.get('model', 'gpt-4-1106-preview')
        max_tokens = data.get('max_tokens', 'false')
        max_tokens = int(max_tokens) if max_tokens.isdigit() else None
        n = data.get('n', 'false')
        n = int(n) if n.isdigit() else None

        chat_gpt_response = send_prompt_to_chat_gpt(prompt, model, max_tokens, n, response_type='json')
        return jsonify({'chat_gpt_response': chat_gpt_response, 'request_data': data})


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=3535)

