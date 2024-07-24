import json
import bson
import jwt
from bson import json_util
from fastapi import HTTPException, status, APIRouter, Depends, Response, Request
from config.config import settings
from pkg.routes.customer.customer_models import *
from pkg.database.database import database
from pkg.routes.authentication import val_token
from pkg.routes.customer.customer_utils import generate_temp_password, hash_password, verify_password
from pkg.routes.emails import Email
from pkg.routes.members.members import members_collection
from pkg.routes.user_registration import user_utils
from pkg.routes.serializers.userSerializers import customerEntity
from pkg.routes.user_registration.user_utils import generate_otp

customer_router = APIRouter()
customers_collection = database.get_collection('customers')
user_collection = database.get_collection('users')
member_collections = database.get_collection('partners')


@customer_router.post("/customer/cp/register/")
def existing_customer(details):
    details = json.loads(details)
    result = customers_collection.insert_one(details)
    if result.inserted_id:
        return {"status": f"New Customer- {details['name']} added",
                'message': 'Temporary password successfully sent to your email'}
    else:
        raise HTTPException(status_code=500, detail="Failed to insert data")


async def customer_register(details):
    # partners = []
    # partner_details = None
    if 'partner_id' not in details:
        details['partner_id'] = []
    # Ensure 'partner_id' is present in details and is a non-empty string
    # if 'partner_id' in details and details['partner_id']:
    #     print(len(details['partner_id']))  # This line might raise an error if partner_id is not a string
    #     for partners in details['partner_id']:
    #         partner_details = member_collections.find_one({"_id": ObjectId(partners)})
    #         details['partner_id'] = [partner_details['_id']]
    #         details['User_ids'] = partner_details.get('User_ids', [])
    #         if not partner_details:
    #             raise HTTPException(status_code=404, detail=f"Invalid Partner Id {details['partner_id']}")
    # else:
    #     # If 'partner_id' is not provided or is empty
    #     partner_details = partner_details
    details['role'] = "customer"
    # Generate and hash a temporary password
    temp_password = generate_temp_password()
    hashed_temp_password = hash_password(temp_password)
    details['password'] = hashed_temp_password

    # # Update details with partner information if available
    # if partner_details:
    #     details['partner_id'] = [partner_details['_id']]
    #     details['User_ids'] = partner_details.get('User_ids', [])

    # Insert details into the customers collection
    result = customers_collection.insert_one(details)

    # Send an email with the temporary password
    await Email(temp_password, details['email'], 'customer_register').send_email()

    if result.inserted_id:
        return {
            "status": f"New Customer - {details['name']} added",
            "message": "Temporary password successfully sent to your email"
        }
    else:
        raise HTTPException(status_code=500, detail="Failed to insert data")


@customer_router.post("/customer/register")
async def create_customer(customer: Customer):
    details = customer.dict()
    customer_collection = database.get_collection('customers')
    print(customer_collection)
    customer = customers_collection.find_one({'email': details["email"]})
    try:
        if customer:
            raise HTTPException(status_code=409, detail=f"Customer Email- {customer['email']} Exists")
        else:
            print("---")
            return await customer_register(details)
    except bson.errors.InvalidId:
        raise HTTPException(status_code=400, detail="Unable to update Customer details")


#
# @customer_router.post("/edit/customer")
# async def update_customer(edit_customer: EditCustomer, token: str = Depends(val_token)):
#     from pymongo import ReturnDocument
#     if token[0] is True:
#         edit_customer = edit_customer.dict(exclude_none=True)
#         customer_collection = database.get_collection('customers')
#         customer = customers_collection.find_one({'email': edit_customer["email"]})
#         if customer:
#             edit_customer['updated_at'] = datetime.utcnow()
#             result = customer_collection.find_one_and_update({'_id': customer['_id']}, {'$set': edit_customer},
#                                                              return_document=ReturnDocument.AFTER)
#
#             if not result:
#                 raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
#                                     detail=f'Unable to Update for this Customer - {result}')
#         else:
#             raise HTTPException(status_code=409, detail=f"Customer {customer['email']} does not Exists")
#
#     else:
#         raise HTTPException(status_code=401, detail=token)
#
#     return {'status': f'Updated Customer Successfully- {customer["name"]}'}


@customer_router.post('/customer/login')
async def login(payload: LoginCustomerSchema, response: Response):
    # Check if the user exist
    if payload.partner_id is None:
        db_user = customers_collection.find_one({'email': payload.email.lower()})
    else:
        db_user = customers_collection.find_one({'email': payload.email.lower(), 'partner_id': payload.partner_id})
    if not db_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail='User does not Registered')
    user = customerEntity(db_user)
    ACCESS_TOKEN_EXPIRES_IN = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    REFRESH_TOKEN_EXPIRES_IN = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    # Check if user verified his email

    if not verify_password(payload.password, user['password']):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail='Incorrect Email or Password')

    # Create access token
    access_token = user_utils.create_access_token(user['email'], user['name'], 'Customer')
    # Create refresh token
    refresh_token = user_utils.create_refresh_token(user['email'], user['name'], 'Customer')

    # Store refresh and access tokens in cookie
    response.set_cookie('rxtn_customer_token', access_token, ACCESS_TOKEN_EXPIRES_IN,
                        ACCESS_TOKEN_EXPIRES_IN, '/', None, True, True, 'none')
    response.set_cookie('refresh_token', refresh_token,
                        REFRESH_TOKEN_EXPIRES_IN * 60, REFRESH_TOKEN_EXPIRES_IN * 60, '/', None, True, True, 'none')
    response.set_cookie('logged_in', 'True', ACCESS_TOKEN_EXPIRES_IN * 60,
                        ACCESS_TOKEN_EXPIRES_IN * 60, '/', None, True, False, 'none')

    # Send both access
    return {'status': 'success', 'user': user['name'], 'access_token': access_token}


@customer_router.get("/customer/me")
async def user_login(request: Request):
    """login session"""
    access_token = request.cookies.get("rxtn_customer_token")
    if access_token is None:
        raise HTTPException(status_code=400, detail="Token not found in cookies")
    else:
        payload = jwt.decode(access_token, settings.SECRET, algorithms=[settings.ALGORITHM])
        return payload


# List partners route
@customer_router.get("/customers")
async def list_customers(token: str = Depends(val_token)):
    if token[0] is True:
        payload = token[1]
        user = user_collection.find_one({'email': payload["email"]})

        if payload['role'] in ['org-admin', "admin"]:
            if user:
                customers_cursor = customers_collection.find()
                customers = []

                for customer in customers_cursor:
                    # Convert ObjectId to string if necessary
                    customer["_id"] = str(customer["_id"])
                    if customer['partner_id']:
                        partner_information = member_collections.find_one({"_id": ObjectId(customer['partner_id'][0])})
                        if partner_information:
                            member = PartnerResponse(
                                id=str(customer['partner_id'][0]),
                                name=partner_information['name'],
                                email=partner_information['email'],
                                role=partner_information.get('role', ""),
                                phone = partner_information.get('partner_user_id', None)
                            )
                            customer['partner'] = member.dict()
                    customer.pop('password',None)
                    customer.pop('old_passwords',None)
                    customers.append(customer)

                return customers
            else:
                raise HTTPException(status_code=401, detail="Invalid token")
        else:
            raise HTTPException(status_code=401, detail="User does not have access to view Customer")
    else:
        raise HTTPException(status_code=401, detail="Invalid token")


@customer_router.get("/customer/info", response_model=CustomerResponse)
async def update_user(token: str = Depends(val_token)):
    if token[0] is True:
        print(token[1])
        payload = token[1]
        customer = customers_collection.find_one({'email': payload["email"]})
        print(customer)
        if customer:
            customer['id'] = str(customer['_id'])
            if customer['partner_id']:
                partner_information = member_collections.find_one({"_id": ObjectId(customer['partner_id'][0])})
                if partner_information:

                    member = PartnerResponse(
                        id=str(customer['partner_id'][0]),
                        name=partner_information['name'],
                        email=partner_information['email'],
                        role=partner_information.get('role', ""),
                        phone =partner_information.get('partner_user_id', None)
                    )
                    customer['partner'] = member.dict()
            customer['created_at'] = str(customer['created_at'])
            return json.loads(json_util.dumps(customer))
        # Check if the user is found and updated
        else:
            raise HTTPException(status_code=404, detail="Customer not found")

    else:
        raise HTTPException(status_code=401, detail=token)


def generate_html_message(changes: dict) -> str:
    html_message = "<ul>"
    for field, value in changes.items():
        html_message += f"<li><strong>{field.capitalize()}:</strong> {value}</li>"
    html_message += "</ul>"
    return html_message


@customer_router.post("/edit/customer")
async def update_customer(edit_customer: EditCustomer, token: str = Depends(val_token)):
    if token[0] is True:
        payload = token[1]
        customer_collection = database.get_collection('customers')
        edit_customer = edit_customer.dict(exclude_none=True)
        # if payload['role'] in ['org-admin', 'admin']:
        customer = customer_collection.find_one({'email': edit_customer["email"]})
        if customer:
            edit_customer['updated_at'] = datetime.utcnow()
            result = customer_collection.update_one({"_id": customer["_id"]}, {"$set": edit_customer})
            if result:
                return {"message": "- {customer['name']} updated successfully"}
        # else:
        #
        #     customer = customer_collection.find_one({'email': edit_customer["email"]})
        #     print(customer)
        #     if customer:
        #         result = customers_collection.update_one(
        #             {'_id': ObjectId(customer_id)},
        #             {'$set': pending_changes, '$unset': {'pending_changes': ""}}
        #         )
            elif result.modified_count == 0:
                raise HTTPException(status_code=500, detail="Failed to apply changes.")
            else:
                raise HTTPException(status_code=400, detail=f"Customer {edit_customer['email']} -Unable to update information")
                # message = "Changes approved and applied successfully."
                # edit_customer['pending_changes'] = {
                #     **edit_customer,
                #     'updated_at': datetime.utcnow()
                # }
                # result = customer_collection.update_one(
                #     {'_id': customer['_id']},
                #     {'$set': {'pending_changes': edit_customer['pending_changes']}}
                # )
                #
                # if result.modified_count == 0:
                #     raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                #                         detail=f'Unable to queue update for this customer.')
                #
                # # Notify admin about pending changes
                # customer_request = {'name': customer['email'], 'fields': str(edit_customer['pending_changes'])}
                # edit_customer['pending_changes'].pop('updated_at')
                # message = generate_html_message(edit_customer['pending_changes'])
                # print(message)
                # admin_email = "giri1208srinivas@gmail.com"
                # subject = f"Approval Required: Changes to Customer {customer['email']}"
                # body = f"Pending changes for customer:\n\n{edit_customer['pending_changes']}"
                # if customer['partner_id']:
                #     for partner in customer['partner_id']:
                #         member = members_collection.find_one({'_id': ObjectId(partner)})
                #         await Email(subject, member['email'], 'customer_request', message).send_email()
                #
                # await Email(subject, admin_email, 'customer_request', message).send_email()

        else:
            raise HTTPException(status_code=404, detail=f"Customer {edit_customer['email']} does not exist")

    else:
        raise HTTPException(status_code=401, detail=token)

    # return {'status': f'Customer update queued for approval - {customer["name"]}'}


# @customer_router.post("/admin/approve/{customer_id}")
# async def approve_customer_edit(customer_id: str, approval: AdminApprovalRequest):
#     if not ObjectId.is_valid(customer_id):
#         raise HTTPException(status_code=400, detail="Invalid customer ID")
#
#     customer = customers_collection.find_one({'_id': ObjectId(customer_id)})
#     if not customer:
#         raise HTTPException(status_code=404, detail="Customer not found")
#
#     pending_changes = customer.get('pending_changes')
#     if not pending_changes:
#         raise HTTPException(status_code=404, detail="No pending changes found")
#
#     if approval.approve:
#         # Apply the changes
#         result = customers_collection.update_one(
#             {'_id': ObjectId(customer_id)},
#             {'$set': pending_changes, '$unset': {'pending_changes': ""}}
#         )
#         if result.modified_count == 0:
#             raise HTTPException(status_code=500, detail="Failed to apply changes.")
#         message = "Changes approved and applied successfully."
#     else:
#         # Discard the changes
#         result = customers_collection.update_one(
#             {'_id': ObjectId(customer_id)},
#             {'$unset': {'pending_changes': ""}}
#         )
#         if result.modified_count == 0:
#             raise HTTPException(status_code=500, detail="Failed to discard changes.")
#         message = "Changes rejected and discarded."
#
#     return {'message': message}


# Password reset endpoint
@customer_router.post("/reset-password")
async def reset_password(request: PasswordResetRequest):
    # Find the customer by email
    customer = customers_collection.find_one({"email": request.email})

    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    # Verify the current password
    if not verify_password(request.current_password, customer["password"]):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid current password")

    # Hash the new password
    new_hashed_password = hash_password(request.new_password)

    # Update the customer's password and store the old one
    customers_collection.update_one(
        {"_id": customer["_id"]},
        {
            "$set": {"password": new_hashed_password},
            "$push": {
                "old_passwords": {
                    "password": customer["password"],
                    "expires_at": datetime.utcnow() + timedelta(days=30)
                }
            }
        }
    )

    return {"message": "Password reset successfully"}


# Routes
@customer_router.post("/forgot-password")
async def forgot_password(request: ForgotPasswordRequest):
    customer = customers_collection.find_one({"email": request.email})

    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")

    otp = generate_otp()
    otp_expiration = datetime.now() + timedelta(minutes=10)  # OTP valid for 10 minutes

    customers_collection.update_one(
        {"_id": customer["_id"]},
        {"$set": {"otp": otp, "otp_expires_at": otp_expiration}}
    )

    email_subject = "Password Reset OTP"
    email_body = f"Your OTP for password reset is: <b>{otp}</b>. It is valid for 10 minutes."

    await Email(otp['reset_otp'], request.email,'reset', email_body).send_email()

    return {"message": "OTP sent to your email"}


@customer_router.post("/verify-otp")
async def verify_otp(request: VerifyOtpRequest):
    customer = customers_collection.find_one({"email": request.email})

    if not customer:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Customer not found")
    if customer["otp"]['reset_otp'] != request.otp or customer["otp_expires_at"] < datetime.now():
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid or expired OTP")

    new_hashed_password = hash_password(request.new_password)

    customers_collection.update_one(
        {"_id": customer["_id"]},
        {"$set": {"password": new_hashed_password}, "$unset": {"otp": "", "otp_expires_at": ""}}
    )

    return {"message": "Password reset successfully"}


@customer_router.post("/customer/logout")
def logout(response: Response):
    # Clear the access token
    response.set_cookie(
        key="rxtn_customer_token",
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
