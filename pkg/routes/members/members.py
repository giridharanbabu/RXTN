import uuid

from fastapi import HTTPException, status, APIRouter, Request, Cookie, Depends, Response
from pkg.routes.customer.customer_models import VerifyOtpRequest, ForgotPasswordRequest
from pkg.routes.members.members_models import *
from pkg.routes.serializers.userSerializers import customerEntity
from pkg.routes.user_registration import user_utils
from pkg.routes.customer.customer_utils import generate_temp_password, hash_password, generate_html_message, \
    verify_password
from pkg.database.database import database
from pkg.routes.authentication import val_token, generate_otp_token
from pkg.routes.emails import Email
from random import randbytes
import hashlib, base64
from config.config import settings
from pkg.routes.user_registration.user_utils import generate_otp

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
        while True:
            partner_user_id = str(uuid.uuid4())
            if not members_collection.find_one({'partner_user_id': partner_user_id}):
                payload.partner_user_id = partner_user_id
                break
        # Compare password and passwordConfirm
        if payload.password != payload.passwordConfirm:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail='Passwords do not match')
        #  Hash the password
        payload.password = hash_password(payload.password)
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
                             "updated_at": datetime.utcnow(), "status": "pending"}})
                token = generate_otp_token(payload,hotp_v.at(0) )
                message =f"https://rxtn.onrender.com/members/verifyemail/{token}"
                await Email(message, payload.email, 'verification').send_email()
            except Exception as error:
                members_collection.find_one_and_update({"_id": result.inserted_id}, {
                    "$set": {"verification_code": None, "updated_at": datetime.utcnow()}, "status": "pending"})
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
        details['status'] = "approved"
        while True:
            partner_user_id = str(uuid.uuid4())
            test = members_collection.find_one({'partner_user_id': partner_user_id})
            print(test)
            if not members_collection.find_one({'partner_user_id': partner_user_id}):
                details['partner_user_id'] = partner_user_id
                break
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


#
# @members_router.post("/edit/request")
# async def edit_request(requestmodel: RequestModel):
#     request_details = requestmodel.dict()
#     member = members_collection.find_one({'_id': ObjectId(requestmodel.partner_id)})
#     if member:
#         request_details['User_ids'] = member['User_ids']
#         result = members_collection.insert_one(request_details)
#         if result:
#             for users in member['User_ids']:
#                 users_detail = user_collection.find_one({'_id': ObjectId(users)})
#                 email_body = {'name': member['name'], 'fields': request_details['request_fields']}
#                 await Email('Profile Edit Request', users_detail['email'], 'edit_request', email_body).send_email()
#             return {'status': 'success', 'message': 'Request sent successfully'}
#         else:
#             raise HTTPException(status_code=500, detail="Failed to insert data")
#     else:
#         raise HTTPException(status_code=404, detail="Partner Not Found")


#
# @members_router.post("/edit/partner")
# async def edit_member(member: Members, token: str = Depends(val_token)):
#     if token[0] is True:
#         payload = token[1]
#         user = user_collection.find_one({'email': payload["email"]})
#         print(user['role'])
#         if user['role'] in ['org-admin', 'admin']:
#             details = member.dict()
#             # members_collection = database.get_collection('members')
#             member = members_collection.find_one({'email': details["email"]})
#             details['updated_time'] = datetime.utcnow()
#             if member:
#                 # if member['role'] == 'admin' or member['role'] == 'user':
#                 result = members_collection.update_one({"_id": member["_id"]}, {"$set": details})
#                 if result:
#                     return {"message": "Partner updated successfully"}
#                 else:
#                     raise HTTPException(status_code=500, detail="Failed to insert data")
#                 # else:
#                 #     raise HTTPException(status_code=401, detail='User does not have permission to update')
#             else:
#                 raise HTTPException(status_code=409, detail=f"{member['email']} does not  Exists")
#         else:
#             raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
#                                 detail='No permission to Edit User')
#     else:
#         raise HTTPException(status_code=401, detail=token)


@members_router.post("/edit/partner")
async def update_partner(member: Members, token: str = Depends(val_token)):
    if token[0] is True:
        payload = token[1]
        edit_members = member.dict(exclude_none=True)
        # if payload['role'] in ['org-admin', 'admin']:
        member = members_collection.find_one({'email': edit_members["email"]})
        if member:
            edit_members['updated_at'] = datetime.utcnow()
            edit_members.pop('role')
            result = members_collection.update_one({"_id": member["_id"]}, {"$set": edit_members})
            if result:
                return {"message": "Partner updated successfully"}
            elif result.modified_count == 0:
                raise HTTPException(status_code=500, detail="Failed to apply changes.")
            else:
                raise HTTPException(status_code=400,
                                    detail=f"Customer {edit_members['email']} -Unable to update information")
        # else:
        #     member = members_collection.find_one({'email': edit_members["email"]})
        #     print(member)
        #     edit_members.pop('role')
        #     if member:
        #         edit_members['pending_changes'] = {
        #             **edit_members,
        #             'updated_at': datetime.utcnow()
        #         }
        #         result = members_collection.update_one(
        #             {'_id': member['_id']},
        #             {'$set': {'pending_changes': edit_members['pending_changes']}}
        #         )
        #
        #         if result.modified_count == 0:
        #             raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
        #                                 detail=f'Unable to queue update for this customer.')
        #
        #         # Notify admin about pending changes
        #         customer_request = {'name': member['email'], 'fields': str(edit_members['pending_changes'])}
        #         edit_members['pending_changes'].pop('updated_at')
        #         message = generate_html_message(edit_members['pending_changes'])
        #         print(message)
        #         admin_email = "giri1208srinivas@gmail.com"
        #         subject = f"Approval Required: Changes to Customer {member['email']}"
        #         body = f"Pending changes for customer:\n\n{edit_members['pending_changes']}"
        #
        #         await Email(subject, admin_email, 'customer_request', message).send_email()
        #         return {'status': f'Partner update queued for approval - {member["name"]}'}

        else:
            raise HTTPException(status_code=404, detail=f"Partner {edit_members['email']} does not exist")

    else:
        raise HTTPException(status_code=401, detail=token)


@members_router.post("/admin/approve/{partner_id}")
async def approve_partner(partner_id: str, approval: AdminApprovalRequest, token: str = Depends(val_token)):
    if not ObjectId.is_valid(partner_id):
        raise HTTPException(status_code=400, detail="Invalid customer ID")
    if token[0] is True:
        payload = token[1]
        user = user_collection.find_one({'email': payload["email"]})
        if user['role'] in ['org-admin', "admin"]:
            member = members_collection.find_one({'_id': ObjectId(partner_id)})
            if not member:
                raise HTTPException(status_code=404, detail="Customer not found")

            if approval.status:
                # Apply the changes
                result = members_collection.update_one(
                    {'_id': ObjectId(partner_id)},
                    {'$set': {"status": approval.status}}
                )
                if result.modified_count == 0:
                    raise HTTPException(status_code=500, detail="Failed to apply changes.")
                message = "Changes approved and applied successfully."
            else:
                message = {"unable to get approval status"}
            return {'message': message}
        else:
            raise HTTPException(status_code=401, detail="User does not have access to approve Partner")
    else:
        raise HTTPException(status_code=401, detail="Invalid token")
        #
# @members_router.post("/admin/approve/{partner_id}")
# async def approve_customer_edit(customer_id: str, approval: AdminApprovalRequest):
#     if not ObjectId.is_valid(customer_id):
#         raise HTTPException(status_code=400, detail="Invalid customer ID")
#
#     customer = members_collection.find_one({'_id': ObjectId(customer_id)})
#     if not customer:
#         raise HTTPException(status_code=404, detail="Customer not found")
#
#     pending_changes = customer.get('pending_changes')
#     if not pending_changes:
#         raise HTTPException(status_code=404, detail="No pending changes found")
#
#     if approval.approve:
#         # Apply the changes
#         result = members_collection.update_one(
#             {'_id': ObjectId(customer_id)},
#             {'$set': pending_changes, '$unset': {'pending_changes': ""}}
#         )
#         if result.modified_count == 0:
#             raise HTTPException(status_code=500, detail="Failed to apply changes.")
#         message = "Changes approved and applied successfully."
#     else:
#         # Discard the changes
#         result = members_collection.update_one(
#             {'_id': ObjectId(customer_id)},
#             {'$unset': {'pending_changes': ""}}
#         )
#         if result.modified_count == 0:
#             raise HTTPException(status_code=500, detail="Failed to discard changes.")
#         message = "Changes rejected and discarded."
#
#     return {'message': message}


# Utility function to convert _id to string
def parse_object_id(document):
    """Convert the '_id' field to a string."""
    if '_id' in document:
        document['id'] = str(document['_id'])
        del document['_id']
    return document


# List partners route
@members_router.get("/partners", response_model=List[MembersResponse])
async def list_partners(token: str = Depends(val_token)):
    if token[0] is True:
        payload = token[1]
        user = user_collection.find_one({'email': payload["email"]})
        partners = []
        if payload['role'] in ['org-admin', "admin"]:
            if user:
                cursor = members_collection.find()

                partners = [parse_object_id(doc) for doc in cursor]

                # if 'partner_user_id' not in partner:
                #     partner['partner_user_id'] = None
                # partners.append(MembersResponse(
                #     id=str(partner['_id']),
                #     name=partner['name'],
                #     email=partner['email'],
                #     role=partner['role'],
                #     created_at=partner['created_at'],
                #     partner_user_id=partner['partner_user_id']
                # ))
                return partners
            else:
                raise HTTPException(status_code=401, detail="Invalid token")
        else:
            raise HTTPException(status_code=401, detail="User does not have access to view Partner")
    else:
        raise HTTPException(status_code=401, detail="Invalid token")


# Routes
@members_router.post("/member/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    member = members_collection.find_one({"email": request.email})

    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")

    otp = generate_otp()
    otp_expiration = datetime.now() + timedelta(minutes=10)  # OTP valid for 10 minutes
    members_collection.update_one(
        {"_id": member["_id"]},
        {"$set": {"otp": otp, "otp_expires_at": otp_expiration}}
    )
    email_subject = "Password Reset OTP"
    email_body = f"Your OTP for password reset is: <b>{otp}</b>. It is valid for 10 minutes."
    await Email(otp['reset_otp'], request.email, 'reset', email_body).send_email()
    return {"message": "OTP sent to your email"}


@members_router.post("/member/verify-otp")
async def verify_otp(request: VerifyOtpRequest):
    member = members_collection.find_one({"email": request.email})

    if not member:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Member not found")
    if member["otp"]['reset_otp'] != request.otp or member["otp_expires_at"] < datetime.now():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")
    new_hashed_password = hash_password(request.new_password)
    members_collection.update_one(
        {"_id": member["_id"]},
        {"$set": {"password": new_hashed_password}, "$unset": {"otp": "", "otp_expires_at": ""}}
    )
    return {"message": "Password reset successfully"}


@members_router.post('/member/login')
async def login(payload: LoginMemberSchema, response: Response):
    # Check if the user exist

    db_user = members_collection.find_one({'email': payload.email.lower()})
    print(db_user)
    if not db_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail='User does not Registered')
    if db_user['status'] == 'approved':
        user = customerEntity(db_user)
        print(user)
        ACCESS_TOKEN_EXPIRES_IN = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        REFRESH_TOKEN_EXPIRES_IN = settings.ACCESS_TOKEN_EXPIRE_MINUTES
        # Check if user verified his email
        if not user['verified']:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail='Please verify your email address')

        if not verify_password(payload.password, user['password']):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                detail='Incorrect Email or Password')

        # Create access token
        access_token = user_utils.create_access_token(user['email'], user['name'], 'Customer')
        # Create refresh token
        refresh_token = user_utils.create_refresh_token(user['email'], user['name'], 'Customer')

        # Store refresh and access tokens in cookie
        response.set_cookie('rxtn_member_token', access_token, ACCESS_TOKEN_EXPIRES_IN,
                            ACCESS_TOKEN_EXPIRES_IN, '/', None, True, True, 'none')
        response.set_cookie('refresh_token', refresh_token,
                            REFRESH_TOKEN_EXPIRES_IN * 60, REFRESH_TOKEN_EXPIRES_IN * 60, '/', None, True, True, 'none')
        response.set_cookie('logged_in', 'True', ACCESS_TOKEN_EXPIRES_IN * 60,
                            ACCESS_TOKEN_EXPIRES_IN * 60, '/', None, True, False, 'none')

        # Send both access
        return {'status': 'success', 'user': user['name'], 'access_token': access_token}
    else:
        raise HTTPException(status_code=401,
                            detail='User does not approved or disabled user')


@members_router.post("/member/logout")
def logout(response: Response):
    # Clear the access token
    response.set_cookie(
        key="rxtn_member_token",
        value="",
        max_age=0,
        expires=0,
        path="/",
        domain=None,
        secure=True,  # Set to False for development over HTTP
        httponly=True,
        samesite="none"
    )

    # Clear the refresh token
    response.set_cookie(
        key="refresh_token",
        value="",
        max_age=0,
        expires=0,
        path="/",
        domain=None,
        secure=True,  # Set to False for development over HTTP
        httponly=True,
        samesite="none"
    )

    # Clear the logged_in indicator
    response.set_cookie(
        key="logged_in",
        value="",
        max_age=0,
        expires=0,
        path="/",
        domain=None,
        secure=True,  # Can be False if the logged_in cookie isn't critical
        httponly=False,  # Allow JavaScript access if needed
        samesite="none"
    )

    return {"message": "Logged out successfully"}
