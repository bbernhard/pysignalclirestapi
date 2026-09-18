"""SignalCliRestApi Python library."""

import base64
import json
import ssl
from token import OP
from urllib.parse import urlencode
from abc import ABC, abstractmethod
from requests.models import HTTPBasicAuth
from six import raise_from
import requests
from .helpers import bytes_to_base64
from typing import Optional


class SignalCliRestApiError(Exception):
    """SignalCliRestApiError base class."""
    pass


class SignalCliRestApiAuth(ABC):
    """SignalCliRestApiAuth base class."""

    @abstractmethod
    def get_auth(self):
        pass


class SignalCliRestApiHTTPBasicAuth(SignalCliRestApiAuth):
    """SignalCliRestApiHTTPBasicAuth offers HTTP basic authentication."""

    def __init__(self, basic_auth_user:str, basic_auth_pwd:str):
        self._auth = HTTPBasicAuth(basic_auth_user, basic_auth_pwd)

    def get_auth(self):
        return self._auth


class SignalCliRestApi(object):
    """SignalCliRestApi implementation."""

    def __init__(self, base_url:str, number:str, auth:Optional[any] = None, verify_ssl:bool = True):
        """Initialize the class."""
        super(SignalCliRestApi, self).__init__()
        self._session = requests.Session()
        self._base_url = base_url
        self._number = number
        self._verify_ssl = verify_ssl
        
        if auth:
            assert issubclass(
                type(auth), SignalCliRestApiAuth), "Expecting a subclass of SignalCliRestApiAuth as auth parameter"
            self._auth = auth.get_auth()
        else:
            self._auth = None

        self._mode = self.mode() # init mode for receive with websockets
    
    #TODO should this be called from _requester to reduce reduncancy?
    def _format_params(self, params, endpoint:Optional[str] = None): 
        """Format parameters/args/data for API calls.
        
        If endpoint is set to "receive", boolean values will be converted to a string.

        Args:
            params (list): Parameters/args to format
            endpoint (str, optional): Optionally, include an endpoint if specific actions need to be taken with it.

        Returns:
            list: Formatted params/data
        """

        # Create a JSON query object
        formatted_data = {}
        about = self.about()
        api_versions = about["versions"]
        
        for item, value in params.items(): # Check params, add anything that isn't blank to the query
            if value !=None:
                # Allow conditional formatting, depending on the endpoint
                if endpoint in ['receive', 'list_groups']: # This is still needed as of 2025/03/19, but only for receive endpoint?
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
                            
                elif item in ['members', 'admins']: # Convert single user sent as string to a list to prevent error
                    value = [value] if isinstance(value, str) else value
                
                elif endpoint in ['update_group', 'update_profile']: # Format attachments
                    if item == 'filename':
                        with open(value, "rb") as ofile:
                            value = bytes_to_base64(ofile.read())
                        item = 'base64_avatar'
                    elif item == 'attachment_as_bytes':
                        value = bytes_to_base64(value)
                        item = 'base64_avatar'
                
                formatted_data.update({item : value})
        
        return formatted_data
    
    def _requester(self, method:str, url:str, data:Optional[dict] = None, success_code:list[int] | int = 200, error_unknown:Optional[str] = None, error_couldnt:Optional[str] = None):
        """Internal requester

        Args:
            method (str): Rest API method.
            url (str): API url
            data (dict, optional): Optional params or JSON data.
            success_code (list[int] | int, optional): Success code(s) returned by API call. Defaults to 200.
            error_unknown (str, optional): Custom error for "unknown error".
            error_couldnt (str, optional): Custom error for "Couldn't".
        """
        #TODO try to move formatter here
        #if data: 
            #self._format_params(params)
        params = None
        json = None
        
        if isinstance(success_code, int):
            success_code = [success_code]
            
        try:
            
            if method in ['post','put','delete']:
                json=data
            
            else:
                params=data

            resp = self._session.request(method=method, url=url, params=params, json=json, auth=self._auth, verify=self._verify_ssl)
            if resp.status_code not in success_code:
                json_resp = resp.json()
                if "error" in json_resp:
                    raise SignalCliRestApiError(json_resp["error"])
                raise SignalCliRestApiError(
                    f"Unknown error {error_unknown}")
            else:
                return resp # Return raw response for now
        except Exception as exc:
            if exc.__class__ == SignalCliRestApiError:
                raise exc
            raise_from(SignalCliRestApiError(f"Couldn't {error_couldnt}: "), exc)
    
    #GET /v1/about
    def about(self) -> dict:
        """Get general API information including capabilities, API version, and what mode is being used.

        Returns:
            dict: API information.
        """
        
        resp = requests.get(self._base_url + "/v1/about", auth=self._auth, verify=self._verify_ssl)
        if resp.status_code == 200:
            return resp.json()
        
        else:
            # This is likely an auth error
            raise_from(SignalCliRestApiError("Failed to get API infomration"), resp.raise_for_status())
            
    def api_info(self): #TODO should this be removed?
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

    def has_capability(self, endpoint, capability, about=None): #TODO should this be _has_capability?
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
    
    #GET /v1/health
    #TODO is this needed at all?
    def _check_health(self):
        url = self._base_url + "/v1/health"
        request = self._requester(method='get', url=url, success_code=204, error_unknown='while checking Signal Docker Container health', error_couldnt='get Signal Docker Container health')
        # I don't think there is any response data
        #return request.json()

    # # # GROUPS # # #
    #TODO get rid of the extra shit and just return the id
    # POST /v1/groups/{number}
    def create_group(self, name:str, members:list, description:Optional[str] = None, expiration_time:int=0, group_link:str='disabled', permissions:Optional[dict] = None) -> dict:
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
            dict: Group ID.
        """
        members = [members] if isinstance(members, str) else members
        params = {
            'name': name,
            'members': members,
            'description': description,
            'expiration_time': expiration_time,
            'group_link': group_link,
            'permissions': permissions
            }
        
        url = self._base_url + "/v1/groups/" + self._number
        data = self._format_params(params)
        #TODO confirm whether 200 is ever returned
        request = self._requester(method='post', url=url, data=data, success_code=[201,200], error_unknown='while creating Signal Messenger group', error_couldnt='create Signal Messenger group')
        return request.json()

    #TODO expand doesn't seem to do shit
    # GET /v1/groups/{number}
    def list_groups(self, expand:bool = False):
        """List all Signal groups.
        
        Includes groups you are no longer apart of.

        Args:
            expand (bool, optional): Expand the response to show more details. Defaults to False.

        Returns:
            list: Your groups
        """
        
        
        url = self._base_url + "/v1/groups/" + self._number
        
        request = self._requester(method='get', url=url, data = self._format_params({"expand": expand}, endpoint="list_groups"), success_code=200, error_unknown='while listing Signal Messenger groups', error_couldnt='list Signal Messenger groups')
        return request.json()
    
    # GET /v1/groups/{number}/{groupid}
    def get_group(self, groupid:str):
        """Get a single Signal group. 

        Args:
            groupid (str): Signal group ID.

        Returns:
            dict: Group details.
        """
        url = self._base_url + "/v1/groups/" + self._number + '/' + str(groupid)
        
        request = self._requester(method='get', url=url, success_code=200, error_unknown='while getting Signal Messenger group', error_couldnt='get Signal Messenger group')
        return request.json()
    
    # PUT /v1/groups/{number}/{groupid}
    def update_group(self, groupid:str, name:Optional[str] = None, description:Optional[str] = None, expiration_time:Optional[int] = None, filename:Optional[str] = None, attachment_as_bytes:Optional[str] = None):
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
        params = {
            'groupid': groupid,
            'name': name,
            'description': description,
            'expiration_time': expiration_time,
            'filename': filename,
            'attachment_as_bytes': attachment_as_bytes
            }
        
        if filename is not None and attachment_as_bytes is not None:
            raise SignalCliRestApiError(f"Can't use filename and attachment_as_bytes, please only send one")
        
        url = self._base_url + "/v1/groups/" + self._number + '/' + str(groupid)
        data = self._format_params(params, 'update_group')
        # TODO add some sort of confirmation for the user
        request = self._requester(method='put', url=url ,data=data, success_code=204, error_unknown='while updating Signal Messenger group', error_couldnt='update Signal Messenger group')
        #return request
    
    # DELETE /v1/groups/{number}/{groupid}
    def delete_group(self, groupid:str):
        """Delete a Signal group.

        Args:
            groupid (str): Signal group ID.
        """
        url = self._base_url + "/v1/groups/" + self._number + '/' + str(groupid)
        
        request = self._requester(method='delete', url=url, success_code=200, error_unknown='while deleting Signal Messenger group', error_couldnt='delete Signal Messenger group')
    
    # POST /v1/groups/{number}/{groupid}/join
    def join_group(self, groupid:str):
        """Join a Signal group by ID.

        Args:
            groupid (str): Signal group ID to join.
        """
        
        url = self._base_url + "/v1/groups/" + self._number + '/' + str(groupid) + '/join'
        #TODO if success is not clear, add an additional call to get_group() and return the details
        request = self._requester(method='post', url=url, success_code=204, error_unknown='while joining Signal Messenger group', error_couldnt='join Signal Messenger group')
        #return request.json()
    
    # POST /v1/groups/{number}/{groupid}/quit
    def leave_group(self, groupid:str):
        """Leave a Signal group.

        Args:
            groupid (str): Signal group ID.
        """
        url = self._base_url + "/v1/groups/" + self._number + '/' + str(groupid) + '/quit'
        
        request = self._requester(method='post', url=url, success_code=204, error_unknown='while leaving Signal Messenger group', error_couldnt='leave Signal Messenger group')
        #return request.json()
    
    # POST /v1/groups/{number}/{groupid}/block
    def block_group(self, groupid:str):
        """Block a Signal group.

        Args:
            groupid (str): Signal group ID.
        """
        url = self._base_url + "/v1/groups/" + self._number + '/' + str(groupid) + '/block'
        
        request = self._requester(method='post', url=url, success_code=204, error_unknown='while blocking Signal Messenger group', error_couldnt='block Signal Messenger group')
        #return request.json()
    
    # POST /v1/groups/{number}/{groupid}/members
    def add_group_members(self, groupid:str, members:list):
        """Add user(s) (members) to a Signal group.

        Args:
            groupid (str): _Signal group ID.
            members (str, list): Member(s) to add.  Will accept a single user as a string, otherwise use a list.
        """
        
        params = {
            'groupid': groupid,
            'members': members
            }
        
        url = self._base_url + "/v1/groups/" + self._number + '/' + str(groupid) + '/members'
        data = self._format_params(params)
        
        request = self._requester(method='post', url=url, data=data, success_code=204, error_unknown='while adding members to Signal Messenger group', error_couldnt='add members to Signal Messenger group')
        pass
        #TODO add some sort of response?
    
    # DELETE /v1/groups/{number}/{groupid}/members
    def remove_group_members(self, groupid:str, members: str | list[str] ):
        """Remove user(s) (members) to a Signal group.

        Args:
            groupid (str): _Signal group ID.
            members (str | list[str]): Member(s) to remove.  Will accept a single user as a string, otherwise use a list.
        """

        params = {
            'groupid': groupid,
            'members': members
            }
        
        url = self._base_url + "/v1/groups/" + self._number + '/' + str(groupid) + '/members'
        data = self._format_params(params)
        
        request = self._requester(method='delete', url=url, data=data, success_code=204, error_unknown='while removing members from Signal Messenger group', error_couldnt='remove members from Signal Messenger group')
    
    # POST /v1/groups/{number}/{groupid}/admins     
    def add_group_admins(self, groupid:str, admins:list):
        """Promote user(s) to admin of a Signal group.  User must already be in the group to be promoted.

        Args:
            groupid (str): _Signal group ID.
            admins (str, list): Users(s) to promote.  Will accept a single user as a string, otherwise use a list.
        """
        
        params = {
            'groupid': groupid,
            'admins': admins
            }
        
        url = self._base_url + "/v1/groups/" + self._number + '/' + str(groupid) + '/admins'
        data = self._format_params(params)
        
        request = self._requester(method='post', url=url, data=data, success_code=204, error_unknown='while adding admins to Signal Messenger group', error_couldnt='add admins to Signal Messenger group')
    
    # DELETE /v1/groups/{number}/{groupid}/admins
    def remove_group_admins(self, groupid:str, admins:list):
        """Demote admin(s) of a Signal group.  Demoting a user will not remove them from the group.

        Args:
            groupid (str): _Signal group ID.
            admins (str, list): Users(s) to demote.  Will accept a single user as a string, otherwise use a list.
        """
        
        unformatted_data = {
            'groupid': groupid,
            'admins': admins
            }
        
        url = self._base_url + "/v1/groups/" + self._number + '/' + str(groupid) + '/admins'
        data = self._format_params(unformatted_data)
        
        request = self._requester(method='delete', url=url, data=data, success_code=204, error_unknown='while removing admins from Signal Messenger group', error_couldnt='remove admins from Signal Messenger group')
        
    # # # MESSAGES # # #
    def _ws_url_for_receive(self, data: dict) -> str:
        """Convert base_url (http/https) + receive endpoint to ws/wss URL with query params.
        
        Args:
            data (dict): Formatted parameters
        
        Returns: 
            str: Websocket URL
        """
        base = self._base_url.rstrip("/")
        if base.startswith("https://"):
            ws_base = "wss://" + base.removeprefix("https://")
        elif base.startswith("http://"):
            ws_base = "ws://" + base.removeprefix("http://")
        else:
            # If user provided host:port without scheme, default to ws://
            ws_base = "ws://" + base

        query = urlencode({k: v for k, v in (data or {}).items() if v is not None})
        path = f"/v1/receive/{self._number}"
        return f"{ws_base}{path}" + (f"?{query}" if query else "")

    def _ws_headers(self) -> dict:
        """
        WebSocket handshake headers. Supports HTTP Basic auth if configured via SignalCliRestApiHTTPBasicAuth.
        """
        headers = {}
        if isinstance(self._auth, HTTPBasicAuth):
            user = getattr(self._auth, "username", None)
            pwd = getattr(self._auth, "password", None)
            if user is not None and pwd is not None:
                token = base64.b64encode(f"{user}:{pwd}".encode("utf-8")).decode("ascii")
                headers["Authorization"] = f"Basic {token}"
        return headers

    
    async def stream_messages(self):
        """Stream messages via websocket (API must be in 'json-rpc; mode)

        Yields:
            dict: Single envelope (message)
        """
        if self._mode != "json-rpc":
            raise SignalCliRestApiError(
                "API is not in json-rpc mode. Use `receive()`"
            )
        try:
            import websockets 
        
        except Exception as exc:
            raise_from(
                SignalCliRestApiError("websockets package is required for json-rpc receive"),
                exc,
            )

        # Params don't work with websocket
        ws_url = self._ws_url_for_receive(data = {})

        ssl_ctx = None
        if ws_url.startswith("wss://"):
            ssl_ctx = ssl.create_default_context()
            if not self._verify_ssl:
                ssl_ctx.check_hostname = False
                ssl_ctx.verify_mode = ssl.CERT_NONE

        try:
            async with websockets.connect(
                uri = ws_url,
                additional_headers=self._ws_headers() or None,
                ssl=ssl_ctx,
            ) as websocket:
                # Yield the messages instead of storing them in a list
                async for raw in websocket:
                    try:
                        yield json.loads(raw)
                    except json.JSONDecodeError:
                        continue
        
        except websockets.InvalidURI as exc:
            error_message:str = "WebSocket connection failed: "
            # If the exception was caused by an invalid status, it's probably because the `base_url` is set to http, which makes the websocket start with `ws`. The proxy server tries to upgrade the connection, resulting in an HTTP 301 error
            exc_context = exc.__context__
            if isinstance(exc_context, websockets.InvalidStatus):
                # This confirms that the issue is caused by the something (probably the proxy) trying to redirect/upgrade the connection
                #TODO it might be worth checking for other redirect codes?
                if exc_context.args[0].status_code == 301:
                    error_message += "The server returned a redirect. This typically occurs when a secure connection is required. Ensure your API base URL starts with 'https://'."
                    
                else:
                    error_message += exc.msg
            
            else:
                error_message += exc.msg
            raise_from(
                    SignalCliRestApiError(error_message),
                    exc,
                )
        except Exception as exc:
            raise_from(
                SignalCliRestApiError("Couldn't receive Signal Messenger data via websocket"),
                exc,
            )
        
    #TODO complete docstring
    # GET /v1/receive/{number}
    def receive(
        self,
        ignore_attachments:bool = False,
        ignore_stories:bool = False,
        send_read_receipts:bool = False,
        max_messages:Optional[int] = None,
        timeout:int = 1,
    ) -> list[dict]:
        """Receive (get) Signal Messages from the Signal Network.
        
        Args:
            ignore_attachments (bool, optional): If True, attachments will be ignored. Defaults to False.
            ignore_stories (bool, optional): If True, stories will be ignored. Defaults to False.
            send_read_receipts (bool, optional): If True, read receipts will be sent for received messages. Defaults to False.
            
        Returns:
            list: List of messages
        """
        if self._mode == "json-rpc":
            raise SignalCliRestApiError(
                "API is in json-rpc mode. use `stream_messages()`"
            )

        params = {
            "ignore_attachments": ignore_attachments,
            "ignore_stories": ignore_stories,
            "send_read_receipts": send_read_receipts,
            "max_messages": max_messages,
            "timeout": timeout,
        }

        url = self._base_url + "/v1/receive/" + self._number
        data = self._format_params(params=params, endpoint="receive")

        request = self._requester(
            method="get",
            url=url,
            data=data,
            success_code=200,
            error_unknown="while receiving Signal Messenger data",
            error_couldnt="receive Signal Messenger data",
        )
        return request.json()

    
    #TODO use string literal for the text_mode?
    # POST /v2/send
    def send_message(self, 
        message:str,
        recipients:list,
        edit_timestamp:Optional[int] = None,
        notify_self:bool=False,
        filenames=None,
        attachments_as_bytes:Optional[list] = None,
        mentions:Optional[list] = None,
        quote_timestamp:Optional[int] = None,
        quote_author:Optional[str] = None,
        quote_message:Optional[str] = None,
        quote_mentions:Optional[list] = None,
        text_mode="normal"
        ):
        """Send a message to one (or more) recipients.
        
        Supports attachments, styled text, mentioning, and quoting if using V2.
        
        Args:
            message (str): Message.
            recipients (list): Recipient(s).
            notify_self (bool, optional): Requires API version 0.92+. If True, other devices linked to the same account will get a notification for messages you send. Defaults to False (no notification).
            filenames (str, optional): Filename(s) to be sent.
            edit_timestamp (int, optional): Timestamp of message to edit.
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
            \\*italic text*
            \\*\\*bold text**
            \\~strikethrough text~
            ||spoiler||
            \\`monospace`
            
        
        Returns:
            dict: Message timestamp.
        """
        if isinstance(recipients, str): # If sending "recipients" in data, recipients must be sent as a list, even it is a single recipient.
            recipients = [recipients]
        
        params = {
            'message': message,
            'recipients':recipients,
            'notify_self': notify_self,
            'edit_timestamp': edit_timestamp,
            'filenames': filenames,
            'attachments_as_bytes': attachments_as_bytes,
            'mentions': mentions,
            'quote_timestamp': quote_timestamp,
            'quote_author': quote_author,
            'quote_message': quote_message,
            'quote_mentions': quote_mentions,
            'text_mode':text_mode,
            'number':self._number # whoops, thats kind of important to have
            }
        
        # fall back to old api version to stay downwards compatible.
        about = self.about()
        api_versions = about["versions"]
        endpoint = "v2/send"
        if "v2" not in api_versions:
            endpoint = "v1/send"
            
        url =  self._base_url + f'/{endpoint}'

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
        

        data = self._format_params(params, endpoint='send_message')
        response = self._requester(method='post', url=url, data=data, success_code=201, error_unknown='while sending message', error_couldnt='send message')
        return json.loads(response.content)
    
    # DELETE /v1/remote-delete/{number}
    def delete_message(self,
        recipient:str,
        timestamp:int
        )-> dict:
        """Delete a Signal message.

        Args:
            recipient (str): Original message recipient.
            timestamp (int): Message timestamp

        Returns:
            dict: A new timestamp for the deleted message (im not sure what you can do with this though)
        """
        params = {
            "recipient": recipient,
            "timestamp": timestamp
        }
        
        url = self._base_url + "/v1/remote-delete/" + self._number
        data = self._format_params(params)
        
        resp = self._requester(method='delete', url=url, data=data, success_code=201, error_unknown='while deleting message', error_couldnt='delete message')
        return resp.json()
    
    # PUT /v1/typing-indicator/{number}
    def show_typing_indicator(self, recipient:str):
        """Show a typing indicator

        Args:
            recipients (str): Recipient.
        """
        params = {
            "recipient": recipient
        }
        
        url = self._base_url + "/v1/typing-indicator/" + self._number
        data = self._format_params(params)
        
        resp = self._requester(method='put', url=url, data=data, success_code=204, error_unknown='while showing typing indicator', error_couldnt='show typing indicator')
        return resp.json()
    
    # DELETE /v1/typing-indicator/{number}
    def hide_typing_indicator(self, recipient:str):
        """Hide a typing indicator

        Args:
            recipients (str): Recipient.
        """
        params = {
            "recipient": recipient
        }
        
        url = self._base_url + "/v1/typing-indicator/" + self._number
        data = self._format_params(params)
        
        resp = self._requester(method='delete', url=url, data=data, success_code=204, error_unknown='while hiding typing indicator', error_couldnt='hide typing indicator')
        return resp.json()
    
    # # # PROFILES # # #
    # PUT /v1/profiles/{number}
    def update_profile(self, name:str, filename:Optional[str] = None, attachment_as_bytes:Optional[bytes] = None):
        """Update Signal profile.

        Use filename OR attachment_as_bytes, not both!
        
        Args:
            name (str, optional): New profile name.
            filename (str, optional): Filename of new avatar.
            attachment_as_bytes (bytes, optional): Attachment(s) in bytes format.
        """
        params = {
            'name': name,
            'filename':filename,
            'attachment_as_bytes': attachment_as_bytes
            }
        
        if filename is not None and attachment_as_bytes is not None:
            SignalCliRestApiError(f"Provide filename or attachment_as_bytes, not both!")
        
        url = self._base_url + "/v1/profiles/" + self._number
        data = self._format_params(params, 'update_group')
        # TODO add some sort of confirmation for the user
        request = self._requester(method='put', url=url ,data=data, success_code=204, error_unknown='while updating profile', error_couldnt='update profile')
        #return request
    
    # # # REACTIONS # # #
    # POST /v1/reactions/{number}
    def add_reaction(self, reaction:str, recipient:str, timestamp:int, target_author:Optional[str] = None):
        """Add (send) a reaction to a message. Uses timestamp to identify the message to react to.
        
        Reacting to a message that you have already reacted to will overwrite the previous reaction.
        
        Warning! Data in reaction and timestamp field is not validated and will not return an error, even if it is wrong.
                
        Args:
            reaction (str): Reaction. Must be an Emoji.
            recipient (str): Message recipient. Eg: +15555555555. NOTE: As of 2026/03/27, this does not work with group IDs. Instead, use the recipients number.
            timestamp (int): Message timestamp to add reaction to.
            target_author (str, optional): The target message author. If not provided, recipient will be used.

        Returns:
            Nothing is returned.
        """
        # If target author isn't provided, default to recipient
        target_author = target_author if target_author else recipient
        
        params = {
            'reaction': reaction,
            'recipient': recipient,
            'timestamp': timestamp,
            'target_author': target_author
            }
        
        url = self._base_url + "/v1/reactions/" + self._number
        data = self._format_params(params)
        
        self._requester(method='post', url=url, data=data, success_code=204, error_unknown='while adding reaction', error_couldnt='add reaction')
    
    # DELETE /v1/reactions/{number}
    def remove_reaction(self, recipient:str, timestamp:int, target_author:Optional[str] = None): #TODO if groupID is sent with no recipient ID, throw an error
        """Remove (delete) a reaction to a message. Uses timestamp to identify the message.
        
        Warning! Data in timestamp field is not validated and will not return an error, even if it is wrong.  This includes trying to remove a reaction that does not exist.
                
        Args:
            recipient (str): Message recipient. Eg: +15555555555, or group ID.
            timestamp (int): Message timestamp to remove reaction from.
            target_author (str, optional): The target message author. If not provided, recipient will be used. 

        Returns:
            Nothing is returned.
        """
        target_author = target_author if target_author else recipient
        
        params = {
            'recipient': recipient,
            'timestamp': timestamp,
            'target_author': target_author
            }
        
        url = self._base_url + "/v1/reactions/" + self._number
        data = self._format_params(params)
        
        self._requester(method='delete', url=url, data=data, success_code=204, error_unknown='while removing reaction', error_couldnt='remove reaction')
    
    # # # ATTACHMENTS # # #
    # GET /v1/attachments
    def list_attachments(self):
        """Get a list of all files (attachments) in Signal's media folder.

        Returns:
            list: List of files.
        """
        url = self._base_url + "/v1/attachments"
        
        request = self._requester(method='get', url=url, success_code=200, error_unknown='while listing attachments', error_couldnt='list attachments')
        return request.json()
    
    # GET /v1/attachments/{attachment}
    def get_attachment(self, attachment_id:str) -> bytes:
        """Get a signal file (attachment) in bytes

        Args:
            attachment_id (str): File (attachment) ID.


        Returns:
            bytes: Attachment in bytes.
        """
        url = self._base_url + "/v1/attachments/" + attachment_id
        
        request = self._requester(method='get', url=url, success_code=200, error_unknown='while getting attachment', error_couldnt='get attachment')
        return request.content
    
    # DELETE /v1/attachments/{attachment}
    def delete_attachment(self, attachment_id):
        """Delete file (attachment) from filesystem

        Args:
            attachment_id (str): File (attachment) ID.
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

    # # # SEARCH # # #
    # GET v1/search/{number}
    def search(self, numbers: list | str):
        """Check if one or more phone numbers are registered with the Signal Service.

        Args:
            numbers (list | str): Number(s) to check. Ensure numbers are E.164 formatted

        Returns:
            list[dict]: Result(s) for number(s) checked
        """
        
        if isinstance(numbers, str): # If sending "recipients" in data, recipients must be sent as a list, even it is a single recipient.
            numbers = [numbers]
        
        url = self._base_url + "/v1/search/" + self._number
        params = {
            "numbers": numbers
            }
        data = self._format_params(params)
        
        resp = self._requester(method="get", url=url, data=data, success_code=[200], error_couldnt="search number(s)", error_unknown="while searching number(s)")
        return resp.json()

    # # # CONTACTS # # #
    # GET /v1/contacts/{number}
    def list_contacts(self):
        """Get all Signal contacts for your account.

        Returns:
            list: List of contacts.
        """
        url = self._base_url + "/v1/contacts/" +self._number
        
        request = self._requester(method='get', url=url, success_code=200, error_unknown='while updating profile', error_couldnt='update profile')
        return request.json()
    
    # PUT /v1/contacts/{number}
    def update_contact(self, contact:str, name:Optional[str] = None, expiration_in_seconds:Optional[int] = None):
        """Update a signal Contact.  Must be the main device.  If you linked your account to SignalCli via a QR code, this won't work.

        Args:
            contact (str): Contact number to update.
            name (str, optional): Contact name. Defaults to None.
            expiration_in_seconds (int, optional): Disappearing Messages expiration in seconds. Defaults to None (disabled).
        """
        params = {
            'recipient': contact, # Field is actually named recipient, but I think it makes more sense to cal it contact
            'name': name,
            'expiration_in_seconds': expiration_in_seconds
            }
        
        url = self._base_url + "/v1/contacts/" + self._number
        data = self._format_params(params)
        
        request = self._requester(method='put', url=url, data=data, success_code=204, error_unknown='while updating profile', error_couldnt='update profile')
        return request.json()
    
    # POST /v1/contacts/{number}/sync
    def sync_contacts(self):
        """Send a synchronization message with the local contacts list to all linked devices. This command should only be used if this is the primary device.
        """
        
        url = self._base_url + "/v1/contacts/" + self._number +'/sync'
        self._requester(method='post', url=url, success_code=204, error_unknown='while updating profile', error_couldnt='update profile')
    
    # # # RECEIPTS # # #
    # POST /v1/receipts/{number}
    def send_receipt(self, recipient:str, timestamp:int, receipt_type:str='read'):
        """Mark a message as read or viewed.  See the difference between read and viewed below.
        
        From AsamK, the signal-cli maintainer:  "viewed" receipts are used e.g. for voice notes. When the user sees the voice note, a "read" receipt is sent, when the user has listened to the voice note, a "viewed" receipt is sent (displayed as a blue dot in the apps).

        Args:
            recipient (str): Message recipient. Eg: +15555555555. NOTE: As of 2026/03/27, this does not work with group IDs. Instead, use the recipients number.
            timestamp (int): Message timestamp to mark as read/viewed.
            receipt_type (str, optional): Receipt type.  Can be 'read', 'viewed'. Defaults to 'read'.
        """
        
        params = {
            'recipient': recipient,
            'timestamp': timestamp,
            'receipt_type': receipt_type
            }
        url = self._base_url + "/v1/receipts/" + self._number
        data = self._format_params(params)
        
        request = self._requester(method='post', url=url, data=data, success_code=204, error_unknown='while sending receipt', error_couldnt='send receipt')
        #return request.json() #TODO confirm if this returns anything
    
    # # # IDENTITIES # # #
    def list_indentities(self):
        """List all identities for your Signal account.
        
        Order of identities may change between calls

        Returns:
            list: List of identities.
        """
        print("DEPRECATION WARNING: 'list_indentities' will be removed in future release as it was a mis-spelling. Use 'list_identities' going forward!")
        return self.list_identities()
    
    # GET /v1/identities/{number}
    def list_identities(self):
        """List all identities for your Signal account.
        
        Order of identities may change between calls

        Returns:
            list: List of identities.
        """

        url = self._base_url + "/v1/identities/" + self._number
        
        request = self._requester(method='get', url=url, success_code=200, error_unknown='getting identities', error_couldnt='get identities')
        return request.json()
    
    def verify_indentity(self, number_to_trust:str, verified_safety_number:str, trust_all_known_keys:bool=False):
        """Verify/Trust an identity.

        Args:
            number_to_trust (str): Number to mark as verified/trusted.
            verified_safety_number (str): Safety number of identity.  Can be gotten from list_identities()
            trust_all_known_keys (bool, optional): If set to True, all known keys of this user are trusted.  Only recommended for testing!  Defaults to False.
        """
        print("DEPRECATION WARNING: 'verify_indentity' will be removed in future release as it was a mis-spelling. Use 'verify_identity' going forward!")
        self.verify_identity(identity_to_trust=number_to_trust, verified_safety_number=verified_safety_number, trust_all_known_keys=trust_all_known_keys)
    
    # PUT /v1/identities/{number}/trust/{numberToTrust}
    def verify_identity(self, identity_to_trust:str, verified_safety_number:str, trust_all_known_keys:bool=False):
        """Verify/Trust an identity.

        Args:
            identity_to_trust (str): Number or UUID to mark as verified/trusted.
            verified_safety_number (str): Safety number of identity.  Can be gotten from list_identities()
            trust_all_known_keys (bool, optional): If set to True, all known keys of this user are trusted.  Only recommended for testing!  Defaults to False.
        """
        
        params = {
            'verified_safety_number': verified_safety_number,
            'trust_all_known_keys': trust_all_known_keys
            }
        url = self._base_url + "/v1/identities/" + self._number +'/trust/' + identity_to_trust
        data = self._format_params(params)
        
        request = self._requester(method='put', url=url, data=data, success_code=204, error_unknown='while verifying identity', error_couldnt='verify identity')
    
    # # # DEVICES # # #
    # GET /v1/qrcodelink
    def link_with_qr(self, device_name:str, qrcode_version:int=10):
        """Generate QR code to link a device

        Args:
            device_name (str): Device name.
            qrcode_version (int, optional): QRCode version. Defaults to 10.

        Returns:
            str: base64 encoded QR code PNG.
        """
        url = self._base_url + "/v1/qrcodelink"
        
        params = {
            'device_name': device_name,
            'qrcode_version':  qrcode_version
            }
        
        data = self._format_params(params=params)
        
        request = self._requester(method='get', url=url, data=data, success_code=200, error_unknown='generating QR code', error_couldnt='generate QR code')
        return bytes_to_base64(request.content)
    
    # GET /v1/qrcodelink/raw
    def get_device_uri(self, device_name: str):
        """Generate the deviceLinkUri string for linking without scanning a QR code.
        

        Args:
            device_name (str): Device name.

        Returns:
            str: Device Link Uri
        """
        url = self._base_url + "/v1/qrcodelink/raw"
        params = {
            'device_name': device_name,
            }
        
        data = self._format_params(params=params)
        
        resp = self._requester(method='get', url=url, data=data, success_code=200, error_unknown='generating deviceLinkUri', error_couldnt='generate deviceLinkUrie')
        return resp.json().get("device_link_uri")
    
    #TODO this will raise an exception if you try to register a number that is already set up with the API
    #TODO this doesn't check if the number is already registered elsewhere, which I think is fine?
    # POST /v1/register/{number}
    def register(self, number:str, captcha:str, use_voice:bool = False):
        """Register a number with Signal
        
        \nTo get the captcha token, go to https://signalcaptchas.org/registration/generate.html.
        After solving the captcha, right-click on the "Open Signal" link and copy it. This is your captcha token
        
        Once you've received your verification code, use `self.verify_registration` for complete the process

        Args:
            number (str): E.164 formatted number to register
            captcha (str): Captcha token
            use_voice (bool, optional): Use voice for verification (defaults to SMS). Defaults to False.
        """
        #TODO should this raise an error?
        if not number.startswith("+"):
            pass
        url = self._base_url + "/v1/register/" + number
        
        params = {
            "captcha": captcha,
            "use_voice": use_voice
            }
        
        data = self._format_params(params=params)
        resp = self._requester(method='post', url=url, data=data, success_code=201, error_unknown='while registering number', error_couldnt='register number')
    
    #POST /v1/register/{number}/verify/{token}
    def verify_registration(self, number:str, token:str, pin:Optional[str] = None):
        """Verify/complete registration of a number.

        Args:
            number (str): E.164 formatted number
            token (str): The token/code you received from Signal
            pin (str, optional): Pin for account. Defaults to None.
        """
        url = self._base_url + "/v1/register/" + number + "/verify/" + token
        
        params = {
            "pin": pin,
            }
        
        data = self._format_params(params=params)
        resp = self._requester(method='post', url=url, data=data, success_code=201, error_unknown='while registering number', error_couldnt='register number')
    
    # # # ACCOUNTS # # #
    # GET /v1/accounts
    def list_accounts(self): 
        """List all registered or linked accounts. 

        Returns:
            list[str]: Numbers of linked or registered accounts.
        """
        url = self._base_url + "/v1/accounts"
        
        request = self._requester(method='get', url=url, success_code=200, error_unknown='getting linked/registered accounts', error_couldnt='get linked/registered accounts')
        return request.json()
    
    # POST /v1/accounts/{number}/pin
    def add_pin(self, pin:str): #TODO test if you have a device where this is the main account
        """Add pin to your Signal account. Doesn't work if signal-cli is not the main device.

        Args:
            pin (str): Pin

        Returns:
            _type_: _description_
        """ #TODO add return type
        url = self._base_url + "/v1/accounts/" + self._number + "/pin"
        params = {'pin': pin}
        
        data = self._format_params(params=params)
        
        request = self._requester(method='post', url=url, data=data, success_code=201, error_unknown='setting account pin', error_couldnt='set account pin')
        return request.json()
        
    # DELETE /v1/accounts/{number}/pin
    def remove_pin(self):
        """Remove pin from your Signal account. Doesn't work if signal-cli is not the main device.

        Returns:
            _type_: _description_
        """#TODO add return type
        url = self._base_url + "/v1/accounts/" + self._number + "/pin" 
        
        request = self._requester(method='delete', url=url, success_code=204, error_unknown='removing account pin', error_couldnt='remove account pin')
        return request.json()
    
    # # # POLLS # # #
    # DELETE /v1/polls/{number}
    def end_poll(self, recipient:str|int, poll_timestamp:int):
        url = self._base_url + "/v1/polls/" + self._number
        
        params = {
            # Per https://github.com/bbernhard/signal-cli-rest-api/issues/843, the poll timestamp needs to be sent as a string
            "poll_timestamp": str(poll_timestamp),
            "recipient": recipient
            }
                
        data = self._format_params(params=params)
        request = self._requester(method='delete', url=url, data=data, success_code=204, error_unknown='removing poll', error_couldnt='remove poll')    
    # POST /v1/polls/{number}
    def create_poll(self, recipient:str|int, question:str, answers:list[str], allow_multiple_selections:bool=False):
        url = self._base_url + "/v1/polls/" + self._number
        
        params = {
            "allow_multiple_selections": allow_multiple_selections,
            "answers": answers,
            "question": question,
            "recipient": recipient
            }

        data = self._format_params(params=params)
        request = self._requester(method='post', url=url, data=data, success_code=201, error_unknown='creating poll', error_couldnt='create poll')
        return request.json()
    