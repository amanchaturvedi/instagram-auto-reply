from dotenv import load_dotenv
import os

load_dotenv()

ACCESS_TOKEN = os.getenv("ACCESS_TOKEN")

BASE_URL = "https://graph.instagram.com/v25.0"

MY_USERNAME = "the_lost_aperture_"
IG_USER_ID = "27392931747065676"

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