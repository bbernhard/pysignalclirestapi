Forked from: https://github.com/bbernhard/pysignalclirestapi.  Planning to try and merge back once I've finished adding and testing everything!

Small python library for the [Signal Cli REST API](https://github.com/bbernhard/signal-cli-rest-api)

### Quickstart
If you have set up the REST API already, you can start sending and receiving messages in Python!

Intialize the client
```
# Seperated for clarity
SERVER = "http://localhose:8080" # Your server address and port
SERVER_NUMBER ="+123456789" # The phone number you registered with the API


signal = SignalCliRestApi(SERVER,SERVER_NUMBER) 
```

Send a message
```
myMessage = "Hello World" # Your message
myFriendSteve = +987654321 # The number you want to message (must be registered with Signal)

sendMe = signal.send_message(message=myMessage,recipients=myFriendSteve)

```
receive messages
```
myMessages = signal.receive(send_read_receipts=True) # Send read receipts so everyone knows you have seen their message
```

## Endpoint progress tracking
Anything that was already part of the package before I added stuff should work, but I haven't fully tested all the ones I have added, which is why I haven't tried to merge yet!  If an endpoint is not listed, assume it is not added.

### General
| Service | Status | Function Name | Notes |
| --- | --- | --- | --- |
| about | Working | about() | Was already here. |
No other general endpoints have been added.
### Devices
No device endpoints have been added.
### Accounts
No accounts endpoints have been added.
### Groups
| Service | Status | Function Name | Notes |
| --- | --- | --- | --- |
| GET groups | Working | list_groups() |  |
| POST groups | In Progress | create_group() | Have not run into any issues yet |
| GET group | In Progress | get_group() | Want to try messing with the group IDs to see how it reacts |
| PUT group | Partially Working | update_group() | Images are accepted but do not always appear |
| DELETE group | In Progress | delete_group() | Need to try deleting a group that I do not own |
| POST group admins | In Progress | add_group_admins() | Need to try different number types and formats |
| DELETE group admins | In Progress | remove_group_admins() | Need to try different number types and formats |
| POST block group | Untested | block_group() | Need a group I didn't create to test with |
| POST join group | Untested | join_group() | Need a group I didn't create to test with |
| POST group members | In Progress | add_group_members() | Need to try different number types and formats |
| DELETE group members | In Progress | remove_group_members() | Need to try different number types and formats |
| POST quit group | Untested | leave_group() | Need a group I didn't create to test with |

### Messages
| Service | Status | Function Name | Description |
| --- | --- | --- | --- |
| receive | Working | receive() | Was working when I got here, added some more args and a docstring |
| send | Working* | send_message() | Have not tested with API V1 |

### Attachments
| Service | Status | Function Name | Description |
| --- | --- | --- | --- |
| attachments | Working* | list_attachments() | Converted to use my sender, seems fine as far as I can tell. |
| GET attachment | Working | get_attachment() | Haven't touched |
| DELETE attachment | Working | delete_attachment() | Haven't touched |

### Profiles
| Service | Status | Function Name | Description |
| --- | --- | --- | --- |
| profiles | Working | update_profile | Haven't touched |

### Identities
| Service | Status | Function Name | Description |
| --- | --- | --- | --- |
| identities | Working | list_identities() |  |
| trust identities | In Progress | verify_identity() | Not sure if this should be renamed, also had some issues with the trust all known keys |

### Reactions
| Service | Status | Function Name | Description |
| --- | --- | --- | --- |
| POST reaction | Working | send_reaction() |  |
| DELETE reaction | Working | delete_reaction() |  |
Maybe the methods here should be "add" and "remove" instead of "send" and "delete"?

### Receipts
| Service | Status | Function Name | Description |
| --- | --- | --- | --- |
| receipts | In Progress | send_receipt() | Not clear to me what viewed vs read does |
### Search
| Service | Status | Function Name | Description |
| --- | --- | --- | --- |
| search | Working* | search() | Seems to only work with numbers in your account region? |

### Sticker Packs
No sticker pack endpoints have been added.

### Contacts
| Service | Status | Function Name | Description |
| --- | --- | --- | --- |
| GET contacts | Working | get_contacts() |  |
| POST contacts | Untested | update_contact() | Must have API set up as main device, which mine is not |
| sync contacts | Untested | sync_contacts() | Must have API set up as main device, which mine is not |

