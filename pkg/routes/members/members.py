from fastapi import HTTPException, status, APIRouter, Request, Cookie, Depends
from pkg.routes.members.members_models import *
from pkg.routes.user_registration import user_utils
from pkg.routes.customer.customer_utils import generate_temp_password, hash_password
from pkg.database.database import database
from pkg.routes.authentication import val_token
from pkg.routes.emails import Email
from random import randbytes
import hashlib, base64
from config.config import settings

members_router = APIRouter()
members_collection = database.get_collection('partners')
user_collection = database.get_collection('users')
request_collection = database.get_collection('pt_req_log')


@members_router.post("/partner/signup")
async def create_user(payload: CreateMemberSchema):
    # Check if user already exist
    find_user = members_collection.find_one({'email': payload.email.lower()})
    if find_user:
        if find_user['verified'] is False:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail='User Not Verified,Please verify your email address')
        else:
            raise HTTPException(status_code=status.HTTP_409_CONFLICT,
                                detail='Account already exist')
    else:
        # Compare password and passwordConfirm
        if payload.password != payload.passwordConfirm:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Passwords do not match')
        #  Hash the password
        payload.password = user_utils.hash_password(payload.password)
        del payload.passwordConfirm
        payload.verified = False
        payload.email = payload.email.lower()
        payload.created_at = datetime.utcnow()
        payload.updated_at = payload.created_at
        result = members_collection.insert_one(payload.dict())
        new_user = members_collection.find_one({'_id': result.inserted_id})
        if new_user:
            try:
                token = randbytes(10)
                hashedCode = hashlib.sha256()
                hashedCode.update(token)
                verification_code = hashedCode.hexdigest()
                import pyotp
                secret = base64.b32encode(bytes(token.hex(), 'utf-8'))
                verification_code = base64.b32encode(bytes(verification_code, 'utf-8'))
                hotp_v = pyotp.HOTP(verification_code)
                members_collection.find_one_and_update({"_id": result.inserted_id}, {
                    "$set": {"verification_code": hotp_v.at(0),
                             "Verification_expireAt": datetime.utcnow() + timedelta(
                                 minutes=settings.EMAIL_EXPIRATION_TIME_MIN),
                             "updated_at": datetime.utcnow()}})
                await Email(hotp_v.at(0), payload.email, 'verification').send_email()
            except Exception as error:
                members_collection.find_one_and_update({"_id": result.inserted_id}, {
                    "$set": {"verification_code": None, "updated_at": datetime.utcnow()}})
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                    detail='There was an error sending email')
            return {'status': 'success', 'message': 'Verification token successfully sent to your email'}
        else:
            raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                detail='There was an error registering user')


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
        cursor = members_collection.find(search_criteria)
        temp_password = generate_temp_password()
        hashed_temp_password = hash_password(temp_password)
        details['password'] = hashed_temp_password
        details['verified'] = True
        # Iterate over the results
        document_list = []
        for document in cursor:
            document_list.append(document)
        if document_list:
            raise HTTPException(status_code=409, detail=f"Partner {member['name']} Exists with Email {member['email']}")
        else:
            find_user = user_collection.find_one({'email': token[1]['email']})
            result = members_collection.insert_one(details)
            await Email(temp_password, details['email'], 'customer_register').send_email()
            if result.inserted_id:
                update_user = user_collection.update_one({'email': token[1]['email']}, {
                    '$push': {'members': {'member_id': result.inserted_id, 'member_name': details['name']}}},
                                                         upsert=True)

                if update_user:
                    update_business_users = members_collection.update_one({'_id': ObjectId(result.inserted_id)}, {
                        '$push': {'User_ids': find_user['_id']}
                    }, upsert=True)
                    return {"status": f"Partner- {details['name']} added",
                        'message': 'Temporary password successfully sent to your email'}
            else:
                raise HTTPException(status_code=500, detail="Failed to insert data")

    else:
        raise HTTPException(status_code=401, detail=token)


@members_router.post("/edit/request")
async def edit_request(requestmodel: RequestModel):
    request_details = requestmodel.dict()
    member = members_collection.find_one({'_id': ObjectId(requestmodel.partner_id)})
    if member:
        request_details['User_ids'] = member['User_ids']
        result = members_collection.insert_one(request_details)
        if result:
            for users in member['User_ids']:
                users_detail = user_collection.find_one({'_id': ObjectId(users)})
                email_body = {'name': member['name'], 'fields': request_details['request_fields']}
                await Email('Profile Edit Request', users_detail['email'], 'edit_request', email_body).send_email()
            return {'status': 'success', 'message': 'Request sent successfully'}
        else:
            raise HTTPException(status_code=500, detail="Failed to insert data")
    else:
        raise HTTPException(status_code=404, detail="Partner Not Found")


@members_router.post("/edit/partner")
async def edit_member(member: Members, token: str = Depends(val_token)):
    if token[0] is True:
        user = user_collection.find_one({'email': payload["email"]})
        if user['role'] in ['org-admin', 'admin']:
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
