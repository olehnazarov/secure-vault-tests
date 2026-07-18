import os

BASE_URL = os.environ.get("SECUREVAULT_BASE_URL", "http://18.215.161.231:8000")

USERS = {
    "alpha_admin": {
        "email": "admin@org-alpha.com",
        "password": "Alpha@1234",
        "role": "admin",
        "org": "org-alpha",
    },
    "alpha_analyst": {
        "email": "analyst@org-alpha.com",
        "password": "Alpha@1234",
        "role": "analyst",
        "org": "org-alpha",
    },
    "beta_admin": {
        "email": "admin@org-beta.com",
        "password": "Beta@1234",
        "role": "admin",
        "org": "org-beta",
    },
}
