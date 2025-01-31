class EmailData:
    def __init__(self, subject, body, messageId, conversationId):
        self.Oggetto = subject
        self.Messaggio = body
        self.MessageId = messageId
        self.ConversationId = conversationId
        self.EmailCategory = None
