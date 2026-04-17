import os
import json

HOME = os.path.expanduser("~")
STATE = os.path.join(HOME, ".docksmith")

IMAGES = os.path.join(STATE, "images")
LAYERS = os.path.join(STATE, "layers")
CACHE = os.path.join(STATE, "cache")


def init_state():
    os.makedirs(IMAGES, exist_ok=True)
    os.makedirs(LAYERS, exist_ok=True)
    os.makedirs(CACHE, exist_ok=True)


def list_images():

    files = os.listdir(IMAGES)

    print("NAME\tTAG\tID\tCREATED")

    for f in files:

        path = os.path.join(IMAGES, f)

        data = json.load(open(path))

        name = data.get("name", "")
        tag = data.get("tag", "")
        digest = data.get("digest", "none").replace("sha256:", "")[:12]
        created = data.get("created", "")

        print(f"{name}\t{tag}\t{digest}\t{created}")
