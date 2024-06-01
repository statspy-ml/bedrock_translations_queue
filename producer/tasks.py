from celery import Celery
import psycopg2
import time
import json
import os
from langchain_community.chat_models import BedrockChat
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, BaseMessage
import boto3
from typing import List, Dict, Optional, Any
from langchain_core.callbacks import CallbackManagerForLLMRun
from langchain_community.llms.utils import enforce_stop_tokens
from langchain.schema.output import ChatResult, ChatGeneration

app = Celery('tasks',
             broker='pyamqp://user:password@rabbitmq//',
             backend='db+postgresql://user:password@postgres/translations',
             include=['tasks'])

# Configuração do modelo com credenciais AWS
aws_access_key_id = os.getenv('AWS_ACCESS_KEY_ID')
aws_secret_access_key = os.getenv('AWS_SECRET_ACCESS_KEY')
aws_session_token = os.getenv('AWS_SESSION_TOKEN')  # Se necessário

boto3_session = boto3.Session(
    aws_access_key_id=aws_access_key_id,
    aws_secret_access_key=aws_secret_access_key,
    aws_session_token=aws_session_token,
    region_name='us-east-1'
)

brt = boto3_session.client(service_name='bedrock-runtime')


class BedrockChatV3(BedrockChat):
    """A chat model that uses the Bedrock API."""

    def _format_messages(self, messages: List[BaseMessage]) -> List[Dict[str, str]]:
        list_of_messages = []
        for i, message in enumerate(messages):
            if i % 2 == 0 and not isinstance(message, HumanMessage):
                raise Exception(f"Expected to see a HumanMessage at the position {i}, but found {message.__class__}")
            elif i % 2 == 1 and not isinstance(message, AIMessage):
                raise Exception(f"Expected to see a AIMessage at the position {i}, but found {message.__class__}")

            list_of_messages.append({
                "role": "user" if isinstance(message, HumanMessage) else "assistant",
                "content": message.content
            })
        return list_of_messages

    def _prepare_input_and_invoke(self, prompt: List[BaseMessage], stop: Optional[List[str]] = None,
                                  run_manager: Optional[CallbackManagerForLLMRun] = None, **kwargs: Any) -> str:
        _model_kwargs = self.model_kwargs or {}

        messages = prompt
        params = {**_model_kwargs, **kwargs}
        params["anthropic_version"] = "bedrock-2023-05-31"
        if "max_tokens" not in params:
            params["max_tokens"] = 256
        if self._guardrails_enabled:
            params.update(self._get_guardrails_canonical())

        if isinstance(messages[0], SystemMessage):
            system = messages[0].content
            messages = messages[1:]
        messages = self._format_messages(messages)
        input_body = params
        input_body["system"] = system
        input_body["messages"] = messages
        body = json.dumps(input_body)
        accept = "application/json"
        contentType = "application/json"

        request_options = {
            "modelId": self.model_id,
            "accept": accept,
            "contentType": contentType,
            "body": body
        }

        if self._guardrails_enabled:
            request_options["guardrail"] = "ENABLED"
            if self.guardrails.get("trace"):  # type: ignore[union-attr]
                request_options["trace"] = "ENABLED"

        try:
            response = self.client.invoke_model(**request_options)
            body = json.loads(response.get("body").read().decode())
            text = body['content'][0]['text']

        except Exception as e:
            raise ValueError(f"Error raised by bedrock service: {e}")

        if stop is not None:
            text = enforce_stop_tokens(text, stop)

        services_trace = self._get_bedrock_services_signal(body)  # type: ignore[arg-type]

        if services_trace.get("signal") and run_manager is not None:
            run_manager.on_llm_error(
                Exception(
                    f"Error raised by bedrock service: {services_trace.get('reason')}"
                ),
                **services_trace,
            )

        return text

    def _generate(self, messages: List[BaseMessage], stop: Optional[List[str]] = None,
                  run_manager: Optional[CallbackManagerForLLMRun] = None, **kwargs: Any) -> ChatResult:
        completion = ""

        params: Dict[str, Any] = {**kwargs}
        if stop:
            params["stop_sequences"] = stop

        completion = self._prepare_input_and_invoke(
            prompt=messages, stop=stop, run_manager=run_manager, **params
        )

        message = AIMessage(content=completion)
        return ChatResult(generations=[ChatGeneration(message=message)])


chat = BedrockChatV3(model_id="amazon.titan-text-premier-v1:0", model_kwargs={"temperature": 0.5}, verbose=True, region_name='us-east-1', client=brt)


def get_db_connection():
    conn = psycopg2.connect(
        dbname='translations',
        user='user',
        password='password',
        host='postgres'
    )
    return conn


@app.task
def send_to_queue(chave, comentario):
    conn = get_db_connection()
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS translations
                 (chave INTEGER PRIMARY KEY, comentario TEXT, translation TEXT, time_taken REAL, processed BOOLEAN DEFAULT FALSE)''')

    # Verifica se a mensagem já foi processada
    c.execute("SELECT processed FROM translations WHERE chave = %s AND comentario = %s", (chave, comentario))
    result = c.fetchone()
    if result and result[0]:
        print(f"Mensagem já processada: chave={chave}, comentario={comentario}")
        conn.close()
        return

    # Processar tradução
    start_time = time.time()
    prompt = f"You are a helpful assistant that makes perfect translations from English to Portuguese. Translate the given sentences from English to Brazilian Portuguese. You shall do the translations without giving any explanations or additional comments.\n\nHuman: {comentario}\n\nAssistant:"
    native_request = {
        "inputText": prompt,
        "textGenerationConfig": {
            "maxTokenCount": 512,
            "temperature": 0.5,
        },
    }
    try:
        request = json.dumps(native_request)
        response = chat.client.invoke_model(modelId="amazon.titan-text-premier-v1:0", body=request)
        model_response = json.loads(response["body"].read())
        response_text = model_response["results"][0]["outputText"]
    except Exception as e:
        response_text = f"Error - {str(e)}"
    end_time = time.time()
    duration = end_time - start_time

    # Persistir resultado no PostgreSQL e marcar como processada
    c.execute("INSERT INTO translations (chave, comentario, translation, time_taken, processed) VALUES (%s, %s, %s, %s, %s) ON CONFLICT (chave) DO UPDATE SET comentario = EXCLUDED.comentario, translation = EXCLUDED.translation, time_taken = EXCLUDED.time_taken, processed = EXCLUDED.processed",
              (chave, comentario, response_text, duration, True))
    conn.commit()
    conn.close()
