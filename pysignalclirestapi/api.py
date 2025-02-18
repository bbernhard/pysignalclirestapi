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
        """Format parameters/args/data for API calls.
        
        If endpoint is set to "receive", boolean values will be converted to a string.

        Args:
            params (list): Parameters/args to format
            endpoint (str, optional): Optionally, include an endpoint if specific actions need to be taken with it.

        Returns:
            list: Formatted params/data
        """
        formattedData = {}
        
        params.pop('self')
        # Create a JSON query object
        formattedData = {}
        about = self.about()
        api_versions = about["versions"]
        for item, value in params.items(): # Check params, add anything that isn't blank to the query
            if value !=None:
                # Allow conditional formatting, depending on the endpoint
                if endpoint in ['receive']:
                    value = 'true' if value is True else 'false' if value is False else value # Convert bool to string
                
                elif endpoint in ['send_message']:
                    if "v2" in api_versions:
                        if item == 'attachments_as_bytes':
                            value = [
                                bytes_to_base64(attachment) for attachment in value
                            ]
                            item = 'base64_attachments'

                        elif item == 'filenames':
                            attachments = []
                            for filename in value:
                                with open(filename, "rb") as ofile:
                                    base64_attachment = bytes_to_base64(ofile.read())
                                    attachments.append(base64_attachment)
                            value = attachments
                            item = 'base64_attachments'
                    else:  # fall back to api version 1 to stay downwards compatible
                        if item == 'filenames' and len(value) == 1:
                            with open(value[0], "rb") as ofile:
                                base64_attachment = bytes_to_base64(ofile.read())
                                attachment = base64_attachment
                            value = attachment
                            item = 'base64_attachments'
                   
                elif endpoint in ['update_contact']:
                    item = 'recipient' if item == 'contact' else item # Rename contact to recipient
                
                elif endpoint in ['update_group', 'update_profile']: # Format attachments
                    if item == 'filename':
                        with open(value, "rb") as ofile:
                            value = bytes_to_base64(ofile.read())
                        item = 'base64_avatar'
                    elif item == 'attachment_as_bytes':
                        value = bytes_to_base64(value)
                        item = 'base64_avatar'
                
                elif endpoint in ['verify_indentity'] and item in ['number_to_trust']: # Skip trusted number as it is added to URL.
                    continue
                
                formattedData.update({item : value})
        
        return formattedData
    
    def _requester(self, method, url, data=None, successCode:any=200, errorUnknown=None, errorCouldnt=None):
        """Internal requester

        Args:
            method (str): Rest API method.
            url (str): API url
            data (any, optional): Optional params or JSON data.
            successCode (ant, optional): Success code(s) returned by API call. Defaults to 200.
            errorUnknown (str, optional): Custom error for "unknown error".
            errorCouldnt (str, optional): Custom error for "Couldn't".
        """
        
        params = None
        json = None
        if isinstance(successCode, list):
            pass
        else: # Make it a list
            successCode = [successCode]
        try:
            
            if method in ['post','put','delete']:
                json=data
            
            else:
                params=data

            resp = requests.request(method=method, url=url, params=params, json=json, auth=self._auth, verify=self._verify_ssl)
            if resp.status_code not in successCode:
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
        """Get general information about the API.

        Returns:
            dict: API details.
        """
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

    def create_group(self, name:str, members:list, description:str=None, expiration_time:int=0, group_link:str='disabled', permissions:dict=None):
        """Create a Signal group.

        Args:
            name (str): Group name.
            members (str, list): Member(s) to add.  Will accept a single user as a string, otherwise use a list.
            description (str, optional): Group description.
            eexpiration_time (int, optional): Disappearing Messages expiration in seconds. Defaults to None (disabled).
            group_link (str, optional): Allow users to join from a link.  Options are 'disabled', 'enabled', 'enabled-with-approval'. Defaults to 'disabled'.
            permissions (dict, optional): Set additional permissions (see below).
            
        Permissions:
            add_members (str): Whether group members can add users.  Options are 'only-admins', 'every-member'.  Defaults to 'only-admins'.
            edit_group (str): Whether group members can edit (update) the group.  Options are 'only-admins', 'every-member'.  Defaults to 'only-admins'.

        Returns:
            _type_: Group ID.
        """
        members = [members] if isinstance(members, str) else members
        rawParams = locals().copy()
        
        url = self._base_url + "/v1/groups/" + self._number
        data = self._formatParams(rawParams)
        #TODO confirm whether 200 is ever returned
        request = self._requester(method='post', url=url, data=data, successCode=[201,200], errorUnknown='while creating Signal Messenger group', errorCouldnt='create Signal Messenger group')
        return request.json()

    def list_groups(self):
        """List all Signal groups.
        
        Includes groups you are no longer apart of.
        
        Returns:
            list: Your groups.
        """
        url = self._base_url + "/v1/groups/" + self._number
        
        request = self._requester(method='get', url=url, successCode=200, errorUnknown='while listing Signal Messenger groups', errorCouldnt='list Signal Messenger groups')
        return request.json()
    
    def get_group(self, groupid:str):
        """Get a single Signal group. 

        Args:
            groupid (str): Signal group ID.

        Returns:
            dict: Group details.
        """
        url = self._base_url + "/v1/groups/" + self._number + '/' + str(groupid)
        
        request = self._requester(method='get', url=url, successCode=200, errorUnknown='while getting Signal Messenger group', errorCouldnt='get Signal Messenger group')
        return request.json()
    
    def update_group(self, groupid:str, name:str=None, description:str=None, expiration_time:int=None, filename:str=None, attachment_as_bytes:str=None): #TODO look into rate limiting, maybe thats why it has so much trouble sending
        """Update a signal group.
        
        Use filename OR attachment_as_bytes, not both!
        
        Args:
            groupid (str): Signal group ID.
            name (str, optional): Updated group name.
            description (str, optional): Updated group description.
            expiration_time (int, optional): Disappearing Messages expiration in seconds. Defaults to None (disabled).
            filename (str, optional): Filename of new profile image.
            attachment_as_bytes (str, optional): Attachment(s) in bytes format.
        """
        rawParams = locals().copy()
        if filename is not None and attachment_as_bytes is not None:
            raise_from(SignalCliRestApiError(f"Can't use filename and attachment_as_bytes, please only send one"))
        
        url = self._base_url + "/v1/groups/" + self._number + '/' + str(groupid)
        data = self._formatParams(rawParams, 'update_group')
        # TODO add some sort of confirmation for the user
        request = self._requester(method='put', url=url ,data=data, successCode=204, errorUnknown='while updating Signal Messenger group', errorCouldnt='update Signal Messenger group')
        #return request
    def delete_group(self, groupid:str):
        """Delete a Signal group.

        Args:
            groupid (str): Signal group ID.
        """
        url = self._base_url + "/v1/groups/" + self._number + '/' + str(groupid)
        
        request = self._requester(method='delete', url=url, successCode=200, errorUnknown='while deleting Signal Messenger group', errorCouldnt='delete Signal Messenger group')
    
    def join_group(self, groupid:str):
        """Join a Signal group by ID.

        Args:
            groupid (str): Signal group ID to join.
        """
        
        url = self._base_url + "/v1/groups/" + self._number + '/' + str(groupid) + '/join'
        #TODO if success is not clear, add an additional call to get_group() and return the details
        request = self._requester(method='post', url=url, successCode=204, errorUnknown='while joining Signal Messenger group', errorCouldnt='join Signal Messenger group')
        #return request.json()
    
    def leave_group(self, groupid:str):
        """Leave a Signal group.

        Args:
            groupid (str): Signal group ID.
        """
        url = self._base_url + "/v1/groups/" + self._number + '/' + str(groupid) + '/quit'
        
        request = self._requester(method='post', url=url, successCode=204, errorUnknown='while leaving Signal Messenger group', errorCouldnt='leave Signal Messenger group')
        #return request.json()
    
    def block_group(self, groupid:str):
        """Block a Signal group.

        Args:
            groupid (str): Signal group ID.
        """
        url = self._base_url + "/v1/groups/" + self._number + '/' + str(groupid) + '/block'
        
        request = self._requester(method='post', url=url, successCode=204, errorUnknown='while blocking Signal Messenger group', errorCouldnt='block Signal Messenger group')
        #return request.json()
    
    def add_group_members(self, groupid:str, members:list):
        """Add user(s) (members) to a Signal group.

        Args:
            groupid (str): _Signal group ID.
            members (str, list): Member(s) to add.  Will accept a single user as a string, otherwise use a list.
        """
        members = [members] if isinstance(members,str) else members # Listify! #TODO could this be moved to the data formatter
        
        rawParams = locals().copy()
        url = self._base_url + "/v1/groups/" + self._number + '/' + str(groupid) + '/members'
        data = self._formatParams(rawParams)
        
        request = self._requester(method='post', url=url, data=data, successCode=204, errorUnknown='while adding members to Signal Messenger group', errorCouldnt='add members to Signal Messenger group')
        #TODO add some sort of response?
    
    def remove_group_members(self, groupid:str, members:list):
        """Remove user(s) (members) to a Signal group.

        Args:
            groupid (str): _Signal group ID.
            members (str, list): Member(s) to remove.  Will accept a single user as a string, otherwise use a list.
        """
        members = [members] if isinstance(members, str) else members # Listify! #TODO could this be moved to the data formatter
        
        rawParams = locals().copy()
        url = self._base_url + "/v1/groups/" + self._number + '/' + str(groupid) + '/members'
        data = self._formatParams(rawParams)
        
        request = self._requester(method='delete', url=url, data=data, successCode=204, errorUnknown='while removing members from Signal Messenger group', errorCouldnt='remove members from Signal Messenger group')
            
    def add_group_admins(self, groupid:str, admins:list):
        """Promote user(s) to admin of a Signal group.  User must already be in the group to be promoted.

        Args:
            groupid (str): _Signal group ID.
            admins (str, list): Users(s) to promote.  Will accept a single user as a string, otherwise use a list.
        """
        admins = [admins] if isinstance(admins, str) else admins # Listify! #TODO could this be moved to the data formatter
        
        rawParams = locals().copy()
        url = self._base_url + "/v1/groups/" + self._number + '/' + str(groupid) + '/admins'
        data = self._formatParams(rawParams)
        
        request = self._requester(method='post', url=url, data=data, successCode=204, errorUnknown='while adding admins to Signal Messenger group', errorCouldnt='add admins to Signal Messenger group')
    
    def remove_group_admins(self, groupid:str, admins:list):
        """Demote admin(s) of a Signal group.  Demoting a user will not remove them from the group.

        Args:
            groupid (str): _Signal group ID.
            admins (str, list): Users(s) to demote.  Will accept a single user as a string, otherwise use a list.
        """
        admins = [admins] if isinstance(admins, str) else admins # Listify! #TODO could this be moved to the data formatter
        
        rawParams = locals().copy()
        url = self._base_url + "/v1/groups/" + self._number + '/' + str(groupid) + '/admins'
        data = self._formatParams(rawParams)
        
        request = self._requester(method='delete', url=url, data=data, successCode=204, errorUnknown='while removing admins from Signal Messenger group', errorCouldnt='remove admins from Signal Messenger group')

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

    def update_profile(self, name:str, filename:str=None, attachment_as_bytes:str=None):
        """Update Signal profile.

        Use filename OR attachment_as_bytes, not both!
        
        Args:
            name (str, optional): New profile name.
            filename (str, optional): Filename of new avatar.
            attachment_as_bytes (str, optional): Attachment(s) in bytes format.
        """
        rawParams = locals().copy()
        if filename is not None and attachment_as_bytes is not None:
            raise_from(SignalCliRestApiError(f"Can't use filename and attachment_as_bytes, please only send one"))
        
        url = self._base_url + "/v1/profiles/" + self._number
        data = self._formatParams(rawParams, 'update_group')
        # TODO add some sort of confirmation for the user
        request = self._requester(method='put', url=url ,data=data, successCode=204, errorUnknown='while updating profile', errorCouldnt='update profile')
        #return request

    def send_message(self, message:str, recipients:list, filenames=None, attachments_as_bytes:list=None,
                     mentions:list=None, quote_timestamp:int=None, quote_author:str=None, quote_message:str=None,
                     quote_mentions:list=None, text_mode="normal"):
        """Send a message to one (or more) recipients.
        
        Supports attachments, styled text, mentioning, and quoting if using V2.
        
        Args:
            message (str): Message.
            recipients (list): Recipient(s).
            filenames (str, optional): Filename(s) to be sent.
            attachments_as_bytes (list, optional): Attachment(s) in bytes format (inside a list).
            mentions (list, optional): Mention another user. See formatting below.
            quote_timestamp (int, optional): Timestamp of qouted message.
            quote_author (str, optional): The quoted message author.
            quote_message (str, optional): The quoted message content.
            quote_mentions (list, optional): Any mentions contained within the quote.
            text_mode (str, optional): Set text mode ["styled","normal"]. See styled text options below. Defaults to "normal".
        
        Mention objects should be formatted as dict/JSON and need to contain the following.
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
            dict: Sent message timestamp.
        """
        if isinstance(recipients,str): # If sending "recipients" in data, recipients must be sent as a list, even it is a single recipient.
            recipients = [recipients]
        number = self._number
        
        rawParams = locals().copy()
        # fall back to old api version to stay downwards compatible.
        about = self.about()
        api_versions = about["versions"]
        endpoint = "v2/send"
        if "v2" not in api_versions:
            endpoint = "v1/send"
            
        url = f"{self._base_url}/{endpoint}"

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
        

        data = self._formatParams(rawParams, endpoint='send_message')
        response = self._requester(method='post', url=url, data=data, successCode=201, errorUnknown='while sending message', errorCouldnt='send message')
        return json.loads(response.content)
    
    
        data = {
            "message": message,
            "number": self._number,
            "recipients": recipients,
        }
        #TODO could this all use the _formatter
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
            recipient (str): Message recipient. Eg: +15555555555, or group ID.
            timestamp (int): Message timestamp to add reaction to.
            target_author (str, optional): The target message author. If not provided, recipient will be used.

        Returns:
            Nothing is returned.
        """
        target_author = target_author if target_author else recipient
        rawParams = locals().copy()
        url = self._base_url + "/v1/reactions/" + self._number
        data = self._formatParams(rawParams)
        
        self._requester(method='post', url=url, data=data, successCode=204, errorUnknown='while adding reaction', errorCouldnt='add reaction')
    
    def delete_reaction(self, recipient:str, timestamp:int, target_author:str=None): #TODO if groupID is sent with no recipient ID, throw an error
        """Delete (remove) a reaction to a message. Uses timestamp to identify the message.
        
        Warning! Data in timestamp field is not validated and will not return an error, even if it is wrong.  This includes trying to remove a reaction that does not exist.
                
        Args:
            recipient (str): Message recipient. Eg: +15555555555, or group ID.
            timestamp (int): Message timestamp to remove reaction from.
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
        """Get a list of all files (attachments) in Signal's media folder.

        Returns:
            list: List of files.
        """
        url = self._base_url + "/v1/attachments"
        
        request = self._requester(method='get', url=url, successCode=200, errorUnknown='while listing attachments', errorCouldnt='list attachments')
        return request.json()

    def get_attachment(self, attachment_id:str):
        """Get a signal file (attachment) in bytes.

        Args:
            attachment_id (str): File (attachment) name.


        Returns:
            bytes: Attachment in bytes.
        """
        url = self._base_url + "/v1/attachments/" + attachment_id
        request = self._requester(method='get', url=url, successCode=200, errorUnknown='while getting attachment', errorCouldnt='get attachment')
        return request.content

    def delete_attachment(self, attachment_id):
        """Delete file (attachment) from filesystem

        Args:
            attachment_id (str): File (attachment) name.
        """

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
        """Get all Signal contacts for your account.

        Returns:
            list: List of contacts.
        """
        url = self._base_url + "/v1/contacts/" +self._number
        
        request = self._requester(method='get', url=url, successCode=200, errorUnknown='while updating profile', errorCouldnt='update profile')
        return request.json()
    
    def update_contact(self, contact:str, name:str=None, expiration_in_seconds:int=None):
        """Update a signal Contact.  Must be the main device.  If you linked your account to SignalCli via a QR code, this won't work.

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
    
    def sync_contacts(self):
        """Send a synchronization message with the local contacts list to all linked devices. This command should only be used if this is the primary device.
        """
        
        url = self._base_url + "/v1/contacts/" + self._number +'/sync'
        self._requester(method='post', url=url, successCode=204, errorUnknown='while updating profile', errorCouldnt='update profile')
    
    def send_receipt(self, recipient:str, timestamp:int, receipt_type:str='read'):
        """Mark a message as read or viewed.

        Args:
            recipient (str): _Message recipient. Eg: +15555555555, or group ID.
            timestamp (int): Message timestamp to mark as read/viewed.
            receipt_type (str, optional): Receipt type.  Can be 'read' or 'viewed'. Defaults to 'read'.
        """
        
        rawParams = locals().copy()
        url = self._base_url + "/v1/receipts/" + self._number
        data = self._formatParams(rawParams)
        
        request = self._requester(method='post', url=url, data=data, successCode=204, errorUnknown='while sending receipt', errorCouldnt='send receipt')
        #return request.json() #TODO confirm if this returns anything
        
    def list_indentities(self):
        """List all identities for your Signal account.
        
        Order of identities may change between calls

        Returns:
            list: List of identities.
        """

        url = self._base_url + "/v1/identities/" + self._number
        
        request = self._requester(method='get', url=url, successCode=200, errorUnknown='getting identities', errorCouldnt='get identities')
        return request.json()
    
    def verify_indentity(self, number_to_trust:str, verified_safety_number:str, trust_all_known_keys:bool=False):
        """Verify/Trust an identity.

        Args:
            number_to_trust (str): Number to mark as verified/trusted.
            verified_safety_number (str): Safety number of identity.  Can be gotten from list_identities()
            trust_all_known_keys (bool, optional): If set to True, all known keys of this user are trusted.  Only recommended for testing!  Defaults to False.
        """
        
        rawParams = locals().copy()
        url = self._base_url + "/v1/identities/" + self._number +'/trust/' + number_to_trust
        data = self._formatParams(rawParams, endpoint='verify_indentity')
        
        request = self._requester(method='put', url=url, data=data, successCode=204, errorUnknown='while verifying identity', errorCouldnt='verify identity')