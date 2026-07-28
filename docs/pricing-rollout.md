# Canonical pricing rollout

1. Back up the database and deploy migrations 0014–0016.
2. Run `python manage.py migrate_legacy_pricing --report /tmp/pricing-exceptions.csv` and review counts/CSV.
3. Run again with `--apply`; imported rental packages remain `DRAFT` until commercial review.
4. Configure public, corporate, and OTA applicability, tax and settlement terms; approve one unambiguous active book per scope.
5. Repeat the apply command safely if interrupted. Source IDs make imports idempotent.
6. Reconcile the exception CSV manually. Never infer a historical rate or rewrite an issued invoice.
7. Verify quote, trip snapshot, closeout, invoice and ledger totals before enabling creation traffic.
