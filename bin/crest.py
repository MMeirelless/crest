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
    verify = Option(require=False, default=True, validate=validators.Boolean())
    debug = Option(require=False, default=False, validate=validators.Boolean())

    warnings = []
    errors = []

    def stream(self, records):
        for record in records:

            method = self.method.lower()
            data = self.data if self.data else None
            headers = self.try_loads(self.headers) if self.headers else {}

            if "localhost" in self.url and type(headers) == dict:
                headers[
                    "Authorization"
                ] = f"Splunk {self._metadata.searchinfo.session_key}"

            if self.debug:
                record["url"] = self.url
                record["data"] = data
                record["method"] = method
                record["headers"] = headers

            else:
                response = self.rest(self.url, data, headers, method)

                if response != None:
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
                "SSL verification is set to True. Change the 'verify' option if necessary. Be careful!"
            )
            return None

    def try_loads(self, json):
        try:
            json = loads(json)
            return json
        except:
            self.warnings.append(
                f'"{json}" is not a valid JSON. If this is correct, ignore this message.'
            )
            return json

    def trigger_warnings(self):
        if len(self.warnings) > 0:
            for warning in self.warnings:
                self.write_warning(warning)

    def trigger_errors(self):
        if len(self.errors) > 0:
            for error in self.errors:
                self.write_error(error)

dispatch(CustomRest, sys.argv, sys.stdin, sys.stdout, __name__)