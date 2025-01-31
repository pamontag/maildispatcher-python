import os
import logging
from azure.servicebus.aio import ServiceBusClient
from azure.servicebus import ServiceBusMessage

class MessageServices:
    def __init__(self):
        self.CONNECTION_STRING = os.getenv("ServiceBusConnection")

    async def send_single_message(self, sender, email_data):
        # Create a Service Bus message and send it to the queue
        application_properties = {}
        application_properties["subject"] = email_data.Oggetto
        application_properties["messageId"] = email_data.MessageId
        application_properties["conversationId"] = email_data.ConversationId
        application_properties["emailCategory"] = email_data.EmailCategory
        message = ServiceBusMessage(email_data.Messaggio, application_properties=application_properties)
        await sender.send_messages(message)

    async def send_message(self, queue_name, email_data):
        # create a Service Bus client using the connection string
        async with ServiceBusClient.from_connection_string(
            conn_str=self.CONNECTION_STRING,
            logging_enable=True) as servicebus_client:
            # Get a Queue Sender object to send messages to the queue
            sender = servicebus_client.get_queue_sender(queue_name=queue_name)
            async with sender:
                # Send one message
                logging.info(f"Sending messageId {email_data.MessageId} to the queue {queue_name}")
                await self.send_single_message(sender, email_data)
                logging.info(f"Message messageId {email_data.MessageId} sent to the queue {queue_name}")
    
        
        