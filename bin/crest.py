# -*- coding: utf-8 -*-

"""
Splunk Generating/Streaming Command: CustomRest (crest)

This command allows Splunk users to execute REST requests (GET, POST, PUT, PATCH, DELETE)
directly from an SPL search.

It operates in two modes:
1. Generating Mode: If used at the start of a search (e.g., | crest ...), it executes a single request.
2. Streaming Mode: If used after other commands (e.g., ... | crest ...), it executes one request
   for EACH incoming event, allowing for token substitution ($field$).

Key Features:
- Supports GET, POST, PUT, PATCH, DELETE.
- Token substitution in streaming mode (e.g., url=".../$field$").
- Automatic response parsing for JSON, CSV, TSV, XML (with parse_response=true).
- Nested JSON parsing (with json_path="results.items").
- Simplified authentication (with auth_token and auth_type).
- Rate-limiting control (with delay=0.5).
- SSL verification disable (with verify_ssl=false).
- Automatic Splunk auth for 'localhost' calls.
"""

import sys
import os
import requests
import csv
import xml.etree.ElementTree as ET
import time  # Imported for 'delay' functionality
from json import loads, JSONDecodeError
from csv import Sniffer, Error as CSVError

# Add 'lib' directory to path to import 'splunklib'
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
    """
    Implements the 'crest' command.
    Inherits from StreamingCommand to support both generating and streaming modes.
    """

    # --- Request Parameters ---
    url = Option(require=True, doc="The URL of the API endpoint.")
    method = Option(require=True, doc="The HTTP method (get, post, put, patch, delete).")
    data = Option(require=False, doc="The request body (e.g., JSON as a string) for POST/PUT/PATCH.")
    headers = Option(require=False, doc="HTTP headers (as a JSON string) to be sent.")
    
    # --- Authentication Parameters ---
    auth_token = Option(require=False, default=None, doc="Authentication token (Bearer, Basic, etc.).")
    auth_type = Option(require=False, default='Bearer', doc="Authentication type (Bearer, Basic, token).")

    # --- Behavior Parameters ---
    timeout = Option(require=False, default=10, validate=validators.Integer(), doc="Request timeout in seconds.")
    delay = Option(require=False, default=0, validate=validators.Float(), doc="Delay in seconds between requests (for streaming mode).")
    verify_ssl = Option(require=False, default=True, validate=validators.Boolean(), doc="If true, verifies SSL certificate. Use false for self-signed certs (not recommended).")
    debug = Option(require=False, default=False, validate=validators.Boolean(), doc="If true, returns request parameters instead of executing the call.")

    # --- Parsing Parameters ---
    parse_response = Option(require=False, default=False, validate=validators.Boolean(), doc="If true, attempts to parse the response (JSON, CSV, XML) into multiple events.")
    delimiter = Option(require=False, default=None, doc="Forces a specific delimiter for CSV parsing (e.g., ';'). If None, auto-detects.")
    json_path = Option(require=False, default=None, doc="Path to extract a list from a nested JSON (e.g., 'results' or 'data.items').")
    
    # --- Internal Lists ---
    warnings = []  # Accumulates non-fatal warnings
    errors = []    # Accumulates fatal errors

    def _substitute_tokens(self, text_string, record):
        """
        Replaces $field$ tokens in a string with values from the event (record).
        Used for url, data, and headers in streaming mode.
        """
        if not text_string or not record:
            return text_string
        
        # Iterate over each field in the Splunk event
        for key, value in record.items():
            token = f'${key}$'
            # Replace all occurrences of the token
            text_string = text_string.replace(token, str(value))
        
        # (Optional: add warning if any $...$ tokens remain)
        return text_string

    def stream(self, records):
        """
        Main method called by Splunk.
        Processes the incoming events (records).
        """
        
        has_run = False  # Flag to detect if the 'for' loop ran

        try:
            # --- Streaming Mode ---
            # If events are piped to the command, this loop executes.
            for record in records:
                has_run = True
                # 'process_record' is a generator (yields), so we iterate over its results
                for processed_record in self.process_record(record):
                    yield processed_record
                
                # If a 'delay' is set, pause between events
                if self.delay > 0:
                    time.sleep(self.delay)
            
            # --- Generating Mode ---
            # If no events were piped (e.g., | crest ...), 'has_run' will be False.
            if not has_run:
                # Execute the processing logic once with an empty event
                for processed_record in self.process_record({}):
                    yield processed_record
        
        except Exception as e:
            self.errors.append(f"Unexpected error in 'stream' method: {e}")

        # At the end, fire all accumulated warnings and errors
        self.trigger_warnings()
        self.trigger_errors()


    def process_record(self, record):
        """
        Processes ONE request (either for a streaming event or for generating mode).
        This method is a generator (yields) because parsing can return multiple events.
        """
        try:
            # --- 1. Token Substitution ---
            if record: 
                # Streaming Mode: Substitute tokens in URL, data, and headers
                current_url = self._substitute_tokens(self.url, record)
                current_data = self._substitute_tokens(self.data, record)
                current_headers = self._substitute_tokens(self.headers, record)
            else:
                # Generating Mode: Use parameters as-is
                current_url = self.url
                current_data = self.data
                current_headers = self.headers

            # --- 2. Request Preparation ---
            method = self.method.lower()
            data = current_data if current_data else None
            headers = self.try_loads(current_headers) if current_headers else {}

            # --- 3. Authentication ---
            if self.auth_token:
                # Add auth header if it doesn't already exist
                if 'Authorization' not in headers:
                    if self.auth_type.lower() == 'basic':
                        headers['Authorization'] = f'Basic {self.auth_token}'
                    elif self.auth_type.lower() == 'token':
                        headers['Authorization'] = f'Token {self.auth_token}'
                    else: # Default to Bearer
                        headers['Authorization'] = f'Bearer {self.auth_token}'
            
            # --- 4. Localhost (Splunk) Auth ---
            # *** FIX RE-ADDED ***
            # Allows the command to act on the local Splunk API
            if "localhost" in current_url.lower() and isinstance(headers, dict):
                # Override any other auth with the user's current Splunk session key
                headers["Authorization"] = f"Splunk {self._metadata.searchinfo.session_key}"
                # Note: User must still set verify_ssl=false if Splunkd uses a self-signed cert

            # --- 5. Debug Mode ---
            # If debug=true, don't execute; just return parameters
            if self.debug:
                record["debug_url"] = current_url
                record["debug_data"] = data
                record["debug_method"] = method
                record["debug_headers"] = headers
                record["debug_verify_ssl"] = self.verify_ssl
                yield record
                return  # Stop the generator

            # --- 6. Request Execution ---
            response = self.rest(current_url, data, headers, method, self.verify_ssl)

            if response is None:
                # 'self.rest' already logged the error
                yield record  # Return the original event that failed
                return  # Stop the generator
            
            # --- 7. Response Parsing ---
            if self.parse_response:
                # Hand off to the parsing generator
                for parsed_event in self.parse_response_data(response, record, current_url):
                    yield parsed_event
            
            # --- 8. Default Response (No Parsing) ---
            else:
                record["status_code"] = response.status_code
                record["status_message"] = response.text
                if response.status_code < 200 or response.status_code >= 300:
                    self.warnings.append(f"Request to {current_url} returned HTTP status {response.status_code}")
                yield record

        except Exception as e:
            self.errors.append(f"Unexpected error in 'process_record': {e}")
            yield record # Yield the problematic record


    def parse_response_data(self, response, base_record, url_called):
        """
        Detects content type and routes to the correct parser.
        This is also a generator.
        """
        metadata = {
            "crest_status_code": response.status_code,
            "crest_url": url_called
        }

        # --- FIX: Handle 204 (No Content) status ---
        # RESTful APIs often return 204 on successful POST/DELETE with no body
        if response.status_code == 204:
            metadata['crest_status_message'] = "Success (No Content)"
            yield {**base_record, **metadata}
            return  # Stop the generator

        content_type = response.headers.get('Content-Type', '').lower()
        
        try:
            # --- Parser Router ---
            if 'application/json' in content_type:
                for event in self.parse_json(response.json(), base_record, metadata, self.json_path):
                    yield event
            
            elif 'application/xml' in content_type or 'text/xml' in content_type or url_called.lower().endswith('.xml'):
                for event in self.parse_xml(response.text, base_record, metadata):
                    yield event

            elif 'text/' in content_type or \
                 url_called.lower().endswith(('.csv', '.tsv', '.txt')):
                for event in self.parse_csv(response.text, base_record, metadata):
                    yield event
            
            else:
                # Fallback if type is not recognized
                self.warnings.append(f"Unrecognized content-type: '{content_type}'. Returning raw response.")
                yield self.yield_raw_response(response, base_record)

        except JSONDecodeError:
             # Common case: Content-Type is JSON, but body is empty (e.g., 200 OK)
             self.warnings.append(f"Content-Type was JSON, but response body was empty or malformed.")
             yield self.yield_raw_response(response, base_record)
        except Exception as e:
            self.errors.append(f"Failed to parse response: {e}")
            yield self.yield_raw_response(response, base_record)

    def yield_raw_response(self, response, record):
        """Helper to return the raw response (default behavior)."""
        record["status_code"] = response.status_code
        record["status_message"] = response.text
        return record
    
    def parse_json(self, data, base_record, metadata, json_path=None):
        """
        JSON parser. Now supports 'json_path' for nested data.
        """
        
        parse_target = data  # What we will parse

        # --- NEW: json_path logic ---
        if json_path:
            try:
                temp_data = data
                path_parts = json_path.split('.')
                for part in path_parts:
                    temp_data = temp_data[part]
                parse_target = temp_data  # Success, 'parse_target' is now the nested list
            except (KeyError, TypeError, AttributeError):
                self.warnings.append(f"json_path '{json_path}' not found. Parsing from root.")
                # 'parse_target' remains 'data' (the original)

        # --- Parsing Logic (now on 'parse_target') ---
        if isinstance(parse_target, list):
            # Case 1: A list of objects (most common)
            # e.g., [ {'a': 1}, {'a': 2} ]
            for item in parse_target:
                if isinstance(item, dict):
                    yield {**base_record, **metadata, **item}
                else: # List of simple values
                    yield {**base_record, **metadata, 'value': item}
        
        elif isinstance(parse_target, dict):
            # Case 2: A dictionary of objects (e.g., apis.guru)
            is_dict_of_dicts = False
            if parse_target.values(): 
                is_dict_of_dicts = all(isinstance(v, dict) for v in parse_target.values())

            if is_dict_of_dicts:
                # e.g., { 'api1': {'info':...}, 'api2': {'info':...} }
                for key, value_dict in parse_target.items():
                    value_dict['json_parent_key'] = key  # Add parent key as a field
                    yield {**base_record, **metadata, **value_dict}
            else:
                # Case 3: A single JSON object
                # e.g., { 'a': 1, 'b': 2 }
                yield {**base_record, **metadata, **parse_target}
        else:
            # Case 4: A single simple value
            yield {**base_record, **metadata, 'value': parse_target}

    def parse_csv(self, text_data, base_record, metadata):
        """
        CSV/TSV parser.
        - Skips comment lines (#).
        - Auto-detects delimiter (unless 'delimiter' is provided).
        """
        
        detected_delimiter = None
        
        try:
            # 1. Clean the data: filter out comments and blank lines
            all_lines = text_data.splitlines()
            cleaned_lines = [l for l in all_lines if l.strip() and not l.strip().startswith('#')]
            
            if not cleaned_lines:
                self.warnings.append("CSV data is empty or contains only comment lines.")
                return
        except Exception as e:
            self.errors.append(f"Error while cleaning CSV lines: {e}")
            return

        # 2. Detect delimiter
        if self.delimiter:
            detected_delimiter = self.delimiter
        else:
            try:
                sample = "\n".join(cleaned_lines[:10]) # Sample first 10 clean lines
                sniffer = Sniffer()
                dialect = sniffer.sniff(sample)
                detected_delimiter = dialect.delimiter
            except CSVError:
                self.warnings.append("Could not auto-detect CSV delimiter. Defaulting to comma (,).")
                detected_delimiter = ','
            except Exception as e:
                self.warnings.append(f"Error during CSV sniffing: {e}. Defaulting to comma (,).")
                detected_delimiter = ','

        # 3. Read the data
        try:
            reader = csv.DictReader(cleaned_lines, delimiter=detected_delimiter)
            for row in reader:
                # Clean null bytes which can break Splunk
                cleaned_row = {k.replace('\x00', ''): v.replace('\x00', '') for k, v in row.items() if k}
                yield {**base_record, **metadata, **cleaned_row}
        except Exception as e:
            self.errors.append(f"Failed to read CSV with detected delimiter '{detected_delimiter}': {e}")
            yield base_record


    def parse_xml(self, text_data, base_record, metadata):
        """
        Simple XML parser.
        Assumes each child tag of the root is an event.
        """
        try:
            root = ET.fromstring(text_data)
            for child in root:
                event = {}
                event.update(child.attrib) # Tag attributes
                if child.text and child.text.strip():
                    event['xml_value'] = child.text.strip()
                # Sub-tags
                for sub_child in child:
                    if sub_child.text and sub_child.text.strip():
                        event[sub_child.tag] = sub_child.text.strip()
                
                yield {**base_record, **metadata, **event}
        except Exception as e:
             self.errors.append(f"Failed to parse XML: {e}")
             yield base_record


    def rest(self, url, data, headers, method, verify_ssl):
        """
        Wrapper for the 'requests' module. Executes the HTTP call.
        """
        
        # Enforce HTTPS (allow http for localhost)
        if not url.lower().startswith("https://") and not "localhost" in url.lower():
            self.errors.append(f"External URL must use HTTPS. Insecure URL: {url}")
            return None
        
        try:
            # --- Method Router ---
            if method == "get":
                return requests.get(
                    url, headers=headers, data=data, timeout=self.timeout, verify=verify_ssl
                )
            elif method == "post":
                return requests.post(
                    url, headers=headers, data=data, timeout=self.timeout, verify=verify_ssl
                )
            elif method == "put": # NEW
                return requests.put(
                    url, headers=headers, data=data, timeout=self.timeout, verify=verify_ssl
                )
            elif method == "patch": # NEW
                return requests.patch(
                    url, headers=headers, data=data, timeout=self.timeout, verify=verify_ssl
                )
            elif method == "delete":
                return requests.delete(
                    url, headers=headers, data=data, timeout=self.timeout, verify=verify_ssl
                )
            else:
                self.errors.append(
                    "Method not recognized. Use: get, post, put, patch, delete."
                )
                return None
        
        except requests.exceptions.RequestException as e:
            self.errors.append(f"HTTP request failed: {e}")
            # Improved SSL error message
            if not verify_ssl:
                self.errors.append("SSL verification was disabled (verify_ssl=false).")
            else:
                self.errors.append("SSL verification failed. To disable (unsafe), use verify_ssl=false.")
            return None

    def try_loads(self, json_str):
        """Helper to safely load JSON from a string, handling errors."""
        if not json_str:
            return None
        try:
            return loads(json_str)
        except (JSONDecodeError, TypeError):
            self.warnings.append(
                f'"{json_str}" is not a valid JSON. If this is a plain string, ignore this warning.'
            )
            return json_str  # Return the original string

    # --- Error/Warning Helpers ---

    def trigger_warnings(self):
        """Write all accumulated warnings."""
        if self.warnings:
            for warning in self.warnings:
                self.write_warning(warning)

    def trigger_errors(self):
        """Write all accumulated errors."""
        if self.errors:
            for error in self.errors:
                self.write_error(error)

# Standard entry point for Splunk commands
dispatch(CustomRest, sys.argv, sys.stdin, sys.stdout, __name__)
