# M-PESA STK Push Backend — Render Deployment

## Files
- `app.py` — Flask API
- `requirements.txt` — Python dependencies
- `.env.example` — local environment-variable template
- `render.yaml` — Render deployment configuration
- `.gitignore` — prevents secrets and SQLite files from being committed

## Deploy
1. Push this folder to a GitHub repository.
2. In Render, choose **New → Blueprint** and select the repository, or create a Web Service manually.
3. If using the Blueprint, Render reads `render.yaml`.
4. Set these environment variables in Render:
   - `MPESA_ENV=sandbox`
   - `MPESA_CONSUMER_KEY`
   - `MPESA_CONSUMER_SECRET`
   - `MPESA_PASSKEY`
   - `MPESA_SHORTCODE`
   - `MPESA_CALLBACK_URL=https://YOUR-SERVICE.onrender.com/mpesa/callback`
   - `DB_FILE=payments.db`
5. Deploy.
6. Open `https://YOUR-SERVICE.onrender.com/`. It should return:
   `M-PESA STK backend is running.`

## Important SQLite note
The free Render filesystem is ephemeral. `payments.db` can therefore be lost after a restart/redeploy.
For persistent payment records, either:
- use a paid Render Persistent Disk and set `DB_FILE=/var/data/payments.db`, with the disk mounted at `/var/data`; or
- migrate the payment table to PostgreSQL.

## M-PESA callback
The callback URL must be publicly reachable over HTTPS:
`https://YOUR-SERVICE.onrender.com/mpesa/callback`

Keep M-PESA credentials out of GitHub. Put them in Render's Environment Variables.
