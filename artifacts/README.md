# Example Showcase Artifacts

These bundle-local YAML files are the sole source of truth for projected Example
Showcase artifacts.

Included artifact groups:

- `workflows/` - runnable demo workflow manifests.
- `agents/` - demo agent manifests referenced by agent workflow steps.
- `skills/` - demo skill contracts used by the agents.
- `tools/` - deterministic demo tool contracts used by connector steps.
- `datasets/` and `saved_queries/` - project-assigned dataset-query examples.

`extension-descriptor.yaml` publishes every workflow, agent, skill, tool,
dataset, and saved query through a bundle-local YAML ref. Installing the bundle
does not create a project, connection, or assignment. Assign the projected
dataset and workflow to a project, then select that project's Toolbox PostgreSQL
connection when using `demo_dataset_open_orders`.
