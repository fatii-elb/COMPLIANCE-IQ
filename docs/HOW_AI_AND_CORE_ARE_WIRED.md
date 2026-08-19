# How the AI Service and the Core Service Are Wired Together
### A beginner's guide — plus what happens at launch, and why you keep inserting a key

This explains, in plain language, how the two ComplianceIQ services connect, what
happens step-by-step when you start the app, and the thing that confuses everyone:
**why you have to paste a key every time you launch.**

---

## 1. The two services, as a story 🧩

Imagine a small company:

- **The Core Service = the records office + the security guard.**
  It owns all the data (the compliance *findings*), and it's the only one allowed
  to **hand out ID badges** (login tokens). It has a private stamp nobody else has.

- **The AI Service = the smart analyst.**
  It doesn't own any data and can't make ID badges. It **reads** findings from the
  Core and **explains** them using AI. To be let in anywhere, it must show a badge
  the Core stamped — and it can **check** whether a badge is genuine, but it can
  **never make one**.

> **One sentence:** *The Core owns the data and issues identity; the AI reads that
> data and only verifies identity.*

That asymmetry — Core makes badges, AI only checks them — is the whole reason the
key setup works the way it does. Hold onto it; it explains section 5.

---

## 2. Who calls whom? (the direction of the wire) ➡️

There are two *possible* directions. Only **one** is actually built:

```
✅ BUILT:  AI  ──asks──►  Core          "give me finding X"
                          the AI pulls findings from the Core, then explains them

🔵 NOT BUILT:  Core  ──asks──►  AI       "please enrich this finding"
                          the Core could push findings to the AI, but that code doesn't exist yet
```

So in practice: **a user talks to the AI's own web console → the AI calls the Core
to fetch the finding → the AI runs its RAG + LLM reasoning → shows the answer.**

```
You (browser)
   ↓  open the AI console
AI Service  (http://localhost:8100)
   ↓  "I need finding #123"  (over HTTP, carrying your badge)
Core Service  (http://localhost:8000)
   ↓  returns the finding
AI Service  → RAG + LLM → grounded, cited answer
   ↓
You (browser)
```

---

## 3. The three things that must match for the wire to work 🔌

For the AI to successfully call the Core, **three** things have to line up. This is
"the wiring." Think of it as: the right **address**, the right **shape**, and the
right **badge**.

### 3a. The ADDRESS — where the Core lives
The AI needs to know the Core's URL. It's a setting:

| Setting (env var) | Value in Docker | Meaning |
|---|---|---|
| `CIQ_CORE_CLIENT` | `http` | "Talk to a *real* Core over the network" (the other option, `stub`, means "pretend, offline") |
| `CIQ_CORE_API_BASE_URL` | `http://core:8000` | the Core's address |

> **Beginner trap:** inside Docker, the AI reaches the Core at **`http://core:8000`**,
> *not* `http://localhost:8000`. Inside a container, "localhost" means *this
> container itself*, not your laptop and not the Core. Containers find each other by
> their **service name** (`core`), like calling a coworker by name across the office.

### 3b. The SHAPE — the exact format of a finding
The Core can describe a finding in a rich way (lots of extra fields) or in a slim,
**exactly-11-field** "AI contract" way. The AI is a *picky eater* — it rejects any
extra fields. So the AI is wired to ask the Core's special endpoints:

```
GET /api/v1/findings/ai-contract          (list)
GET /api/v1/findings/{id}/ai-contract     (one finding)
```

These give the AI precisely the 11 fields it expects — same field names, same
values. (This match was verified end-to-end; both services agree byte-for-byte.)

### 3c. The BADGE — the login token (JWT)
Every call carries a **JWT** (a signed digital ID card) in the request header:

```
Authorization: Bearer eyJhbGciOiJSUzI1NiIs...
```

- The **Core signs** this token with its **private key** (secret, only the Core has it).
- The **AI verifies** it with the Core's **public key** (safe to share).
- The AI checks: is the signature real? not expired? issued by `complianceiq-core`?
  for audience `complianceiq`? If yes → it trusts *who you are* and *which tenant
  you belong to*. If anything's off → **401 Unauthorized**.

This public/private key pair is **the key you keep inserting.** Section 5 explains
exactly why.

---

## 4. What happens when you launch the app? 🚀

You launch everything with **Docker Compose** — one command that starts several
containers that work together. Here's the whole sequence.

### The one-time setup (before the very first launch)
```powershell
# 1. Make ONE RSA key pair (a private half + a public half)
python scripts/gen_integration_keys.py
```
This writes two things:
- `secrets/core-signing.pem` → the **private** key (for the Core to sign badges)
- `.env` gets `CIQ_JWT_PUBLIC_KEY={...}` → the **public** key as a "JWK" (for the AI to verify badges)

Both halves come from the *same* key pair, so they fit together like a lock and its key.

### Every launch
```powershell
# 2. Load the private key into THIS terminal (see section 5 for why every time)
$env:JWT_PRIVATE_KEY = Get-Content secrets/core-signing.pem -Raw

# 3. Build and start all the containers
docker compose up --build
```

### What Docker Compose does, step by step
```
docker compose up --build
        │
        ├─ (1) postgres        starts the Core's database, waits until "healthy"
        │
        ├─ (2) core-migrate    runs `alembic upgrade head` once (creates DB tables), then exits
        │
        ├─ (3) core            starts the Core API on port 8000
        │                       - reads JWT_PRIVATE_KEY  → can now SIGN badges
        │                       - publishes its public key at /.well-known/jwks.json
        │                       - waits until it reports "healthy" (GET /health = 200)
        │
        └─ (4) ai              starts the AI on port 8100 (only after Core is healthy)
                                - reads CIQ_JWT_PUBLIC_KEY → can now VERIFY badges
                                - reads CIQ_CORE_CLIENT=http + CIQ_CORE_API_BASE_URL=http://core:8000
                                  → knows to call the real Core at that address
```

Notice the **order** matters, and Docker enforces it with "healthchecks":
`postgres` → `core-migrate` → `core` → `ai`. The AI won't start talking until the
Core is up and healthy.

When it's done:
- **Core** → `http://localhost:8000`  (has `/health`, `/.well-known/jwks.json`)
- **AI console** → `http://localhost:8100`

```
┌─────────────── Docker (one network) ───────────────┐
│                                                     │
│   postgres ──► core-migrate ──► core (:8000) ──► ai (:8100)
│                                    ▲                 │
│                                    └── ai calls http://core:8000
│                                                     │
└──────── you reach core at :8000, ai at :8100 ───────┘
```

> **Inside the app itself** (what happens after a container starts): the AI runs
> `python -m complianceiq` → builds its object graph → loads the compliance corpus →
> starts listening. But for "how are they wired," the Compose picture above is what
> matters.

---

## 5. Why do I have to insert a key EVERY time? 🔑 (the real answer)

This is the part that feels annoying. Here's exactly why, in plain terms.

### There are two key halves, and they're stored differently
| Half | Used by | Where it lives | Secret? |
|---|---|---|---|
| **Public** key (JWK) | AI (to *verify*) | saved in `.env` | No — public, safe to keep on disk |
| **Private** key (PEM) | Core (to *sign*) | `secrets/core-signing.pem` | **Yes** — must stay secret |

The **public** half is already saved in `.env`, and Docker Compose reads `.env`
automatically. So you **never** re-insert that one.

The **private** half is the one you keep inserting. Two reasons:

**Reason 1 — it's multi-line, and `.env` files can't hold multi-line values.**
A private key looks like this (many lines):
```
-----BEGIN PRIVATE KEY-----
MIIEvQIBADANBgkqhkiG9w0BAQEFAASCBKcwggSj...
...many more lines...
-----END PRIVATE KEY-----
```
A `.env` file is strictly one `NAME=value` per line — it has no clean way to store
something with line breaks. So we can't just park the private key in `.env` like the
public one.

**Reason 2 — a terminal environment variable only lives for that one session.**
When you run:
```powershell
$env:JWT_PRIVATE_KEY = Get-Content secrets/core-signing.pem -Raw
```
you're putting the key into **this terminal window's memory**. The moment you
**close the terminal** (or open a *new* one), that memory is wiped. Docker Compose
reads `${JWT_PRIVATE_KEY}` from the terminal you launch it in — so if the terminal
doesn't have it, the Core has no key and refuses to start (that's the `:?` guard in
the compose file: *"set JWT_PRIVATE_KEY — see README"*).

So: **you re-insert the private key each time simply because it's a secret,
multi-line value that we deliberately keep out of files and only load into the
current terminal session.** It's a safety choice (secrets shouldn't sit in `.env`),
not a bug.

### ⚠️ Important clarification: you do NOT regenerate the key each time
Run `python scripts/gen_integration_keys.py` **once**. That makes the key pair.
After that, every launch you only **re-load** the *existing* key with the
`$env:JWT_PRIVATE_KEY = Get-Content ...` line. If you run the generator again, it
makes a **brand-new** key — which would invalidate any tokens signed with the old
one. So: generate once, re-load each session.

### How to stop re-typing it (three easy options)
1. **Keep the same terminal open.** As long as you don't close the window, the
   variable stays set — run `docker compose up` as many times as you like.

2. **Make a tiny launcher script** so it's one command. Create `up.ps1`:
   ```powershell
   $env:JWT_PRIVATE_KEY = Get-Content secrets/core-signing.pem -Raw
   docker compose up --build
   ```
   Then each time you just run `./up.ps1`. (Bash version, `up.sh`:)
   ```bash
   export JWT_PRIVATE_KEY="$(cat secrets/core-signing.pem)"
   docker compose up --build
   ```

3. **(Advanced) Use Docker secrets or a mounted key file.** Cleaner for real
   deployments, but overkill for local dev and it needs a small code change on the
   Core side to read a file path instead of an env var — so stick with option 2 for
   now.

> **Rule of thumb:** *Generate the key once. Each new terminal, re-load the private
> key (or just run `up.ps1`). Never commit `secrets/` or the private key to git.*

---

## 6. Quick "is it wired correctly?" checks ✅

Once `docker compose up` is running, open a second terminal:

```powershell
# Core is alive?
curl http://localhost:8000/health

# Core is publishing its public key (this is what the AI verifies against)?
curl http://localhost:8000/.well-known/jwks.json

# AI is alive?
curl http://localhost:8100/health
```

And to prove the two *agree* on the data + token formats without Docker at all:
```powershell
$env:PYTHONPATH = "ai-service/src;core-service"
python check_compatibility.py       # expect ✅ COMPATIBLE
```

---

## 7. The 60-second recap 🎯

- **Core = data owner + badge issuer** (has the private key). **AI = analyst + badge
  checker** (has the public key). The AI **pulls** findings from the Core.
- Three things make the wire work: the **address** (`http://core:8000`), the
  **shape** (`/ai-contract` = exactly 11 fields), and the **badge** (RS256 JWT).
- **Launch** = `docker compose up --build`, which starts postgres → core-migrate →
  core → ai in that order, on one network where the AI calls the Core by name.
- **You re-insert the private key each launch** because it's a **secret, multi-line**
  value we keep out of `.env` and only load into the current terminal — which forgets
  it when closed. The **public** key stays in `.env`, so that one you never re-enter.
- **Generate the key once**, re-load it each session (or use an `up.ps1` one-liner).
