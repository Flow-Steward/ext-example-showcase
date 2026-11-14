# Example Showcase Artifacts

These bundle-local YAML files are the sole source of truth for projected Example
Showcase artifacts.

Included artifact groups:

- `workflows/` - runnable demo workflow manifests.
- `agents/` - demo agent manifests referenced by agent workflow steps.
- `skills/` - demo skill contracts used by the agents.
- `tools/` - deterministic demo tool contracts used by connector steps.

`extension-descriptor.yaml` publishes the 13 workflows, five agents, five skills
and three tools through bundle-local YAML refs. Installing the bundle does not
create projects or connections.

The PostgreSQL Dataset and saved-query references and the manual workflow bundle
live under `examples/postgresql/`. They are not automatic projections. Create a
project-owned Dataset and saved query using your PostgreSQL connection, then
import the workflow bundle and select that query. See
[the PostgreSQL setup guide](../docs/postgresql-dataset-example.md).
