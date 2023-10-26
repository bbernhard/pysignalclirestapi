"""SignalCliRestApi Python library."""

import sys
import base64
import json
from abc import ABC, abstractmethod
from requests.models import HTTPBasicAuth
from future.utils import raise_from
import requests
from .helpers import bytes_to_base64


class SignalCliRestApiError(Exception):
    """SignalCliRestApiError base class."""
    pass


class SignalCliRestApiAuth(ABC):
    """SignalCliRestApiAuth base class."""

    @abstractmethod
    def get_auth():
        pass


class SignalCliRestApiHTTPBasicAuth(SignalCliRestApiAuth):
    """SignalCliRestApiHTTPBasicAuth offers HTTP basic authentication."""

    def __init__(self, basic_auth_user, basic_auth_pwd):
        self._auth = HTTPBasicAuth(basic_auth_user, basic_auth_pwd)

    def get_auth(self):
        return self._auth


class SignalCliRestApi(object):
    """SignalCliRestApi implementation."""

    def __init__(self, base_url, number, auth=None, verify_ssl=True):
        """Initialize the class."""
        super(SignalCliRestApi, self).__init__()
        self._base_url = base_url
        self._number = number
        self._verify_ssl = verify_ssl
        if auth:
            assert issubclass(
                type(auth), SignalCliRestApiAuth), "Expecting a subclass of SignalCliRestApiAuth as auth parameter"
            self._auth = auth.get_auth()
        else:
            self._auth = None

    def about(self):
        resp = requests.get(self._base_url + "/v1/about", auth=self._auth, verify=self._verify_ssl)
        if resp.status_code == 200:
            return resp.json()
        return None

    def api_info(self):
        try:
            data = self.about()
            if data is None:
                return ["v1", 1]
            api_versions = data["versions"]
            build_nr = 1
            try:
                build_nr = data["build"]
            except KeyError:
                pass

            return api_versions, build_nr

        except Exception as exc:
            raise_from(SignalCliRestApiError(
                "Couldn't determine REST API version"), exc)

    def has_capability(self, endpoint, capability, about=None):
        if about is None:
            about = self.about()

        return capability in about.get("capabilities", {}).get(endpoint, [])

    def mode(self):
        data = self.about()

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
            resp = requests.post(url, json=data, auth=self._auth, verify=self._verify_ssl)
            if resp.status_code != 201 and resp.status_code != 200:
                json_resp = resp.json()
                if "error" in json_resp:
                    raise SignalCliRestApiError(json_resp["error"])
                raise SignalCliRestApiError(
                    "Unknown error while creating Signal Messenger group")
            return resp.json()["id"]
        except Exception as exc:
            if exc.__class__ == SignalCliRestApiError:
                raise exc
            raise_from(SignalCliRestApiError(
                "Couldn't create Signal Messenger group: "), exc)

    def list_groups(self):
        try:
            url = self._base_url + "/v1/groups/" + self._number
            resp = requests.get(url, auth=self._auth, verify=self._verify_ssl)
            json_resp = resp.json()
            if resp.status_code != 200:
                if "error" in json_resp:
                    raise SignalCliRestApiError(json_resp["error"])
                raise SignalCliRestApiError(
                    "Unknown error while listing Signal Messenger groups")
            return json_resp
        except Exception as exc:
            if exc.__class__ == SignalCliRestApiError:
                raise exc
            raise_from(SignalCliRestApiError(
                "Couldn't list Signal Messenger groups: "), exc)

    def receive(self):
        try:
            url = self._base_url + "/v1/receive/" + self._number
            resp = requests.get(url, auth=self._auth, verify=self._verify_ssl)
            json_resp = resp.json()
            if resp.status_code != 200:
                if "error" in json_resp:
                    raise SignalCliRestApiError(json_resp["error"])
                raise SignalCliRestApiError(
                    "Unknown error while receiving Signal Messenger data")
            return json_resp
        except Exception as exc:
            if exc.__class__ == SignalCliRestApiError:
                raise exc
            raise_from(SignalCliRestApiError(
                "Couldn't receive Signal Messenger data: "), exc)

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
                    base64_avatar = bytes_to_base64(ofile.read())
                    data["base64_avatar"] = base64_avatar

            resp = requests.put(url, json=data, auth=self._auth, verify=self._verify_ssl)
            if resp.status_code != 204:
                json_resp = resp.json()
                if "error" in json_resp:
                    raise SignalCliRestApiError(json_resp["error"])
                raise SignalCliRestApiError(
                    "Unknown error while updating profile")
        except Exception as exc:
            if exc.__class__ == SignalCliRestApiError:
                raise exc
            raise_from(SignalCliRestApiError("Couldn't update profile: "), exc)

    def send_message(self, message, recipients, filenames=None, attachments_as_bytes=None,
                     mentions=None, quote_timestamp=None, quote_author=None, quote_message=None, quote_mentions=None):
        """Send a message to one (or more) recipients.

        Additionally files can be attached.
        """

        about = self.about()

        api_versions = about["versions"]

        endpoint = "v2/send"
        # fall back to old api version to stay downwards compatible.
        if "v2" not in api_versions:
            endpoint = "v1/send"

        if filenames is not None and len(filenames) > 1:
            if "v2" not in api_versions:  # multiple attachments only allowed when api version >= v2
                raise SignalCliRestApiError(
                    "This signal-cli-rest-api version is not capable of sending multiple attachments. Please upgrade your signal-cli-rest-api docker container!")
        if mentions and not self.has_capability(endpoint, "mentions"):
            raise SignalCliRestApiError(
                "This signal-cli-rest-api version is not capable of sending mentions. Please upgrade your signal-cli-rest-api docker container!")
        if (quote_timestamp or quote_author or quote_message or quote_mentions) and not self.has_capability(endpoint, "quotes"):
            raise SignalCliRestApiError(
                "This signal-cli-rest-api version is not capable of sending quotes. Please upgrade your signal-cli-rest-api docker container!")

        url = f"{self._base_url}/{endpoint}"

        data = {
            "message": message,
            "number": self._number,
            "recipients": recipients,
        }
        if mentions:
            data["mentions"] = mentions
        if quote_timestamp:
            data["quote_timestamp"] = quote_timestamp
        if quote_author:
            data["quote_author"] = quote_author
        if quote_message:
            data["quote_message"] = quote_message
        if quote_mentions:
            data["quote_mentions"] = quote_mentions

        try:
            if "v2" in api_versions:
                if attachments_as_bytes is None:
                    base64_attachments = []
                else:
                    base64_attachments = [
                        bytes_to_base64(attachment) for attachment in attachments_as_bytes
                    ]
                if filenames is not None:
                    for filename in filenames:
                        with open(filename, "rb") as ofile:
                            base64_attachment = bytes_to_base64(ofile.read())
                            base64_attachments.append(base64_attachment)
                data["base64_attachments"] = base64_attachments
            else:  # fall back to api version 1 to stay downwards compatible
                if filenames is not None and len(filenames) == 1:
                    with open(filenames[0], "rb") as ofile:
                        base64_attachment = bytes_to_base64(ofile.read())
                        data["base64_attachment"] = base64_attachment

            resp = requests.post(url, json=data, auth=self._auth, verify=self._verify_ssl)
            if resp.status_code != 201:
                json_resp = resp.json()
                if "error" in json_resp:
                    raise SignalCliRestApiError(json_resp["error"])
                raise SignalCliRestApiError(
                    "Unknown error while sending signal message")
        except Exception as exc:
            if exc.__class__ == SignalCliRestApiError:
                raise exc
            raise_from(SignalCliRestApiError(
                "Couldn't send signal message"), exc)

    def list_attachments(self):
        """List all downloaded attachments."""

        try:
            url = self._base_url + "/v1/attachments"
            resp = requests.get(url, auth=self._auth, verify=self._verify_ssl)
            if resp.status_code != 200:
                json_resp = resp.json()
                if "error" in json_resp:
                    raise SignalCliRestApiError(json_resp["error"])
                raise SignalCliRestApiError("Unknown error while listing attachments")

            return resp.json()
        except Exception as exc:
            if exc.__class__ == SignalCliRestApiError:
                raise exc
            raise_from(SignalCliRestApiError("Couldn't list attachments: "), exc)

    def get_attachment(self, attachment_id):
        """Serve the attachment with the given id."""

        try:
            url = self._base_url + "/v1/attachments/" + attachment_id

            resp = requests.get(url, auth=self._auth, verify=self._verify_ssl)
            if resp.status_code != 200:
                json_resp = resp.json()
                if "error" in json_resp:
                    raise SignalCliRestApiError(json_resp["error"])
                raise SignalCliRestApiError("Unknown error while getting attachment")

            return resp.content
        except Exception as exc:
            if exc.__class__ == SignalCliRestApiError:
                raise exc
            raise_from(SignalCliRestApiError("Couldn't get attachment: "), exc)

    def delete_attachment(self, attachment_id):
        """Remove the attachment with the given id from filesystem."""

        try:
            url = self._base_url + "/v1/attachments/" + attachment_id

            resp = requests.delete(url, auth=self._auth, verify=self._verify_ssl)
            if resp.status_code != 204:
                json_resp = resp.json()
                if "error" in json_resp:
                    raise SignalCliRestApiError(json_resp["error"])
                raise SignalCliRestApiError("Unknown error while deleting attachment")
        except Exception as exc:
            if exc.__class__ == SignalCliRestApiError:
                raise exc
            raise_from(SignalCliRestApiError("Couldn't delete attachment: "), exc)
