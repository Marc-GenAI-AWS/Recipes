# Docker Compose sidecars in a SageMaker AI Code Editor space

**Run a multi-container Docker Compose stack alongside your SageMaker AI Code Editor
container, on one shared network, so every service — and the editor itself — addresses
the others by DNS name instead of published ports.**

## Use this when

- You want to author `Dockerfile`s and a `compose.yaml` **directly inside** a Code
  Editor space and build/run them from that same space's terminal.
- You need **more than one** sidecar. This is the multi-container successor to the
  single-sidecar `docker run -p 8888:8888` pattern in
  [`../nvidia-bionemo-evo2/`](../nvidia-bionemo-evo2/); use that one if a single
  container is genuinely all you need.
- You're isolating each agent or tool in its own container but want them on one
  shared network — the intended use case for this layout.
- You want **zero port publishing**. Service-to-service and editor-to-service
  traffic stays on a user-defined bridge network.
- **When not to use this:** if you need to reach a service from your laptop's
  browser rather than the editor terminal, you still need a `ports:` mapping —
  see [Extending the pattern](#extending-the-pattern).

## What this recipe proves

- You can `docker compose build` and `docker compose up` from inside a Code Editor
  space, given a space image with docker enabled.
- Containers built this way run **alongside** the Code Editor container on the same
  host — the sidecar model.
- By joining the Code Editor container to the compose network, the editor's terminal
  reaches every service by name (`curl http://svc-a:8080/`) with no published ports.

## Prerequisites

- A SageMaker AI **Code Editor** space launched from an image that provides the
  `docker` CLI **and** whose runtime exposes `/var/run/docker.sock` to the space
  (i.e. local docker is enabled on the space). SageMaker Distribution images
  published from 2024 onward support this configuration.
- Outbound internet from the space — needed the first time to pull the
  `python:3.12-slim` base image and, if missing, the `docker compose` plugin binary.
  No ECR or IAM setup is required; nothing is pulled from a private registry.
- ~200 MB of free disk in the space for the base image and two built layers.

## Files

```
docker-compose-sidecars/
├── README.md              this file
├── compose.yaml           two services on a named user-defined network
├── services/
│   ├── svc-a/             tiny python http server, returns JSON
│   │   ├── Dockerfile
│   │   └── app.py
│   └── svc-b/             same, but also fetches svc-a to prove DNS works
│       ├── Dockerfile
│       └── app.py
├── scripts/
│   ├── bootstrap.sh       one-shot: verify, build, up, attach editor
│   └── attach-editor.sh   joins THIS container to agents-net
└── client/
    └── ping.py            call svc-a and svc-b from the editor terminal
```

## Run it

From the Code Editor's integrated terminal, at the recipe root:

```bash
bash scripts/bootstrap.sh
```

That script:

1. Verifies `docker` is available.
2. Installs the `docker compose` plugin into `~/.docker/cli-plugins` if it is not
   already present (user-writable, no root needed).
3. Runs `docker compose build` — this is the step that builds `svc-a` and `svc-b`
   from the local `Dockerfile`s you can edit right in the editor.
4. Runs `docker compose up -d`.
5. Calls `scripts/attach-editor.sh`, which resolves this container's ID and runs
   `docker network connect agents-net <this-container>`.
6. Prints the compose status and the current members of `agents-net`.

Then verify from the same terminal:

```bash
curl -s http://svc-a:8080/ | python -m json.tool
curl -s http://svc-b:8080/ | python -m json.tool
python client/ping.py
```

Expected output: `svc-b`'s response embeds `svc-a`'s response inside
`peer_response`, which proves container-to-container DNS resolution over the
compose network.

```json
{
  "service": "svc-b",
  "hostname": "svc-b",
  "peer_url": "http://svc-a:8080/",
  "peer_response": {
    "service": "svc-a",
    "hostname": "svc-a",
    "hello": "world"
  }
}
```

## Architecture

```
SageMaker AI Code Editor space (single host)
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│  ┌──────────────────┐   ┌────────┐   ┌────────┐             │
│  │  code-editor     │   │ svc-a  │   │ svc-b  │             │
│  │  container       │   │        │   │        │             │
│  │  (your terminal) │   │ :8080  │   │ :8080  │             │
│  └─────────┬────────┘   └───┬────┘   └───┬────┘             │
│            │                │            │                  │
│            └────────────────┴────────────┘                  │
│                     agents-net (docker user-defined bridge) │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Two things make this work:

1. **`networks: agents-net` with `name: agents-net`** in `compose.yaml`. The `name:`
   key pins the actual network name so `docker network connect` can refer to it
   without a compose project prefix.
2. **`scripts/attach-editor.sh`** discovers the Code Editor container's ID from
   `/proc/self/cgroup` and runs `docker network connect agents-net <id>`. Docker's
   embedded DNS then resolves `svc-a` and `svc-b` from inside the editor. No
   `ports:` are published.

## Extending the pattern

- **More services.** Add another entry under `services:` in `compose.yaml` with its
  own `build:` path. Each container gets a DNS name equal to its `container_name`.
- **Private images from ECR.** Replace `build:` with
  `image: <acct>.dkr.ecr.<region>.amazonaws.com/<repo>:<tag>` and add an
  `aws ecr get-login-password ... | docker login ...` step to `bootstrap.sh` before
  `docker compose up`.
- **GPU workloads** (equivalent to the BioNeMo recipe's `--gpus all`). Add:
  ```yaml
  deploy:
    resources:
      reservations:
        devices:
          - driver: nvidia
            count: all
            capabilities: [gpu]
  ```
  to any service that needs GPUs. The host still needs the NVIDIA container runtime
  installed — this is not automatic in every SageMaker image.
- **Browser access.** To hit a service from your laptop's browser rather than the
  editor terminal, add `ports: ["<host>:<container>"]` to that service. The
  compose-network DNS keeps working alongside it.
- **Persistent state.** Add named `volumes:` for anything you don't want to lose
  across `docker compose down`.

## Cleanup

```bash
docker compose down          # stops and removes svc-a and svc-b
docker network rm agents-net # only needed if you also want to drop the net
                             # (the editor is disconnected automatically)
```

## Troubleshooting

- **`docker: command not found`** — the space image doesn't include docker, or local
  docker is not enabled on the space. Recreate the space from an image that
  supports it.
- **`permission denied while trying to connect to /var/run/docker.sock`** — local
  docker is not fully enabled for this space. Check the space's launch
  configuration.
- **`curl: (6) Could not resolve host: svc-a`** from the editor — the editor
  container is not on `agents-net`. Re-run `bash scripts/attach-editor.sh`, then
  `docker network inspect agents-net` to confirm three members.
- **`network with name agents-net already exists`** on `docker compose up` —
  harmless; compose reuses it because `name:` is pinned.

## License

Inherits the repo root license.
