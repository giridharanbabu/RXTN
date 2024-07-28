import json

from fastapi import FastAPI, HTTPException, Depends, Body, APIRouter, UploadFile, File, Form
from typing import List, Optional
from bson import ObjectId
import gridfs
from pkg.routes.authentication import val_token
from pkg.routes.customer.customer import generate_html_message
from pkg.routes.emails import Email
from pkg.routes.ticketing.ticket_models import Ticket, TicketCreate, ChatMessage, ChatMessageCreate, CloseTicket
from pkg.database.database import database
from datetime import datetime
from fastapi.responses import StreamingResponse, JSONResponse

ticket_router = APIRouter()

ticket_collection = database.get_collection('tickets')
chat_messages_collections = database.get_collection('chat_messages')
customers_collection = database.get_collection('customers')
member_collections = database.get_collection('partners')
user_collection = database.get_collection('users')


# Utility function to fetch document by ID
async def get_document_by_id(id):
    doc = ticket_collection.find_one({"_id": ObjectId(id)})
    if doc:
        doc["_id"] = str(doc["_id"])  # Convert ObjectId to string
    return doc


async def get_document_by_id_byrequester(id, receiver_id, name):
    print({"_id": ObjectId(id), name: receiver_id})
    doc = ticket_collection.find_one({"_id": ObjectId(id), name: receiver_id})
    if doc:
        doc["_id"] = str(doc["_id"])  # Convert ObjectId to string
    return doc


# Create a new ticket
@ticket_router.post("/tickets", response_model=Ticket)
async def create_ticket(ticket: TicketCreate, token: str = Depends(val_token)):
    if token[0] is True:
        payload = token[1]
        ticket_doc = ticket.dict()
        ticket_doc["status"] = "open"
        ticket_doc["created_at"] = datetime.utcnow()
        customer_details = customers_collection.find_one({'email': payload['email']})
        ticket_doc['customer'] = str(customer_details['_id'])
        ticket_doc["customer_name"] = customer_details['name']
        subject = f"Query Raised: Request from  {customer_details['email']}"
        body = f"Description:\n\n{ticket_doc['description']}"

        if len(customer_details['partner_id']):
            get_partner = customer_details['partner_id'][0]
            ticket_doc['partner'] = str(get_partner)
            member = member_collections.find_one({'_id': ObjectId(get_partner)})
            ticket_doc['partner'] = str(member['_id'])
            ticket_doc['partner_name'] = str(member['name'])
            # update_ticket_status = member_collections.update_one(
            #     {'_id': ObjectId(member['_id'])},
            #     {'$set': {'tickets': tickets}}
            # )
            await Email(subject, member['email'], 'query_request', body).send_email()
        admin_email = "giri1208srinivas@gmail.com"

        await Email(subject, admin_email, 'query_request', body).send_email()
        user_details = user_collection.find_one({'email': admin_email})
        ticket_doc['admin'] = str(user_details['_id'])
        ticket_doc['admin_name'] = user_details['name']
        result = ticket_collection.insert_one(ticket_doc)
        ticket_doc["_id"] = str(result.inserted_id)  # Convert ObjectId to string for response
        # return ticket_doc
        ticket_info = {"ticket_id": ticket_doc["_id"], "status": ticket_doc["status"],
                       "created_at": ticket_doc["created_at"], "created_by": ticket_doc['customer']}
        update_customer = customers_collection.update_one({'_id': ObjectId(customer_details['_id'])},
                                                          {'$set': {'tickets': ticket_info}})

        return Ticket(**ticket_doc)
    else:
        raise HTTPException(status_code=401, detail=token[1])


# Get a ticket by ID
@ticket_router.get("/tickets/{ticket_id}", response_model=Ticket)
async def get_ticket(ticket_id: str, token: str = Depends(val_token)):
    if token[0] is True:
        payload = token[1]
        if payload['role'] == 'customer':
            details = customers_collection.find_one({'email': payload['email']})
        elif payload['role'] == 'partner':
            details = member_collections.find_one({'email': payload['email']})
        elif payload['role'] in ['org-admin', 'admin']:
            details = user_collection.find_one({'email': payload['email']})
            payload['role'] = 'admin'

        ticket = await get_document_by_id_byrequester(ticket_id, str(details['_id']), payload['role'])

        if ticket is None:
            raise HTTPException(status_code=404, detail="Ticket not found")
        ticket["_id"] = str(ticket["_id"])  # Ensure _id is returned as a string
        return ticket  # Ticket(**ticket)
    else:
        raise HTTPException(status_code=401, detail=token[1])


# Get a ticket by ID
@ticket_router.get("/tickets/")
async def get_all_ticket(token: str = Depends(val_token)):
    if token[0] is True:
        payload = token[1]
        user = user_collection.find_one({'email': payload["email"]})

        if payload['role'] in ['org-admin', "admin"]:
            if user:
                ticket_cursor = ticket_collection.find()
                tickets = []

                for ticket in ticket_cursor:
                    # Convert ObjectId to string if necessary
                    ticket["_id"] = str(ticket["_id"])
                    tickets.append(ticket)

                return tickets
            else:
                raise HTTPException(status_code=401, detail="Invalid token")
        else:
            raise HTTPException(status_code=401, detail="User does not have access to view tickets")
    else:
        raise HTTPException(status_code=401, detail="Invalid token")


# @ticket_router.get("/tickets/{ticket_id}/initiate", response_model=Ticket)
# async def initiate_ticket(ticket_id: str, token: str = Depends(val_token)):
#     if token[0] is True:
#         payload = token[1]
#         if payload['role'] == 'customer':
#             details = customers_collection.find_one({'email': payload['email']})
#             sender_id = str(details['id'])
#         elif payload['role'] == 'partner':
#             details = member_collections.find_one({'email': payload['email']})
#             sender_id  = str(details['id'])
#         elif payload['role'] in ['org-admin', 'admin']:
#             details = user_collection.find_one({'email': payload['email']})
#             payload['role'] = 'admin'
#             sender_id  = str(details['id'])
#
#
#         ticket = await get_document_by_id_byrequester(ticket_id, str(details['_id']), payload['role'])
#         if  payload['role'] in ['admin', 'org-admin']:
#             receiver_id = ticket['customer']
#         elif payload['role'] =='partner':
#             receiver_id = ticket['customer']
#         elif payload['role'] == 'customer':
#             if
#
#         result = ticket_collection.update_one(
#             {'_id': ObjectId(ticket_id)},
#             {'$set': {"response":{"user":payload['name'], "user_id": sender_id, "customer":ticket['Custome_name']}}}
#         )
#         if ticket is None:
#             raise HTTPException(status_code=404, detail="Ticket not found")
#         ticket["_id"] = str(ticket["_id"])  # Ensure _id is returned as a string
#         return ticket  # Ticket(**ticket)

# Create a chat message for a ticket
@ticket_router.post("/tickets/{ticket_id}/messages", response_model=ChatMessage)
async def create_chat_message(
        ticket_id: str,
        content: str = Form(...),
        token: str = Depends(val_token),
        files:  List[UploadFile] = File([])
):
    message_doc = {'content': content}
    # message_doc = message.dict()
    if token[0] is True:
        payload = token[1]
        if payload['role'] == 'customer':
            details = customers_collection.find_one({'email': payload['email']})
            message_doc['sender_id'] = str(details['_id'])
            message_doc['sender_name'] = details['name']
            message_doc['role'] = payload['role']
        elif payload['role'] == 'partner':
            details = member_collections.find_one({'email': payload['email']})
            message_doc['sender_name'] = details['name']
            message_doc['sender_id'] = str(details['_id'])
            message_doc['role'] = payload['role']
        elif payload['role'] in ['org-admin', 'admin']:
            details = user_collection.find_one({'email': payload['email']})
            payload['role'] = 'admin'
            message_doc['role'] = 'admin'
            message_doc['sender_name'] = details['name']
            message_doc['sender_id'] = str(details['_id'])

        ticket = await get_document_by_id_byrequester(ticket_id, str(details['_id']), payload['role'])
        if ticket is None:
            raise HTTPException(status_code=404, detail="Ticket not found")
        message_doc['ticket_id'] = ticket_id
        message_doc["created_at"] = datetime.utcnow()

        # Handle file upload
        print("files", files)
        if files:
            message_doc['files'] = []
            for file in files:
                file_data = await file.read()
                file_id = database.store_file(file_data, file.filename)
                message_doc['files'].append({'file_id': str(file_id), 'file_name': file.filename})

        else:
            message_doc['files'] = []

        result = chat_messages_collections.insert_one(message_doc)
        ticket_collection.update_one(
            {'_id': ObjectId(ticket_id)},
            {'$set': { "current_status": payload['role']+"-responded" ,"last_message": {"role":payload['role'] ,"name":details['name'], "id":str(details['_id']) }}}
        )
        message_doc["_id"] = str(result.inserted_id)  # Convert ObjectId to string for response
        return ChatMessage(**message_doc)
    else:
        raise HTTPException(status_code=401, detail=token[1])


async def get_documents_by_filter(filter):
    cursor = chat_messages_collections.find(filter)
    documents = list(cursor)
    for doc in documents:
        doc["_id"] = str(doc["_id"])  # Convert ObjectId to string
    return documents


# Get chat messages for a ticket
# @ticket_router.get("/tickets/{ticket_id}/messages", response_model=List[ChatMessage])
# async def get_chat_messages(ticket_id: str):
#     ticket = await get_document_by_id(ticket_id)
#     if ticket is None:
#         raise HTTPException(status_code=404, detail="Ticket not found")
#
#     messages = await get_documents_by_filter({"ticket_id": ticket_id})
#     return [ChatMessage(**message) for message in messages]

@ticket_router.get("/files/{file_id}")
async def get_file(file_id: str, token: str = Depends(val_token)):
    if token[0] is True:
        file = database.get_file(file_id)
        if file is None:
            raise HTTPException(status_code=404, detail="File not found")

        response = StreamingResponse(file, media_type="application/octet-stream")
        response.headers["Content-Disposition"] = f"attachment; filename={file.filename}"
        return response
    else:
        raise HTTPException(status_code=401, detail=token[1])


@ticket_router.get("/tickets/{ticket_id}/messages")#, response_model=List[ChatMessage])
async def get_chat_messages(ticket_id: str, token: str = Depends(val_token)):
    if not token[0]:
        raise HTTPException(status_code=401, detail=token[1])
    if token[0] is True:
        payload = token[1]

        role_to_collection = {
            'customer': customers_collection,
            'partner': member_collections,
            'org-admin': user_collection,
            'admin': user_collection
        }

        collection = role_to_collection.get(payload['role'])

        if collection is None:
            raise HTTPException(status_code=403, detail="Unauthorized role")

        details = collection.find_one({'email': payload['email']})

        if details is None:
            raise HTTPException(status_code=404, detail="User not found")

        # Adjust the role for admin users
        if payload['role'] in ['org-admin', 'admin']:
            payload['role'] = 'admin'

        ticket = await get_document_by_id(ticket_id)
        if ticket is None:
            raise HTTPException(status_code=404, detail="Ticket not found")
        messages = await get_documents_by_filter({"ticket_id": ticket_id})
        # return messages
        chat_messages = []
        # Process and modify messages
        for message in messages:
            chat_message_data = {
                '_id': message['_id'],
                'ticket_id': message['ticket_id'],
                'content': message['content'],
                'created_at': message['created_at'],
                'role': message['role'],
                'receiver_id': str(message['sender_id']) if message['sender_id'] != str(details['_id']) else None,
                'receiver_name': str(message['sender_name']) if message['sender_id'] != str(details['_id']) else None,
                'sender_id': str(message['sender_id']) if message['sender_id'] == str(details['_id']) else None,
                'sender_name': str(message['sender_name']) if message['sender_id'] == str(details['_id']) else None,
                'files':  message.get('files', None)
            # 'files': message['files'] if message['files'] in message else None,
            }
            # Filter out None values explicitly

            filtered_chat_message = {k: v for k, v in chat_message_data.items() if v is not None}
            chat_messages.append(filtered_chat_message)
        # response_data = [msg.dict(exclude_none=True) for msg in chat_messages]

        return chat_messages
        # return ChatMessage
    else:
        raise HTTPException(status_code=401, detail=token[1])


@ticket_router.post("/tickets/{ticket_id}/close", response_model=CloseTicket)
async def close_chat_message(ticket_id: str, message: ChatMessageCreate, token: str = Depends(val_token)):
    message_doc = message.dict()
    print(token)
    if token[0] is True:
        payload = token[1]
        if payload['role'] == 'customer':
            details = customers_collection.find_one({'email': payload['email']})
        elif payload['role'] == 'partner':
            details = member_collections.find_one({'email': payload['email']})
            message_doc['sender_name'] = details['name']
        elif payload['role'] in ['org-admin', 'admin']:
            details = user_collection.find_one({'email': payload['email']})
            payload['role'] = 'admin'

        ticket = await get_document_by_id_byrequester(ticket_id, str(details['_id']), payload['role'])
        # ticket = await get_document_by_id(ticket_id)
        if ticket is None:
            raise HTTPException(status_code=404, detail="Ticket not found")
        message_doc['ticket_id'] = ticket_id
        message_doc["created_at"] = datetime.utcnow()
        update_ticket_status = ticket_collection.update_one(
            {'_id': ObjectId(ticket_id)},
            {'$set': {"status": "closed", "current_status": "closed", "close_description": message_doc['content'],
                      "closed_by": str(details['_id']), "role": payload['role'], "resolved_date": datetime.now()}}
        )
        message_doc['close_description'] = message_doc['content']
        message_doc['closed_by'] = str(details['_id'])
        message_doc['role'] = payload['role']
        message_doc['status'] = "closed"
        message_doc['resolved_date'] = datetime.now()
        message_doc["_id"] = str(update_ticket_status.upserted_id)  # Convert ObjectId to string for response
        return CloseTicket(**message_doc)
    else:
        raise HTTPException(status_code=401, detail=token[1])


@ticket_router.get("/tickets/login/")
async def ticket_byloginuser(token: str = Depends(val_token)):
    if token[0] is True:
        payload = token[1]
        print(payload['role'], payload['email'])
        if payload['role'] == 'customer':
            details = customers_collection.find_one({'email': payload['email']})
        elif payload['role'] == 'partner':
            details = member_collections.find_one({'email': payload['email']})
        elif payload['role'] in ['org-admin', 'admin']:
            details = user_collection.find_one({'email': payload['email']})
            print(details)
            payload['role'] = 'admin'
        print(details['_id'])
        ticket_cursor = ticket_collection.find({payload['role']: str(details['_id'])})
        tickets = []
        print(ticket_cursor)
        for ticket in ticket_cursor:
            # Convert ObjectId to string if necessary
            ticket["_id"] = str(ticket["_id"])
            tickets.append(ticket)

        return tickets
    else:
        raise HTTPException(status_code=401, detail="Invalid token")


@ticket_router.get("/tickets/{role}/{id}")
async def get_all_ticket_role(role, userid, token: str = Depends(val_token)):
    details = 0
    if token[0] is True:
        payload = token[1]
        user = user_collection.find_one({'email': payload["email"]})

        if payload['role'] in ['org-admin', "admin"]:
            if user:
                if role == 'customer':
                    details = customers_collection.find_one({'_id': ObjectId(userid)})
                elif role == 'partner':
                    details = member_collections.find_one({'_id': ObjectId(userid)})
                elif role in ['org-admin', 'admin']:
                    details = user_collection.find_one({'_id': ObjectId(userid)})
                    role = 'admin'
                ticket_cursor = ticket_collection.find({role: str(details['_id'])})
                tickets = []
                print(ticket_cursor)
                for ticket in ticket_cursor:
                    # Convert ObjectId to string if necessary
                    ticket["_id"] = str(ticket["_id"])
                    tickets.append(ticket)

                return tickets
            else:
                raise HTTPException(status_code=401, detail="Invalid token")

        else:
            raise HTTPException(status_code=401, detail="User does not have access to view tickets")
    else:
        raise HTTPException(status_code=401, detail="Invalid token")
