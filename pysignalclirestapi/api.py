"""SignalCliRestApi Python library."""

import base64
import json
import requests

class SignalCliRestApiError(Exception):
    """SignalCliRestApiError base classi."""
    pass

class SignalCliRestApi(object):
    """SignalCliRestApi implementation."""
    def __init__(self, base_url, number):
        """Initialize the class."""
        super(SignalCliRestApi, self).__init__()
        
        self._base_url = base_url
        self._number = number

    def api_info(self):
        try:
            resp = requests.get(self._base_url + "/v1/about")
            if resp.status_code == 404:
                return ["v1", 1]
            data = json.loads(resp.content)
            api_versions = data["versions"]
            build_nr = 1
            try:
                build_nr = data["build"]
            except KeyError:
                pass

            return api_versions, build_nr

        except Exception as exc:
            raise SignalCliRestApiError("Couldn't determine REST API version") from exc


    def send_message(self, message, recipients=[], group_id=None, filenames=None):
        """Send a message to one (or more) recipients.
         
        Additionally files can be attached.
        """

        if group_id is None and len(recipients) == 0:
            raise SignalCliRestApiError("Can't send message: please provide either one (or more) recipients or alternatively a group id!")

        if group_id is not None and len(recipients) > 0:
            raise SignalCliRestApiError("Can't send message: please provide either one (or more) recipients or alternatively a group id - but not both!")
        
        api_versions, build_nr = self.api_info()
        if filenames is not None and len(filenames) > 1:
            if "v2" not in api_versions: # multiple attachments only allowed when api version >= v2
                raise SignalCliRestApiError("This signal-cli-rest-api version is not capable of sending multiple attachments. Please upgrade your signal-cli-rest-api docker container!")

        if build_nr <= 1 and group_id is not None:
            raise SignalCliRestApiError("This signal-cli-rest-api version is not capable of sending messages to a group. Please upgrade your signal-cli-rest-api docker container!") 
        
        
        url = self._base_url + "/v2/send"
        if "v2" not in api_versions: # fall back to old api version to stay downwards compatible.
            url = self._base_url + "/v1/send"

        data = {
            "message": message,
            "number": self._number, 
        }

        if len(recipients) > 0:
            data["recipients"] = recipients

        if group_id is not None:
            data["group_id"] = group_id

        try:
            if "v2" in api_versions:
                base64_attachments = []
                if filenames is not None: 
                    for filename in filenames:
                        with open(filename, "rb") as ofile:
                            base64_attachments.append(str(base64.b64encode(ofile.read()), "utf-8"))
                data["base64_attachments"] = base64_attachments
            else: # fall back to api version 1 to stay downwards compatible
                if filenames is not None and len(filenames) == 1:
                    with open(filenames[0], "rb") as ofile:
                        data["base64_attachment"] = str(base64.b64encode(ofile.read()), "utf-8")
            
            resp = requests.post(url, json=data)
            if resp.status_code != 201:
                json_resp = resp.json()
                if "error" in json_resp:
                    raise SignalCliRestApiError(json_resp["error"])
                raise SignalCliRestApiError("unknown error while sending signal message")
        except Exception as exc:
            raise SignalCliRestApiError("Couldn't send signal message") from exc
