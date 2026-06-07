# Data loader

Load sessions from the Caltech ACN-Data API and map them to the project’s standardized format.

## Implementation (`loader.py`)

- **API**: Requests use the Eve API at `https://ev.caltech.edu/api/v1/`. The `where` parameter is **MongoDB-style JSON** (e.g. `{"connectionTime": {"$gte": "RFC1123"}, {"$lte": "..."}}`) and is URL-encoded. This matches the API; the acnportal `DataClient` uses a different format and is not used for the request.
- **Auth**: `ACN_DATA_API_TOKEN` from environment or `.env`; passed as HTTP Basic auth (token as username, empty password).
- **Query window**: Midnight-to-midnight **UTC** for the requested calendar day. Pagination via `_links.next` is followed.
- **`load_sessions(site_id, day_date, api_token=None, n_steps=96, dt_hours=0.25)`**: Returns `DaySessions`. Raises `ValueError` if token is missing or API returns an error.
- **`raw_session_to_standard(raw, day_start_utc, dt_hours, n_steps)`**: Maps one API session dict to `Session` (connectionTime/disconnectTime → arrival_idx/departure_idx, kWhDelivered → energy_kwh, sessionID, spaceID, max power).

No synthetic data; API key required.
