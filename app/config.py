from dotenv import load_dotenv
import os

load_dotenv()

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")

BASE_URL = "https://graph.instagram.com/v25.0"

MY_USERNAME = "the_lost_aperture_"
IG_USER_ID = "27392931747065676"

# Public reply posted after a DM is successfully sent.
# Leave blank to disable the web Reply action and comment processing.
REPLY_MESSAGE = "Please check DM"

# Legacy reply markers are kept for duplicate-reply detection of older comments.
REPLY_MESSAGES = [
    "Please check DM",
    "Please check your DM",
    "Shared the location in DM",
    "I've sent you the location in DM",
    "Location sent! Check your DM",
    "Sent you the location",
]

MEDIA = {
    "dlf_midtown": {
        "media_id": "18073788290362124",
        "location": "DLF Midtown, Moti Nagar, New Delhi",
    },
    "dear_donna": {
        "media_id": "18346742245170886",
        "location": "Dear Donna, Qutab Institutional Area, New Delhi",
    },
    "dhan_mill": {
        "media_id": "17942998797138354",
        "location": "The Dhan Mill, Chhatarpur, Delhi",
    },
    "nukkad": {
        "media_id": "17943925335251130",
        "location": "Nukkad Cafe, Kailash Colony, New Delhi",
    },
    # "china_club": {
    #     "media_id": "17875897377621242",
    #     "location": "China Club, Global Business Park, Sikanderpur, Gurugram",
    # },
    # "nubo": {
    #     "media_id": "18083235794531346",
    #     "location": "Nubo, Galleria Market, Gurugram",
    # },
    # "guwahati_airport": {
    #     "media_id": "18339407164268236",
    #     "location": "Guwahati Airport, Guwahati, Assam",
    # },
    # "woodzo": {
    #     "media_id": "18069156794459590",
    #     "location": "Woodzo, Shangarh, Himachal Pradesh",
    # },
    # "route65": {
    #     "media_id": "18083622698290999",
    #     "location": "M3M Route 65, Sector 65, Gurugram",
    # },
    # "panjab_house": {
    #     "media_id": "18106047890115594",
    #     "location": "Panjab House Kitchen & Bar, Sector 65, Gurugram"
    # },
    # "sunder_nursery1": {
    #     "media_id": "18165184420466476",
    #     "location": "Sunder Nursery, New Delhi"
    # },
    # "sunder_nursery2": {
    #     "media_id": "17890689507673390",
    #     "location": "Sunder Nursery, New Delhi"
    # },
    # "wah_rilang": {
    #     "media_id": "17991933054034507",
    #     "location": "Wah Rilang Viewpoint, Meghalaya"
    # },
    "tehri_lake": {
        "media_id": "17947691208289527",
        "location": "Le ROI Floating Huts & Eco Rooms, Tehri, Uttarakhand"
    },
    "kijiji1": {
        "media_id": "18175835374442926",
        "location": "Kijiji - On The Roof, Sector 47, Gurgaon"
    },
    "kijiji2": {
        "media_id": "18118430858002017",
        "location": "Kijiji - On The Roof, Sector 47, Gurgaon"
    }
}

DM_MESSAGES = [
    """Hey 👋 Thanks for commenting ❤️

📍 Location:
{location}

Follow @the_lost_aperture_ for more hidden gems ✨""",

    """Hi 👋 Thanks for your comment ❤️

📍 Location:
{location}

Follow @the_lost_aperture_ for more hidden gems ✨""",

    """Thanks for reaching out! 😊

📍 Here's the location:
{location}

Follow @the_lost_aperture_ for more hidden gems ✨""",

    """Hey! 😊

As promised, here's the location 📍

{location}

Follow @the_lost_aperture_ for more hidden gems ✨""",

    """Hello 👋

Thanks for your interest ❤️

📍 Location:
{location}

Follow @the_lost_aperture_ for more hidden gems ✨""",

    """Hey there! 😊

Sharing the location as requested 📍

{location}

Follow @the_lost_aperture_ for more hidden gems ✨""",

    """Thanks for commenting! ❤️

📍 You can find it here:
{location}

Follow @the_lost_aperture_ for more hidden gems ✨""",

    """Hi! 👋

Here's the location you asked for 📍

{location}

Hope you visit soon! 😊

Follow @the_lost_aperture_ for more hidden gems ✨""",

    """Hey 😊

Location shared below 👇

📍 {location}

Follow @the_lost_aperture_ for more hidden gems ✨""",

    """Thanks for your comment! ❤️

📍 Location:
{location}

Enjoy exploring! ✨

Follow @the_lost_aperture_ for more hidden gems ❤️"""
]

REPLY_CONFIG_FILE = "reply_config.json"


def _default_replyable_media():
    return {
        media_name: {
            "media_id": media["media_id"],
            "location": media["location"],
        }
        for media_name, media in MEDIA.items()
    }


def load_reply_config():
    import json

    if not os.path.exists(REPLY_CONFIG_FILE):
        return {
            "replyable_reels": {
                media["media_id"]: {
                    "media_name": media_name,
                    "location": media["location"],
                    "enabled": True,
                }
                for media_name, media in MEDIA.items()
            }
        }

    with open(REPLY_CONFIG_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"{REPLY_CONFIG_FILE} must contain a JSON object")

    data.setdefault("replyable_reels", {})
    return data


def save_reply_config(entries):
    import json

    replyable_reels = {}

    for entry in entries:
        media_id = str(entry.get("media_id") or "").strip()
        media_name = str(entry.get("media_name") or "").strip()
        location = str(entry.get("location") or "").strip()
        enabled = bool(entry.get("enabled"))

        if not media_id:
            continue

        if enabled and not location:
            raise ValueError(
                f"Location is required for replyable Reel media_id={media_id}"
            )

        if not media_name:
            media_name = f"reel_{media_id}"

        replyable_reels[media_id] = {
            "media_name": media_name,
            "location": location,
            "enabled": enabled,
        }

    data = {"replyable_reels": replyable_reels}

    temp_file = f"{REPLY_CONFIG_FILE}.tmp"

    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=4, ensure_ascii=False)
        f.write("\n")

    os.replace(temp_file, REPLY_CONFIG_FILE)


def get_reply_config_map():
    return load_reply_config().get("replyable_reels", {})


def get_replyable_media():
    replyable = {}

    for media_id, entry in get_reply_config_map().items():
        if not entry.get("enabled"):
            continue

        location = str(entry.get("location") or "").strip()
        if not location:
            continue

        media_name = str(entry.get("media_name") or "").strip()
        if not media_name:
            media_name = f"reel_{media_id}"

        replyable[media_name] = {
            "media_id": media_id,
            "location": location,
        }

    return replyable


def get_media_config(media_name):
    for configured_name, media in get_replyable_media().items():
        if configured_name == media_name:
            return media

    # Keep old queued comments processable after a Reel is disabled in the UI.
    if media_name in MEDIA:
        return MEDIA[media_name]

    raise KeyError(f"Unknown media: {media_name}")
