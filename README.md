# Custom REST Command (`crest`)

The `crest` command is a powerful and flexible custom Splunk search command that allows you to send HTTP requests directly from your Splunk searches.

It supports `GET`, `POST`, `PUT`, `PATCH`, and `DELETE` methods, allowing you to interact with RESTful APIs and web services. The command can run as a *generating* command (to start a search) or a *streaming* command (to act on existing results), making it a complete tool for API integration.

This command is shipped with the **Custom REST Command** app.

## Table of Contents

- [Installation](#installation)
- [Syntax](#syntax)
- [Operating Modes](#operating-modes)
  - [1. Generating Mode](#1-generating-mode)
  - [2. Streaming Mode](#2-streaming-mode)
- [Parameters](#parameters)
- [Usage Examples](#usage-examples)
  - [Example 1: Basic GET Request (Generating)](#example-1-basic-get-request-generating)
  - [Example 2: JSON Parsing (Generating)](#example-2-json-parsing-generating)
  - [Example 3: Nested JSON Parsing (Generating)](#example-3-nested-json-parsing-generating)
  - [Example 4: CSV Parsing (Generating)](#example-4-csv-parsing-generating)
  - [Example 5: Token Authentication](#example-5-token-authentication)
  - [Example 6: Streaming Mode with Token Substitution](#example-6-streaming-mode-with-token-substitution)
- [Debug Mode](#debug-mode)
- [Notes](#notes)
- [Support](#support)
- [License](#license)

---

## Installation

To install the **Custom REST Command** app and use the `crest` command:

1.  **Download the App**: Obtain the app package from Splunkbase.
2.  **Access Splunk Web**: Log in to your Splunk instance.
3.  **Navigate to Manage Apps**:
    -   Click on the **Apps** menu.
    -   Select **Manage Apps**.
4.  **Install the App**:
    -   Click on **Install app from file**.
    -   Upload the app package.
    -   Click **Upload** and follow the prompts.
5.  **Restart Splunk**: Some installations may require a restart. If prompted, restart your Splunk instance to complete the installation.

---

## Syntax

```spl
| crest url=<string> method=<string> [data=<string>] [headers=<string>] [auth_token=<string>] [auth_type=<string>] [parse_response=<boolean>] [json_path=<string>] [delimiter=<string>] [verify_ssl=<boolean>] [delay=<float>] [timeout=<int>] [debug=<boolean>]
```

-   **Note**: Square brackets `[]` denote optional parameters.

---

## Operating Modes

The `crest` command can operate in two distinct modes, depending on where it's placed in your SPL query.

### 1. Generating Mode

This mode is used when `crest` is the *first* command in your search (i.e., starts with `| crest ...`). It runs **once** to fetch data from an external source and bring it into Splunk.

**Use Case:** Importing a threat intelligence feed, fetching a list of users from an API, or checking the status of an external service.

### 2. Streaming Mode

This mode is used when `crest` is placed *after* another command (e.g., `| makeresults ... | crest ...` or `index=_internal | ... | crest ...`). It runs **once for every event** piped into it.

**Use Case:** This is extremely powerful. You can use it to create multiple tickets, update assets in a CMDB, or enrich events one by one. This mode enables **Token Substitution**.

#### Token Substitution

In streaming mode, you can use `$field_name$` syntax in the `url`, `data`, and `headers` parameters to dynamically insert values from the incoming Splunk event.

-   **Example:** `... | eval user="admin", id=123 | crest url="https://api.local/users/$id$" data="{'name': '$user$'}"`
-   **Result:** The command will make a request to `https://api.local/users/123` with the payload `{'name': 'admin'}`.

---

## Parameters

-   **`url`** (required): The endpoint URL to send the HTTP request to.
    -   In Streaming Mode, supports token substitution (e.g., `url=".../users/$id$"`).
-   **`method`** (required): The HTTP method to use.
    -   Supported: `get`, `post`, `put`, `patch`, `delete`.
-   **`data`** (optional): The payload (body) to send with `POST`, `PUT`, or `PATCH` requests. This should be a string, typically formatted as JSON.
    -   In Streaming Mode, supports token substitution (e.g., `data="{'user': '$user_name$'}"`).
-   **`headers`** (optional): Custom headers to include in the request. Should be a JSON-formatted string (e.g., `headers="{'X-API-Key': '123'}"`).
    -   In Streaming Mode, supports token substitution.
-   **`auth_token`** (optional): A helper to easily add an `Authorization` header. This is the token string itself.
-   **`auth_type`** (optional): Specifies the type of token for `auth_token`.
    -   Default: `Bearer`.
    -   Supported: `Bearer`, `Basic`, `Token`. (e.g., `auth_type="Basic" auth_token="dXNlcjpwYXNz..."`).
-   **`parse_response`** (optional): Set to `true` to automatically parse the API response into Splunk events (a table).
    -   Default: `false` (returns a single event with `status_code` and `status_message`).
    -   Supported formats: `JSON` (list of objects, or dict of objects), `CSV`, `TSV` (auto-detects delimiter), and `XML`.
-   **`json_path`** (optional): Used with `parse_response=true` for nested JSON. Specifies the key to find the list of results.
    -   Example: If the response is `{"count": 10, "results": [...] }`, use `json_path="results"`.
    -   Supports dot notation for deeper nesting (e.g., `json_path="data.items"`).
-   **`delimiter`** (optional): Used with `parse_response=true`. Forces a specific delimiter for CSV parsing (e.g., `delimiter=";"`). If not set, it auto-detects (comma, tab, semicolon, etc.).
-   **`verify_ssl`** (optional): Set to `false` to disable SSL certificate verification.
    -   Default: `true`.
    -   **Warning:** Only use `verify_ssl=false` in test environments or when you fully trust the endpoint (e.g., `localhost` with a self-signed cert).
-   **`delay`** (optional): The number of seconds to wait *between* requests in Streaming Mode. Useful for rate limiting.
    -   Default: `0` (no delay).
    -   Example: `delay=0.5` (waits 500ms after each call).
-   **`timeout`** (optional): The number of seconds to wait for the server to respond.
    -   Default: `10`.
-   **`debug`** (optional): Set to `true` to return the request details (URL, headers, data) *without* executing the request.
    -   Default: `false`.

---

## Usage Examples

### Example 1: Basic GET Request (Generating)

Fetches a simple GET request and returns the raw response.

```spl
| crest url="https://httpbin.org/get" method="get"
```

**Result:** A single event with `status_code=200` and `status_message` containing the full JSON response.

### Example 2: JSON Parsing (Generating)

Fetches a list of public APIs from an open API and parses the JSON response into a table.

```spl
| crest url="https://api.apis.guru/v2/list.json" method="get" parse_response=true
```

**Result:** A table of thousands of APIs. The `json_parent_key` column shows the API name, and other columns (`added`, `preferred`) are populated from the response.

### Example 3: Nested JSON Parsing (Generating)

Fetches a list of public APIs, but this time the list is *nested* inside a key named "entries".

```spl
| crest url="https://api.publicapis.org/entries" method="get" parse_response=true json_path="entries"
```

**Result:** A table of APIs with columns like `API`, `Category`, and `Link`. Using `json_path` is crucial here.

### Example 4: CSV Parsing (Generating)

Fetches a threat intelligence feed in CSV format and automatically parses it into a table. The command will auto-detect the comma delimiter and skip the `#` comment lines.

```spl
| crest url="https://hole.cert.pl/domains/v2/domains.csv" method="get" parse_response=true
```

**Result:** A table of malicious domains with columns like `hostname`, `ip`, and `classification`.

### Example 5: Token Authentication

Sends an authenticated request using the simple `auth_token` helper.

```spl
| crest url="https://httpbin.org/bearer" method="get" auth_token="my-secret-token-123"
```

**Result:** A single event. The `status_message` will show `"authenticated": true` and `"token": "my-secret-token-123"`.

### Example 6: Streaming Mode with Token Substitution

Creates three new tickets in an external system by piping events into `crest`. This demonstrates token substitution and the `delay` parameter for rate limiting.

```spl
| makeresults count=3
| streamstats count
| eval ticket_title = "Ticket " + count, user_email = "user" + count + "@example.com"
| crest url="https://api.my-helpdesk.com/v1/tickets" method="post" \
    data="{'summary': '$ticket_title$', 'requester': '$user_email$', 'status': 'new'}" \
    auth_token="my-api-key" \
    delay=1
```

**Result:** This runs **3 times**.
1.  **POSTs** to `/v1/tickets` with `{'summary': 'Ticket 1', 'requester': 'user1@example.com', ...}`
2.  Waits 1 second.
3.  **POSTs** to `/v1/tickets` with `{'summary': 'Ticket 2', 'requester': 'user2@example.com', ...}`
4.  Waits 1 second.
5.  ...and so on. The search results will show 3 events, each with the `status_code` of its respective API call.

---

## Debug Mode

Use the `debug=true` parameter to see what the command *would* send. This is essential for troubleshooting token substitution, headers, and data formatting.

```spl
| makeresults
| eval user="matheus", ticket_id=55
| crest url="https://api.local/tickets/$ticket_id$" method="put" \
    data="{'assignee': '$user$'}" \
    auth_token="123" \
    debug=true
```

**Result:** A single event with fields showing the *final* values:
-   `debug_url`: `https://api.local/tickets/55`
-   `debug_data`: `{'assignee': 'matheus'}`
-   `debug_headers`: `{'Authorization': 'Bearer 123'}`
-   `debug_method`: `put`

---

## Notes

-   **HTTPS Enforcement**: By default, the command requires `https://` for all URLs *except* `localhost`.
-   **SSL Verification**: SSL verification is **enabled by default**. If you are querying an internal endpoint with a self-signed certificate, you must use `verify_ssl=false`.
-   **Localhost Session Auth**: When making requests to `localhost` (e.g., the local Splunk REST API), the command automatically includes your Splunk session key in the `Authorization` header. You will likely need to use `verify_ssl=false` as well.
    -   ```spl
        | crest url="https://localhost:8089/services/authentication/current-context" method="get" verify_ssl=false parse_response=true
        ```
-   **Timeouts**: The default timeout is 10 seconds. You can increase this with the `timeout` parameter for long-running API calls.
-   **Data Payloads**: When writing JSON for `data` and `headers`, you must use **single quotes** for the *outer* string and **double quotes** for the *inner* keys and values, as required by Splunk's SPL parser.
    -   **Correct:** `data='{"user":"matheus","role":"admin"}'`
    -   **Incorrect:** `data="{\"user\":\"matheus\",\"role\":\"admin\"}"` (This is valid but difficult to read and escape)
-   **Empty Responses (204 No Content)**: The command correctly handles successful but empty responses (like `204 No Content`) and will not produce a parsing error.

---

## License

This app is licensed under the MIT License.

---

**Disclaimer**: Use this command responsibly. Make sure you have permission to access the URLs you are querying, and be aware of the load and security implications of sending HTTP requests from your Splunk instance.
