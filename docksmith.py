import argparse
import os
import json

from utils import init_state, IMAGES, LAYERS
from engine.build import build_image
from runtime.run import run_container
from utils import list_images


def remove_image(image):

    image_file = os.path.join(IMAGES, image.replace(":", "_") + ".json")

    if not os.path.exists(image_file):
        print("Error: image not found")
        return

    manifest = json.load(open(image_file))

    for layer in manifest.get("layers", []):

        digest = layer if isinstance(layer, str) else layer["digest"]

        # strip sha256: prefix if present
        if isinstance(digest, str) and digest.startswith("sha256:"):
            digest = digest[len("sha256:"):]

        path = os.path.join(LAYERS, "sha256:" + digest + ".tar")

        if os.path.exists(path):
            os.remove(path)

    os.remove(image_file)

    print("Image removed")


def main():

    init_state()

    parser = argparse.ArgumentParser()

    sub = parser.add_subparsers(dest="cmd")

    build = sub.add_parser("build")
    build.add_argument("-t")
    build.add_argument("--no-cache", action="store_true", dest="no_cache")
    build.add_argument("context")

    run = sub.add_parser("run")
    run.add_argument("image")
    run.add_argument("-e", action="append")

    sub.add_parser("images")

    rmi = sub.add_parser("rmi")
    rmi.add_argument("image")

    args, remaining = parser.parse_known_args()

    if args.cmd == "build":
        build_image(args.t, args.context, args.no_cache)

    elif args.cmd == "run":
        run_container(args.image, remaining, args.e)

    elif args.cmd == "images":
        list_images()

    elif args.cmd == "rmi":
        remove_image(args.image)


if __name__ == "__main__":
    main()
