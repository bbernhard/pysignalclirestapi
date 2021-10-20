"""SignalCliRestApi Python library."""

import sys
import base64
import json
from future.utils import raise_from
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
            raise_from(SignalCliRestApiError("Couldn't determine REST API version"), exc)

    def mode(self):
        resp = requests.get(self._base_url + "/v1/about")
        data = json.loads(resp.content)

        mode = "unknown"
        try:
            mode = data["mode"]
        except KeyError:
            pass
        return mode

    def create_group(self, name, members):
        try:

            url = self._base_url + "/v1/groups/" + self._number 
            data = {
                "members": members,
                "name": name
            }
            resp = requests.post(url, json=data)
            if resp.status_code != 201 and resp.status_code != 200:
                json_resp = resp.json()
                if "error" in json_resp:
                    raise SignalCliRestApiError(json_resp["error"])
                raise SignalCliRestApiError("Unknown error while creating Signal Messenger group")
            return resp.json()["id"]
        except Exception as exc:
            if exc.__class__ == SignalCliRestApiError:
                raise exc
            raise_from(SignalCliRestApiError("Couldn't create Signal Messenger group: "), exc)

    def list_groups(self):
        try:
            url = self._base_url + "/v1/groups/" + self._number 
            resp = requests.get(url)
            json_resp = resp.json()
            if resp.status_code != 200: 
                if "error" in json_resp:
                    raise SignalCliRestApiError(json_resp["error"])
                raise SignalCliRestApiError("Unknown error while listing Signal Messenger groups")
            return json_resp
        except Exception as exc:
            if exc.__class__ == SignalCliRestApiError:
                raise exc
            raise_from(SignalCliRestApiError("Couldn't list Signal Messenger groups: "), exc)

    def receive(self):
        try:
            url = self._base_url + "/v1/receive/" + self._number
            resp = requests.get(url)
            json_resp = resp.json()
            if resp.status_code != 200: 
                if "error" in json_resp:
                    raise SignalCliRestApiError(json_resp["error"])
                raise SignalCliRestApiError("Unknown error while receiving Signal Messenger data")
            return json_resp
        except Exception as exc:
            if exc.__class__ == SignalCliRestApiError:
                raise exc
            raise_from(SignalCliRestApiError("Couldn't receive Signal Messenger data: "), exc)

    def update_profile(self, name, filename=None):
        """Update Profile.
           
        Set the name and optionally an avatar.
        """

        try:
            url = self._base_url + "/v1/profiles/" + self._number
            data = {
                "name": name
            }

            if filename is not None:
                with open(filename, "rb") as ofile:
                    base64_avatar = None
                    if sys.version_info >= (3, 0):
                        base64_avatar = str(base64.b64encode(ofile.read()), encoding="utf-8")
                    else:
                        base64_avatar = str(base64.b64encode(ofile.read())).encode("utf-8")

                    data["base64_avatar"] = base64_avatar

            resp = requests.put(url, json=data)
            if resp.status_code != 204:
                json_resp = resp.json()
                if "error" in json_resp:
                    raise SignalCliRestApiError(json_resp["error"])
                raise SignalCliRestApiError("Unknown error while updating profile")
        except Exception as exc:
            if exc.__class__ == SignalCliRestApiError:
                raise exc
            raise_from(SignalCliRestApiError("Couldn't update profile: "), exc)

    def send_message(self, message, recipients, filenames=None):
        """Send a message to one (or more) recipients.
         
        Additionally files can be attached.
        """
        
        api_versions, build_nr = self.api_info()
        if filenames is not None and len(filenames) > 1:
            if "v2" not in api_versions: # multiple attachments only allowed when api version >= v2
                raise SignalCliRestApiError("This signal-cli-rest-api version is not capable of sending multiple attachments. Please upgrade your signal-cli-rest-api docker container!")
        
        
        url = self._base_url + "/v2/send"
        if "v2" not in api_versions: # fall back to old api version to stay downwards compatible.
            url = self._base_url + "/v1/send"

        data = {
            "message": message,
            "number": self._number, 
        }

        data["recipients"] = recipients

        try:
            if "v2" in api_versions:
                base64_attachments = []
                if filenames is not None: 
                    for filename in filenames:
                        with open(filename, "rb") as ofile:
                            base64_attachment = None 
                            if sys.version_info >= (3, 0):
                                base64_attachment = str(base64.b64encode(ofile.read()), encoding="utf-8")
                            else:
                                base64_attachment = str(base64.b64encode(ofile.read())).encode("utf-8")
                            base64_attachments.append(base64_attachment)
                data["base64_attachments"] = base64_attachments
            else: # fall back to api version 1 to stay downwards compatible
                if filenames is not None and len(filenames) == 1:
                    with open(filenames[0], "rb") as ofile:
                        base64_attachment = None 
                        if sys.version_info >= (3, 0):
                            base64_attachment = str(base64.b64encode(ofile.read()), encoding="utf-8")
                        else:
                            base64_attachment = str(base64.b64encode(ofile.read())).encode("utf-8")
                        data["base64_attachment"] = base64_attachment
            
            resp = requests.post(url, json=data)
            if resp.status_code != 201:
                json_resp = resp.json()
                if "error" in json_resp:
                    raise SignalCliRestApiError(json_resp["error"])
                raise SignalCliRestApiError("Unknown error while sending signal message")
        except Exception as exc:
            if exc.__class__ == SignalCliRestApiError:
                raise exc
            raise_from(SignalCliRestApiError("Couldn't send signal message"), exc)
