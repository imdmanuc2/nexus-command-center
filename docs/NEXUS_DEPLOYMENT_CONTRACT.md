# Nexus Deployment Contract

## Purpose

This document defines the platform-neutral deployment requirements for
Nexus Command Center.

Nexus may be deployed directly on Linux, in a container environment, on
Umbrel, or through another supported platform adapter. Those deployment
mechanisms may differ, but they must preserve the same Nexus peer trust
and security model.

## 1. Nexus Peer Permission Principle

Nexus-to-Nexus discovery, pairing, authentication, and normal peer
communication operate through the Nexus peer API.

They must not require:

- SSH access
- root privileges
- sudo privileges
- Docker daemon access
- membership in the Docker group
- access to a container runtime socket
- Umbrel administrative privileges
- passwordless administrative access

A deployment platform may require elevated privileges while installing,
updating, starting, stopping, or otherwise administering Nexus. Those
deployment privileges are separate from Nexus peer trust.

Managed Host operations are also separate from Nexus peer trust. A user
may explicitly authorize Nexus to manage another host through an
allow-listed management transport such as SSH without making SSH part of
the Nexus pairing protocol.

## 2. Peer Listener

The Nexus peer service uses TCP port 8561 by default.

The listener address is controlled by:

    NEXUS_PEER_HTTP_HOST

The listener port is controlled by:

    NEXUS_PEER_HTTP_PORT

A deployment must make the configured peer listener reachable by Nexus
systems that the user intends to connect.

Port 8561 is an unprivileged TCP port and does not require root
privileges merely to bind the listener.

## 3. Advertised Peer Endpoint

Every Nexus deployment that participates in outbound pairing must
explicitly configure:

    NEXUS_PEER_ADVERTISE_URL

Example:

    NEXUS_PEER_ADVERTISE_URL=http://nexus.example:8561

The value represents the callback endpoint another Nexus system can use
to reach this Nexus peer service.

The core Nexus application must not infer this value from:

- 0.0.0.0
- localhost
- hostname guesses
- arbitrary network interfaces
- Docker bridge addresses
- Umbrel-specific addresses
- hard-coded private subnets

Selecting the correct externally reachable endpoint is a deployment
responsibility.

Platform adapters may obtain the endpoint from platform configuration,
installer input, or another explicit deployment source, but must pass
the resulting value to Nexus through the canonical environment
variable.

## 4. Permanent Machine Identity

Every Nexus installation owns a permanent Ed25519 machine identity.

That identity is part of Nexus peer trust and must survive:

- application restarts
- host restarts
- container recreation
- application upgrades
- image upgrades
- normal service maintenance

Deployment tooling must preserve the Nexus private-data location that
contains the permanent machine identity.

A normal update, restart, repair, or container replacement must never
silently regenerate the machine identity.

Identity replacement is a separate explicit administrative operation
because connected peers bind trust to that identity.

## 5. Private Runtime Data

Nexus private runtime material must not be committed to source control
or baked into a distributable container image.

For a native checkout, the canonical private-data location is:

    backend/data/private/

The directory should be accessible only to the Nexus runtime account
where supported by the host platform.

Nexus-generated machine identity material enforces restrictive
permissions itself, including private directory and key-file
permissions.

Container and appliance deployments must provide equivalent persistent
private storage with permissions appropriate to their platform.

## 6. Runtime Account

Nexus does not require root as its normal runtime identity.

A standalone Linux installation may run Nexus under a dedicated
unprivileged service account.

A development installation may run Nexus under the owning development
account.

A container or appliance deployment may use the runtime identity
appropriate to that platform.

Regardless of platform, the runtime identity needs access only to the
files, database resources, network listeners, and explicitly authorized
capabilities required by Nexus.

Peer pairing does not justify granting additional operating-system
privileges.

## 7. Deployment Adapters

Deployment-specific logic belongs in deployment adapters or installers,
not in the Nexus peer protocol.

Examples include:

### Standalone Linux / systemd

The installer may use administrative privileges to:

- create a service account
- install systemd units
- create directories
- configure ownership
- start or restart services

The running Nexus peer service itself remains unprivileged.

### Docker or Compose

The deployment may:

- publish port 8561
- persist Nexus private data
- inject Nexus environment variables
- manage container lifecycle

Nexus pairing must not require access to the Docker socket.

### Umbrel

The Umbrel adapter may use Umbrel's application lifecycle, storage,
networking, and ownership model.

Umbrel-specific lifecycle behavior must not become a requirement of the
Nexus peer protocol.

## 8. Managed Host Privileges

Nexus Managed Host capabilities are distinct from Nexus peer
connections.

A Managed Host may use SSH or an allow-listed privileged helper when a
user explicitly authorizes host-management operations.

Such privileges must be:

- capability scoped
- target validated
- explicitly configured
- auditable
- independent of Nexus peer authentication

Connecting two Nexus systems must not automatically grant either Nexus
system host-management privileges over the other.

## 9. Build Identity

Deployments should expose deterministic Nexus build identity.

Canonical build metadata is supplied through:

    NEXUS_VERSION
    NEXUS_REVISION

Container builds should identify the exact source revision used to
produce the image.

Mutable image tags may be useful for development convenience, but
security-sensitive deployment and acceptance testing should use an
immutable version or revision-derived artifact whenever available.

## 10. Minimum Pairing Deployment Requirements

A Nexus installation is deployment-ready for Nexus-to-Nexus pairing
when all of the following are true:

1. The Nexus peer listener is running.
2. TCP port 8561, or the explicitly configured replacement port, is
   reachable between intended peers.
3. `NEXUS_PEER_ADVERTISE_URL` is explicitly configured with a reachable
   callback endpoint.
4. The permanent Nexus machine identity is present and persistent.
5. Private runtime storage is writable by the Nexus runtime identity
   and protected from unrelated users where the platform supports it.
6. The deployed build can be identified deterministically.
7. No SSH, Docker daemon, root, sudo, or appliance-administrator
   permission is required for the pairing transaction itself.

Discovery and incoming peer connections remain controlled by the
user-facing Nexus settings and are not implicitly enabled by satisfying
these deployment requirements.

## 11. Security Boundary

The Nexus peer trust boundary is cryptographic identity plus the Nexus
peer API.

It is not:

- a Unix account
- an SSH account
- a Docker permission
- an Umbrel account
- a shared administrator credential

Deployment tooling must preserve this separation.
