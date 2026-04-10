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

    # remove layer files
    for layer in manifest.get("layers", []):

        digest = layer if isinstance(layer, str) else layer["digest"]

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
    build.add_argument("context")

    run = sub.add_parser("run")
    run.add_argument("image")
    run.add_argument("command", nargs="*")
    run.add_argument("-e", action="append")

    sub.add_parser("images")

    rmi = sub.add_parser("rmi")
    rmi.add_argument("image")

    args = parser.parse_args()

    if args.cmd == "build":
        build_image(args.t, args.context)

    elif args.cmd == "run":
        run_container(args.image, args.command, args.e)

    elif args.cmd == "images":
        list_images()

    elif args.cmd == "rmi":
        remove_image(args.image)


if __name__ == "__main__":
    main()
