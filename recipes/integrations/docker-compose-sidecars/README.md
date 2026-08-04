# Docker Compose sidecars in a SageMaker AI Code Editor space

**Run a multi-container Docker Compose stack alongside your SageMaker AI Code Editor
container, working within Studio's local-Docker guardrails, so the editor and every
service reach each other with no port publishing at all.**

## Use this when

- You want to author `Dockerfile`s and a `compose.yaml` **directly inside** a Code
  Editor space and build/run them from that same space's terminal.
- You need **more than one** sidecar. This is the multi-container successor to the
  single-sidecar `docker run -p 8888:8888` pattern in
  [`../nvidia-bionemo-evo2/`](../nvidia-bionemo-evo2/); use that one if a single
  container is genuinely all you need.
- You're isolating each agent or tool in its own container inside the space.
- You've hit `The request for current resource is not allowed on SageMaker Studio.`
  or `'sagemaker' is the only user allowed network input` and need the compose
  spelling that satisfies the daemon.
- **When not to use this:** on your laptop or plain EC2. There you'd use a
  user-defined bridge and container-name DNS. The localhost pattern below is a
  Studio-specific workaround, not a general best practice.

## Important: how SageMaker Studio's local Docker actually works

Studio-specific constraints you cannot work around from `compose.yaml` alone. All
of these are enforced by the daemon in the space:

- **Only one network exists — `sagemaker` — and it is the *only* network any new
  container may attach to.** Attempts to create additional networks or attach
  containers to `bridge` are rejected with
  `The request for current resource is not allowed on SageMaker Studio.` /
  `[ContainerCreate] SageMaker Studio Docker Usage only allows 'sagemaker' as
  network input`.
- **The `sagemaker` network is a shared network namespace, not a normal
  user-defined bridge.** Every container in the space — the Code Editor container,
  `svc-a`, `svc-b`, anything else Studio starts — sees the same `localhost`, the
  same port table, the same `hostname`. Two services cannot both bind port 8080;
  they must be given distinct ports. There is no container-name DNS resolution —
  `curl http://svc-a:8080/` returns `Could not resolve host: svc-a`. Use
  `127.0.0.1:<port>` instead.
- **`docker network inspect sagemaker` and `docker exec` into containers are
  forbidden by the daemon.** Debug via `docker logs <container>` and by hitting
  `127.0.0.1:<port>` from the editor.
- **`docker build` is likewise pinned to the `sagemaker` network.** Each service's
  `build:` block must set `network: sagemaker` explicitly, or the build fails with
  `[ImageBuild] 'sagemaker' is the only user allowed network input`.

The rest of this README is written for those constraints.

## What this recipe proves

- You can `docker compose build` and `docker compose up` from inside a Code Editor
  space, given a space image and domain configuration that support docker.
- Containers built this way run **alongside** the Code Editor container in the same
  network namespace — services are reachable from the editor at
  `http://127.0.0.1:<port>` with no port publishing at all.
- Services can talk to each other the same way (`svc-b` fetches
  `http://127.0.0.1:8080/` to reach `svc-a`).

## Prerequisites

- A SageMaker AI **Code Editor** space launched from an image that provides the
  `docker` CLI **and** whose runtime exposes `/var/run/docker.sock` to the space.
  SageMaker Distribution images published from 2024 onward support this.
- **Local Docker enabled on the SageMaker domain.** The `docker` CLI being present
  in the image is not enough — the domain itself must have
  `DockerSettings.EnableDockerAccess = ENABLED` or the daemon socket will not be
  mounted into the space. See [Enable local Docker on the domain](#enable-local-docker-on-the-domain).
- Outbound internet from the space — needed the first time to pull the
  `python:3.12-slim` base image and, if missing, the `docker compose` plugin binary.
  No ECR or IAM setup is required for this demo; nothing is pulled from a private
  registry.
- ~200 MB of free disk in the space for the base image and two built layers.

### Enable local Docker on the domain

One-time, requires an IAM principal with `sagemaker:UpdateDomain` on the domain.
Replace the domain ID and region with your own.

```bash
export DOMAIN_ID=d-xxxxxxxxxxxx
export AWS_REGION=us-west-2

aws sagemaker update-domain \
  --domain-id "$DOMAIN_ID" \
  --region "$AWS_REGION" \
  --domain-settings-for-update '{"DockerSettings":{"EnableDockerAccess":"ENABLED"}}'

aws sagemaker describe-domain \
  --domain-id "$DOMAIN_ID" \
  --region "$AWS_REGION" \
  --query 'DomainSettings.DockerSettings'
# expect: { "EnableDockerAccess": "ENABLED", "VpcOnlyTrustedAccounts": [] }
```

After enabling, **stop and restart** any existing spaces — the docker socket is
only mounted at space startup, so a running space will not pick up the change until
it is restarted. Then inside the space terminal, confirm:

```bash
ls -l /var/run/docker.sock
docker version   # Server: section should be populated
```

## Files

```
docker-compose-sidecars/
├── README.md              this file
├── compose.yaml           two services pinned to network_mode: sagemaker
├── services/
│   ├── svc-a/             tiny python http server on port 8080
│   │   ├── Dockerfile
│   │   └── app.py
│   └── svc-b/             python http server on port 8081; calls svc-a
│       ├── Dockerfile     via 127.0.0.1:8080 to prove shared-namespace reach
│       └── app.py
├── scripts/
│   └── bootstrap.sh       one-shot: verify, build, up
└── client/
    └── ping.py            call svc-a (:8080) and svc-b (:8081) from the editor
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
3. Runs `docker compose build` — builds `svc-a` and `svc-b` from the local
   `Dockerfile`s using `network: sagemaker` (as required by Studio).
4. Runs `docker compose up -d` — starts both services with
   `network_mode: "sagemaker"`, so each container-create call satisfies Studio's
   "only `sagemaker` allowed" guardrail.
5. Prints the compose status.

Then verify from the same terminal:

```bash
curl -s http://127.0.0.1:8080/ | python -m json.tool
curl -s http://127.0.0.1:8081/ | python -m json.tool
python client/ping.py
```

Expected output: `svc-b`'s response embeds `svc-a`'s response inside
`peer_response`, which proves services in the space can call each other via
`127.0.0.1` in the shared namespace.

```json
{
  "service": "svc-b",
  "hostname": "...",
  "port": 8081,
  "peer_url": "http://127.0.0.1:8080/",
  "peer_response": {
    "service": "svc-a",
    "hostname": "...",
    "port": 8080,
    "hello": "world"
  }
}
```

## Architecture

```
SageMaker AI Code Editor space (single shared network namespace)
┌─────────────────────────────────────────────────────────────┐
│                                                             │
│   code-editor container   svc-a container   svc-b container │
│   (your terminal, curl)   python :8080      python :8081    │
│                                                             │
│           all three share one 127.0.0.1 and one port table  │
│                     (network_mode: "sagemaker")             │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

Two things make this work:

1. **Each service uses `network_mode: "sagemaker"`** instead of a top-level
   `networks:` list. Compose's `networks:` list creates the container on the
   default bridge first and then attaches the target network, which trips Studio's
   guardrail. `network_mode` sets `HostConfig.NetworkMode` at create time —
   matching `docker run --network sagemaker` — and satisfies the daemon.
2. **Each `build:` block sets `network: sagemaker`.** The same restriction applies
   during `docker build`, so builds must be told explicitly.

Because the `sagemaker` network is really a single namespace, services are
addressed by port on `127.0.0.1`, not by name:

- `svc-a` binds `0.0.0.0:8080`
- `svc-b` binds `0.0.0.0:8081` and calls `http://127.0.0.1:8080/` to reach `svc-a`
- the editor terminal reaches either with `curl http://127.0.0.1:<port>/`

The port assignments live in `compose.yaml` via `SVC_PORT` (and `PEER_URL` for
`svc-b`), so adding a third service is just picking an unused port and passing it
in.

## Extending the pattern

- **More services.** Add another entry under `services:` in `compose.yaml` with its
  own `build:` path and `network_mode: "sagemaker"`. **Give it a unique port** —
  every service shares one port table with the editor and with every other service.
  A collision is `OSError: [Errno 98] Address already in use`.
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
- **Browser access.** `ports:` publication does not help you on Studio — ingress to
  your laptop's browser goes through Studio's HTTPS front door, not through the
  docker daemon. Use Studio's built-in JupyterServer / Code Editor proxy paths, or
  push an image and run it in a separate hosted endpoint.
- **Persistent state.** Add named `volumes:` for anything you don't want to lose
  across `docker compose down`. Volumes work as usual.

## Cleanup

```bash
docker compose down   # stops and removes svc-a and svc-b
                      # do NOT try to rm the sagemaker network — Studio owns it
                      # and the daemon will refuse the request
```

## Troubleshooting

- **`docker: command not found`** — the space image doesn't include docker, or local
  docker is not enabled on the space. Recreate the space from an image that
  supports it.
- **`permission denied while trying to connect to /var/run/docker.sock`** — local
  docker is not fully enabled for this space. Check the space's launch
  configuration.
- **`dial unix /var/run/docker.sock: connect: no such file or directory`** (and
  `docker version` shows a client version but empty server) — the domain does not
  have `EnableDockerAccess: ENABLED`, or the space was started before the setting
  was applied. Run the `update-domain` command above, then stop and restart the
  space.
- **`Forbidden. Reason: [ImageBuild] 'sagemaker' is the only user allowed network
  input`** on `docker compose build` — each service's `build:` block must set
  `network: sagemaker` (already applied here).
- **`The request for current resource is not allowed on SageMaker Studio.`** on
  `docker compose up` — Studio only permits containers created directly on the
  `sagemaker` network. Use `network_mode: "sagemaker"` on each service rather than
  a top-level `networks:` list (already applied here). The underlying daemon
  message is `[ContainerCreate] SageMaker Studio Docker Usage only allows
  'sagemaker' as network input`; compose surfaces it as the generic "not allowed"
  text.
- **`OSError: [Errno 98] Address already in use`** in a service's logs — two
  containers (or a container and the editor) are trying to bind the same port in
  the shared namespace. Assign each service a unique port via its `SVC_PORT` env in
  `compose.yaml`.
- **`curl: (6) Could not resolve host: svc-a`** from the editor or from another
  service — DNS by container name doesn't work on the `sagemaker` network. Use
  `http://127.0.0.1:<port>/` instead.
- **`docker exec ... 403 Forbidden`** or **`docker network inspect sagemaker ... not
  allowed`** — expected. Studio blocks both. Debug with `docker logs <container>`
  and by curling `127.0.0.1:<port>` from the editor terminal.

## License

Inherits the repo root license.
