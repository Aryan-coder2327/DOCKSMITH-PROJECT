import os
import tempfile
import subprocess
import json
import datetime
import tarfile
import hashlib
import time
import shutil

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

    return digest, len(data)


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

    env_pairs = {}
    for e in env:
        if "=" in e:
            k, v = e.split("=", 1)
            env_pairs[k] = v

    env_state = "".join(f"{k}={env_pairs[k]}" for k in sorted(env_pairs.keys()))
    data = str(prev_layer) + instruction + workdir + env_state

    return hashlib.sha256(data.encode()).hexdigest()


def get_layer_size(digest):

    path = os.path.join(LAYERS, "sha256:" + digest + ".tar")
    if os.path.exists(path):
        return os.path.getsize(path)
    return 0


def build_image(tag, context, no_cache=False):

    docksmithfile = os.path.join(context, "Docksmithfile")
    instructions = parse_file(docksmithfile)
    root = tempfile.mkdtemp(prefix="docksmith_build_")

    layers = []
    env = []
    workdir = "/"
    cmd = None
    cache_invalidated = False
    all_cache_hit = True
    base_digest = ""

    build_start = time.time()

    print("Starting build")

    try:

        for i, inst in enumerate(instructions):

            parts = inst.split()
            instr = parts[0]

            step_start = time.time()

            if instr == "FROM":

                print(f"Step {i+1}/{len(instructions)} : {inst}")

                base = parts[1]
                image_file = os.path.join(IMAGES, base.replace(":", "_") + ".json")

                if not os.path.exists(image_file):
                    raise Exception(f"Base image {base} not found")

                base_manifest = json.load(open(image_file))

                # store base digest for use as first cache key anchor
                base_digest = base_manifest.get("digest", "")

                for layer in base_manifest["layers"]:
                    digest = layer["digest"].split(":")[1]
                    tar_path = os.path.join(LAYERS, "sha256:" + digest + ".tar")
                    with tarfile.open(tar_path) as tar:
                        tar.extractall(root)
                    layers.append(layer)

            elif instr == "WORKDIR":
                workdir = parts[1]
                os.makedirs(os.path.join(root, workdir.lstrip("/")), exist_ok=True)
                print(f"Step {i+1}/{len(instructions)} : {inst}")

            elif instr == "ENV":
                env.append(parts[1])
                print(f"Step {i+1}/{len(instructions)} : {inst}")

            elif instr == "CMD":
                cmd = json.loads(inst[4:])
                print(f"Step {i+1}/{len(instructions)} : {inst}")

            elif instr in ["COPY", "RUN"]:

                # use base_digest as anchor if no COPY/RUN layers yet
                if layers:
                    prev_layer = layers[-1]["digest"]
                else:
                    prev_layer = base_digest

                extra = ""
                if instr == "COPY":
                    src_path = os.path.join(context, parts[1])
                    extra = hash_copy_sources(src_path)

                key = compute_cache_key(prev_layer, inst + extra, workdir, env)

                cached = None
                if not no_cache and not cache_invalidated:
                    cached = cache_lookup(key)
                    if cached:
                        layer_path = os.path.join(LAYERS, "sha256:" + cached + ".tar")
                        if not os.path.exists(layer_path):
                            cached = None

                if cached:

                    elapsed = time.time() - step_start
                    print(f"Step {i+1}/{len(instructions)} : {inst} [CACHE HIT] {elapsed:.2f}s")

                    tar_path = os.path.join(LAYERS, "sha256:" + cached + ".tar")
                    with tarfile.open(tar_path) as tar:
                        tar.extractall(root)

                    actual_size = get_layer_size(cached)

                    layers.append({
                        "digest": "sha256:" + cached,
                        "size": actual_size,
                        "createdBy": inst
                    })

                else:

                    all_cache_hit = False
                    cache_invalidated = True

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

                        env_exports = " ".join(
                            f"export {e.split('=',1)[0]}={e.split('=',1)[1]};"
                            for e in env if "=" in e
                        )

                        subprocess.run(
                            [
                                "sudo",
                                "chroot",
                                root,
                                "/bin/sh",
                                "-c",
                                f"{env_exports} " + " ".join(parts[1:])
                            ],
                            check=True,
                            stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE
                        )

                    snapshot_after = snapshot_files(root)
                    changed = compute_diff(snapshot_before, snapshot_after)
                    digest, size = create_layer(root, changed)

                    elapsed = time.time() - step_start
                    print(f"Step {i+1}/{len(instructions)} : {inst} [CACHE MISS] {elapsed:.2f}s")

                    layers.append({
                        "digest": "sha256:" + digest,
                        "size": size,
                        "createdBy": inst
                    })

                    if not no_cache:
                        cache_store(key, digest)

    finally:
        shutil.rmtree(root, ignore_errors=True)

    name, tagname = tag.split(":")

    image_file = os.path.join(IMAGES, tag.replace(":", "_") + ".json")
    original_created = None

    if all_cache_hit and os.path.exists(image_file):
        try:
            existing = json.load(open(image_file))
            original_created = existing.get("created")
        except:
            pass

    created = original_created if original_created else str(datetime.datetime.now())

    manifest = {
        "name": name,
        "tag": tagname,
        "digest": "",
        "created": created,
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

    with open(image_file, "w") as f:
        json.dump(manifest, f, indent=2)

    total = time.time() - build_start
    print(f"Successfully built sha256:{digest[:12]} {tag} ({total:.2f}s)")
