from fastapi import HTTPException, status, APIRouter, Request, Cookie, Depends
from pkg.routes.members.members_models import *
from pkg.database.database import database
from pkg.routes.authentication import val_token
from pkg.routes.emails import Email
members_router = APIRouter()
members_collection = database.get_collection('members')
user_collection = database.get_collection('users')
request_collection = database.get_collection('pt_req_log')

@members_router.post("/partner/register")
async def create_member(member: Members, token: str = Depends(val_token)):
    if token[0] is True:
        details = member.dict()
        member = members_collection.find_one({'email': details["email"]})
        if member:
            raise HTTPException(status_code=409, detail=f"Partner {member['name']} Exists with Email {member['email']}")
        search_criteria = {"email": token[1]['email'], "members": {
            "$elemMatch": {
                "member_name": details['name']
            }
        }}
        # Find documents matching the search criteria
        cursor = user_collection.find(search_criteria)
        # Iterate over the results
        document_list = []
        for document in cursor:
            document_list.append(document)
        if document_list:
            raise HTTPException(status_code=409, detail=f"Partner {member['name']} Exists with Email {member['email']}")
        else:
            find_user = user_collection.find_one({'email': token[1]['email']})
            result = members_collection.insert_one(details)
            if result.inserted_id:
                update_user = user_collection.update_one({'email': token[1]['email']}, {
                    '$push': {'members': {'member_id': result.inserted_id, 'member_name': details['name']}}},
                                                         upsert=True)

                if update_user:
                    update_business_users = members_collection.update_one({'_id': ObjectId(result.inserted_id)}, {
                        '$push': {'User_ids': find_user['_id']}
                    }, upsert=True)
                    return {"status": f"Partner- {details['name']} added"}
            else:
                raise HTTPException(status_code=500, detail="Failed to insert data")

    else:
        raise HTTPException(status_code=401, detail=token)


@members_router.post("/edit/request")
async def edit_request(requestmodel : RequestModel):
    request_details = requestmodel.dict()
    member = members_collection.find_one({'_id': ObjectId(requestmodel.partner_id)})
    if member:
        request_details['User_ids'] = member['User_ids']
        result = members_collection.insert_one(request_details)
        if result:
            for users in member['User_ids']:
                users_detail = user_collection.find_one({'_id': ObjectId(users)})
                email_body = {'name': member['name'], 'fields': request_details['request_fields']}
                await Email('Profile Edit Request', users_detail['email'], 'edit_request',email_body ).send_email()
            return {'status': 'success', 'message': 'Request sent successfully'}
        else:
            raise HTTPException(status_code=500, detail="Failed to insert data")
    else:
        raise HTTPException(status_code=404, detail="Partner Not Found")


@members_router.post("/edit/partner")
async def edit_member(member: Members, token: str = Depends(val_token)):
    if token[0] is True:
        user = user_collection.find_one({'email': payload["email"]})
        if user['role'] in ['org-admin','admin']:
            details = member.dict()
            # members_collection = database.get_collection('members')
            member = members_collection.find_one({'email': details["email"]})
            details['updated_time'] = datetime.utcnow()
            if member:
                if member['role'] == 'admin' or member['role'] == 'user':
                    result = members_collection.update_one({"_id": member["_id"]}, {"$set": details})
                    if result:
                        return {"message": "Partner updated successfully"}
                    else:
                        raise HTTPException(status_code=500, detail="Failed to insert data")
                else:
                    raise HTTPException(status_code=401, detail='User does not have permission to update')
            else:
                raise HTTPException(status_code=409, detail=f"{member['email']} does not  Exists")
        else:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail='No permission to Edit User')
    else:
        raise HTTPException(status_code=401, detail=token)
