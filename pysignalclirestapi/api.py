"""SignalCliRestApi Python library."""

import base64
import json
import requests

class SignalCliRestApiError(Exception):
    """SignalCliRestApiError base classi."""
    pass

class SignalCliRestApi(object):
    """SignalCliRestApi implementation."""
    def __init__(self, base_url, number, api_version=1):
        """Initialize the class."""
        super(SignalCliRestApi, self).__init__()
        
        try:
            self._api_version = int(api_version)
        except ValueError:
            raise SignalCliRestApiError("api version needs to be an integer!")
        
        self._base_url = base_url
        self._number = number

        if self._api_version > 2:
            raise SignalCliRestApiError("api version not supported!")

    def supported_api_versions(self):
        try:
            resp = requests.get(self._base_url + "/v1/about")
            if resp.status_code == 404:
                return ["v1"]
            return json.loads(resp.content)["versions"]
        except Exception as exc:
            raise SignalCliRestApiError("Couldn't determine REST API version") from exc

    def send_message(self, message, recipients, filenames=None):
        """Send a message to one (or more) recipients.
         
        Additionally a file can be attached.
        """
        url = self._base_url + "/v" + str(self._api_version) + "/send"
        data = {
            "message": message,
            "number": self._number,
            "recipients": recipients,
        }

        api_versions = self.supported_api_versions()
        if filenames is not None and len(filenames) > 1:
            if "v2" not in api_versions:
                raise SignalCliRestApiError("This signal-cli-rest-api version is not capable of sending multiple attachments. Please upgrade your signal-cli-rest-api docker container!")

        try:
            base64_attachments = []
            if filenames is not None: 
                for filename in filenames:
                    with open(filename, "rb") as ofile:
                        base64_attachments.append(str(base64.b64encode(ofile.read()), "utf-8"))
            data["base64_attachments"] = base64_attachments
            resp = requests.post(url, json=data)
            if resp.status_code != 201:
                json_resp = resp.json()
                if "error" in json_resp:
                    raise SignalCliRestApiError(json_resp["error"])
                raise SignalCliRestApiError("unknown error while sending signal message")
        except Exception as exc:
            raise SignalCliRestApiError("Couldn't send signal message") from exc
