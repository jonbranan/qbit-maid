# Auto-deploy qbit-maid to Komodo

Status: **implemented** on branch `dev-komodo-deploy`.
Komodo instance: `https://k.jonb.io` · Stack: `qbit-maid`

## What this does

Every successful image build now triggers a Komodo stack deploy:

| Workflow | Trigger | Image tag | Komodo target |
|---|---|---|---|
| `.gitea/workflows/docker.yml` | push to `main` | `:latest` | stack `qbit-maid` |
| `.gitea/workflows/docker-dev.yml` | push to `dev*` | `:dev` | `vars.KOMODO_STACK_DEV` (skipped if unset) |

The deploy step runs **after** `Build and push`, so the new image is already in
the registry when Komodo pulls it. If the deploy fails, the workflow goes red.

## Why not just use the existing webhook?

You already have webhooks configured, and this is the important part: **a push
webhook on the stack does not reliably deploy new container builds.**

The webhook fires on `git push`. That happens *before* Gitea Actions has built
and pushed the image — the build takes minutes. So Komodo receives the deploy
request while the registry still holds the *previous* `:latest`. It pulls that,
deploys it, and reports success. The new code never lands until something else
triggers a second deploy.

The ordering is the whole problem, and a webhook cannot fix it because the
webhook is tied to the push event, not the build event.

So the workflow calls the Komodo API directly instead:

```
POST https://k.jonb.io/execute/DeployStack
x-api-key: <key>
x-api-secret: <secret>
{"stack": "qbit-maid"}
```

This is the same call the Komodo UI makes when you click **Deploy**, just
triggered from CI at the right moment.

### What to do with the existing webhook

If you have a stack webhook pointing at
`/listener/github/stack/qbit-maid/deploy`, it is now redundant and will cause a
second, useless deploy on every push (deploying the stale image). **Remove it**
in Gitea → repo Settings → Webhooks.

Keep webhooks only if you later point them at a *Procedure* rather than the
stack — see "Using a Procedure" below.

## One Komodo setting to verify

`DeployStack` runs `docker compose pull` before `up` **only when the stack has
`auto_pull` enabled**. It defaults to `true`, so this is probably already fine —
but if it has been turned off, deploys will silently reuse the cached image and
you will see no change.

Check in the Komodo UI: stack `qbit-maid` → Config → **Auto Pull** should be on.

## Setup (one-time)

### 1. Komodo API key

Komodo → **Settings → API Keys → New**. The key's user needs **Execute**
permission on the `qbit-maid` stack. Copy the key and secret — the secret is
shown once.

### 2. Gitea secrets

Repo → **Settings → Actions → Secrets**:

| Name | Value |
|---|---|
| `KOMODO_URL` | `https://k.jonb.io` |
| `KOMODO_API_KEY` | from step 1 |
| `KOMODO_API_SECRET` | from step 1 |

### 3. Dev stack (optional)

Repo → **Settings → Actions → Variables**:

| Name | Value |
|---|---|
| `KOMODO_STACK_DEV` | your dev stack name, e.g. `qbit-maid-dev` |

If this variable is unset, the dev workflow logs `KOMODO_TARGET is not set -
skipping Komodo deploy` and still passes. Dev builds never fail because of a
missing dev stack.

## The deploy script

`.gitea/scripts/komodo-deploy.sh` is shared by both workflows. It:

1. Skips cleanly if `KOMODO_TARGET` is empty (unless `KOMODO_REQUIRED=true`).
2. POSTs to `/execute/DeployStack` (or `/execute/RunProcedure`).
3. Fails on any non-200, printing Komodo's error body.
4. Polls `/read/GetUpdate` until the update reaches `Complete`, then checks
   `success` and prints the Komodo log on failure.

The execute endpoint returns immediately with an `Update` object — a `200` means
"queued", not "deployed". That is why step 4 exists.

Tunable via env: `KOMODO_TARGET_TYPE` (`stack`/`procedure`), `KOMODO_WAIT`
(default `true`), `KOMODO_WAIT_TIMEOUT` (default 600s), `KOMODO_WAIT_INTERVAL`
(default 10s).

### Using a Procedure instead of a direct stack deploy

If you later wrap the deploy in a Komodo Procedure (deploy + healthcheck +
notification, say), point the workflow at it instead of editing the script:

```yaml
env:
  KOMODO_TARGET_TYPE: 'procedure'
  KOMODO_TARGET: 'qbit-maid deploy'
```

`RunProcedure` takes `{"procedure": "<name>"}` and returns the same `Update`
shape, so the polling logic is unchanged.

## Testing

Verified locally against a mock of the Komodo API — 12 checks covering the
success path, deploy failure, bad credentials (401), unknown stack (400),
empty target skip, required-but-empty target, unreachable host, and the
procedure target type. All pass.

Live verification still needed:

1. Push `dev-komodo-deploy` — it matches `dev*`, so `docker-dev.yml` runs. With
   `KOMODO_STACK_DEV` unset it will skip the deploy; set the variable first if
   you want to exercise it.
2. Merge to `main` and confirm the Komodo UI shows a new `DeployStack` update
   for `qbit-maid`, operator = the API key's user.
3. Confirm the running container picked up the new image digest.

## Rollback

Delete the `Deploy to Komodo` step from the workflow(s). Nothing on the Komodo
side is modified by CI beyond triggering a deploy.
