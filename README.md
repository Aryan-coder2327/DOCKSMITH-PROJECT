# 🛠️ Docksmith

> A minimal Docker-like container engine built in Python — demonstrating layered filesystems, build caching, image manifests, and container runtime isolation.

---

## Authors

| Name | Role |
|------|------|
| Aryan Tripathi | Developer |
| Arya Singh | Developer |
| Anushka Singhal | Developer |
| Arnav Singh | Developer |

---

## Overview

Docksmith is a lightweight container build system and runtime implemented in Python. It replicates the core workflow of Docker in a simplified, educational form — reading a `Docksmithfile`, building container images using layered filesystem techniques, and running containers in an isolated environment via Linux primitives.

---

## Features

### 1. Image Build System

Docksmith parses and executes instructions from a `Docksmithfile`, similar to a `Dockerfile`.

**Supported instructions:**

| Instruction | Behavior |
|-------------|----------|
| `FROM` | Loads a base image |
| `COPY` | Copies files from the build context |
| `RUN` | Executes commands during the build |
| `WORKDIR` | Sets the working directory |
| `ENV` | Sets environment variables |
| `CMD` | Defines the default command when the container runs |

The final image is stored as a JSON manifest.

---

### 2. Layered Filesystem

Each `COPY` and `RUN` instruction creates an **immutable filesystem layer**.

- Stored as `.tar` archives
- Named using the **SHA-256 digest** of layer contents
- Contain only files added or modified at that step
- Stored under `~/.docksmith/layers/`

When a container runs, all layers are extracted sequentially to reconstruct the full filesystem.

---

### 3. Deterministic Build Cache

Before executing a `COPY` or `RUN` instruction, Docksmith computes a **cache key** from:

- Previous layer digest
- Instruction text
- Current working directory
- Environment variables
- Hash of source files (for `COPY`)

If the key matches a prior run → `[CACHE HIT]`  
Otherwise → `[CACHE MISS]`

This makes builds fast, reproducible, and cache-friendly.

---

### 4. Image Storage

Images are stored as JSON manifests in `~/.docksmith/images/`.

Each manifest contains:
- Image name and tag
- Creation timestamp
- Configuration (`ENV`, `CMD`, `WORKDIR`)
- Ordered list of layer digests

---

### 5. Container Runtime

The runtime performs the following steps to launch a container:

1. Read the image manifest
2. Extract all layers into a temporary filesystem
3. Enter the filesystem using Linux `chroot`
4. Execute the container command

This provides **filesystem isolation** — files created inside the container don't affect the host system.

---

## Project Structure

```
docksmith/
├── docksmith.py        # CLI entrypoint
├── utils.py            # Utility functions
│
├── engine/
│   ├── build.py        # Image build logic
│   ├── cache.py        # Build cache management
│   └── runtime.py      # Container runtime (chroot + exec)
│
├── base_image/
│   └── Docksmithfile   # Base image definition
│
└── sample_app/
    ├── Docksmithfile   # App image definition
    └── app.py          # Sample application
```

---

## System Requirements

- Python 3.8 or higher
- Linux environment (Ubuntu recommended)
- Root/sudo access for `chroot` operations

> ⚠️ Must be run on a Linux system or Linux virtual machine. macOS and Windows are not supported.

---

## Getting Started

### Step 1 — Clone the Repository

```bash
git clone https://github.com/Aryan-coder2327/DOCKSMITH-PROJECT
cd DOCKSMITH-PROJECT
```

---

### Step 2 — Build the Base Image

```bash
python3 docksmith.py build -t base:latest base_image
```

**Expected output:**
```
Starting build
Step 1/2 : WORKDIR /
Step 2/2 : CMD ["python3"]
Build complete
```

---

### Step 3 — Build the Application Image

```bash
python3 docksmith.py build -t myapp:latest sample_app
```

**First run (cold cache):**
```
Step 1/9 : FROM base:latest
Step 2/9 : WORKDIR /app
Step 3/9 : ENV NAME=Docksmith
Step 4/9 : COPY usr /usr
[CACHE MISS]
...
```

**Subsequent runs (warm cache):**
```
Step 4/9 : COPY usr /usr
[CACHE HIT]
...
```

---

### Step 4 — List Available Images

```bash
python3 docksmith.py images
```

**Example output:**
```
NAME    TAG     ID              CREATED
base    latest  sha256:a1b2c3  2024-01-01 10:00:00
myapp   latest  sha256:d4e5f6  2024-01-01 10:01:00
```

---

### Step 5 — Run the Container

```bash
sudo HOME=$HOME python3 docksmith.py run myapp:latest
```

**Expected output:**
```
Running container...
Hello World
```

> `sudo` is required because `chroot` is a privileged operation.

---

### Step 6 — Inspect Image Layers

List all stored layers:
```bash
ls ~/.docksmith/layers
```

Inspect the contents of a specific layer:
```bash
tar -tf ~/.docksmith/layers/<layer-digest>.tar
```

Each layer contains only the files modified by that particular build instruction.

---

## Concepts Demonstrated

| Concept | Description |
|---------|-------------|
| Layered filesystem | Each build step creates a separate, immutable layer |
| Content-addressable storage | Layers are identified by SHA-256 digest of their contents |
| Deterministic build caching | Cache keys are computed from instruction + context; identical steps are skipped |
| Image manifests | JSON files describing image config and layer ordering |
| Container runtime isolation | `chroot` confines the container to its own filesystem view |

---

## Educational Purpose

Docksmith was built to demystify how container engines like Docker work internally — from parsing build instructions and managing layered filesystems, to isolating containers at runtime. It is intentionally minimal and readable, serving as a hands-on reference for anyone learning systems programming or container internals.

---

## License

This project was developed for educational purposes as part of coursework at PES University.
