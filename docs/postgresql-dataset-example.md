# Run the PostgreSQL Dataset example

This example reads open orders from **your own PostgreSQL database**. It is a manual
setup example and is not installed automatically with Example Showcase. The host
requires an automatically projected Dataset and its connector to have the same
extension owner; this example deliberately uses the separate PostgreSQL extension.

1. Install PostgreSQL (`flowsteward.data-connector-mcp-toolbox-postgres`) and create
   a PostgreSQL connection in your test project, with read access to `orders`.
2. In Datasets, create a project-owned Dataset using that connection. Introspect
   the real schema and permit only `orders.order_id`, `orders.status` and
   `orders.total_amount`. Assign the Dataset to the same project.
3. Add a read-only saved query to that Dataset:
   ```sql
   SELECT order_id, status, total_amount FROM orders WHERE status = 'open'
   ```
   Preview it and keep its saved-query ID. The reference column schema is in
   `examples/postgresql/datasets/demo_sales_open_orders.yaml`; the query reference is in
   `examples/postgresql/saved_queries/demo_open_orders_query.yaml`. Adapt the schema to your
   database rather than importing an unbound extension-owned Dataset.
4. Import `examples/postgresql/workflows/demo_dataset_open_orders.bundle.yaml` through Workflows →
   Import YAML. In the dependency check, map PostgreSQL to your installed PostgreSQL extension. This creates a disabled draft workflow, not an extension projection. The adjacent raw workflow YAML is an authoring reference, not an import file.
5. Bind the workflow to your test project. Open **Load open orders** in the builder
   and select the saved query you created in step 3. Apply the changes.
6. Use Test Run. The first step returns up to ten real rows, the second counts them,
   and the final step ends successfully. `request_note` remains optional.

No credentials or connection IDs belong in these YAML templates. No database is
created and no rows are inserted or modified by this example.
