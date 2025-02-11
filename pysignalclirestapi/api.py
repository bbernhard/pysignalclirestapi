"""SignalCliRestApi Python library."""

import sys
import base64
import json
from abc import ABC, abstractmethod
from requests.models import HTTPBasicAuth
from six import raise_from
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
    
    def _formatParams(self, params, endpoint:str=None):
        formattedData = {}
        
        params.pop('self')
        # Create a JSON query object
        formattedData = {}
        for item, value in params.items(): # Check params, add anything that isn't blank to the query
            if value !=None:
                # Allow conditional formatting, depending on the endpoint
                if endpoint in ['receive']:
                    value = 'true' if value is True else 'false' if value is False else value # Convert bool to string
                    
                elif endpoint in ['update_contact']:
                    item = 'recipient' if item == 'contact' else item # Rename contact to recipient
                    
                formattedData.update({item : value})
        
        return formattedData
    
    def _requester(self, method, url, data=None, successCode:int=200, errorUnknown=None, errorCouldnt=None):
        """Internal central requester.

        Args:
            method (str): Rest API method.
            url (str): API url
            data (any, optional): Optional params or JSON data. Defaults to None.
            successCode (int, optional): Custom success code. Defaults to 200.
            errorUnknown (str, optional): Custom error for "unknown error". Defaults to None.
            errorCouldnt (str, optional): Custom error for "Couldn't". Defaults to None.
        """
        
        params = None
        json = None
        
        try:
            
            if method in ['post','put','delete']:
                json=data
            
            else:
                params=data

            resp = requests.request(method=method, url=url, params=params, json=json, auth=self._auth, verify=self._verify_ssl)
            if resp.status_code != successCode:
                json_resp = resp.json()
                if "error" in json_resp:
                    raise SignalCliRestApiError(json_resp["error"])
                raise SignalCliRestApiError(
                    f"Unknown error {errorUnknown}")
            else:
                return resp # Return raw response for now
        except Exception as exc:
            if exc.__class__ == SignalCliRestApiError:
                raise exc
            raise_from(SignalCliRestApiError(f"Couldn't {errorCouldnt}: "), exc)
        
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

    def create_group(self, name:str, members:list):
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

    def receive(self, ignore_attachments:bool=False, ignore_stories:bool=False, send_read_receipts:bool=False, max_messages:int=None, timeout:int=1):
        """Receive (get) Signal Messages from the Signal Network. 
        
        If you are running the docker container in normal/native mode, this is a GET endpoint. In json-rpc mode this is a websocket endpoint.
        
        Args:
            ignore_attachments (bool, optional): Ignore attachments. Defaults to False.
            ignore_stories (bool, optional): Ignore stories. Defaults to False.
            send_read_receipts (bool, optional): Send read receipts. Defaults to False.
            max_messages (int, optional): Maximum messages to get per request.  Messages will be returned oldest to newest. Defaults to None (unlimited).
            timeout (int, optional): Receive timeout in seconds. Defaults to 1.

        Returns:
            list: List of messages
        """
        rawParams = locals().copy()
        url = self._base_url + "/v1/receive/" + self._number
        data = self._formatParams(params=rawParams, endpoint='receive')
        
        request = self._requester(method='get', url=url, data=data, successCode=200, errorUnknown='while receiving Signal Messenger data', errorCouldnt='receive Signal Messenger data')
        return request.json()

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

    def send_message(self, message:str, recipients:list, filenames=None, attachments_as_bytes=None,
                     mentions=None, quote_timestamp=None, quote_author=None, quote_message=None,
                     quote_mentions=None, text_mode="normal"):
        """Send a message to one (or more) recipients.
        
        Supports attachments, styled text, mentioning, and quoting
        
        Args:
            message (str): Message.
            recipients (list): Recipient(s).
            filenames (_type_, optional): _description_.
            attachments_as_bytes (list, optional): Attachment(s) in base64.
            mentions (list, optional): Mention another user. See formatting below.
            quote_timestamp (int, optional): Timestamp of qouted message.
            quote_author (str, optional): The quoted message author.
            quote_message (str, optional): The quoted message content.
            quote_mentions (list, optional): Any mentions contained within the quote.
            text_mode (str, optional): Set text mode ["styled","normal"]. See styled text options below. Defaults to "normal".
        
        Mentions objects should be formatted as dict/JSON and need to contain the following
            author (str): The person you are mention.
            length (int): The length of the mention.
            start (int): The starting character of the mention.
        
        Text styling (must set text_mode to "styled")
            \*italic text*
            \*\*bold text**
            \~strikethrough text~
            ||spoiler||
            \`monospace`
        
        Returns:
            dict Sent message timestamp.
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

        if isinstance(recipients,str): # If sending "recipients" in data, recipients must be sent as a list, even it is a single recipient.
            recipients = [recipients]
        
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

        if "v2" in api_versions:
            data["text_mode"] = text_mode

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
            else:
                return json.loads(resp.content)
        except Exception as exc:
            if exc.__class__ == SignalCliRestApiError:
                raise exc
            raise_from(SignalCliRestApiError(
                "Couldn't send signal message"), exc)
    
    def send_reaction(self, reaction:str, recipient:str, timestamp:int, target_author:str=None):
        """Send (add) a reaction to a message. Uses timestamp to identify the message to react to.
        
        Reacting to a message that you have already reacted to will overwrite the previous reaction.
        
        Warning! Data in reaction and timestamp field is not validated and will not return an error, even if it is wrong.
                
        Args:
            reaction (str): Reaction. Must be an Emoji.
            recipient (str): Message recipient. Eg: +15555555555
            timestamp (int): The timestamp of the target message (the message you want to react to).
            target_author (str, optional): The target message author. If not provided, recipient will be used.

        Returns:
            Nothing is returned.
        """
        target_author = target_author if target_author else recipient
        rawParams = locals().copy()
        url = self._base_url + "/v1/reactions/" + self._number
        data = self._formatParams(rawParams)
        
        self._requester(method='post', url=url, data=data, successCode=204, errorUnknown='while adding reaction', errorCouldnt='add reaction')
    
    def delete_reaction(self, recipient:str, timestamp:int, target_author:str=None): #TODO add docstring
        """Delete (remove) a reaction to a message. Uses timestamp to identify the message.
        
        Warning! Data in timestamp field is not validated and will not return an error, even if it is wrong.  This includes trying to remove a reaction that does not exist.
                
        Args:
            recipient (str): Message recipient. Eg: +15555555555
            timestamp (int): The timestamp of the target message (the message you want to remove the reaction from).
            target_author (str, optional): The target message author. If not provided, recipient will be used.

        Returns:
            Nothing is returned.
        """
        target_author = target_author if target_author else recipient
        rawParams = locals().copy()
        url = self._base_url + "/v1/reactions/" + self._number
        data = self._formatParams(rawParams)
        
        self._requester(method='delete', url=url, data=data, successCode=204, errorUnknown='while removing reaction', errorCouldnt='remove reaction')
    
    def list_attachments(self):
        """List all downloaded attachments."""
        url = self._base_url + "/v1/attachments"
        
        request = self._requester(method='get', url=url, successCode=200, errorUnknown='while listing attachments', errorCouldnt='list attachments')
        return request.json()

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

    def search(self, numbers):
        """Check if one or more phone numbers are registered with the Signal Service."""

        try:
            url = self._base_url + "/v1/search"
            params = {"number": self._number, "numbers": numbers}

            resp = requests.get(url, params=params, auth=self._auth, verify=self._verify_ssl)
            if resp.status_code != 200:
                json_resp = resp.json()
                if "error" in json_resp:
                    raise SignalCliRestApiError(json_resp["error"])
                raise SignalCliRestApiError("Unknown error while searching phone numbers")

            return resp.json()
        except Exception as exc:
            if exc.__class__ == SignalCliRestApiError:
                raise exc
            raise_from(SignalCliRestApiError("Couldn't search for phone numbers: "), exc)
            
    def get_contacts(self):
        """Get all Signal contacts.

        Returns:
            list: List of contacts.
        """
        url = self._base_url + "/v1/contacts/" +self._number
        
        request = self._requester(method='get', url=url, successCode=200, errorUnknown='while updating profile', errorCouldnt='update profile')
        return request.json()
    
    def update_contact(self, contact:str, name:str=None, expiration_in_seconds:int=None):
        """Update a signal Contact. Only works if run as the main device, will not work if linked.

        Args:
            contact (str): Contact number to update.
            name (str, optional): Contact name. Defaults to None.
            expiration_in_seconds (int, optional): Disappearing Messages expiration in seconds. Defaults to None (disabled).
        """
        rawParams = locals().copy()
        url = self._base_url + "/v1/contacts/" + self._number
        data = self._formatParams(rawParams, endpoint='update_contact')
        
        request = self._requester(method='put', url=url, data=data, successCode=204, errorUnknown='while updating profile', errorCouldnt='update profile')
        return request.json()