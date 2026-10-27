# Plan: Auto-deploy qbit-maid to Komodo from Gitea Actions

Status: **proposal** — no workflow changes made yet.
Branch: `dev-komodo-deploy`

## Goal

When a commit lands on `main` (or a `dev*` branch), the image is built and pushed
to `git.jonb.io/jblu/qbit-maid`, and then the matching Komodo resource is
redeployed automatically — with no manual click in the Komodo UI.

## Current state

Two Gitea Actions workflows exist, both build-and-push only:

| File | Trigger | Tag pushed |
|---|---|---|
| `.gitea/workflows/docker.yml` | push to `main` | `git.jonb.io/jblu/qbit-maid:latest` |
| `.gitea/workflows/docker-dev.yml` | push to `dev*` | `git.jonb.io/jblu/qbit-maid:dev` |

Neither workflow talks to Komodo. There are currently **no Komodo references
anywhere in the repo**, so the Komodo side (stack/deployment resource, registry
credentials) is assumed to be configured out-of-band in the Komodo UI.

## Design options

| # | Approach | Ordering | CI change | Notes |
|---|---|---|---|---|
| A | **Gitea Actions step calls Komodo API** (`POST /execute/DeployStack`) | ✅ deploy strictly after image push | small | Needs API key/secret as Gitea secrets; runner must reach Komodo |
| B | Gitea repo webhook → Komodo `/listener/github/stack/<name>/deploy` | ❌ fires on push, races the image build | none | Komodo may pull the *old* `:latest`; needs `KOMODO_WEBHOOK_SECRET` |
| C | Komodo **Build** resource builds from the Gitea repo, deploy attached | ✅ | removes CI build | Moves building off Gitea Actions; bigger change |
| D | Komodo **Auto Update** (poll registry for new `:latest` digest) | ⚠️ up to poll interval late | none | Zero-effort safety net, not "on push" |

**Recommendation: A, with D enabled as a backstop.**

A gives deterministic ordering — the deploy can only start once the push step has
succeeded. D costs nothing and catches any deploy that A misses (e.g. a manual
`docker push`, or a failed API call).

B is the tempting "no code" option but it is genuinely racy: the webhook fires on
`git push`, which is *before* the image exists in the registry. Komodo would
redeploy the previous `:latest`. Only pick B if you also switch to C.

## Implementation

### 1. Komodo-side prerequisites (manual, in the Komodo UI)

1. Confirm the resource type and name — a **Stack** (`DeployStack`) or a
   **Deployment** (`Deploy`). The plan below assumes a Stack named `qbit-maid`.
2. Make sure the Komodo server can pull from `git.jonb.io`. Add the registry
   credentials under **Settings → Docker Registries** (or the stack's
   `docker_account`), otherwise the redeploy will fail on `docker pull`.
3. Create an API key: **Settings → API Keys → New**. Scope it to a user that has
   **Execute** permission on the `qbit-maid` stack. Save the key + secret.
4. Optional backstop: set the stack's update mode to **Auto Update**.

### 2. Gitea secrets / variables

Repo → **Settings → Actions → Secrets**:

| Name | Kind | Value |
|---|---|---|
| `KOMODO_URL` | secret | `https://komo.example.com` (no trailing slash) |
| `KOMODO_API_KEY` | secret | from step 1.3 |
| `KOMODO_API_SECRET` | secret | from step 1.3 |
| `KOMODO_STACK` | variable | `qbit-maid` |

`KOMODO_STACK` is a *variable*, not a secret — it is not sensitive and being able
to see it in the UI makes the workflow easier to read.

### 3. Workflow change

Append one step to each workflow, after `Build and push`. For `docker.yml`:

```yaml
      -
        name: Trigger Komodo deploy
        env:
          KOMODO_URL: ${{ secrets.KOMODO_URL }}
          KOMODO_API_KEY: ${{ secrets.KOMODO_API_KEY }}
          KOMODO_API_SECRET: ${{ secrets.KOMODO_API_SECRET }}
          KOMODO_STACK: ${{ vars.KOMODO_STACK }}
        run: |
          set -euo pipefail
          response=$(curl -sS -w '\n%{http_code}' \
            -X POST "${KOMODO_URL}/execute/DeployStack" \
            -H 'Content-Type: application/json' \
            -H "x-api-key: ${KOMODO_API_KEY}" \
            -H "x-api-secret: ${KOMODO_API_SECRET}" \
            -d "{\"stack\": \"${KOMODO_STACK}\"}")
          body=$(printf '%s' "$response" | sed '$d')
          code=$(printf '%s' "$response" | tail -n1)
          echo "Komodo responded HTTP ${code}"
          echo "$body"
          [ "$code" = "200" ] || exit 1
```

`docker-dev.yml` is identical except `KOMODO_STACK` points at the dev stack
(e.g. `qbit-maid-dev`), so dev pushes never touch production.

Notes on the API call:

- Endpoint is `POST /execute/DeployStack` with the params object as the body.
  The equivalent generic form is `POST /execute` with
  `{"type": "DeployStack", "params": {"stack": "..."}}`.
- Auth headers are `x-api-key` and `x-api-secret`.
- `DeployStack` accepts `{"stack": "<id or name>", "services": [], "stop_time": null}`.
  Use the resource **id** rather than the name if the name is likely to change.
- **The call returns immediately** with an `Update` object; the deploy runs
  asynchronously. A `200` means "queued", not "deployed". See step 4.

### 4. Optional: wait for the deploy to actually finish

If you want the workflow to go red when the deploy fails, poll
`POST /read/GetUpdate` with `{"update_id": "<id>"}` until `status` is `Complete`,
then check `success`. Sketch:

```bash
update_id=$(printf '%s' "$body" | python3 -c 'import sys,json; print(json.load(sys.stdin)["_id"]["$oid"])')
for _ in $(seq 1 60); do
  sleep 5
  u=$(curl -sS -X POST "${KOMODO_URL}/read/GetUpdate" \
        -H 'Content-Type: application/json' \
        -H "x-api-key: ${KOMODO_API_KEY}" \
        -H "x-api-secret: ${KOMODO_API_SECRET}" \
        -d "{\"update_id\": \"${update_id}\"}")
  status=$(printf '%s' "$u" | python3 -c 'import sys,json; print(json.load(sys.stdin)["status"])')
  [ "$status" = "Complete" ] || continue
  printf '%s' "$u" | python3 -c 'import sys,json; sys.exit(0 if json.load(sys.stdin)["success"] else 1)'
done
echo "Timed out waiting for deploy"; exit 1
```

Recommendation: ship step 3 first, add step 4 only if you find yourself wanting
the CI signal. Polling adds up to 5 minutes of runner time per deploy.

### 5. Testing

1. Push `dev-komodo-deploy` — this matches `dev*`, so `docker-dev.yml` runs and
   exercises the new step against the dev stack. Confirm the Komodo UI shows a
   new `Deploy` update with operator = your API key's user.
2. Verify the running container actually picked up the new image
   (`docker inspect` the image digest, or check the app's log line).
3. Merge to `main` and confirm the production stack redeploys.
4. Negative test: temporarily set `KOMODO_API_SECRET` to a bad value and confirm
   the step fails loudly rather than silently passing.

### 6. Rollback

The change is additive — delete the `Trigger Komodo deploy` step and the
workflows are back to build-and-push only. No Komodo state is modified by the
workflow beyond triggering a deploy.

## Open questions

These need answers before the workflow change is written:

1. **Stack or Deployment?** Determines `DeployStack` vs `Deploy`.
2. **Resource name(s)** for prod and dev.
3. **Is Komodo reachable from the Gitea runner?** If Komodo is on a private
   network and the runner is not, option A is out and we fall back to B+C or D.
4. **Does Komodo already have registry credentials for `git.jonb.io`?** If not,
   the first automated deploy will fail at pull time.
5. **Should dev deploys be automatic?** Some people prefer dev to stay manual.
