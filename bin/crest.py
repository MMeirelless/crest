import sys
import os
import requests
from json import loads

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "lib"))
from splunklib.searchcommands import (
    dispatch,
    StreamingCommand,
    Configuration,
    Option,
    validators,
)


@Configuration()
class CustomRest(StreamingCommand):

    url = Option(require=True)
    data = Option(require=False)
    method = Option(require=True)
    headers = Option(require=False)
    timeout = Option(require=False, default=10, validate=validators.Integer())
    debug = Option(require=False, default=False, validate=validators.Boolean())
    verify = True   # Enforced True

    warnings = []
    errors = []

    def stream(self, records):
        for record in records:

            method = self.method.lower()
            data = self.data if self.data else None
            headers = self.try_loads(self.headers) if self.headers else {}

            # If URL contains 'localhost', add Splunk token if possible
            if "localhost" in self.url.lower() and isinstance(headers, dict):
                self.verify = False        
                headers["Authorization"] = f"Splunk {self._metadata.searchinfo.session_key}"

            if self.debug:
                record["url"] = self.url
                record["data"] = data
                record["method"] = method
                record["headers"] = headers
                record["verify"] = self.verify
                
            else:
                response = self.rest(self.url, data, headers, method)

                if response is not None:
                    status_code = response.status_code
                    status_message = response.text

                    record["status_code"] = status_code
                    record["status_message"] = status_message

                    if status_code < 200 or status_code >= 300:
                        self.trigger_warnings()
                else:
                    self.trigger_errors()

            yield record

    def rest(self, url, data, headers, method):
        
        # Enforce HTTPS for any external URL
        if not url.lower().startswith("https://") and not "localhost" in self.url.lower():
            self.errors.append(f"External URL must use HTTPS. Insecure URL found: {url}")
            return None

        try:
            if method == "post":
                return requests.post(
                    url,
                    headers=headers,
                    data=data,
                    timeout=self.timeout,
                    verify=self.verify,
                )
            elif method == "get":
                return requests.get(
                    url,
                    headers=headers,
                    data=data,
                    timeout=self.timeout,
                    verify=self.verify,
                )
            elif method == "delete":
                return requests.delete(
                    url,
                    headers=headers,
                    data=data,
                    timeout=self.timeout,
                    verify=self.verify,
                )
            else:
                self.errors.append(
                    "Method not recognized. Recognized methods are: post, get, and delete."
                )
                return None

        except requests.exceptions.RequestException as e:
            self.errors.append(f"HTTP request failed: {e}")
            self.errors.append(
                "SSL verification is set to True. Make sure you're using a secure connection that uses SSL."
            )
            return None

    def try_loads(self, json_str):
        try:
            return loads(json_str)
        except:
            self.warnings.append(
                f'"{json_str}" is not a valid JSON. If this is correct, ignore this message.'
            )
            return json_str

    def trigger_warnings(self):
        if self.warnings:
            for warning in self.warnings:
                self.write_warning(warning)

    def trigger_errors(self):
        if self.errors:
            for error in self.errors:
                self.write_error(error)

dispatch(CustomRest, sys.argv, sys.stdin, sys.stdout, __name__)