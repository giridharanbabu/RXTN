import base64
import hashlib
import json
from datetime import datetime, timedelta
from random import randbytes
from bson import json_util
from fastapi import HTTPException, status, APIRouter, Request, Depends, Response
from jose import jwt
from pkg.routes.user_registration.user_models import CreateUserSchema, LoginUserSchema, PasswordResetRequest, \
    UserReponse
from pkg.database.database import database
from pkg.routes.authentication import val_token, verify_otp
from pkg.routes.user_registration import user_utils
from pkg.routes.emails import Email
from pkg.routes.user_registration.user_utils import generate_otp
from pkg.routes.serializers.userSerializers import userEntity
from config.config import settings

user_router = APIRouter()
user_collection = database.get_collection('users')
user_collection.create_index("expireAt", expireAfterSeconds=10)


@user_router.post("/user/register")
async def create_user(payload: CreateUserSchema):
    # Check if user already exist
    if payload.role in ['org-admin', 'admin', 'partner']:
        find_user = user_collection.find_one({'email': payload.email.lower()})
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
            result = user_collection.insert_one(payload.dict())
            new_user = user_collection.find_one({'_id': result.inserted_id})
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
                    user_collection.find_one_and_update({"_id": result.inserted_id}, {
                        "$set": {"verification_code": hotp_v.at(0),
                                 "Verification_expireAt": datetime.utcnow() + timedelta(
                                     minutes=settings.EMAIL_EXPIRATION_TIME_MIN),
                                 "updated_at": datetime.utcnow()}})
                    await Email(hotp_v.at(0), payload.email, 'verification').send_email()
                except Exception as error:
                    user_collection.find_one_and_update({"_id": result.inserted_id}, {
                        "$set": {"verification_code": None, "updated_at": datetime.utcnow()}})
                    raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                        detail='There was an error sending email')
                return {'status': 'success', 'message': 'Verification token successfully sent to your email'}
            else:
                raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                                    detail='There was an error registering user')
    else:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail='No permission to create User')


@user_router.post('/user/login')
async def login(payload: LoginUserSchema, response: Response):
    # Check if the user exist
    db_user = user_collection.find_one({'email': payload.email.lower()})
    if not db_user:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail='Incorrect Email or Password')
    user = userEntity(db_user)
    ACCESS_TOKEN_EXPIRES_IN = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    REFRESH_TOKEN_EXPIRES_IN = settings.ACCESS_TOKEN_EXPIRE_MINUTES
    # Check if user verified his email
    if not user['verified']:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                            detail='Please verify your email address')

    # Check if the password is valid
    if not user_utils.verify_password(payload.password, user['password']):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                            detail='Incorrect Email or Password')

    # Create access token
    access_token = user_utils.create_refresh_token(user['email'], user['name'], user['role'])

    # Create refresh token
    refresh_token = user_utils.create_access_token(user['email'], user['name'], user['role'])

    # Store refresh and access tokens in cookie
    response.set_cookie('access_token', access_token, ACCESS_TOKEN_EXPIRES_IN * 60,
                        ACCESS_TOKEN_EXPIRES_IN * 60, '/', None, True, True, 'none')
    response.set_cookie('refresh_token', refresh_token,
                        REFRESH_TOKEN_EXPIRES_IN * 60, REFRESH_TOKEN_EXPIRES_IN * 60, '/', None, False, True, 'lax')
    response.set_cookie('logged_in', 'True', ACCESS_TOKEN_EXPIRES_IN * 60,
                        ACCESS_TOKEN_EXPIRES_IN * 60, '/', None, False, False, 'lax')

    # Send both access
    return {'status': 'success', 'access_token': access_token}


@user_router.get("/user/me")
async def user_login(request: Request):
    """login session"""
    access_token = request.cookies.get("access_token")
    if access_token is None:
        raise HTTPException(status_code=400, detail="Token not found in cookies")
    else:
        payload = jwt.decode(access_token, settings.SECRET, algorithms=[settings.ALGORITHM])
        return payload


@user_router.post("/edit/users")
async def update_user(new_data: dict, token: str = Depends(val_token)):
    if token[0] is True:
        payload = token[1]

        user = user_collection.find_one({'email': payload["email"]})
        if user['role'] == ['org-admin', "admin"]:
            if user:
                # Update the user data in MongoDB
                result = user_collection.update_one({"_id": user["_id"]}, {"$set": new_data})
                print(result)
            # Check if the user is found and updated
            else:
                raise HTTPException(status_code=404, detail="User not found")

            return {"message": "User updated successfully"}

        else:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED,
                                detail='No permission to Edit User')
    else:
        raise HTTPException(status_code=401, detail="Does not have Permission to Edit")


@user_router.post("/request-reset-password/")
async def request_reset_password(request: PasswordResetRequest):
    user = user_collection.find_one({'email': request.email})
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    reset_otp = generate_otp()
    # In a real application, send the reset password email asynchronously
    try:
        await Email(reset_otp['reset_otp'], request.email, 'reset').send_email()

    except Exception as error:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                            detail='There was an error sending email')
    user_collection.update_one({"_id": user["_id"]}, {"$set": reset_otp})
    return {"message": "Password reset email sent"}


@user_router.post("/reset-password/")
async def reset_password(new_password, otp: str = Depends(verify_otp)):
    if otp[0] is True:
        payload = otp[1]
        user = user_collection.find_one({'email': payload["email"]})
        if user:
            # Update the user data in MongoDB
            new_password = user_utils.hash_password(new_password)
            print(new_password)
            result = user_collection.update_one({"_id": user["_id"]},
                                                {"$set": {"password": new_password, "updated_at": datetime.utcnow()}})
            if result:
                return {"message": "Password reset successfully"}
            else:
                raise HTTPException(status_code=501, detail="Unable to update password")

        else:
            raise HTTPException(status_code=404, detail="User not found")
    else:
        raise HTTPException(status_code=401, detail=token)


@user_router.get("/user/info", response_model=UserReponse)
async def update_user(token: str = Depends(val_token)):
    if token[0] is True:
        payload = token[1]
        user = user_collection.find_one({'email': payload["email"]})
        members_count = 0
        business_count = 0
        if user:
            if 'members' in user:
                members_count = len(user['members'])
            user['members_count'] = members_count
            user['created_at'] = str(user['created_at'])
            return json.loads(json_util.dumps(user))
        # Check if the user is found and updated
        else:
            raise HTTPException(status_code=404, detail="User not found")

    else:
        raise HTTPException(status_code=401, detail=token)


@user_router.post("/user/logout")
def logout(response: Response):
    # Clear the access token
    response.set_cookie(
        key="access_token",
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
