import os, base64, sqlite3
from datetime import datetime
import requests
from dotenv import load_dotenv
from flask import Flask, request, jsonify

load_dotenv()
app=Flask(__name__)

ENV=os.getenv("MPESA_ENV","sandbox").lower()
BASE="https://api.safaricom.co.ke" if ENV=="production" else "https://sandbox.safaricom.co.ke"
KEY=os.getenv("MPESA_CONSUMER_KEY","")
SECRET=os.getenv("MPESA_CONSUMER_SECRET","")
PASSKEY=os.getenv("MPESA_PASSKEY","")
SHORTCODE=os.getenv("MPESA_SHORTCODE","3563012")
CALLBACK=os.getenv("MPESA_CALLBACK_URL","")
DB=os.getenv("DB_FILE","payments.db")

def conn():
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row; return c

def init():
    c=conn()
    c.execute("""CREATE TABLE IF NOT EXISTS payments(
      id INTEGER PRIMARY KEY, checkout_id TEXT UNIQUE, phone TEXT, amount REAL,
      reference TEXT, status TEXT, result_desc TEXT, receipt TEXT, created_at TEXT)""")
    c.commit(); c.close()

def token():
    r=requests.get(BASE+"/oauth/v1/generate?grant_type=client_credentials",
                   auth=(KEY,SECRET),timeout=30)
    r.raise_for_status()
    return r.json()["access_token"]

def normalize(p):
    p=str(p).strip().replace(" ","")
    if p.startswith("+254"): p=p[1:]
    elif p.startswith("07") or p.startswith("01"): p="254"+p[1:]
    return p

@app.after_request
def cors(r):
    r.headers["Access-Control-Allow-Origin"]="*"
    r.headers["Access-Control-Allow-Headers"]="Content-Type"
    return r

@app.get("/")
def home(): return "M-PESA STK backend is running."

@app.post("/pay")
def pay():
    d=request.get_json(silent=True) or {}
    phone=normalize(d.get("phone",""))
    try: amount=int(float(d.get("amount",0)))
    except: amount=0
    reference=str(d.get("reference","ORDER")).strip()[:50] or "ORDER"

    if not (phone.isdigit() and len(phone)==12 and phone.startswith("2547")):
        return jsonify(ok=False,message="Enter a valid Kenyan number, e.g. 0712345678."),400
    if amount<1: return jsonify(ok=False,message="Enter an amount of at least KES 1."),400
    if not all([KEY,SECRET,PASSKEY,CALLBACK]):
        return jsonify(ok=False,message="Backend credentials/callback are not configured."),500

    try:
        ts=datetime.now().strftime("%Y%m%d%H%M%S")
        password=base64.b64encode(f"{SHORTCODE}{PASSKEY}{ts}".encode()).decode()
        body={
          "BusinessShortCode":SHORTCODE,
          "Password":password,
          "Timestamp":ts,
          "TransactionType":"CustomerBuyGoodsOnline",
          "Amount":amount,
          "PartyA":phone,
          "PartyB":SHORTCODE,
          "PhoneNumber":phone,
          "CallBackURL":CALLBACK,
          "AccountReference":reference,
          "TransactionDesc":"Payment"
        }
        r=requests.post(BASE+"/mpesa/stkpush/v1/processrequest",
                        json=body,headers={"Authorization":"Bearer "+token()},timeout=30)
        data=r.json()
        if r.status_code>=400 or data.get("ResponseCode") not in (None,"0"):
            return jsonify(ok=False,message=data.get("errorMessage") or data.get("ResponseDescription") or "Safaricom rejected the request.",safaricom=data),400
        cid=data.get("CheckoutRequestID")
        c=conn()
        c.execute("INSERT OR REPLACE INTO payments(checkout_id,phone,amount,reference,status,created_at) VALUES(?,?,?,?,?,?)",
                  (cid,phone,amount,reference,"STK_SENT",datetime.now().isoformat(timespec="seconds")))
        c.commit(); c.close()
        return jsonify(ok=True,message=data.get("CustomerMessage","STK Push sent. Check the phone."),checkout_request_id=cid)
    except Exception as e:
        return jsonify(ok=False,message="Payment server error: "+str(e)),502

@app.post("/mpesa/callback")
def callback():
    d=request.get_json(silent=True) or {}
    s=d.get("Body",{}).get("stkCallback",{})
    cid=s.get("CheckoutRequestID"); code=s.get("ResultCode")
    desc=s.get("ResultDesc","")
    receipt=None
    for item in s.get("CallbackMetadata",{}).get("Item",[]):
        if item.get("Name")=="MpesaReceiptNumber": receipt=item.get("Value")
    status="SUCCESS" if str(code)=="0" else "FAILED"
    if cid:
        c=conn(); c.execute("UPDATE payments SET status=?,result_desc=?,receipt=? WHERE checkout_id=?",(status,desc,receipt,cid)); c.commit(); c.close()
    return jsonify(ResultCode=0,ResultDesc="Accepted")

@app.get("/payment/<cid>")
def status(cid):
    c=conn(); row=c.execute("SELECT status,result_desc,receipt FROM payments WHERE checkout_id=?",(cid,)).fetchone(); c.close()
    if not row:return jsonify(ok=False,message="Payment not found"),404
    return jsonify(ok=True,status=row["status"],result_desc=row["result_desc"],receipt=row["receipt"])

init()
if __name__=="__main__":
    app.run(host="0.0.0.0",port=int(os.getenv("PORT","5000")))
