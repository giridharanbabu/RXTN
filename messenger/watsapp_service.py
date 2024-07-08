
import os
from twilio.rest import Client
TWILIO_ACCOUNT_SID = "ACca6b2babc4a12a43886d8135d298560a"
TWILIO_AUTH_TOKEN = "00ffd81e2f439433b3886be653c8584b"
# Find your Account SID and Auth Token at twilio.com/console
# and set the environment variables. See http://twil.io/secure
account_sid = "ACca6b2babc4a12a43886d8135d298560a"
auth_token = "00ffd81e2f439433b3886be653c8584b"
client = Client(account_sid, auth_token)

message = client.messages.create(
    from_='whatsapp:+14155238886',
    body='Hello, there!',
    to='whatsapp:+919655545283'
)

print(message.sid)
