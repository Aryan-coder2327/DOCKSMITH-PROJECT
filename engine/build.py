import os
import tempfile
import subprocess
import json
import datetime
import tarfile
import hashlib

from engine.parser import parse_file
from engine.cache import cache_lookup, cache_store
from utils import IMAGES, LAYERS


def snapshot_files(root):

    files = {}

    for dirpath, dirs, filenames in os.walk(root):

        for f in filenames:

            path = os.path.join(dirpath, f)

            if not os.path.isfile(path):
                continue

            stat = os.stat(path)

            files[path] = (stat.st_size, stat.st_mtime)

    return files


def compute_diff(before, after):

    changed = []

    for file in after:

        if file not in before:
            changed.append(file)

        elif before[file] != after[file]:
            changed.append(file)

    return changed


def create_layer(root, changed_files):

    fd, tar_path = tempfile.mkstemp(suffix=".tar")
    os.close(fd)

    with tarfile.open(tar_path, "w") as tar:

        for full in sorted(changed_files):

            if not os.path.isfile(full):
                continue

            arc = os.path.relpath(full, root)

            try:
                info = tar.gettarinfo(full, arcname=arc)
                info.mtime = 0

                with open(full, "rb") as file:
                    tar.addfile(info, file)

            except:
                continue

    with open(tar_path, "rb") as f:
        data = f.read()

    digest = hashlib.sha256(data).hexdigest()

    final = os.path.join(LAYERS, "sha256:" + digest + ".tar")

    if not os.path.exists(final):
        with open(final, "wb") as out:
            out.write(data)

    os.remove(tar_path)

    size = len(data)

    return digest, size


def hash_copy_sources(src_path):

    hashes = []

    for root, dirs, files in os.walk(src_path):

        for f in sorted(files):

            p = os.path.join(root, f)

            if not os.path.isfile(p):
                continue

            try:
                with open(p, "rb") as file:
                    data = file.read()

                hashes.append(hashlib.sha256(data).hexdigest())

            except:
                continue

    return "".join(hashes)


def compute_cache_key(prev_layer, instruction, workdir, env):

    env_state = "".join(sorted(env))

    data = str(prev_layer) + instruction + workdir + env_state

    return hashlib.sha256(data.encode()).hexdigest()


def build_image(tag, context):

    docksmithfile = os.path.join(context, "Docksmithfile")

    instructions = parse_file(docksmithfile)

    root = tempfile.mkdtemp(prefix="docksmith_build_")

    layers = []
    env = []
    workdir = "/"
    cmd = None

    print("Starting build")

    for i, inst in enumerate(instructions):

        print(f"Step {i+1}/{len(instructions)} : {inst}")

        parts = inst.split()
        instr = parts[0]

        if instr == "FROM":

            base = parts[1]

            image_file = os.path.join(IMAGES, base.replace(":", "_") + ".json")

            if not os.path.exists(image_file):
                raise Exception(f"Base image {base} not found")

            base_manifest = json.load(open(image_file))

            for layer in base_manifest["layers"]:

                digest = layer["digest"].split(":")[1]

                tar_path = os.path.join(LAYERS, "sha256:" + digest + ".tar")

                with tarfile.open(tar_path) as tar:
                    tar.extractall(root)

                layers.append(layer)

        elif instr == "WORKDIR":

            workdir = parts[1]

            os.makedirs(os.path.join(root, workdir.lstrip("/")), exist_ok=True)

        elif instr == "ENV":

            env.append(parts[1])

        elif instr == "CMD":

            cmd = json.loads(inst[4:])

        elif instr in ["COPY", "RUN"]:

            prev_layer = layers[-1]["digest"] if layers else ""

            extra = ""

            if instr == "COPY":
                src_path = os.path.join(context, parts[1])
                extra = hash_copy_sources(src_path)

            key = compute_cache_key(prev_layer, inst + extra, workdir, env)

            cached = cache_lookup(key)

            if cached:

                print("[CACHE HIT]")

                layers.append({
                    "digest": "sha256:" + cached,
                    "size": 0,
                    "createdBy": inst
                })

            else:

                print("[CACHE MISS]")

                snapshot_before = snapshot_files(root)

                if instr == "COPY":

                    src = parts[1]
                    dest = os.path.join(root, parts[2].lstrip("/"))
                    src_path = os.path.join(context, src)

                    os.makedirs(dest, exist_ok=True)

                    subprocess.run(
                        ["cp", "-r", src_path + "/.", dest],
                        check=True
                    )

                elif instr == "RUN":

                    subprocess.run(
                        [
                            "sudo",
                            "chroot",
                            root,
                            "/bin/sh",
                            "-c",
                            " ".join(parts[1:])
                        ],
                        check=True
                    )

                snapshot_after = snapshot_files(root)

                changed = compute_diff(snapshot_before, snapshot_after)

                digest, size = create_layer(root, changed)

                layer_obj = {
                    "digest": "sha256:" + digest,
                    "size": size,
                    "createdBy": inst
                }

                layers.append(layer_obj)

                cache_store(key, digest)

    name, tagname = tag.split(":")

    manifest = {
        "name": name,
        "tag": tagname,
        "digest": "",
        "created": str(datetime.datetime.now()),
        "config": {
            "Env": env,
            "Cmd": cmd,
            "WorkingDir": workdir
        },
        "layers": layers
    }

    data = json.dumps(manifest, sort_keys=True).encode()

    digest = hashlib.sha256(data).hexdigest()

    manifest["digest"] = "sha256:" + digest

    image_file = os.path.join(IMAGES, tag.replace(":", "_") + ".json")

    with open(image_file, "w") as f:
        json.dump(manifest, f, indent=2)

    print("Build complete")
