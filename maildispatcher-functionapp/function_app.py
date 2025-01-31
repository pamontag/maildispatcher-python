import logging
import os
import azure.functions as func
import json
from azureai import AzureAI
from messageservices import MessageServices
from model import EmailData

app = func.FunctionApp()
queue_name_env = os.environ["QUEUE_NAME"]
connection_env = os.environ["CONNECTION_SETTING"]
queue_name_output_env = os.environ["QUEUE_OUTPUT_NAME"]
queue_name_reply_env = os.environ["QUEUE_RETRY_NAME"]

@app.function_name(name="MailDispatcherFunction")
@app.service_bus_queue_trigger(arg_name="msg", 
                               queue_name=queue_name_env, 
                               connection=connection_env)
async def main(msg: func.ServiceBusMessage):
    body = msg.get_body().decode('utf-8')
    subject = msg.application_properties.get('subject')
    msgid = msg.application_properties.get('messageId')
    conversationId = msg.application_properties.get('conversationId')
    result = json.dumps({
        'msgid': msgid,
        'subject': subject,
        'body': body,
        'conversationId': conversationId
    }, default=str)
    logging.info('Python ServiceBus queue trigger processed message: %s',
                 result)
    azureai = AzureAI()
    await azureai.init() 
    msg = EmailData(subject, body, msgid, conversationId)
    jsonresult = await azureai.get_correct_mail_from_msg(msg)
    logging.info(jsonresult.content.replace("```json", "").replace("```", ""))
    jsonresult = json.loads(jsonresult.content.replace("```json", "").replace("```", ""))
    msg.EmailCategory = jsonresult['mailToTestResult']
    messageservices = MessageServices()
    await messageservices.send_message(queue_name_reply_env if msg.EmailCategory == "UNKNOWN" else queue_name_output_env, msg)
    
