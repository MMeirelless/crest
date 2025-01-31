# Custom REST Command (`crest`)

The `crest` command is a custom Splunk search command that allows you to send HTTP requests directly from your Splunk searches. It supports `GET`, `POST`, and `DELETE` methods, allowing you to interact with RESTful APIs and web services within your Splunk environment.

This command is shipped with the **Custom REST Command** app.

## Table of Contents

- [Installation](#installation)
- [Syntax](#syntax)
- [Parameters](#parameters)
- [Usage](#usage)
    - [Example 1: GET Request](#example-1-get-request)
    - [Example 2: POST Request](#example-2-post-request)
    - [Example 3: DELETE Request](#example-3-delete-request)
- [Debug Mode](#debug-mode)
- [Notes](#notes)
- [Support](#support)
- [License](#license)

---

## Installation

To install the **Custom REST Command** app and use the `crest` command:

1. **Download the App**: Obtain the app package from Splunkbase.
2. **Access Splunk Web**: Log in to your Splunk instance.
3. **Navigate to Manage Apps**:
    - Click on the **Apps** menu.
    - Select **Manage Apps**.
4. **Install the App**:
    - Click on **Install app from file**.
    - Upload the app package.
    - Click **Upload** and follow the prompts.
5. **Restart Splunk**: Some installations may require a restart. If prompted, restart your Splunk instance to complete the installation.

---

## Syntax

`| crest url=<string> method=<string> [data=<string>] [headers=<string>] [debug=<boolean>] [verify=<boolean>] [timeout=<int>]`

- **Note**: Square brackets `[]` denote optional parameters.

---

## Parameters

- **`url`** (required): The endpoint URL to send the HTTP request to.
- **`method`** (required): The HTTP method to use. Supported methods are `get`, `post`, and `delete`.
- **`data`** (optional): The payload to send with a `POST` request. Should be a JSON-formatted string.
- **`headers`** (optional): Custom headers to include in the request. Should be a JSON-formatted string.
- **`debug`** (optional): Set to `true` to enable debug mode, which displays request details without executing the request.
- **`verify`** (optional): Set to `false` to disable SSL verification in your REST calls. Be careful with this option!
- **`timeout`** (optional): Default is 10s, but you can change it according to your needs..

---

## Usage

### Example 1: GET Request

Send a `GET` request to `http://example.com/api`.

`| crest url="http://example.com/api" method="get"`

**Explanation**: This command sends a `GET` request to the specified URL and returns the response data in the search results.

### Example 2: POST Request

Send a `POST` request with a data payload to `http://example.com/api`.

`| crest url="http://example.com/api" method="post" data="{'key':'value'}"`

**Explanation**: This command sends a `POST` request to the specified URL with the provided JSON data as the payload.

### Example 3: DELETE Request

Send a `DELETE` request to `http://example.com/api/resource`.

`| crest url="http://example.com/api/resource" method="delete"`

**Explanation**: This command sends a `DELETE` request to remove the specified resource at the given URL.

---

## Debug Mode

Use the `debug` parameter to display the request details without executing the actual HTTP request. This is useful for verifying the request configuration.

`| crest url="http://example.com/api" method="get" debug="true"`

**Explanation**: When `debug` is set to `true`, the command outputs the request details (such as `url`, `method`, `headers`, and `data`) without sending the HTTP request.

---

## Notes

- **SSL Verification**: SSL verification is enabled by default. Ensure that your Splunk instance can verify the SSL certificates of the endpoints you are accessing. If you need to disable SSL verification (not recommended due to security risks), you can include the option `verify="false"` in the command.
- **Session Authorization**: When making requests to `localhost`, the command automatically includes the Splunk session key in the `Authorization` header.  This uses your user to authenticate the internal request.
- **Timeouts**: The command uses a default timeout of 10 seconds for HTTP requests. You can change this using the timeout option if necessary.
- **Error Handling**: The command includes error handling for network problems and invalid parameters. 
- **Data Payloads**: When sending JSON data in the `data` and `header` parameters, make sure it is properly formatted. For example:
    - `data="{\"user\":\"matheus\",\"role\":\"admin\"}"`

---

## License

This app is licensed under the MIT License.

---

**Disclaimer**: Use this command responsibly. Make sure you have permission to access the URLs you are querying, and be aware of the load and security implications of sending HTTP requests from your Splunk instance.