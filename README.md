## Running the application

1. `npm run dev` (inside client/) -> starts our client
2. `adk api_server --allow_origins "ALL"` (inside server/) -> starts adk backend
3. `python main.py` (inside server) -> starts the FASTAPI wrapper service which our client interacts with

## Dependencies

- Node v22.12.0
- Python3.10

## Frontend Setup
1. Run `npm install`

## Backend Setup
1. `python3.10 -m venv venv && source venv/bin/activate` (inside server folder)
2. Then `pip install google-adk`


### Notes
- Within `server/my_agent/` you will need to create a .env file containing:
    - GOOGLE_API_KEY
    - SUPABASE_URL
    - SUPABASE_SERVICE_ROLE_KEY
    - CHECKOUT_BASE_URL
