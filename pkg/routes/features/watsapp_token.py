from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from twilio.rest import Client
import os

app = FastAPI()

# Twilio credentials
account_sid = "ACca6b2babc4a12a43886d8135d298560a"  # Replace with your Account SID
auth_token = "00d6cbacdc66c48f3b8463b6ddd2ae4d"  # Replace with your Auth Token
twilio_whatsapp_number = "whatsapp:+918754481812"  # Replace with your Twilio WhatsApp number

client = Client(account_sid, auth_token)


class Message(BaseModel):
    to: str
    body: str


@app.post("/send-message/")
async def send_whatsapp_message(message: Message):
    # try:
    # Send WhatsApp message
    sent_message = client.messages.create(
        body=message.body,
        from_=twilio_whatsapp_number,
        to=f"whatsapp:{message.to}"
    )
    return {"status": "Message sent", "message_sid": sent_message.sid}
    #
    # except Exception as e:
    #     raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8011)
