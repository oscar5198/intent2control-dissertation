# Deployment Notes

Deployment for the study interface is currently undecided. The application must eventually run on QMUL-managed infrastructure, but the final hosting technology, backend language, database, access method, and operational constraints are TBC.

## Minimum hosting needs

The final deployment should provide:

- A public HTTPS website.
- Static file and audio serving.
- Server-side processing.
- A secure database.
- Environment variables or protected configuration.
- An access restricted administration or export method.
- Backups.
- Support for external participants.
- Appropriate data location and five-year retention.

Participant data, research audio, exported datasets, local databases, logs, uploaded files, and secrets must not be committed to Git.

## PHP deployment option

A PHP deployment may be suitable if QMUL provides a managed web server with PHP support.

Items to confirm:

- Supported PHP version: TBC.
- Available database system: TBC.
- File storage location for audio: TBC.
- HTTPS and domain configuration: TBC.
- Method for protected configuration: TBC.
- Administration or export access method: TBC.

## Python deployment option

A Python deployment may be suitable if QMUL provides a managed Python application environment.

Items to confirm:

- Supported Python version: TBC.
- Supported application server: TBC.
- Available database system: TBC.
- Static and audio file serving approach: TBC.
- HTTPS and domain configuration: TBC.
- Method for protected configuration: TBC.

## Node.js deployment option

A Node.js deployment may be suitable if QMUL provides a managed Node.js environment.

Items to confirm:

- Supported Node.js version: TBC.
- Supported process manager or hosting model: TBC.
- Available database system: TBC.
- Static and audio file serving approach: TBC.
- HTTPS and domain configuration: TBC.
- Method for protected configuration: TBC.

## Container-based deployment option

A container-based deployment may be suitable if QMUL supports Docker or another container platform.

Items to confirm:

- Supported container runtime: TBC.
- Image build and deployment process: TBC.
- Persistent database or volume support: TBC.
- Static and audio file storage approach: TBC.
- HTTPS and reverse proxy configuration: TBC.
- Backup and recovery process: TBC.

## Data location and retention

The data retention period is five years. This five-year period must remain consistent with the final approved QMUL Participant Information Sheet, consent documentation, and institutional policy.

The final data location, retention start point, deletion or archival procedure, responsible data custodian, backup policy, and access control policy must be agreed before deployment. These items are TBC.

The final implementation must follow QMUL requirements for storage, access, retention, deletion, archival, and backups.
