from datetime import datetime

from bson import ObjectId
from fastapi import FastAPI, HTTPException, Depends, APIRouter
from starlette import status

from pkg.database.database import database
from pkg.routes.authentication import val_token
from pkg.routes.emails import Email
from pkg.routes.mf_process.mf_model import MFRequest, MFAccount, RequestStatus

mf_router = APIRouter()
customers_collection = database.get_collection('customers')
user_collection = database.get_collection('users')
member_collections = database.get_collection('members')

requests_db = []
accounts_db = []


def generate_html_message(changes: dict) -> str:
    html_message = "<ul>"
    for field, value in changes.items():
        html_message += f"<li><strong>{field.capitalize()}:</strong> {value}</li>"
    html_message += "</ul>"
    return html_message


@mf_router.post("/request-mf/")
async def request_mf(mf_request: MFRequest, token: str = Depends(val_token)):
    mf_request = mf_request.dict()
    if token[0] is True:
        payload = token[1]
        if payload['role'] == 'Customer':
            customer = customers_collection.find_one({'email': payload["email"]})
            message = generate_html_message(mf_request)
            mf_request['pending_changes'] = {
                **mf_request,
                'updated_at': datetime.utcnow()
            }
            result = customers_collection.update_one(
                {'_id': customer['_id']},
                {'$set': {'mf_pending_changes': mf_request['pending_changes']}}
            )

            if result.modified_count == 0:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST,
                                    detail=f'Unable to queue update for this customer.')

            admin_email = "giri1208srinivas@gmail.com"
            subject = f"Approval Required: MF request {customer['email']}"

            if customer['partner_id']:
                for partner in customer['partner_id']:
                    member = member_collections.find_one({'_id': ObjectId(partner)})
                    await Email(subject, member['email'], 'customer_request', message).send_email()

            await Email(subject, admin_email, 'customer_request', message).send_email()
    # Notify admin and partner logic here (e.g., send an email)
    return {"message": "Request received and admin notified", "request": mf_request['pending_changes']}


@mf_router.post("/create-account/")
def create_account(mf_account: MFAccount):
    for request in requests_db:
        if request.customer_id == mf_account.customer_id and request.fund_name == mf_account.fund_name:
            request.status = RequestStatus.processed
            accounts_db.append(mf_account)
            return {"message": "Account created", "account": mf_account}
    raise HTTPException(status_code=404, detail="Request not found")


@mf_router.get("/process-mf/")
def process_mf():
    # Process mutual fund transactions
    processed_accounts = [account for account in accounts_db if account.amount > 0]
    return {"processed_accounts": processed_accounts}
