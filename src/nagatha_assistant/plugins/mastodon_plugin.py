import asyncio
from mastodon import Mastodon
from nagatha_assistant.core.plugin import Plugin
import os
import logging
from dotenv import load_dotenv, find_dotenv

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables from a .env file in the project root, if found
_dotenv_path = find_dotenv()
if _dotenv_path:
    load_dotenv(_dotenv_path)
else:
    load_dotenv()


class MastodonPlugin(Plugin):
    name = "mastodon"
    version = "0.1.0"

    def __init__(self):
        logger.info("Initializing MastodonPlugin...")
        self.client = None
        self.log = logger

    async def setup(self, config: dict):
        logger.info("Setting up Mastodon client...")
        try:
            client_id = os.environ.get("MASTODON_CLIENT_ID")
            client_secret = os.environ.get("MASTODON_CLIENT_SECRET")
            access_token = os.environ.get("MASTODON_ACCESS_TOKEN")
            api_base_url = os.environ.get("MASTODON_API_BASE_URL")
            logger.debug(f"Environment Variables: MASTODON_CLIENT_ID={client_id}, MASTODON_CLIENT_SECRET={'set' if client_secret else 'not set'}, MASTODON_ACCESS_TOKEN={'set' if access_token else 'not set'}, MASTODON_API_BASE_URL={api_base_url}")
            # Validate api_base_url
            if not api_base_url or not api_base_url.startswith("http"):
                logger.error(f"Invalid api_base_url: {api_base_url}. It must start with 'http' or 'https'.")
                return {"error": "Invalid api_base_url. Please check your environment variables or configuration."}

            self.client = Mastodon(
                client_id=client_id,
                client_secret=client_secret,
                access_token=access_token,
                api_base_url=api_base_url
            )
            logger.info("Mastodon client initialized successfully")
            return {"status": "Mastodon client initialized"}
        except Exception as e:
            logger.error(f"Failed to initialize Mastodon client: {e}", exc_info=True)
            return {"error": str(e)}

    async def teardown(self):
        self.client = None
        return {"status": "Mastodon client torn down"}

    def function_specs(self):
        specs = [
            {
                "name": "authenticate",
                "description": "Authenticate with the Mastodon server.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "client_id": {"type": "string"},
                        "client_secret": {"type": "string"},
                        "access_token": {"type": "string"},
                        "api_base_url": {"type": "string"}
                    },
                    "required": ["client_id", "client_secret", "access_token", "api_base_url"]
                }
            },
            {
                "name": "read_local_timeline",
                "description": "Fetch the most recent posts from the local timeline.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer"}
                    },
                    "required": []
                }
            },
            {
                "name": "read_federated_timeline",
                "description": "Fetch the most recent posts from the federated timeline.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer"}
                    },
                    "required": []
                }
            },
            {
                "name": "post_status",
                "description": "Compose and post a new status.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "status": {"type": "string"},
                        "visibility": {"type": "string"},
                        "in_reply_to_id": {"type": "string"},
                        "media_ids": {
                            "type": "array",
                            "items": {"type": "string"}
                        }
                    },
                    "required": ["status"]
                }
            },
            {
                "name": "summarize_hashtag",
                "description": "Fetch the latest posts for a hashtag and return a short summary.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "hashtag": {"type": "string"},
                        "limit": {"type": "integer"}
                    },
                    "required": ["hashtag"]
                }
            },
            {
                "name": "search_trending_hashtags",
                "description": "List current trending hashtags on the server.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer"}
                    },
                    "required": []
                }
            },
            {
                "name": "get_notifications",
                "description": "Fetch your latest notifications.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "limit": {"type": "integer"}
                    },
                    "required": []
                }
            },
            {
                "name": "follow_account",
                "description": "Follow an account.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_id": {"type": "string"}
                    },
                    "required": ["account_id"]
                }
            },
            {
                "name": "unfollow_account",
                "description": "Unfollow an account.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_id": {"type": "string"}
                    },
                    "required": ["account_id"]
                }
            },
            {
                "name": "mute_account",
                "description": "Mute an account.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_id": {"type": "string"}
                    },
                    "required": ["account_id"]
                }
            },
            {
                "name": "block_account",
                "description": "Block an account.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_id": {"type": "string"}
                    },
                    "required": ["account_id"]
                }
            },
            {
                "name": "upload_media",
                "description": "Upload media and return its media ID.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "file_path": {"type": "string"},
                        "description": {"type": "string"}
                    },
                    "required": ["file_path"]
                }
            },
            {
                "name": "delete_status",
                "description": "Delete a previously posted status.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "status_id": {"type": "string"}
                    },
                    "required": ["status_id"]
                }
            },
            {
                "name": "admin_list_pending_accounts",
                "description": "List new account registrations (admin-only).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "page": {"type": "integer"}
                    },
                    "required": []
                }
            },
            {
                "name": "admin_approve_account",
                "description": "Approve a new account registration (admin-only).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_id": {"type": "string"}
                    },
                    "required": ["account_id"]
                }
            },
            {
                "name": "admin_reject_account",
                "description": "Reject a new account registration (admin-only).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "account_id": {"type": "string"}
                    },
                    "required": ["account_id"]
                }
            },
            {
                "name": "admin_remove_report",
                "description": "Remove or act on reported content (admin-only).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "report_id": {"type": "string"},
                        "action": {"type": "string"}
                    },
                    "required": ["report_id", "action"]
                }
            }
        ]
        return specs

    async def call(self, name, arguments):
        logger.info(f"Calling function '{name}' with arguments: {arguments}")
        try:
            if name != "authenticate" and not self.client:
                logger.warning("Mastodon client is not initialized. Attempting auto-authentication...")
                client_id = os.getenv("MASTODON_CLIENT_ID")
                client_secret = os.getenv("MASTODON_CLIENT_SECRET")
                access_token = os.getenv("MASTODON_ACCESS_TOKEN")
                api_base_url = os.getenv("MASTODON_API_BASE_URL")
                if client_id and client_secret and access_token and api_base_url:
                    self.client = Mastodon(
                        client_id=client_id,
                        client_secret=client_secret,
                        access_token=access_token,
                        api_base_url=api_base_url
                    )
                    logger.info("Auto-authentication successful")
                else:
                    logger.error("Auto-authentication failed due to missing environment variables")
                    return {"error": "Mastodon client is not initialized. Please run 'authenticate' first."}

            if name == "authenticate":
                logger.info("Authenticating with provided arguments...")
                for key in ("client_id", "client_secret", "access_token", "api_base_url"):
                    if not arguments.get(key):
                        env_var = f"MASTODON_{key.upper()}" if key != "api_base_url" else "MASTODON_API_BASE_URL"
                        env_value = os.getenv(env_var)
                        if env_value:
                            arguments[key] = env_value
                for key in ("client_id", "client_secret", "access_token", "api_base_url"):
                    if key not in arguments or not arguments[key]:
                        logger.error(f"Missing parameter: {key}")
                        return {"error": f"Missing parameter: {key}"}
                self.client = Mastodon(
                    client_id=arguments["client_id"],
                    client_secret=arguments["client_secret"],
                    access_token=arguments["access_token"],
                    api_base_url=arguments["api_base_url"]
                )
                logger.info("Authentication successful")
                return {"status": "Authenticated with Mastodon server"}

            elif name == "read_local_timeline":
                limit = arguments.get("limit")
                logger.info(f"Fetching local timeline with limit: {limit}")
                result = await asyncio.to_thread(self.client.timeline_local, limit=limit)
                logger.debug(f"Local timeline fetched: {result}")
                return result

            elif name == "read_federated_timeline":
                limit = arguments.get("limit")
                logger.info(f"Fetching federated timeline with limit: {limit}")
                result = await asyncio.to_thread(self.client.timeline_public, limit=limit, local=False)
                logger.debug(f"Federated timeline fetched: {result}")
                return result

            elif name == "post_status":
                if "status" not in arguments:
                    logger.error("Missing parameter: status")
                    return {"error": "Missing parameter: status"}
                status = arguments["status"]
                visibility = arguments.get("visibility")
                in_reply_to_id = arguments.get("in_reply_to_id")
                media_ids = arguments.get("media_ids")
                logger.info(f"Posting status: {status}, visibility: {visibility}, in_reply_to_id: {in_reply_to_id}, media_ids: {media_ids}")
                result = await asyncio.to_thread(
                    self.client.status_post,
                    status,
                    visibility=visibility,
                    in_reply_to_id=in_reply_to_id,
                    media_ids=media_ids
                )
                logger.debug(f"Status posted: {result}")
                return result
            elif name == "summarize_hashtag":
                if "hashtag" not in arguments:
                    logger.error("Missing parameter: hashtag")
                    return {"error": "Missing parameter: hashtag"}
                hashtag = arguments["hashtag"]
                limit = arguments.get("limit")
                logger.info(f"Fetching posts for hashtag #{hashtag} with limit: {limit}")
                posts = await asyncio.to_thread(self.client.timeline_hashtag, hashtag, limit=limit)
                summary = f"Fetched {len(posts)} posts for hashtag #{hashtag}."
                logger.info(summary)
                return summary
            elif name == "search_trending_hashtags":
                limit = arguments.get("limit")
                logger.info(f"Fetching trending hashtags with limit: {limit}")
                tags = await asyncio.to_thread(self.client.trending_tags)
                if limit is not None:
                    tags = tags[:limit]
                logger.debug(f"Trending hashtags fetched: {tags}")
                return tags
            elif name == "get_notifications":
                limit = arguments.get("limit")
                logger.info(f"Fetching notifications with limit: {limit}")
                result = await asyncio.to_thread(self.client.notifications, limit=limit)
                logger.debug(f"Notifications fetched: {result}")
                return result
            elif name in ("follow_account", "unfollow_account", "mute_account", "block_account"):
                if "account_id" not in arguments:
                    logger.error("Missing parameter: account_id")
                    return {"error": "Missing parameter: account_id"}
                account_id = arguments["account_id"]
                logger.info(f"{name.replace('_', ' ').title()} account with ID: {account_id}")
                if name == "follow_account":
                    result = await asyncio.to_thread(self.client.account_follow, account_id)
                elif name == "unfollow_account":
                    result = await asyncio.to_thread(self.client.account_unfollow, account_id)
                elif name == "mute_account":
                    result = await asyncio.to_thread(self.client.account_mute, account_id)
                else:
                    result = await asyncio.to_thread(self.client.account_block, account_id)
                logger.debug(f"Account {name} result: {result}")
                return result
            elif name == "upload_media":
                if "file_path" not in arguments:
                    logger.error("Missing parameter: file_path")
                    return {"error": "Missing parameter: file_path"}
                file_path = arguments["file_path"]
                description = arguments.get("description")
                logger.info(f"Uploading media from file: {file_path}, description: {description}")
                def media_upload():
                    with open(file_path, "rb") as f:
                        return self.client.media_post(f, description=description)

                result = await asyncio.to_thread(media_upload)
                media_id = result.get("id")
                logger.info(f"Media uploaded, media ID: {media_id}")
                return {"media_id": media_id}
            elif name == "delete_status":
                if "status_id" not in arguments:
                    logger.error("Missing parameter: status_id")
                    return {"error": "Missing parameter: status_id"}
                status_id = arguments["status_id"]
                logger.info(f"Deleting status with ID: {status_id}")
                result = await asyncio.to_thread(self.client.status_delete, status_id)
                logger.info(f"Status deleted: {result}")
                return result
            elif name in ("admin_list_pending_accounts", "admin_approve_account", "admin_reject_account"):
                if name == "admin_list_pending_accounts":
                    page = arguments.get("page")
                    logger.info(f"Listing pending accounts, page: {page}")
                    result = await asyncio.to_thread(self.client.admin_accounts_pending, page=page)
                    logger.debug(f"Pending accounts: {result}")
                elif name == "admin_approve_account":
                    if "account_id" not in arguments:
                        logger.error("Missing parameter: account_id")
                        return {"error": "Missing parameter: account_id"}
                    account_id = arguments["account_id"]
                    logger.info(f"Approving account with ID: {account_id}")
                    result = await asyncio.to_thread(self.client.admin_accounts_approve, account_id)
                    logger.info(f"Account approved: {result}")
                else:
                    if "account_id" not in arguments:
                        logger.error("Missing parameter: account_id")
                        return {"error": "Missing parameter: account_id"}
                    account_id = arguments["account_id"]
                    logger.info(f"Rejecting account with ID: {account_id}")
                    result = await asyncio.to_thread(self.client.admin_accounts_reject, account_id)
                    logger.info(f"Account rejected: {result}")
                return result
            elif name == "admin_remove_report":
                if "report_id" not in arguments or "action" not in arguments:
                    logger.error("Missing parameters: report_id and action are required")
                    return {"error": "Missing parameters: report_id and action are required"}
                report_id = arguments["report_id"]
                action_val = arguments["action"]
                logger.info(f"Removing report with ID: {report_id}, action: {action_val}")
                try:
                    result = await asyncio.to_thread(self.client.admin_remove_report, report_id, action_val)
                    logger.info(f"Report removed: {result}")
                    return result
                except AttributeError:
                    endpoint = f"admin/reports/{report_id}"
                    result = await asyncio.to_thread(
                        self.client.__class__._api_post, self.client, endpoint, {"action": action_val}
                    )
                    logger.info(f"Report action performed via API: {result}")
                    return result
            else:
                logger.error(f"Function {name} not found")
                return {"error": f"Function {name} not found"}
        except Exception as e:
            logger.error(f"Error in function '{name}': {e}", exc_info=True)
            return {"error": str(e)}
