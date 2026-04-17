import os
import json
import tarfile
import tempfile
import subprocess
import shutil

from utils import IMAGES, LAYERS


def run_container(image, command, env_vars):

    image_file = os.path.join(IMAGES, image.replace(":", "_") + ".json")

    if not os.path.exists(image_file):
        print("Error: Image not found")
        return

    manifest = json.load(open(image_file))

    root = tempfile.mkdtemp(prefix="docksmith_")

    try:

        # assemble filesystem
        for layer in manifest.get("layers", []):

            digest = layer["digest"]

            if digest.startswith("sha256:"):
                digest = digest[len("sha256:"):]

            tar_path = os.path.join(LAYERS, "sha256:" + digest + ".tar")

            # skip sentinel or missing layers gracefully
            if not os.path.exists(tar_path):
                continue

            with tarfile.open(tar_path) as tar:
                tar.extractall(root)

        # determine command
        if command:
            cmd = command
        else:
            cmd = manifest.get("config", {}).get("Cmd")

        if not cmd:
            print("Error: no CMD defined and no command provided")
            return

        # build env from image config
        env = {}

        for e in manifest.get("config", {}).get("Env", []):
            k, v = e.split("=", 1)
            env[k] = v

        # apply -e overrides
        if env_vars:
            for e in env_vars:
                k, v = e.split("=", 1)
                env[k] = v

        # inject env into chroot shell
        env_exports = " ".join(f"export {k}={v};" for k, v in env.items())

        workdir = manifest.get("config", {}).get("WorkingDir", "/")

        print("Running container...")

        result = subprocess.run(
            [
                "sudo",
                "chroot",
                root,
                "/bin/sh",
                "-c",
                f"{env_exports} cd {workdir} && {' '.join(cmd)}"
            ]
        )

        print(f"Container exited with code {result.returncode}")

    finally:
        shutil.rmtree(root, ignore_errors=True)
