# Balloons le Grá — DPD Collection Portal

A staff-facing Streamlit app for:
1. Creating the day's initial DPD collection request.
2. Sending additional-box updates with an automatically calculated new total.
3. Escalating an uncollected collection after 3:00pm.
4. Keeping an append-only audit trail from the staff interface.

## Important before live use

The depot email address and Kevin's CC email were not confirmed, so placeholders are intentionally included.
Do not use the app live until those are replaced.

The address currently used is:
Balloons le Grá, Manor West Shopping Centre, Tralee, Co. Kerry, V92 KAN8.

The account/reference subject prefix is currently:
7104 L3

## Quick start

Install Python 3.11+.

Open a terminal in this folder:

    pip install -r requirements.txt

Set the environment variables shown in `.env.example`.

Then run:

    streamlit run app.py

The app will open in a browser.

## Email

This build sends through SMTP. Use an app-specific password or a transactional/business mail account rather than putting a normal mailbox password into the Python source.

For Microsoft 365 or Google Workspace environments where SMTP authentication is disabled, the sending function can instead be changed to Microsoft Graph / Gmail API.

## Audit log

SQLite stores every send attempt in `collection_log.db`.
The staff-facing UI has no edit/delete controls.
For stronger production-grade immutability, deploy the database on a server with restricted credentials/backups rather than leaving the database file on a staff-accessible computer.

## Deployment

For multiple staff members, deploy this to a small hosted service rather than running it on one shop computer. That gives everyone one private web address and one central audit database.

Recommended next production step:
- private login/access
- hosted database
- verified mail account
- automatic backups
